# -*- coding: utf-8 -*-
"""
notification_service.py – 알림센터(상단 〰 팝오버) 공통 항목 어댑터

설계: docs/plan_unified_notification_queue.md 7장 / 8장 3단계.
여러 출처(스캔 큐, 스캔 이력, 음성 미리 만들기, 시스템 경고, 문제 카드)를 한 가지 항목 형식으로 바꾸고,
로그인 사용자가 볼 수 있는 것만(audience) 걸러서 내려준다. 렌더러는 권한을 몰라도 된다.

항목 형식:
    id          항목 고유 키 (같은 항목이면 폴링마다 같다)
    track_key   진행 → 완료로 넘어가도 유지되는 키 (보고 있는 동안 끝난 작업 토스트용)
    kind        problem / running / recent
    tone        error / running / new / done / muted / notice  (화면 색 + 라벨)
    source      scan / tts / system / problem / plugin
    severity    action_required / notice / None
    title       데이터 문자열(카테고리명·도서명). 없으면 title_key(+title_vars)
    detail      [{key, vars}] - 화면에서 i18n 문구로 바꿔 ' · '로 잇는다.
                vars 값이 {"time": ISO}면 상대 시각("3분 전"), {"key": i18n 키}면 그 문구로 바꾼다.
    raw_detail  서버가 만든 원문(스캐너 진행 단계, 오류 메시지) - 번역 없이 그대로 표시
    target      {db_type, library_id, book_ids?}
    actions     조치 버튼 id 목록 (문제 카드 단계에서 연결)
    progress    {percent, done, total, elapsed_seconds} 또는 None
    created_at / updated_at  타임존 포함 ISO
    read        사용자가 마지막으로 알림을 연 뒤에 바뀐 항목이면 False
"""
import json
import threading
import time
from datetime import datetime, timezone

RECENT_DAYS = 7
RECENT_MAX_ITEMS = 50
_HISTORY_FETCH_LIMIT = 200
# /api/system/status는 2초마다 폴링된다 - 이력 조회는 프로세스 단위로 짧게 캐시한다.
_HISTORY_CACHE_TTL = 5.0
_SEEN_CACHE_TTL = 30.0
LAST_SEEN_SETTING_KEY = 'NOTIFICATIONS_LAST_SEEN_MS'
# [지우기]: 이 시각 이전에 끝난 '최근 완료' 항목은 그 사용자에게서 숨긴다 (기록은 그대로).
CLEARED_SETTING_KEY = 'NOTIFICATIONS_CLEARED_MS'

# 사용자가 직접 누르는 작업들 - 예전 이력 행(trigger_type 기록 전)도 수동으로 본다.
_USER_INITIATED_TASK_TYPES = ('batch_book_scan', 'cover_scan', 'gdrive_copy')

_history_cache = {'at': 0.0, 'rows': []}
_cards_cache = {'at': 0.0, 'cards': []}
_seen_cache = {}
_cleared_cache = {}
_seen_lock = threading.Lock()


def _now_ms():
    return int(time.time() * 1000)


def _ms_to_iso(ms):
    if not ms:
        return ''
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone().isoformat(timespec='seconds')


def _server_time_to_ms(value):
    """스캐너 큐가 남긴 서버 로컬 시각 문자열('YYYY-MM-DD HH:MM:SS') → epoch ms."""
    if not value:
        return 0
    try:
        raw = str(value).strip().replace('T', ' ')
        if raw.endswith('Z'):
            raw = raw[:-1] + '+00:00'
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()  # 큐는 datetime.now()(서버 로컬)로 기록한다
        return int(parsed.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return 0


def _part(key, **vars_):
    return {'key': key, 'vars': vars_}


def _load_kwargs(raw):
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


# ---- 수동/자동 구분 + 표시 대상 ----

def is_manual_trigger(task_type, kwargs):
    trigger = kwargs.get('trigger_type') or kwargs.get('trigger')
    if trigger:
        return trigger == 'manual'
    if kwargs.get('is_cron') is False:
        return True
    return task_type in _USER_INITIATED_TASK_TYPES


def is_notable_history(row):
    """최근 완료로 보여 줄 이력인가: 새 도서/에러/실패/취소가 있거나, 사용자가 직접 누른 작업.

    lazy_scan·예약 스캔처럼 자동으로 돌아 아무 변화 없이 끝난 작업은 숨긴다(이력 테이블에는 남는다).
    루트 접근 실패로 끝난 작업도 숨긴다: '원격 드라이브 연결 끊김' 카드가 (순단 유예를 거쳐) 대신 알린다."""
    from services.scan_problem_service import ROOT_UNREACHABLE_MARKER
    if row.get('status') == 'failed' and ROOT_UNREACHABLE_MARKER in str(row.get('error_message') or ''):
        return False
    if row.get('status') in ('failed', 'cancelled'):
        return True
    summary = row.get('result_summary') or {}
    if int(summary.get('new_books') or 0) > 0 or int(summary.get('errors') or 0) > 0:
        return True
    return is_manual_trigger(row.get('task_type'), _load_kwargs(row.get('kwargs')))


# ---- 출처별 변환 ----

def _scan_title(task_type, kwargs, library_name):
    if task_type == 'batch_book_scan':
        count = len(kwargs.get('book_ids') or [])
        book_title = str(kwargs.get('book_title') or '').strip()
        if count == 1 and book_title:
            name = book_title
        else:
            title_vars = {'count': count}
            if library_name:
                title_vars['library'] = library_name  # 화면에서 "카테고리 · " 접두로 붙인다
            return None, 'notify.scan.selected_books', title_vars
        return (f'{library_name} · {name}' if library_name else name), None, {}
    if task_type == 'lazy_scan' and kwargs.get('library_id') is None:
        return None, 'notify.scan.whole_system', {}
    if library_name:
        return library_name, None, {}
    if kwargs.get('library_id') is not None:
        return None, 'notify.scan.library_fallback', {'id': kwargs.get('library_id'), 'db_type': kwargs.get('db_type', 'general')}
    return None, 'notify.scan.background', {}


def _scan_target(kwargs):
    target = {'db_type': kwargs.get('db_type', 'general'), 'library_id': kwargs.get('library_id')}
    if kwargs.get('book_ids'):
        target['book_ids'] = list(kwargs.get('book_ids'))
    return target


def _base(item_id, track_key, kind, tone, source, *, severity=None, title=None, title_key=None, title_vars=None,
          detail=None, raw_detail='', target=None, actions=None, progress=None, created_ms=0, updated_ms=0,
          task_type=None):
    return {
        'id': item_id,
        'track_key': track_key,
        'kind': kind,
        'tone': tone,
        'source': source,
        'severity': severity,
        'task_type': task_type,
        'title': title,
        'title_key': title_key,
        'title_vars': title_vars or {},
        'detail': detail or [],
        'raw_detail': raw_detail or '',
        'target': target or {},
        'actions': actions or [],
        'progress': progress,
        'created_at': _ms_to_iso(created_ms),
        'updated_at': _ms_to_iso(updated_ms),
        '_updated_ms': int(updated_ms or 0),
    }


def scan_running_items(status, library_name, elapsed_seconds):
    items = []
    running = (status or {}).get('running')
    if running:
        kwargs = running.get('kwargs') or {}
        task_type = running.get('type')
        title, title_key, title_vars = _scan_title(task_type, kwargs, library_name(kwargs.get('db_type', 'general'), kwargs.get('library_id')))
        stage = str(running.get('stage') or '').strip()
        started_ms = _server_time_to_ms(running.get('started_at') or running.get('enqueued_at'))
        items.append(_base(
            f"scan:running:{running.get('key')}", f"scan:{running.get('key')}", 'running', 'running', 'scan',
            task_type=task_type, title=title, title_key=title_key, title_vars=title_vars,
            detail=[] if stage else [_part(f'notify.scan.running.{task_type}')],
            raw_detail=stage, target=_scan_target(kwargs),
            progress={'elapsed_seconds': elapsed_seconds(running.get('started_at') or running.get('enqueued_at'))},
            created_ms=started_ms, updated_ms=started_ms,
        ))
    for task in (status or {}).get('pending') or []:
        kwargs = task.get('kwargs') or {}
        task_type = task.get('type')
        title, title_key, title_vars = _scan_title(task_type, kwargs, library_name(kwargs.get('db_type', 'general'), kwargs.get('library_id')))
        queued_ms = _server_time_to_ms(task.get('enqueued_at'))
        items.append(_base(
            f"scan:pending:{task.get('key')}", f"scan:{task.get('key')}", 'running', 'running', 'scan',
            task_type=task_type, title=title, title_key=title_key, title_vars=title_vars,
            detail=[_part(f'notify.scan.pending.{task_type}')], target=_scan_target(kwargs),
            progress={'pending': True}, created_ms=queued_ms, updated_ms=queued_ms,
        ))
    return items


def tuning_item(db_type):
    now = _now_ms()
    return _base(f'system:tuning:{db_type}', f'system:tuning:{db_type}', 'running', 'running', 'system',
                 title_key='notify.system.maintenance', detail=[_part('notify.system.db_tuning')],
                 target={'db_type': db_type}, created_ms=now, updated_ms=now)


def scan_history_item(row, library_name):
    kwargs = _load_kwargs(row.get('kwargs'))
    task_type = row.get('task_type')
    status = row.get('status') or 'completed'
    summary = row.get('result_summary') or {}
    new_books = int(summary.get('new_books') or 0)
    errors = int(summary.get('errors') or 0)
    title, title_key, title_vars = _scan_title(task_type, kwargs, library_name(kwargs.get('db_type', 'general'), kwargs.get('library_id')))

    detail = [_part(f'notify.scan.status.{status}', task={'key': f'notify.scan.task.{task_type}'})]
    if task_type == 'batch_book_scan' and summary.get('books') is not None:
        detail.append(_part('notify.scan.batch_result', succeeded=int(summary.get('succeeded') or 0),
                            total=int(summary.get('books') or 0)))
        if errors:
            detail.append(_part('notify.scan.failed_books', count=errors))
    else:
        if new_books:
            detail.append(_part('notify.scan.new_books', count=new_books))
        if errors:
            detail.append(_part('notify.scan.failed_books', count=errors))
        if status == 'completed' and not new_books and not errors and 'new_books' in summary:
            detail.append(_part('notify.scan.no_change'))

    if status == 'failed':
        tone = 'error'
    elif status == 'cancelled':
        tone = 'muted'
    elif new_books:
        tone = 'new'
    else:
        tone = 'done'

    raw = ''
    if status == 'failed' and row.get('error_message'):
        raw = str(row['error_message']).strip().splitlines()[0][:300]
    finished_ms = _server_time_to_ms(row.get('finished_at'))
    return _base(
        f"scan:history:{row.get('id')}", f"scan:{row.get('task_key')}", 'recent', tone, 'scan',
        task_type=task_type, title=title, title_key=title_key, title_vars=title_vars,
        detail=detail, raw_detail=raw, target=_scan_target(kwargs),
        created_ms=_server_time_to_ms(row.get('started_at')) or finished_ms, updated_ms=finished_ms,
    )


def tts_items(pregen):
    items = []
    for job in pregen or []:
        status = job.get('status')
        key = f"tts:{job.get('db_type')}:{job.get('id')}"
        title_vars = {}
        title = f"{job.get('title') or ''}"
        target = {'db_type': job.get('db_type'), 'book_ids': [job.get('book_id')] if job.get('book_id') else []}
        total = int(job.get('total') or 0)
        done = int(job.get('done') or 0)
        finished_ms = int(job.get('finished_ms') or 0)
        progress = {'done': done, 'total': total, 'percent': (done * 1000 // total) / 10 if total else job.get('percent', 0)}
        adult = job.get('db_type') == 'adult'
        if status in ('queued', 'running'):
            detail = [_part('notify.tts.queued', total=total) if status == 'queued'
                      else _part('notify.tts.running', percent=progress['percent'], done=done, total=total)]
            now = _now_ms()
            items.append(_base(f'{key}:active', key, 'running', 'running', 'tts', title=title, title_vars=title_vars,
                               detail=detail, target=target, progress=progress if status == 'running' else {'pending': True},
                               created_ms=now, updated_ms=now))
        else:
            tone = 'new' if status == 'done' else ('muted' if status == 'cancelled' else 'error')
            items.append(_base(f'{key}:finished', key, 'recent', tone, 'tts', title=title, title_vars=title_vars,
                               detail=[_part(f'notify.tts.{status}')], target=target,
                               created_ms=finished_ms, updated_ms=finished_ms))
        items[-1]['adult'] = adult
    return items


def system_warning_items(warnings):
    items = []
    for w in warnings or []:
        since = (_part('notify.system.last_ok', when={'time': w.get('last_ok_at')}) if w.get('last_ok_at')
                 else _part('notify.system.first_failed', when={'time': w.get('first_failed_at')}))
        last_ms = _server_time_to_ms(w.get('last_failed_at'))
        items.append(_base(
            f"system:warning:{w.get('key')}", f"system:warning:{w.get('key')}", 'problem', 'error', 'system',
            severity='action_required', title=w.get('label') or w.get('key'),
            detail=[_part('notify.system.failing'), since, _part('notify.system.fail_count', count=int(w.get('fail_count') or 0))],
            raw_detail=w.get('message') or '',
            created_ms=_server_time_to_ms(w.get('first_failed_at')), updated_ms=last_ms,
        ))
    return items


def problem_card_items(cards, library_name):
    """문제 카드(시스템 경고 카드 제외 - 그건 system_warning_items가 작업별 한 줄로 보여 준다).

    여러 카테고리가 동시에 '원격 드라이브 연결 끊김'이면(같은 rclone 리모트 공유 등) 카테고리별 카드 대신
    한 줄로 묶는다 (계획 3장 "결정: 대량 발생 기준" 4번)."""
    from services.problem_service import CODE_SYSTEM_TASK_FAILED
    items = []
    remote = []
    for card in cards or []:
        if card.get('code') == CODE_SYSTEM_TASK_FAILED:
            continue
        severity = card.get('severity')
        lib = library_name(card.get('db_type') or 'general', card.get('library_id')) if card.get('library_id') else ''
        card_info = {
            'group_key': card['group_key'], 'code': card.get('code'), 'db_type': card.get('db_type'),
            'library_id': card.get('library_id'), 'library': lib or '', 'open_count': card.get('open_count', 0),
            'muted': bool(card.get('muted')),
        }
        plugin = card.get('plugin')
        if plugin:
            # 플러그인 카드: 출처를 알 수 있게 플러그인 이름을 항상 앞에 붙인다. 문구는 플러그인이 준 그대로.
            card_info['plugin'] = plugin
            item = _base(
                f"problem:{card['group_key']}", f"problem:{card['group_key']}", 'problem',
                'error' if severity == 'action_required' else 'notice', 'plugin',
                severity=severity, title=f"{plugin.get('name') or plugin.get('id')} · {plugin.get('title') or ''}",
                detail=[_part('notify.problem.plugin_scope', count=card.get('open_count', 0))]
                if int(card.get('open_count') or 0) > 1 else [],
                raw_detail=plugin.get('detail') or '',
                target={'db_type': card.get('db_type'), 'library_id': card.get('library_id'), 'group_key': card['group_key']},
                actions=card.get('actions') or [],
                created_ms=_server_time_to_ms(card.get('first_seen_at')), updated_ms=_server_time_to_ms(card.get('last_seen_at')),
            )
            item['card'] = card_info
            items.append(item)
            continue
        item = _base(
            f"problem:{card['group_key']}", f"problem:{card['group_key']}", 'problem',
            'error' if severity == 'action_required' else 'notice', 'problem',
            severity=severity, title_key=card.get('title_key'),
            detail=[_part(card.get('detail_key')),
                    _part('notify.problem.library', library=lib or '-') if card.get('code') == 'remote_unavailable'
                    else _part('notify.problem.scope', library=lib or '-', count=card.get('open_count', 0))],
            target={'db_type': card.get('db_type'), 'library_id': card.get('library_id'), 'group_key': card['group_key']},
            actions=card.get('actions') or [],
            created_ms=_server_time_to_ms(card.get('first_seen_at')), updated_ms=_server_time_to_ms(card.get('last_seen_at')),
        )
        item['card'] = card_info
        if card.get('code') == 'remote_unavailable':
            remote.append(item)
        else:
            items.append(item)
    if len(remote) >= 2:
        latest = max(remote, key=lambda i: i['_updated_ms'])
        merged = dict(latest)
        merged.update({
            'id': 'problem:remote_unavailable:multi', 'track_key': 'problem:remote_unavailable:multi',
            'detail': [_part('problems.code.remote_unavailable.detail'), _part('notify.problem.remote_multi', count=len(remote))],
            'target': {'cards': [r['card'] for r in remote]},
            'card': None,
        })
        merged['created_at'] = min((r['created_at'] for r in remote if r['created_at']), default='')
        items.insert(0, merged)
    else:
        items = remote + items
    return items


# ---- 이력 캐시 ----

def _recent_history_rows():
    now = time.time()
    if now - _history_cache['at'] < _HISTORY_CACHE_TTL:
        return _history_cache['rows']
    rows = []
    try:
        from repositories.scanner_queue_repository import ScannerQueueRepository
        rows = ScannerQueueRepository.fetch_recent_history(_HISTORY_FETCH_LIMIT)
    except Exception as e:
        print(f"[Notifications] scan history fetch failed: {e}")
    _history_cache.update(at=now, rows=rows)
    return rows


def _open_problem_cards():
    now = time.time()
    if now - _cards_cache['at'] < _HISTORY_CACHE_TTL:
        return _cards_cache['cards']
    cards = []
    try:
        from services.problem_service import ProblemService
        cards = ProblemService.list_cards()
    except Exception as e:
        print(f"[Notifications] problem cards fetch failed: {e}")
    _cards_cache.update(at=now, cards=cards)
    return cards


# ---- 사용자별 시각 설정: 읽음("마지막으로 알림을 연 시각"), 지우기("마지막으로 지운 시각") ----

def _get_user_ms(cache, setting_key, user_id):
    if not user_id:
        return 0
    now = time.time()
    with _seen_lock:
        cached = cache.get(user_id)
        if cached and now - cached[0] < _SEEN_CACHE_TTL:
            return cached[1]
    value = 0
    try:
        from services.settings_service import SettingsService
        value = int(SettingsService.get_user_value(user_id, setting_key, 0) or 0)
    except (TypeError, ValueError):
        value = 0
    except Exception as e:
        print(f"[Notifications] {setting_key} read failed: {e}")
    with _seen_lock:
        cache[user_id] = (now, value)
    return value


def _set_user_ms(cache, setting_key, user_id, value_ms):
    value_ms = int(value_ms or 0)
    from services.settings_service import SettingsService
    SettingsService.set_user_value(user_id, setting_key, str(value_ms))
    with _seen_lock:
        cache[user_id] = (time.time(), value_ms)
    return value_ms


def get_last_seen_ms(user_id):
    return _get_user_ms(_seen_cache, LAST_SEEN_SETTING_KEY, user_id)


def mark_seen(user_id, seen_ms=None):
    return _set_user_ms(_seen_cache, LAST_SEEN_SETTING_KEY, user_id, seen_ms or _now_ms())


def get_cleared_ms(user_id):
    return _get_user_ms(_cleared_cache, CLEARED_SETTING_KEY, user_id)


def clear_notifications(user_id, is_admin):
    """[지우기] (계획 7장 "결정: 알림 일괄 지우기").

    - 최근 완료: 이 사용자에게서만 숨긴다 (NOTIFICATIONS_CLEARED_MS).
    - 참고(notice) 문제 카드: 관리자일 때만 일괄 '알고 있음' - 카드 상태는 공용이라 모든 관리자에게 적용된다.
    - 진행 중 / 조치 필요 카드: 건드리지 않는다.
    되돌리기에 필요한 값(직전 cleared_ms, 음소거한 group_key)을 돌려준다."""
    previous = get_cleared_ms(user_id)
    cleared = _set_user_ms(_cleared_cache, CLEARED_SETTING_KEY, user_id, _now_ms())
    muted = []
    if is_admin:
        from services.problem_service import ProblemService, CODE_SYSTEM_TASK_FAILED, SEVERITY_NOTICE
        for card in ProblemService.list_cards():
            if card.get('severity') != SEVERITY_NOTICE or card.get('code') == CODE_SYSTEM_TASK_FAILED:
                continue
            if ProblemService.mute_card(card['group_key']):
                muted.append(card['group_key'])
        _cards_cache['at'] = 0.0
    return {'previous_cleared_ms': previous, 'cleared_ms': cleared, 'muted_group_keys': muted}


def undo_clear(user_id, is_admin, previous_cleared_ms, muted_group_keys):
    """[되돌리기]: 지우기 직전 시각으로 돌리고, 그때 음소거한 카드를 다시 보이게 한다."""
    restored = _set_user_ms(_cleared_cache, CLEARED_SETTING_KEY, user_id, int(previous_cleared_ms or 0))
    unmuted = []
    if is_admin:
        from services.problem_service import ProblemService
        for group_key in muted_group_keys or []:
            if isinstance(group_key, str) and group_key:
                ProblemService.unmute_card(group_key)
                unmuted.append(group_key)
        _cards_cache['at'] = 0.0
    return {'cleared_ms': restored, 'unmuted_group_keys': unmuted}


# ---- 조립 ----

_KIND_ORDER = {'problem': 0, 'running': 1, 'recent': 2}
_SEVERITY_ORDER = {'action_required': 0, 'notice': 1}


def build_notifications(*, user_id, is_admin, status, pregen, system_warnings, tuning_db_type,
                        library_name, elapsed_seconds, problem_cards=None, history_rows=None):
    """로그인 사용자 기준 알림 목록. 스캔·문제·시스템 항목은 관리자만, 음성 미리 만들기는 요청자 본인 + 관리자
    (pregen은 이미 tts_pregen_service.activity_for로 걸러진 목록)."""
    items = []
    # 원인 카드(원격 드라이브 연결 끊김)가 열린 카테고리의 '스캔 실패' 기록은 같은 원인이라 따로 보이지 않는다.
    cause_libraries = set()
    if is_admin:
        cards = problem_cards if problem_cards is not None else _open_problem_cards()
        cause_libraries = {(c.get('db_type') or 'general', c.get('library_id')) for c in cards or []
                           if c.get('code') == 'remote_unavailable'}
        items += system_warning_items(system_warnings)
        items += problem_card_items(cards, library_name)
        items += scan_running_items(status, library_name, elapsed_seconds)
        if tuning_db_type:
            items.append(tuning_item(tuning_db_type))
    items += tts_items(pregen)

    if is_admin:
        cutoff = _now_ms() - RECENT_DAYS * 86400 * 1000
        rows = history_rows if history_rows is not None else _recent_history_rows()
        for row in rows:
            if not is_notable_history(row):
                continue
            if row.get('status') == 'failed' and cause_libraries:
                kw = _load_kwargs(row.get('kwargs'))
                lib_id = kw.get('library_id')
                try:
                    lib_id = int(lib_id) if lib_id is not None else None
                except (TypeError, ValueError):
                    pass
                if (kw.get('db_type', 'general'), lib_id) in cause_libraries:
                    continue
            item = scan_history_item(row, library_name)
            if item['_updated_ms'] and item['_updated_ms'] < cutoff:
                continue
            items.append(item)

    def sort_key(item):
        kind = _KIND_ORDER.get(item['kind'], 9)
        if item['kind'] == 'problem':
            return (kind, _SEVERITY_ORDER.get(item.get('severity'), 9), -item['_updated_ms'])
        if item['kind'] == 'running':
            return (kind, 1 if (item.get('progress') or {}).get('pending') else 0, 0)
        return (kind, 0, -item['_updated_ms'])

    # [지우기] 이전에 끝난 최근 완료 항목은 이 사용자에게서 숨긴다 (진행 중·문제 카드는 그대로).
    cleared = get_cleared_ms(user_id)
    if cleared:
        items = [i for i in items if not (i['kind'] == 'recent' and i['_updated_ms'] <= cleared)]

    items.sort(key=sort_key)
    recent_seen = 0
    trimmed = []
    for item in items:
        if item['kind'] == 'recent':
            recent_seen += 1
            if recent_seen > RECENT_MAX_ITEMS:
                continue
        trimmed.append(item)

    last_seen = get_last_seen_ms(user_id)
    for item in trimmed:
        item['read'] = item['kind'] == 'running' or item['_updated_ms'] <= last_seen
        item.pop('_updated_ms', None)
    return trimmed
