# -*- coding: utf-8 -*-
"""
plugin_problem_service.py – 플러그인 문제 카드 계약 (알림센터 6단계)

설계: docs/plan_unified_notification_queue.md 3장 "결정: 플러그인 문제 카드 계약" / 8장 6단계.
플러그인은 베이스 클래스 헬퍼 self.report_problem() / self.resolve_problem()으로 부르고(plugins/metadata/base.py),
실제 저장은 여기서 문제 기록 테이블(services/problem_service.py)에 한다.

- 코어는 저장·표시만 한다. 제목/설명 문구는 플러그인이 준다(코어가 플러그인 코드의 의미를 해석하지 않는다).
- 충돌 방지: 코드는 '<plugin id>:<code>', 출처는 'plugin:<plugin id>'로 코어가 붙인다.
- 카드 = 플러그인 x 코드 (group_key 'plugin:<id>|<code>|-'). 스캐너의 대량 발생 판정은 적용하지 않는다.
- 조치 버튼은 새 API 없이 기존 액션 RPC(/api/media/context-menu/book/plugins/action) + action_id로 연결한다.
- 관리자에게만 보인다(알림센터의 문제 카드는 관리자 항목).
- 남용 방지: 플러그인별 열린 문제 PLUGIN_OPEN_LIMIT건 상한(넘으면 오래된 것부터 해결 처리),
  플러그인 비활성화 시 해결 처리, 서버 시작 시 꺼졌거나 지워진 플러그인의 문제 정리.

호출측(플러그인)을 절대 깨뜨리지 않는다: 잘못된 인자·저장 실패는 False를 돌려주고 로그만 남긴다.
"""
import re

from services.problem_service import (
    ProblemService,
    SEVERITY_ACTION_REQUIRED,
    SEVERITY_NOTICE,
    TARGET_TYPES,
    make_series_key,
    now_ms,
)

PLUGIN_OPEN_LIMIT = 1000
PLUGIN_SEVERITIES = (SEVERITY_NOTICE, SEVERITY_ACTION_REQUIRED)
SOURCE_PREFIX = 'plugin:'
SYSTEM_TARGET_ID = '-'

_CODE_RE = re.compile(r'^[A-Za-z0-9_.\-]{1,64}$')
_ACTION_RE = re.compile(r'^[A-Za-z0-9_.:\-]{1,64}$')
_LABEL_MAX = 40
_BOOK_DB_TYPES = ('general', 'adult')


def source_for(plugin_id):
    return f'{SOURCE_PREFIX}{plugin_id}'


def stored_code(plugin_id, code):
    return f'{plugin_id}:{code}'


def group_key_for(plugin_id, code):
    return f'{SOURCE_PREFIX}{plugin_id}|{code}|-'


def is_plugin_source(source):
    return str(source or '').startswith(SOURCE_PREFIX)


def plugin_id_of(source):
    return str(source)[len(SOURCE_PREFIX):] if is_plugin_source(source) else None


def _target_id(target_type, target_id):
    if target_type == 'system' and target_id in (None, ''):
        return SYSTEM_TARGET_ID
    if target_id in (None, ''):
        raise ValueError(f'target_id is required for target_type={target_type}')
    return str(target_id)


def _book_info(db_type, book_id):
    """도서 대상이면 시리즈/카테고리/경로를 코어가 채운다 (카드 안 시리즈별 묶음, [진단] 연결용)."""
    if db_type not in _BOOK_DB_TYPES or not str(book_id).isdigit():
        return {}
    try:
        import database
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT library_id, series_name, file_path FROM books WHERE id = ?", (int(book_id),))
            row = cursor.fetchone()
        return dict(row) if row else {}
    except Exception as e:
        print(f"[PluginProblem] book lookup failed ({db_type}:{book_id}): {e}")
        return {}


def _forget_card_cache():
    """알림 목록이 다음 폴링에서 바로 바뀌도록 카드 캐시(5초)를 비운다 (같은 웹 프로세스에서 불린 경우)."""
    try:
        from services import notification_service
        notification_service._cards_cache['at'] = 0.0
    except Exception:
        pass


def _enforce_open_limit(source):
    """플러그인별 열린 문제가 상한을 넘으면 마지막 발생이 오래된 것부터 해결 처리한다."""
    from repositories.problem_repository import ProblemRepository
    try:
        overflow = ProblemRepository.count_open_by_source(source) - PLUGIN_OPEN_LIMIT
        if overflow > 0:
            ids = ProblemRepository.list_oldest_open_ids_by_source(source, overflow)
            ProblemRepository.resolve_ids(ids, now_ms())
    except Exception as e:
        print(f"[PluginProblem] open-limit trim failed ({source}): {e}")


def report(plugin_id, code, *, title, detail='', severity=SEVERITY_NOTICE, db_type='general',
           target_type='system', target_id=None, target_path=None, library_id=None, series_name=None,
           action_id=None, action_label=None, message=None, plugin_name=None):
    """플러그인 문제를 기록한다. 같은 대상·코드로 다시 부르면 횟수만 늘어난다. 성공 여부(bool)."""
    try:
        plugin_id = str(plugin_id or '').strip()
        code = str(code or '').strip()
        if not plugin_id or not _CODE_RE.match(code):
            raise ValueError(f'invalid code: {code!r} (letters, digits, _ . - up to 64)')
        if severity not in PLUGIN_SEVERITIES:
            raise ValueError(f'severity must be one of {PLUGIN_SEVERITIES}')
        if target_type not in TARGET_TYPES:
            raise ValueError(f'target_type must be one of {TARGET_TYPES}')
        if action_id is not None and not _ACTION_RE.match(str(action_id)):
            raise ValueError(f'invalid action_id: {action_id!r}')
        db_type = str(db_type or 'general')
        tid = _target_id(target_type, target_id)
        series_key = None
        if target_type == 'book':
            info = _book_info(db_type, tid)
            library_id = library_id if library_id is not None else info.get('library_id')
            series_name = series_name if series_name is not None else info.get('series_name')
            target_path = target_path or info.get('file_path')
        if target_type in ('book', 'series') and library_id is not None:
            series_key = make_series_key(library_id, series_name)
        if target_type == 'library' and library_id is None and str(tid).isdigit():
            library_id = int(tid)
        context = {'plugin_id': plugin_id, 'plugin_name': str(plugin_name or plugin_id)[:80], 'code': code}
        if action_id:
            context['action_id'] = str(action_id)
            context['action_label'] = str(action_label or '')[:_LABEL_MAX]
        source = source_for(plugin_id)
        ok = ProblemService.report(
            stored_code(plugin_id, code), target_type, tid, db_type=db_type, library_id=library_id,
            severity=severity, source=source, target_path=target_path, series_key=series_key,
            title=str(title or code), detail=str(detail or ''), message=message, context=context,
            group_key=group_key_for(plugin_id, code),
        )
        if ok:
            _enforce_open_limit(source)
            _forget_card_cache()
        return ok
    except Exception as e:
        print(f"[PluginProblem] report rejected ({plugin_id}:{code}): {e}")
        return False


def resolve(plugin_id, code, *, db_type='general', target_type='system', target_id=None):
    """다음에 성공했을 때 해결 처리한다. 열린 행이 없으면 False."""
    try:
        code = str(code or '').strip()
        if not plugin_id or not _CODE_RE.match(code) or target_type not in TARGET_TYPES:
            return False
        resolved = ProblemService.resolve(stored_code(plugin_id, code), target_type, _target_id(target_type, target_id),
                                          db_type=db_type or 'general')
        if resolved:
            _forget_card_cache()
        return resolved
    except Exception as e:
        print(f"[PluginProblem] resolve failed ({plugin_id}:{code}): {e}")
        return False


def on_plugin_disabled(plugin_id):
    """관리자가 플러그인을 끄면 그 플러그인의 열린 문제를 해결 처리한다(카드가 사라진다). 다시 켜고 다시 보고하면 보인다."""
    from repositories.problem_repository import ProblemRepository
    try:
        return ProblemRepository.resolve_by_source(source_for(plugin_id), now_ms())
    except Exception as e:
        print(f"[PluginProblem] cleanup on disable failed ({plugin_id}): {e}")
        return 0


def cleanup_inactive_plugins(active_plugin_ids):
    """서버 시작 시: 지금 켜져 있지 않은(꺼졌거나 폴더가 지워진) 플러그인의 열린 문제를 해결 처리한다."""
    from repositories.problem_repository import ProblemRepository
    active = {str(p) for p in active_plugin_ids or []}
    total = 0
    try:
        for source in ProblemRepository.list_open_sources(SOURCE_PREFIX):
            if plugin_id_of(source) not in active:
                total += ProblemRepository.resolve_by_source(source, now_ms())
    except Exception as e:
        print(f"[PluginProblem] inactive-plugin cleanup failed: {e}")
    return total
