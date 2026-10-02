# -*- coding: utf-8 -*-
"""
problem_service.py – 문제 기록(알림센터 문제 카드)의 공용 서비스

설계: docs/plan_unified_notification_queue.md (1·3·4·5장).
- 기록은 대상 단위(book/series/library/system) x 코드, 재발은 횟수만 늘린다.
- 카드는 group_key(= code|db_type|library_id) 단위로 묶어 보여 준다.
- 다음에 성공하면 resolve()로 해결 처리 → 카드의 열린 개수가 0이면 카드가 사라진다.

기록/해결은 절대 호출측을 깨뜨리지 않는다(저장 실패는 로그만 남긴다).

사용법:
    ProblemService.report('file_missing', 'book', book_id, db_type='general', library_id=80,
                          target_path=path, series_key=make_series_key(80, series_name))
    ProblemService.resolve('file_missing', 'book', book_id, db_type='general')

    with ProblemService.track('file_corrupt', 'book', book_id, db_type='general', library_id=80):
        parse(path)      # 예외면 report 후 다시 던지고, 성공이면 resolve
"""
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from repositories.problem_repository import ProblemRepository

SEVERITY_ACTION_REQUIRED = 'action_required'
SEVERITY_NOTICE = 'notice'
SEVERITY_AUTO_FIXED = 'auto_fixed'
_SEVERITIES = (SEVERITY_ACTION_REQUIRED, SEVERITY_NOTICE, SEVERITY_AUTO_FIXED)
_SEVERITY_BY_RANK = {2: SEVERITY_ACTION_REQUIRED, 1: SEVERITY_NOTICE, 0: SEVERITY_AUTO_FIXED}

TARGET_TYPES = ('book', 'series', 'library', 'system')

CODE_UNKNOWN = 'unknown'
CODE_SYSTEM_TASK_FAILED = 'system_task_failed'
CODE_USER_REPORT = 'user_report'
# 관리자가 카드에서 직접 [해결됨]으로 닫을 수 있는 코드 (스캐너 코드는 다음 스캔이 판단하므로 제외)
ADMIN_RESOLVABLE_CODES = (CODE_USER_REPORT,)

# 코드 → 화면 문구(i18n 키: static/i18n/*.json "problems.code.<code>.title/detail"), 기본 심각도, 조치 목록.
# 조치 이름은 화면에서 버튼으로 바뀐다("problems.action.<id>"). 실제 동작은 알림센터 단계에서 연결한다.
CATALOG = {
    # 스캐너가 이미 휴지통으로 옮긴 도서(7일 뒤 자동 삭제) - 알려만 준다.
    'file_missing': {'severity': SEVERITY_NOTICE, 'actions': ['rescan']},
    # 한 스캔에서 대량으로 사라졌는데 루트는 살아 있음 → 휴지통 이동을 보류하고 확인을 받는다.
    'mass_missing': {'severity': SEVERITY_ACTION_REQUIRED, 'actions': ['rescan', 'confirm_trash']},
    # 카테고리 루트/마운트 접근 불가 → 삭제 처리 전부 보류. 파괴적 조치는 제공하지 않는다.
    'remote_unavailable': {'severity': SEVERITY_ACTION_REQUIRED, 'actions': ['rescan']},
    'file_corrupt': {'severity': SEVERITY_NOTICE, 'actions': ['rescan']},
    'cover_missing': {'severity': SEVERITY_NOTICE, 'actions': ['rescan']},
    'metadata_invalid': {'severity': SEVERITY_AUTO_FIXED, 'actions': ['auto_fix']},
    CODE_SYSTEM_TASK_FAILED: {'severity': SEVERITY_ACTION_REQUIRED, 'actions': []},
    # 일반 사용자가 뷰어 오류 자리에서 [관리자에게 알리기]를 누름 (5단계). 스캐너가 판단할 근거가 없어
    # 자동 해제하지 않고, 관리자가 확인 후 [해결됨]으로 닫는다.
    CODE_USER_REPORT: {'severity': SEVERITY_NOTICE, 'actions': ['resolve']},
    CODE_UNKNOWN: {'severity': SEVERITY_NOTICE, 'actions': ['report']},
}

# 대량 발생 신호 기준 (3장 "결정: 대량 발생 기준"). 숫자를 코드 곳곳에 흩뿌리지 말고
# 반드시 get_mass_missing_thresholds()로 읽는다 - 나중에 전역/카테고리별 설정으로 넓힐 자리.
MASS_MISSING_RATIO = 0.2
MASS_MISSING_MIN_COUNT = 20

RESOLVED_RETENTION_DAYS = 30
_MESSAGE_MAX_LEN = 500
_TEXT_MAX_LEN = 300


def now_ms():
    return int(time.time() * 1000)


def to_iso(ms):
    """epoch ms → 타임존 포함 ISO 문자열. 서버(UTC)와 브라우저(KST)가 달라도 어긋나지 않는다."""
    if not ms:
        return ''
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone().isoformat(timespec='seconds')


def make_series_key(library_id, series_name):
    return f"{library_id}|{series_name or ''}"


def make_group_key(code, db_type, library_id=None):
    return f"{code}|{db_type}|{library_id if library_id not in (None, '') else '-'}"


def catalog_entry(code):
    entry = CATALOG.get(code) or CATALOG[CODE_UNKNOWN]
    known = code in CATALOG
    i18n_code = code if known else CODE_UNKNOWN
    return {
        'severity': entry['severity'],
        'actions': list(entry['actions']),
        'title_key': f'problems.code.{i18n_code}.title',
        'detail_key': f'problems.code.{i18n_code}.detail',
    }


def get_mass_missing_thresholds(db_type, library_id):
    """한 스캔에서 file_missing이 '대량'인지 판단하는 기준. 지금은 고정값.

    인자(db_type, library_id)는 아직 쓰지 않지만 카테고리별 덮어쓰기를 붙일 자리라 미리 받는다.
    루트 접근 불가 판정은 안전장치라 여기 기준과 무관하게 항상 적용된다(설정 대상 아님)."""
    return {'ratio': MASS_MISSING_RATIO, 'min_count': MASS_MISSING_MIN_COUNT}


def _clip(value, limit):
    if value is None:
        return None
    text = str(value)
    return text[:limit]


def parse_context(raw):
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw) if raw else {}
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _plugin_card_info(group):
    """플러그인 카드의 표시 정보 - 카드의 최근 행 하나에서 플러그인 이름/문구/조치를 읽는다."""
    try:
        rows, _total = ProblemRepository.list_group_items(group['group_key'], limit=1, offset=0)
    except Exception as e:
        print(f"[ProblemService] plugin card info failed ({group.get('group_key')}): {e}")
        rows = []
    row = rows[0] if rows else {}
    ctx = parse_context(row.get('context'))
    plugin_id = ctx.get('plugin_id') or str(group.get('source') or '')[len('plugin:'):]
    return {
        'id': plugin_id,
        'name': ctx.get('plugin_name') or plugin_id,
        'code': ctx.get('code') or '',
        'title': row.get('title') or ctx.get('code') or '',
        'detail': row.get('detail') or '',
        'action_id': ctx.get('action_id') or None,
        'action_label': ctx.get('action_label') or '',
    }


class ProblemService:
    @staticmethod
    def report(code, target_type, target_id, *, db_type='general', library_id=None, severity=None,
               source='scanner', target_path=None, series_key=None, title=None, detail=None,
               message=None, context=None, group_key=None):
        """문제 발생을 기록한다. 같은 대상·코드로 다시 부르면 횟수만 늘어난다. 실패해도 예외를 내지 않는다."""
        try:
            if target_type not in TARGET_TYPES:
                raise ValueError(f'unknown target_type: {target_type}')
            severity = severity or catalog_entry(code)['severity']
            if severity not in _SEVERITIES:
                raise ValueError(f'unknown severity: {severity}')
            if isinstance(context, (dict, list)):
                context = json.dumps(context, ensure_ascii=False)
            ProblemRepository.upsert({
                'code': str(code),
                'severity': severity,
                'source': str(source),
                'db_type': str(db_type or 'general'),
                'library_id': int(library_id) if library_id not in (None, '') else None,
                'target_type': target_type,
                'target_id': str(target_id),
                'target_path': target_path,
                'series_key': series_key,
                'group_key': group_key or make_group_key(code, db_type or 'general', library_id),
                'title': _clip(title, _TEXT_MAX_LEN),
                'detail': _clip(detail, _TEXT_MAX_LEN),
                'message': _clip(message, _MESSAGE_MAX_LEN),
                'context': context,
            }, now_ms())
            return True
        except Exception as e:
            print(f"[ProblemService] report '{code}' {target_type}:{target_id} failed: {e}")
            return False

    @staticmethod
    def resolve(code, target_type, target_id, *, db_type='general'):
        """대상이 다시 정상이 됐을 때 해결 처리한다. 열린 행이 없으면 아무것도 하지 않는다."""
        try:
            return ProblemRepository.resolve(str(code), db_type or 'general', target_type, str(target_id), now_ms()) > 0
        except Exception as e:
            print(f"[ProblemService] resolve '{code}' {target_type}:{target_id} failed: {e}")
            return False

    @staticmethod
    def resolve_targets(db_type, target_type, target_ids, code=None):
        """여러 대상을 한꺼번에 해결 처리한다 (예: 스캔에서 정상 확인된 도서들, 영구 삭제된 도서들)."""
        try:
            return ProblemRepository.resolve_targets(db_type or 'general', target_type, target_ids, now_ms(), code=code)
        except Exception as e:
            print(f"[ProblemService] resolve_targets {target_type} x{len(target_ids or [])} failed: {e}")
            return 0

    @staticmethod
    @contextmanager
    def track(code, target_type, target_id, **report_kwargs):
        """블록이 예외면 report 후 예외를 그대로 다시 던지고, 성공이면 resolve한다."""
        try:
            yield
        except Exception as e:
            report_kwargs.setdefault('message', str(e))
            ProblemService.report(code, target_type, target_id, **report_kwargs)
            raise
        else:
            ProblemService.resolve(code, target_type, target_id, db_type=report_kwargs.get('db_type', 'general'))

    @staticmethod
    def get(code, target_type, target_id, *, db_type='general'):
        try:
            return ProblemRepository.get(str(code), db_type or 'general', target_type, str(target_id))
        except Exception as e:
            print(f"[ProblemService] get '{code}' {target_type}:{target_id} failed: {e}")
            return None

    @staticmethod
    def list_open(target_type=None, code=None):
        try:
            return ProblemRepository.list_open(target_type=target_type, code=code)
        except Exception as e:
            print(f"[ProblemService] list_open failed: {e}")
            return []

    # ---- 카드 ----
    @staticmethod
    def list_cards(include_muted=False):
        """열린 문제 카드 목록. 음소거된 카드는 그 뒤로 대상이 늘었을 때만 다시 보인다."""
        try:
            groups = ProblemRepository.list_groups()
        except Exception as e:
            print(f"[ProblemService] list_cards failed: {e}")
            return []
        cards = []
        for g in groups:
            open_count = int(g.get('open_count') or 0)
            muted = bool(g.get('muted_ms')) and open_count <= int(g.get('muted_count') or 0)
            if muted and not include_muted:
                continue
            entry = catalog_entry(g.get('code'))
            plugin = _plugin_card_info(g) if str(g.get('source') or '').startswith('plugin:') else None
            if plugin:
                # 플러그인 카드: 문구는 플러그인이 준 것, 조치는 플러그인 액션 RPC (6단계 계약)
                entry = {'title_key': None, 'detail_key': None,
                         'actions': ['plugin_action'] if plugin.get('action_id') else []}
            cards.append({
                'group_key': g['group_key'],
                'code': g.get('code'),
                'source': g.get('source'),
                'db_type': g.get('db_type'),
                'library_id': g.get('library_id'),
                'severity': _SEVERITY_BY_RANK.get(int(g.get('severity_rank') or 0), SEVERITY_NOTICE),
                'open_count': open_count,
                'first_seen_at': to_iso(g.get('first_seen_ms')),
                'last_seen_at': to_iso(g.get('last_seen_ms')),
                'muted': muted,
                'title_key': entry['title_key'],
                'detail_key': entry['detail_key'],
                'actions': entry['actions'],
                'plugin': plugin,
            })
        return cards

    @staticmethod
    def list_card_series(group_key, limit=50, offset=0):
        try:
            return ProblemRepository.list_group_series(group_key, limit=limit, offset=offset)
        except Exception as e:
            print(f"[ProblemService] list_card_series '{group_key}' failed: {e}")
            return []

    @staticmethod
    def list_card_items(group_key, series_key=None, limit=50, offset=0):
        try:
            rows, total = ProblemRepository.list_group_items(group_key, series_key=series_key, limit=limit, offset=offset)
        except Exception as e:
            print(f"[ProblemService] list_card_items '{group_key}' failed: {e}")
            return [], 0
        for r in rows:
            r['first_seen_at'] = to_iso(r.get('first_seen_ms'))
            r['last_seen_at'] = to_iso(r.get('last_seen_ms'))
            r['resolved_at'] = to_iso(r.get('resolved_ms'))
        return rows, total

    @staticmethod
    def mute_card(group_key):
        """알고 있음: 지금 개수까지는 숨기고, 대상이 늘어나면 다시 보인다."""
        groups = {g['group_key']: g for g in ProblemRepository.list_groups()}
        current = groups.get(group_key)
        if not current:
            return False
        ProblemRepository.set_group_mute(group_key, int(current.get('open_count') or 0), now_ms())
        return True

    @staticmethod
    def unmute_card(group_key):
        ProblemRepository.clear_group_mute(group_key)
        return True

    @staticmethod
    def resolve_card(group_key):
        """[해결됨]: 카드의 열린 행을 모두 해결 처리한다 (ADMIN_RESOLVABLE_CODES 카드만). 해결한 행 수."""
        code = str(group_key or '').split('|', 1)[0]
        if code not in ADMIN_RESOLVABLE_CODES:
            raise ValueError('이 카드는 직접 해결 처리할 수 없습니다 (다음 스캔에서 자동 해제됩니다).')
        total = 0
        while True:
            rows, _count = ProblemRepository.list_group_items(group_key, limit=500, offset=0)
            if not rows:
                return total
            resolved = ProblemRepository.resolve_ids([r['id'] for r in rows], now_ms())
            if not resolved:
                return total
            total += resolved

    # ---- 수명 관리 / 삭제 연동 ----
    @staticmethod
    def purge_resolved(days=RESOLVED_RETENTION_DAYS):
        try:
            return ProblemRepository.purge_resolved(now_ms() - int(days) * 86400 * 1000)
        except Exception as e:
            print(f"[ProblemService] purge_resolved failed: {e}")
            return 0

    @staticmethod
    def on_library_deleted(db_type, library_id):
        """카테고리 삭제/이동: 그 카테고리 카드가 영원히 남지 않게 기록을 지운다."""
        try:
            return ProblemRepository.delete_by_library(db_type, library_id)
        except Exception as e:
            print(f"[ProblemService] on_library_deleted {db_type}:{library_id} failed: {e}")
            return 0

    @staticmethod
    def on_books_deleted(db_type, book_ids):
        """도서 영구 삭제(휴지통 비우기): 그 도서들의 열린 문제를 해결 처리한다."""
        return ProblemService.resolve_targets(db_type, 'book', book_ids)
