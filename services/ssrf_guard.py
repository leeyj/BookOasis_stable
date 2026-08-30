# -*- coding: utf-8 -*-
"""
ssrf_guard.py – 플러그인 웹뷰/다운로드 API가 사용자 대신 외부 URL을 서버에서
직접 fetch할 때 쓰는 SSRF(서버 위조 요청) 방어 유틸리티.

검증 순서가 중요하다:
  1) scheme 검사
  2) 화이트리스트 매치 (네트워크 I/O 이전 — 비허용 도메인은 DNS 조회조차 하지 않는다)
  3) DNS 해석 후 반환된 모든 IP에 대해 사설/루프백/링크로컬/예약/멀티캐스트 대역 여부 검사

리다이렉트는 자동으로 따라가지 않고 매 hop마다 위 검증을 다시 수행한다 — 화이트리스트에
있는 도메인이 내부망 IP로 리다이렉트시키는 공격을 막기 위함이다.

알려진 한계: requests가 실제 TCP 연결 시 내부적으로 재-DNS resolve를 하므로, 검증 시점과
실제 연결 시점 사이의 DNS 리바인딩(TOCTOU)까지는 막지 못한다. 이를 막으려면 커스텀
HTTPAdapter로 resolve된 IP를 pinning해야 하는데, 이번 스코프에서는 다루지 않는다.
"""
import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit

try:
    import requests
except ImportError:
    requests = None

from services.domain_whitelist_service import host_matches_whitelist

DEFAULT_TIMEOUT = (5, 15)  # (connect, read)


class SSRFBlockedError(Exception):
    """URL 검증 또는 응답 크기 제한 위반으로 요청이 차단되었을 때 발생.
    host는 not_whitelisted 사유일 때 정확히 어떤 호스트가 거부됐는지 알려준다
    (리다이렉트 hop에서 원 URL과 다른 호스트가 걸릴 수 있어 원 URL의 호스트만으로는 부정확함)."""

    def __init__(self, reason, host=None):
        self.reason = reason
        self.host = host
        super().__init__(reason)


def _is_unsafe_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # 파싱 불가한 주소는 안전하지 않은 것으로 취급
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def validate_target_url(url, whitelist_patterns):
    """URL을 서버에서 직접 요청해도 안전한지 검증한다.
    반환: (ok: bool, error_code: str, host: str|None)"""
    try:
        parts = urlsplit(str(url).strip())
    except Exception:
        return False, 'invalid_url', None

    if parts.scheme not in ('http', 'https'):
        return False, 'invalid_scheme', None

    host = parts.hostname
    if not host:
        return False, 'invalid_url', None

    if not host_matches_whitelist(host, whitelist_patterns):
        return False, 'not_whitelisted', host

    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        addr_infos = socket.getaddrinfo(host, port)
    except Exception:
        return False, 'dns_resolve_failed', host

    if not addr_infos:
        return False, 'dns_resolve_failed', host

    for _family, _type, _proto, _canon, sockaddr in addr_infos:
        if _is_unsafe_ip(sockaddr[0]):
            return False, 'private_ip_resolved', host

    return True, '', host


def validate_public_http_url(url):
    """도메인 화이트리스트 없이 scheme + 사설/루프백 IP 여부만 검사한다.
    로고/아이콘처럼 위험도가 낮고 도메인이 지나치게 다양해(방송사마다 별개 CDN) 매번
    사용자 화이트리스트 등록을 요구하면 실사용이 불가능한 리소스에 한해 사용한다.
    반환: (ok: bool, error_code: str, host: str|None)"""
    try:
        parts = urlsplit(str(url).strip())
    except Exception:
        return False, 'invalid_url', None

    if parts.scheme not in ('http', 'https'):
        return False, 'invalid_scheme', None

    host = parts.hostname
    if not host:
        return False, 'invalid_url', None

    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        addr_infos = socket.getaddrinfo(host, port)
    except Exception:
        return False, 'dns_resolve_failed', host

    if not addr_infos:
        return False, 'dns_resolve_failed', host

    for _family, _type, _proto, _canon, sockaddr in addr_infos:
        if _is_unsafe_ip(sockaddr[0]):
            return False, 'private_ip_resolved', host

    return True, '', host


def fetch_with_redirect_revalidation(url, whitelist_patterns, method='GET',
                                      max_redirects=3, timeout=DEFAULT_TIMEOUT,
                                      extra_headers=None):
    """리다이렉트를 자동으로 따라가지 않고 매 hop마다 재검증하며 요청한다.
    원 요청(플러그인 호출을 유발한 브라우저 요청)의 쿠키/인증 헤더는 전달하지 않는다 —
    헤더는 이 함수가 처음부터 새로 구성한다."""
    if requests is None:
        raise SSRFBlockedError('requests_unavailable')

    current_url = url
    headers = {'User-Agent': 'BookOasis-Webview/1.0'}
    if extra_headers:
        headers.update(extra_headers)

    for _ in range(max_redirects + 1):
        ok, reason, host = validate_target_url(current_url, whitelist_patterns)
        if not ok:
            raise SSRFBlockedError(reason, host=host)

        response = requests.request(
            method, current_url, timeout=timeout, allow_redirects=False,
            stream=True, headers=headers
        )

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise SSRFBlockedError('redirect_without_location')
            current_url = urljoin(current_url, location)
            continue

        return response

    raise SSRFBlockedError('too_many_redirects')


def fetch_public_url_with_redirect_revalidation(url, method='GET', max_redirects=3,
                                                 timeout=DEFAULT_TIMEOUT, extra_headers=None):
    """fetch_with_redirect_revalidation의 화이트리스트-없는 버전 (validate_public_http_url 사용).
    도메인 제한 없이 사설/루프백 IP만 차단한다 — 리다이렉트도 매 hop 재검증한다."""
    if requests is None:
        raise SSRFBlockedError('requests_unavailable')

    current_url = url
    headers = {'User-Agent': 'BookOasis-Webview/1.0'}
    if extra_headers:
        headers.update(extra_headers)

    for _ in range(max_redirects + 1):
        ok, reason, host = validate_public_http_url(current_url)
        if not ok:
            raise SSRFBlockedError(reason, host=host)

        response = requests.request(
            method, current_url, timeout=timeout, allow_redirects=False,
            stream=True, headers=headers
        )

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise SSRFBlockedError('redirect_without_location')
            current_url = urljoin(current_url, location)
            continue

        return response

    raise SSRFBlockedError('too_many_redirects')


def read_capped(response, max_bytes, chunk_size=65536):
    """응답 본문을 max_bytes까지만 메모리로 읽는다 (웹뷰 프록시용, 작은 캡 전제)."""
    buf = bytearray()
    for chunk in response.iter_content(chunk_size=chunk_size):
        if not chunk:
            continue
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise SSRFBlockedError('response_too_large')
    return bytes(buf)


def write_capped_to_file(response, dest_path, max_bytes, chunk_size=65536):
    """응답 본문을 max_bytes까지만 디스크로 스트리밍 저장한다 (다운로드용, 큰 캡 전제).
    초과 시 부분 파일을 삭제하고 예외를 던진다. 반환: 실제로 쓴 바이트 수."""
    written = 0
    try:
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_bytes:
                    raise SSRFBlockedError('response_too_large')
                f.write(chunk)
    except Exception:
        try:
            os.remove(dest_path)
        except OSError:
            pass
        raise
    return written
