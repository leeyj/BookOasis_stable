# -*- coding: utf-8 -*-
"""
domain_whitelist_service.py – 외부 도메인 허용 목록(화이트리스트) 관리 (관리자 전용, 전역 단일 목록)

앱은 어떤 외부 도메인도 기본 제공/추천하지 않는다 — 관리자가 자신의 책임 하에 직접
도메인을 추가하며, 등록된 목록은 모든 사용자에게 공통 적용된다. 플러그인 웹뷰/다운로드
API(api/routes/plugin_webview_routes.py)가 이 화이트리스트를 근거로 요청을 허용/차단한다.

과거에는 사용자별로(USER_URL_WHITELIST_{user_id}) 각자 목록을 관리했으나, 일반 사용자가
임의 도메인으로 웹뷰/다운로드를 열 수 있는 것은 보안상 바람직하지 않아 관리자가 전역으로
관리하는 단일 목록으로 전환했다. 기존 사용자별 데이터는 최초 접근 시 전역 목록으로 1회
병합 마이그레이션되며, 원본 legacy 키는 삭제하지 않고 그대로 둔다(더 이상 읽지 않을 뿐).
"""
import json
import re

from repositories.settings_repository import SettingsRepository
from utils.time_helper import utc_now_iso

_SETTINGS_KEY = 'EXTERNAL_DOMAIN_WHITELIST'
_LEGACY_PER_USER_PREFIX = 'USER_URL_WHITELIST_'
_MAX_DOMAINS = 200

_HOSTNAME_RE = re.compile(
    r'^(\*\.)?[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'
)


def normalize_pattern(raw):
    """사용자가 입력한 문자열(도메인 또는 URL 전체)에서 호스트 패턴을 정규화해서 반환한다.
    유효하지 않으면 None."""
    if not raw:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None

    # URL을 통째로 붙여넣은 경우 호스트만 추출
    if '://' in text:
        from urllib.parse import urlsplit
        host = urlsplit(text).hostname
        if not host:
            return None
        text = host
    else:
        # 경로/쿼리/포트가 붙어있으면 제거
        text = text.split('/', 1)[0]
        if not text.startswith('*.'):
            text = text.split(':', 1)[0]

    is_wildcard = text.startswith('*.')
    hostname_part = text[2:] if is_wildcard else text

    try:
        idna_encoded = hostname_part.encode('idna').decode('ascii')
    except Exception:
        idna_encoded = hostname_part

    candidate = f"*.{idna_encoded}" if is_wildcard else idna_encoded

    if not _HOSTNAME_RE.match(candidate):
        return None

    return candidate


def host_matches_whitelist(host, patterns):
    """순수 함수 — 네트워크/DB 접근 없이 호스트가 패턴 목록에 매치되는지만 판정한다."""
    if not host:
        return False
    host = str(host).strip().lower().rstrip('.')
    for pattern in patterns or []:
        if not pattern:
            continue
        pattern = pattern.lower()
        if pattern.startswith('*.'):
            suffix = pattern[1:]  # ".example.com"
            apex = pattern[2:]    # "example.com"
            if host != apex and host.endswith(suffix):
                return True
        elif host == pattern:
            return True
    return False


def extract_host_from_url(url):
    """http/https URL에서 호스트만 추출한다. scheme이 http/https가 아니거나 파싱 불가하면 None."""
    if not url:
        return None
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(str(url).strip())
    except Exception:
        return None
    if parts.scheme not in ('http', 'https'):
        return None
    return parts.hostname


class DomainWhitelistService:
    @staticmethod
    def get_whitelist():
        """전역 화이트리스트 엔트리 목록을 반환한다 ([{pattern, added_at}, ...])."""
        raw = SettingsRepository.get_value(_SETTINGS_KEY)
        if raw is None:
            # 전역 목록이 아직 없으면(구버전에서 갓 업그레이드) 기존 사용자별 목록을 1회 병합한다.
            return DomainWhitelistService._migrate_legacy_per_user_entries()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict) and e.get('pattern')]
        except Exception:
            pass
        return []

    @staticmethod
    def _migrate_legacy_per_user_entries():
        """예전 사용자별(USER_URL_WHITELIST_{user_id}) 화이트리스트를 전역 목록 하나로 병합한다.
        legacy 키 자체는 삭제하지 않는다 - 코드에서 더 이상 읽지 않을 뿐 안전하게 방치."""
        try:
            legacy = SettingsRepository.get_settings_by_prefix(_LEGACY_PER_USER_PREFIX)
            merged = {}
            for raw in legacy.values():
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                for e in data:
                    if isinstance(e, dict) and e.get('pattern') and e['pattern'] not in merged:
                        merged[e['pattern']] = e
            entries = list(merged.values())[:_MAX_DOMAINS]
        except Exception:
            entries = []
        SettingsRepository.set_value(_SETTINGS_KEY, json.dumps(entries, ensure_ascii=False))
        return entries

    @staticmethod
    def get_patterns():
        """매칭용 패턴 문자열 목록만 반환한다."""
        return [e['pattern'] for e in DomainWhitelistService.get_whitelist()]

    @staticmethod
    def add_domain(raw_pattern):
        """도메인을 전역 화이트리스트에 추가한다. (성공 여부, 에러메시지) 튜플 반환."""
        pattern = normalize_pattern(raw_pattern)
        if not pattern:
            return False, '유효하지 않은 도메인 형식입니다.'

        entries = DomainWhitelistService.get_whitelist()
        if any(e['pattern'] == pattern for e in entries):
            return True, ''  # 이미 존재 — 멱등하게 성공 처리

        if len(entries) >= _MAX_DOMAINS:
            return False, f'허용 도메인은 최대 {_MAX_DOMAINS}개까지 등록할 수 있습니다.'

        entries.append({
            'pattern': pattern,
            'added_at': utc_now_iso()
        })
        SettingsRepository.set_value(_SETTINGS_KEY, json.dumps(entries, ensure_ascii=False))
        return True, ''

    @staticmethod
    def remove_domain(pattern):
        """도메인을 전역 화이트리스트에서 제거한다. 존재 여부와 무관하게 항상 성공(멱등)."""
        normalized = normalize_pattern(pattern) or str(pattern or '').strip().lower()
        entries = DomainWhitelistService.get_whitelist()
        remaining = [e for e in entries if e['pattern'] != normalized]
        SettingsRepository.set_value(_SETTINGS_KEY, json.dumps(remaining, ensure_ascii=False))
        return True

    @staticmethod
    def is_host_whitelisted(host):
        return host_matches_whitelist(host, DomainWhitelistService.get_patterns())
