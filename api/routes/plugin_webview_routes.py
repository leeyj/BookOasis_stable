# -*- coding: utf-8 -*-
"""
plugin_webview_routes.py – 플러그인용 외부 도메인 웹뷰/다운로드 API

관리자 전용 기능이 아니라 로그인한 사용자 각자의 개인 화이트리스트 기반 기능이므로
admin_bp가 아니라 api_bp에 직접 등록한다 (api/__init__.py 참고).

앱은 어떤 외부 도메인도 기본 제공/추천하지 않는다 — 사용자가 직접 등록한 도메인에
대해서만 웹뷰 표시/다운로드를 허용한다. 실제 네트워크 요청은 services/ssrf_guard.py의
SSRF 방어 로직을 통해서만 이루어진다.
"""
import os
import re
import time

from flask import Blueprint, request, jsonify, session, Response

from api.auth import login_required
from repositories.category_repository import CategoryRepository
from services.domain_whitelist_service import DomainWhitelistService, extract_host_from_url
from services.ssrf_guard import (
    SSRFBlockedError,
    fetch_with_redirect_revalidation,
    read_capped,
    write_capped_to_file,
)
from utils.drive_helper import is_gdrive_url

plugin_webview_bp = Blueprint('plugin_webview', __name__)

WEBVIEW_MAX_BYTES = 15 * 1024 * 1024       # 15MB — 웹뷰로 표시할 페이지 캡
DOWNLOAD_MAX_BYTES = 500 * 1024 * 1024     # 500MB — 도서 다운로드 캡

_ERROR_MESSAGES = {
    'invalid_url': 'URL 형식이 올바르지 않습니다.',
    'invalid_scheme': 'http/https 주소만 허용됩니다.',
    'not_whitelisted': '이 도메인은 허용 목록에 없습니다. 설정에서 먼저 추가해주세요.',
    'dns_resolve_failed': '도메인을 확인할 수 없습니다.',
    'private_ip_resolved': '내부망/사설 IP로 연결되는 주소는 허용되지 않습니다.',
    'redirect_without_location': '리다이렉트 응답에 대상 주소가 없습니다.',
    'too_many_redirects': '리다이렉트가 너무 많습니다.',
    'response_too_large': '응답 크기가 허용 한도를 초과했습니다.',
    'requests_unavailable': '서버에 requests 모듈이 설치되어 있지 않습니다.',
}


def _error_response(reason, status=403, host=None):
    message = _ERROR_MESSAGES.get(reason, reason)
    if reason == 'not_whitelisted' and host:
        # apex 도메인만 등록해둔 상태에서 www.example.com 같은 서브도메인이 요청되면
        # 별개 호스트로 취급되어 거부된다 — 정확히 어떤 호스트가 막혔는지 보여줘야
        # 사용자가 무엇을 더 등록해야 할지 알 수 있다.
        message = f"허용 목록에 없는 도메인입니다: {host} (설정에서 추가해주세요)"
    return jsonify({'success': False, 'error': reason, 'message': message}), status


# ─────────────────────────────── 화이트리스트 CRUD ───────────────────────────────

@plugin_webview_bp.route('/api/webview/whitelist', methods=['GET'])
@login_required
def get_whitelist():
    domains = DomainWhitelistService.get_whitelist(session['user_id'])
    return jsonify({'success': True, 'domains': domains})


@plugin_webview_bp.route('/api/webview/whitelist', methods=['POST'])
@login_required
def add_whitelist_domain():
    data = request.get_json(silent=True) or {}
    domain = data.get('domain') or request.form.get('domain')
    if not domain:
        return jsonify({'success': False, 'error': 'domain이 필요합니다.'}), 400

    ok, err = DomainWhitelistService.add_domain(session['user_id'], domain)
    if not ok:
        return jsonify({'success': False, 'error': err}), 400

    return jsonify({'success': True, 'domains': DomainWhitelistService.get_whitelist(session['user_id'])})


@plugin_webview_bp.route('/api/webview/whitelist', methods=['DELETE'])
@login_required
def remove_whitelist_domain():
    data = request.get_json(silent=True) or {}
    domain = data.get('domain') or request.args.get('domain')
    if not domain:
        return jsonify({'success': False, 'error': 'domain이 필요합니다.'}), 400

    DomainWhitelistService.remove_domain(session['user_id'], domain)
    return jsonify({'success': True, 'domains': DomainWhitelistService.get_whitelist(session['user_id'])})


# ─────────────────────────────── 웹뷰 프록시 ───────────────────────────────

@plugin_webview_bp.route('/api/webview/proxy', methods=['GET'])
@login_required
def webview_proxy():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'url이 필요합니다.'}), 400

    patterns = DomainWhitelistService.get_patterns(session['user_id'])
    host = extract_host_from_url(url)
    if not host:
        return _error_response('invalid_url', 400)

    try:
        upstream = fetch_with_redirect_revalidation(url, patterns, method='GET')
    except SSRFBlockedError as e:
        return _error_response(e.reason, host=e.host)
    except Exception as e:
        return jsonify({'success': False, 'error': 'fetch_failed', 'message': str(e)}), 502

    try:
        body = read_capped(upstream, WEBVIEW_MAX_BYTES)
    except SSRFBlockedError as e:
        return _error_response(e.reason, 413)
    finally:
        status_code = upstream.status_code
        content_type = upstream.headers.get('Content-Type', 'text/html; charset=utf-8')
        final_url = upstream.url
        encoding = upstream.encoding
        upstream.close()

    if content_type.split(';')[0].strip().lower() == 'text/html':
        body = _inject_base_tag(body, encoding, final_url or url)
        content_type = 'text/html; charset=utf-8'

    response = Response(body, status=status_code, content_type=content_type)
    # 업스트림 헤더는 content_type 외에는 넘기지 않는다 (임베드를 막는 헤더/쿠키 차단이 목적).
    return response


def _inject_base_tag(body, encoding, base_url):
    """상대경로 이미지/CSS/JS/링크가 프록시 origin이 아니라 원본 사이트 기준으로 풀리도록
    <base href="..."> 태그를 <head> 바로 뒤에 주입한다. 완전한 HTML 재작성기는 아니지만
    (예: 인라인 style="background:url(...)"는 처리 못함) 서버 렌더링 페이지 대부분의
    이미지/CSS 깨짐 문제를 간단히 해결해준다."""
    from urllib.parse import urlsplit
    try:
        html_text = body.decode(encoding or 'utf-8', errors='replace')
    except Exception:
        html_text = body.decode('utf-8', errors='replace')

    parts = urlsplit(base_url)
    base_href = f"{parts.scheme}://{parts.netloc}/"
    base_tag = f'<base href="{base_href}">'

    if re.search(r'<head[^>]*>', html_text, re.IGNORECASE):
        html_text = re.sub(r'(<head[^>]*>)', r'\1' + base_tag, html_text, count=1, flags=re.IGNORECASE)
    else:
        html_text = base_tag + html_text

    return html_text.encode('utf-8')


# ─────────────────────────────── 라이브러리로 다운로드 ───────────────────────────────

_FILENAME_UNSAFE_RE = re.compile(r'[\\/\x00-\x1f:*?"<>|]')


def _sanitize_filename(name, fallback='download'):
    name = os.path.basename(str(name or '').strip())
    name = _FILENAME_UNSAFE_RE.sub('_', name).strip(' .')
    if not name:
        name = fallback
    return name[:200]


def _filename_from_content_disposition(header_value):
    if not header_value:
        return None
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', header_value, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _unique_destination_path(directory, filename):
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}_{counter}{ext}")
        counter += 1
    return candidate


def _first_local_root(physical_path):
    roots = [p.strip() for p in str(physical_path or '').replace('\r', '').split('\n') if p.strip()]
    for root in roots:
        if not is_gdrive_url(root) and os.path.isdir(root):
            return root
    return None


@plugin_webview_bp.route('/api/webview/download', methods=['POST'])
@login_required
def download_to_library():
    data = request.get_json(silent=True) or {}
    url = data.get('url')
    library_id = data.get('library_id')
    db_type = data.get('db_type') or 'general'

    if not url or not library_id:
        return jsonify({'success': False, 'error': 'url과 library_id가 필요합니다.'}), 400

    try:
        library_id = int(library_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'library_id 형식이 올바르지 않습니다.'}), 400

    lib_info = CategoryRepository.get_library_by_id(db_type, library_id)
    if not lib_info:
        return jsonify({'success': False, 'error': '라이브러리를 찾을 수 없습니다.'}), 404

    # 권한 체크 — 기존 헬퍼는 예외 시 fail-open이라, 파일 쓰기가 걸린 이 기능에서는
    # 명시적으로 fail-closed 처리한다 (예외가 나면 거부).
    try:
        allowed = CategoryRepository.check_user_category_access(db_type, session['user_id'], library_id)
    except Exception:
        allowed = False
    if not allowed:
        return jsonify({'success': False, 'error': '이 라이브러리에 대한 접근 권한이 없습니다.'}), 403

    patterns = DomainWhitelistService.get_patterns(session['user_id'])
    host = extract_host_from_url(url)
    if not host:
        return _error_response('invalid_url', 400)

    dest_dir = _first_local_root(lib_info.get('physical_path'))
    if not dest_dir:
        return jsonify({'success': False, 'error': '다운로드를 저장할 로컬 경로가 없는 라이브러리입니다 (원격/GDrive 전용).'}), 400

    try:
        upstream = fetch_with_redirect_revalidation(url, patterns, method='GET')
    except SSRFBlockedError as e:
        return _error_response(e.reason, host=e.host)
    except Exception as e:
        return jsonify({'success': False, 'error': 'fetch_failed', 'message': str(e)}), 502

    try:
        from urllib.parse import urlsplit
        cd_name = _filename_from_content_disposition(upstream.headers.get('Content-Disposition'))
        url_name = os.path.basename(urlsplit(url).path)
        raw_name = cd_name or url_name or f"download_{int(time.time())}"
        filename = _sanitize_filename(raw_name)
        if not os.path.splitext(filename)[1] and cd_name is None and url_name and '.' in url_name:
            filename = _sanitize_filename(url_name)

        dest_path = _unique_destination_path(dest_dir, filename)

        try:
            write_capped_to_file(upstream, dest_path, DOWNLOAD_MAX_BYTES)
        except SSRFBlockedError as e:
            return _error_response(e.reason, 413)
    finally:
        upstream.close()

    from tools.scanner.tasks import SUPPORTED_FORMATS
    ext = os.path.splitext(dest_path)[1].lower()
    imported_as_book = ext in SUPPORTED_FORMATS

    result = {
        'success': True,
        'filename': os.path.basename(dest_path),
        'imported_as_book': imported_as_book,
    }
    if not imported_as_book:
        result['warning'] = 'unsupported_format'
        return jsonify(result)

    try:
        from database import get_db_path
        from tools.scanner.core import scan_library_path
        scan_library_path(get_db_path(db_type), library_id, dest_path, force=True)
    except Exception as e:
        result['scan_error'] = str(e)

    return jsonify(result)
