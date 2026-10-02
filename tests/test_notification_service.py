"""알림센터 공통 항목 어댑터(services/notification_service.py) 테스트 - 알림센터 3단계."""
import json
from datetime import datetime, timedelta

import pytest

from services import notification_service as ns


def _lib_name(db_type, library_id):
    return {('general', 80): '리디(GDS,소설)', ('adult', 3): '성인 만화'}.get((db_type, library_id))


def _elapsed(_value):
    return 42


def _server_time(minutes_ago=0):
    return (datetime.now() - timedelta(minutes=minutes_ago)).strftime('%Y-%m-%d %H:%M:%S')


def _history(id_, task_type='library_scan', status='completed', summary=None, trigger='manual', minutes_ago=1, **kwargs):
    kw = {'db_type': 'general', 'library_id': 80, **kwargs}
    if trigger is not None:
        kw['trigger_type'] = trigger
    return {
        'id': id_, 'task_type': task_type, 'task_key': f'{task_type}_general_80', 'status': status,
        'kwargs': json.dumps(kw), 'started_at': _server_time(minutes_ago + 1), 'finished_at': _server_time(minutes_ago),
        'error_message': 'boom\nTraceback...' if status == 'failed' else None, 'result_summary': summary,
    }


@pytest.fixture(autouse=True)
def no_seen_state(monkeypatch):
    monkeypatch.setattr(ns, 'get_last_seen_ms', lambda _uid: 0)
    monkeypatch.setattr(ns, 'get_cleared_ms', lambda _uid: 0)
    ns._cards_cache.update(at=0.0, cards=[])


def _build(is_admin=True, status=None, pregen=None, warnings=None, rows=None, cards=None, tuning=None):
    return ns.build_notifications(
        user_id=1, is_admin=is_admin, status=status or {}, pregen=pregen or [], system_warnings=warnings or [],
        tuning_db_type=tuning, library_name=_lib_name, elapsed_seconds=_elapsed,
        problem_cards=cards or [], history_rows=rows or [],
    )


# ---- 표시 대상 규칙 ----

@pytest.mark.parametrize('row, expected', [
    (_history(1, trigger='manual', summary={'new_books': 0, 'errors': 0}), True),           # 직접 누른 스캔은 변화 없어도
    (_history(2, trigger='cron', summary={'new_books': 0, 'errors': 0}), False),            # 예약 스캔 + 변화 없음 → 숨김
    (_history(3, trigger='cron', summary={'new_books': 2, 'errors': 0}), True),             # 새 도서
    (_history(4, trigger='webhook', summary={'new_books': 0, 'errors': 1}), True),          # 에러
    (_history(5, task_type='lazy_scan', trigger='lazy'), False),
    (_history(6, task_type='lazy_scan', trigger='lazy', status='failed'), True),
    (_history(7, trigger='cron', status='cancelled'), True),
    (_history(8, task_type='batch_book_scan', trigger=None), True),                         # 예전 행: 사용자 작업
    (_history(9, task_type='library_scan', trigger=None), False),                           # 예전 행: 출처 모름 → 자동
])
def test_is_notable_history(row, expected):
    assert ns.is_notable_history(row) is expected


def test_old_rows_with_is_cron_false_count_as_manual():
    row = _history(1, trigger=None, summary=None)
    kwargs = json.loads(row['kwargs'])
    kwargs['is_cron'] = False
    row['kwargs'] = json.dumps(kwargs)
    assert ns.is_notable_history(row)


# ---- 변환 ----

def test_library_scan_history_item_tone_and_detail():
    new = ns.scan_history_item(_history(1, summary={'new_books': 3, 'errors': 1, 'report_file': 'x.json'}), _lib_name)
    assert new['tone'] == 'new' and new['kind'] == 'recent'
    assert new['title'] == '리디(GDS,소설)'
    keys = [p['key'] for p in new['detail']]
    assert keys == ['notify.scan.status.completed', 'notify.scan.new_books', 'notify.scan.failed_books']
    assert new['detail'][0]['vars']['task'] == {'key': 'notify.scan.task.library_scan'}
    assert new['track_key'] == 'scan:library_scan_general_80'
    assert '+' in new['updated_at'] or new['updated_at'].endswith('Z')

    unchanged = ns.scan_history_item(_history(2, summary={'new_books': 0, 'errors': 0}), _lib_name)
    assert unchanged['tone'] == 'done'
    assert unchanged['detail'][-1]['key'] == 'notify.scan.no_change'

    failed = ns.scan_history_item(_history(3, status='failed'), _lib_name)
    assert failed['tone'] == 'error' and failed['raw_detail'] == 'boom'

    cancelled = ns.scan_history_item(_history(4, status='cancelled'), _lib_name)
    assert cancelled['tone'] == 'muted'


def test_batch_history_item_uses_batch_counts_and_single_title():
    row = _history(1, task_type='batch_book_scan', summary={'books': 1, 'succeeded': 1, 'errors': 0},
                   book_ids=[5], book_title='살인 현장은 구름 위')
    item = ns.scan_history_item(row, _lib_name)
    assert item['title'] == '리디(GDS,소설) · 살인 현장은 구름 위'
    assert [p['key'] for p in item['detail']] == ['notify.scan.status.completed', 'notify.scan.batch_result']
    assert item['target']['book_ids'] == [5]

    many = ns.scan_history_item(_history(2, task_type='batch_book_scan', book_ids=[1, 2, 3]), _lib_name)
    assert many['title'] is None and many['title_key'] == 'notify.scan.selected_books'
    assert many['title_vars'] == {'count': 3, 'library': '리디(GDS,소설)'}


def test_running_and_pending_scans():
    status = {
        'running': {'type': 'library_scan', 'key': 'library_scan_general_80', 'kwargs': {'db_type': 'general', 'library_id': 80},
                    'started_at': _server_time(2), 'stage': '도서 파일 10/20 (50%)'},
        'pending': [{'type': 'lazy_scan', 'key': 'lazy_scan', 'kwargs': {}, 'enqueued_at': _server_time(1)}],
    }
    items = ns.scan_running_items(status, _lib_name, _elapsed)
    assert [i['kind'] for i in items] == ['running', 'running']
    assert items[0]['raw_detail'] == '도서 파일 10/20 (50%)' and items[0]['detail'] == []
    assert items[0]['progress'] == {'elapsed_seconds': 42}
    assert items[1]['progress'] == {'pending': True}
    assert items[1]['title_key'] == 'notify.scan.whole_system'
    assert items[1]['detail'][0]['key'] == 'notify.scan.pending.lazy_scan'


def test_tts_items_running_and_finished():
    pregen = [
        {'id': 7, 'db_type': 'general', 'book_id': 5, 'title': '책', 'status': 'running', 'done': 1, 'total': 3, 'percent': 33},
        {'id': 8, 'db_type': 'adult', 'book_id': 6, 'title': '책2', 'status': 'done', 'finished_ms': ns._now_ms() - 1000, 'done': 3, 'total': 3},
        {'id': 9, 'db_type': 'general', 'book_id': 7, 'title': '책3', 'status': 'failed', 'finished_ms': ns._now_ms() - 2000},
    ]
    running, done, failed = ns.tts_items(pregen)
    assert running['kind'] == 'running' and running['progress']['percent'] == 33.3
    assert running['track_key'] == 'tts:general:7' and done['track_key'] == 'tts:adult:8'
    assert done['tone'] == 'new' and done['adult'] is True and done['detail'][0]['key'] == 'notify.tts.done'
    assert failed['tone'] == 'error'


def test_system_warning_items_keep_per_task_lines():
    warnings = [{'key': 'series_summary:general', 'label': '시리즈 목록 갱신 (일반 도서)', 'message': "(1048, 'x')",
                 'first_failed_at': '2026-10-01T10:00:00+00:00', 'last_failed_at': '2026-10-01T11:00:00+00:00',
                 'fail_count': 3, 'last_ok_at': ''}]
    item = ns.system_warning_items(warnings)[0]
    assert item['kind'] == 'problem' and item['tone'] == 'error' and item['severity'] == 'action_required'
    assert item['title'] == '시리즈 목록 갱신 (일반 도서)'
    assert [p['key'] for p in item['detail']] == ['notify.system.failing', 'notify.system.first_failed', 'notify.system.fail_count']
    assert item['detail'][1]['vars']['when'] == {'time': '2026-10-01T10:00:00+00:00'}
    assert item['raw_detail'] == "(1048, 'x')"


def test_problem_cards_skip_system_card_and_map_severity():
    cards = [
        {'group_key': 'system_task_failed|general|-', 'code': 'system_task_failed', 'severity': 'action_required'},
        {'group_key': 'file_missing|general|80', 'code': 'file_missing', 'severity': 'action_required', 'db_type': 'general',
         'library_id': 80, 'open_count': 12, 'title_key': 'problems.code.file_missing.title',
         'detail_key': 'problems.code.file_missing.detail', 'actions': ['rescan'],
         'first_seen_at': '2026-10-01T10:00:00+00:00', 'last_seen_at': '2026-10-01T11:00:00+00:00'},
        {'group_key': 'file_corrupt|general|80', 'code': 'file_corrupt', 'severity': 'notice', 'db_type': 'general',
         'library_id': 80, 'open_count': 1, 'title_key': 'problems.code.file_corrupt.title',
         'detail_key': 'problems.code.file_corrupt.detail', 'actions': []},
    ]
    items = ns.problem_card_items(cards, _lib_name)
    assert [i['tone'] for i in items] == ['error', 'notice']
    assert items[0]['detail'][1]['vars'] == {'library': '리디(GDS,소설)', 'count': 12}
    assert items[0]['actions'] == ['rescan']


# ---- 조립: audience / 순서 / 기간·개수 / 읽음 ----

def _everything():
    return dict(
        status={'running': {'type': 'library_scan', 'key': 'k', 'kwargs': {'db_type': 'general', 'library_id': 80}, 'started_at': _server_time(1)}},
        pregen=[{'id': 7, 'db_type': 'general', 'book_id': 5, 'title': '책', 'status': 'done', 'finished_ms': ns._now_ms() - 1000}],
        warnings=[{'key': 'w', 'label': 'L', 'first_failed_at': '', 'last_failed_at': '', 'fail_count': 1}],
        rows=[_history(1, summary={'new_books': 1})],
        tuning='general',
    )


def test_general_user_sees_only_own_tts_items():
    items = _build(is_admin=False, **_everything())
    assert [i['source'] for i in items] == ['tts']


def test_admin_order_problems_then_running_then_recent():
    items = _build(is_admin=True, **_everything())
    assert [i['kind'] for i in items] == ['problem', 'running', 'running', 'recent', 'recent']
    assert items[1]['source'] == 'scan' and items[2]['id'] == 'system:tuning:general'
    # 최근 완료는 최신순: TTS(1초 전) → 스캔(1분 전)
    assert [i['source'] for i in items[3:]] == ['tts', 'scan']


def test_recent_window_and_limit():
    rows = [_history(i, summary={'new_books': 1}, minutes_ago=i) for i in range(1, 61)]
    rows.append(_history(999, summary={'new_books': 1}, minutes_ago=8 * 24 * 60))  # 8일 전
    items = _build(rows=rows)
    assert len(items) == ns.RECENT_MAX_ITEMS
    assert 'scan:history:999' not in {i['id'] for i in items}


def test_read_flags_follow_last_seen(monkeypatch):
    rows = [_history(1, summary={'new_books': 1}, minutes_ago=10), _history(2, summary={'new_books': 1}, minutes_ago=1)]
    seen_ms = ns._now_ms() - 5 * 60 * 1000
    monkeypatch.setattr(ns, 'get_last_seen_ms', lambda _uid: seen_ms)
    items = {i['id']: i for i in _build(rows=rows, status={'running': {'type': 'library_scan', 'key': 'k', 'kwargs': {}}})}
    assert items['scan:history:1']['read'] is True
    assert items['scan:history:2']['read'] is False
    assert items['scan:running:k']['read'] is True  # 진행 중 항목은 '새 알림'으로 세지 않는다


def test_mark_seen_round_trip(monkeypatch):
    store = {}

    class FakeSettings:
        @staticmethod
        def get_user_value(uid, key, default=None):
            return store.get((uid, key), default)

        @staticmethod
        def set_user_value(uid, key, value):
            store[(uid, key)] = value

    import services.settings_service as settings_module
    monkeypatch.setattr(settings_module, 'SettingsService', FakeSettings)
    monkeypatch.undo()  # autouse fixture의 get_last_seen_ms 대체를 풀고 실제 함수를 쓴다
    monkeypatch.setattr(settings_module, 'SettingsService', FakeSettings)
    ns._seen_cache.clear()
    assert ns.get_last_seen_ms(5) == 0
    seen = ns.mark_seen(5, 1234)
    assert seen == 1234 and store[(5, ns.LAST_SEEN_SETTING_KEY)] == '1234'
    ns._seen_cache.clear()
    assert ns.get_last_seen_ms(5) == 1234


def _remote_card(lib):
    return {'group_key': f'remote_unavailable|general|{lib}', 'code': 'remote_unavailable', 'severity': 'action_required',
            'db_type': 'general', 'library_id': lib, 'open_count': 1, 'title_key': 'problems.code.remote_unavailable.title',
            'detail_key': 'problems.code.remote_unavailable.detail', 'actions': ['rescan'],
            'first_seen_at': '2026-10-01T10:00:00+00:00', 'last_seen_at': '2026-10-01T11:00:00+00:00'}


def test_single_remote_card_stays_per_category():
    items = ns.problem_card_items([_remote_card(80)], _lib_name)
    assert [i['id'] for i in items] == ['problem:remote_unavailable|general|80']
    assert items[0]['card']['library'] == '리디(GDS,소설)'


def test_several_disconnected_categories_fold_into_one_item():
    other = {'group_key': 'file_missing|general|80', 'code': 'file_missing', 'severity': 'notice', 'db_type': 'general',
             'library_id': 80, 'open_count': 2, 'title_key': 't', 'detail_key': 'd', 'actions': ['rescan']}
    items = ns.problem_card_items([_remote_card(80), _remote_card(81), other], _lib_name)
    assert [i['id'] for i in items] == ['problem:remote_unavailable:multi', 'problem:file_missing|general|80']
    multi = items[0]
    assert multi['card'] is None and [c['library_id'] for c in multi['target']['cards']] == [80, 81]
    assert multi['detail'][1] == {'key': 'notify.problem.remote_multi', 'vars': {'count': 2}}


def test_failed_scan_is_hidden_while_its_cause_card_is_open():
    rows = [_history(1, status='failed'), _history(2, status='failed', library_id=81)]
    rows[1]['kwargs'] = json.dumps({'db_type': 'general', 'library_id': 81, 'trigger_type': 'manual'})
    items = _build(rows=rows, cards=[_remote_card(80)])
    ids = [i['id'] for i in items]
    assert 'scan:history:1' not in ids          # 같은 카테고리 실패 → 원인 카드로 대신
    assert 'scan:history:2' in ids              # 다른 카테고리 실패는 그대로
    remote = next(i for i in items if i['id'] == 'problem:remote_unavailable|general|80')
    assert remote['detail'][1] == {'key': 'notify.problem.library', 'vars': {'library': '리디(GDS,소설)'}}


# ---- [지우기] (계획 7장 "결정: 알림 일괄 지우기") ----

def test_clear_hides_only_recent_items_finished_before_cleared(monkeypatch):
    rows = [_history(1, summary={'new_books': 1}, minutes_ago=10), _history(2, summary={'new_books': 1}, minutes_ago=1)]
    cleared_ms = ns._now_ms() - 5 * 60 * 1000
    monkeypatch.setattr(ns, 'get_cleared_ms', lambda _uid: cleared_ms)
    notice = {'group_key': 'file_corrupt|general|80', 'code': 'file_corrupt', 'severity': 'notice', 'db_type': 'general',
              'library_id': 80, 'open_count': 1, 'title_key': 't', 'detail_key': 'd', 'actions': []}
    items = _build(rows=rows, cards=[_remote_card(80), notice],
                   status={'running': {'type': 'library_scan', 'key': 'k', 'kwargs': {}}},
                   warnings=[{'key': 'w', 'label': 'L', 'first_failed_at': '', 'last_failed_at': '', 'fail_count': 1}])
    ids = [i['id'] for i in items]
    assert 'scan:history:1' not in ids          # 지우기 전에 끝남 → 숨김
    assert 'scan:history:2' in ids              # 지운 뒤에 끝남 → 보임
    assert 'scan:running:k' in ids              # 진행 중은 그대로
    assert 'system:warning:w' in ids            # 조치 필요(시스템)는 그대로
    assert 'problem:remote_unavailable|general|80' in ids
    assert 'problem:file_corrupt|general|80' in ids  # 참고 카드는 날짜가 아니라 음소거로 사라진다


def test_general_user_clear_hides_own_finished_tts(monkeypatch):
    monkeypatch.setattr(ns, 'get_cleared_ms', lambda _uid: ns._now_ms())
    items = _build(is_admin=False, **_everything())
    assert items == []


class _FakeSettings:
    store = {}

    @classmethod
    def get_user_value(cls, uid, key, default=None):
        return cls.store.get((uid, key), default)

    @classmethod
    def set_user_value(cls, uid, key, value):
        cls.store[(uid, key)] = value


@pytest.fixture
def clear_env(monkeypatch):
    import services.settings_service as settings_module
    import services.problem_service as problem_module
    monkeypatch.undo()  # autouse의 get_cleared_ms 대체를 풀고 실제 함수를 쓴다
    _FakeSettings.store = {}
    monkeypatch.setattr(settings_module, 'SettingsService', _FakeSettings)
    ns._cleared_cache.clear()
    cards = [
        {'group_key': 'system_task_failed|general|-', 'code': 'system_task_failed', 'severity': 'action_required'},
        {'group_key': 'remote_unavailable|general|80', 'code': 'remote_unavailable', 'severity': 'action_required'},
        {'group_key': 'file_corrupt|general|80', 'code': 'file_corrupt', 'severity': 'notice'},
        {'group_key': 'file_missing|general|81', 'code': 'file_missing', 'severity': 'notice'},
    ]
    calls = {'mute': [], 'unmute': []}
    monkeypatch.setattr(problem_module.ProblemService, 'list_cards', staticmethod(lambda include_muted=False: cards))
    monkeypatch.setattr(problem_module.ProblemService, 'mute_card', staticmethod(lambda gk: calls['mute'].append(gk) or True))
    monkeypatch.setattr(problem_module.ProblemService, 'unmute_card', staticmethod(lambda gk: calls['unmute'].append(gk) or True))
    yield calls
    ns._cleared_cache.clear()


def test_admin_clear_mutes_only_notice_cards_and_undo_restores(clear_env):
    ns._set_user_ms(ns._cleared_cache, ns.CLEARED_SETTING_KEY, 1, 1000)
    result = ns.clear_notifications(1, is_admin=True)
    assert result['previous_cleared_ms'] == 1000 and result['cleared_ms'] > 1000
    assert result['muted_group_keys'] == ['file_corrupt|general|80', 'file_missing|general|81']
    assert clear_env['mute'] == result['muted_group_keys']   # 조치 필요·시스템 카드는 건드리지 않음
    assert ns.get_cleared_ms(1) == result['cleared_ms']

    undo = ns.undo_clear(1, True, result['previous_cleared_ms'], result['muted_group_keys'])
    assert undo['cleared_ms'] == 1000 and ns.get_cleared_ms(1) == 1000
    assert clear_env['unmute'] == result['muted_group_keys']


def test_general_user_clear_never_mutes_shared_cards(clear_env):
    result = ns.clear_notifications(2, is_admin=False)
    assert result['muted_group_keys'] == [] and clear_env['mute'] == []
    assert _FakeSettings.store[(2, ns.CLEARED_SETTING_KEY)] == str(result['cleared_ms'])
    ns.undo_clear(2, False, 0, ['file_corrupt|general|80'])  # 일반 사용자는 되돌리기로도 카드 상태를 못 바꾼다
    assert clear_env['unmute'] == [] and ns.get_cleared_ms(2) == 0


def test_scans_that_failed_because_the_root_was_unreachable_are_not_shown_as_scan_failures():
    # 원격 드라이브 연결 끊김 카드(순단 유예 포함)가 대신 알리므로, 순단마다 '스캔 실패'가 쌓이지 않는다
    blip = _history(1, trigger='cron', status='failed')
    blip['error_message'] = "[root_unreachable] 스캔 대상 경로 접근 실패 (HDD/NAS Wake-up 실패): '/mnt/x' (사유: ...)"
    other = _history(2, trigger='cron', status='failed')
    other['error_message'] = 'KeyError: boom'
    assert ns.is_notable_history(blip) is False
    assert ns.is_notable_history(other) is True
