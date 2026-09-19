import inspect
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from flask import Flask

from api.routes import library_routes
from api.routes.library_routes import library_bp
from api.routes.media_library_routes import media_library_routes_bp
from repositories.mariadb import category_repository as mariadb_repository
from repositories.sqlite import category_repository as sqlite_repository
from services import db_migration_service
from services.category_service import CategoryService
from services.db_migration_service import (
    _SCHEMA_SQL,
    _seed_library_kinds,
    auto_migrate_schema,
    parse_schema_columns,
)
from tools import import_category
from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA


class NonClosingConnection:
    """저장소가 conn.close()를 부르는 인메모리 DB를 테스트 동안 유지하는 래퍼."""

    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        pass


def _new_database(db_type='general'):
    connection = sqlite3.connect(':memory:', check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    _seed_library_kinds(connection, connection.cursor(), db_type)
    return connection


@pytest.fixture
def db(monkeypatch):
    connection = _new_database('general')
    wrapper = NonClosingConnection(connection)

    @contextmanager
    def fake_connection(_db_type):
        yield wrapper

    monkeypatch.setattr(sqlite_repository.database, 'get_connection', lambda *_a, **_k: wrapper)
    monkeypatch.setattr(sqlite_repository.database, 'connection', fake_connection)
    monkeypatch.setattr(
        'services.series_service.SeriesService.get_library_totals_bulk', lambda _db_type: {}
    )
    yield connection
    connection.close()


def _add_library(name='Lib', content_kind=None, db_type='general'):
    return CategoryService.add_library(db_type, name, f'/books/{name}', content_kind=content_kind)


def _kind_of(connection, library_id):
    return connection.execute('SELECT content_kind FROM libraries WHERE id = ?', (library_id,)).fetchone()[0]


# ── 스키마 / 마이그레이션 ───────────────────────────────────────────────────────────────

def test_existing_libraries_become_unspecified_after_migration():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE libraries (id INTEGER PRIMARY KEY, name TEXT, physical_path TEXT)')
    connection.execute("INSERT INTO libraries (name, physical_path) VALUES ('Legacy', '/legacy')")

    auto_migrate_schema(connection, _SCHEMA_SQL)

    row = connection.execute('SELECT content_kind FROM libraries WHERE name = ?', ('Legacy',)).fetchone()
    assert row['content_kind'] == 'unspecified'
    connection.close()


def test_schema_definitions_cover_both_engines():
    assert dict(parse_schema_columns(_SCHEMA_SQL)['libraries'])['content_kind'] == "TEXT NOT NULL DEFAULT 'unspecified'"
    assert 'code' in dict(parse_schema_columns(_SCHEMA_SQL)['library_kinds'])
    assert 'CREATE TABLE IF NOT EXISTS library_kinds' in MARIADB_CENTRAL_SCHEMA
    assert "content_kind VARCHAR(24) NOT NULL DEFAULT 'unspecified'" in MARIADB_CENTRAL_SCHEMA
    safety_net = inspect.getsource(db_migration_service._ensure_mariadb_columns)
    for database_name in ('media_general', 'media_adult', 'media_audiobook', 'media_video'):
        assert f"('{database_name}', 'libraries', 'content_kind'" in safety_net


def test_book_sessions_get_the_four_builtin_kinds_and_other_sessions_start_empty():
    general = _new_database('general')
    audiobook = _new_database('audiobook')

    rows = general.execute('SELECT code, name, is_builtin FROM library_kinds ORDER BY sort_order').fetchall()
    assert [(r['code'], r['name'], r['is_builtin']) for r in rows] == [
        ('manga', '만화', 1), ('novel', '소설', 1), ('book', '도서', 1), ('magazine', '잡지', 1),
    ]
    assert audiobook.execute('SELECT COUNT(*) FROM library_kinds').fetchone()[0] == 0


def test_seeding_is_idempotent_and_keeps_names_the_admin_changed():
    connection = _new_database('general')
    connection.execute("UPDATE library_kinds SET name = '코믹스' WHERE code = 'manga'")
    connection.commit()

    _seed_library_kinds(connection, connection.cursor(), 'general')

    assert connection.execute('SELECT COUNT(*) FROM library_kinds').fetchone()[0] == 4
    assert connection.execute("SELECT name FROM library_kinds WHERE code = 'manga'").fetchone()[0] == '코믹스'


def test_seeding_avoids_a_name_collision_with_an_admin_created_kind():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA_SQL)
    connection.execute("INSERT INTO library_kinds (code, name, is_builtin) VALUES ('comic', '만화', 0)")

    _seed_library_kinds(connection, connection.cursor(), 'general')

    assert connection.execute("SELECT name FROM library_kinds WHERE code = 'manga'").fetchone()[0] == '만화 (manga)'


# ── 저장소 / 서비스 ─────────────────────────────────────────────────────────────────────

def test_a_library_created_without_a_kind_is_unspecified(db):
    library_id = _add_library('NoKind')

    assert _kind_of(db, library_id) == 'unspecified'


def test_a_library_can_be_created_with_a_known_kind(db):
    library_id = _add_library('Comics', content_kind='manga')

    assert _kind_of(db, library_id) == 'manga'


def test_an_unknown_kind_is_rejected(db):
    with pytest.raises(ValueError, match='알 수 없는 속성'):
        _add_library('Bad', content_kind='nope')


def test_editing_without_a_kind_keeps_the_existing_one(db):
    library_id = _add_library('Keep', content_kind='book')

    CategoryService.edit_library('general', library_id, 'Keep renamed', '/books/keep')

    assert _kind_of(db, library_id) == 'book'


def test_editing_can_change_or_clear_the_kind(db):
    library_id = _add_library('Change', content_kind='book')

    CategoryService.edit_library('general', library_id, 'Change', '/books/c', content_kind='magazine')
    assert _kind_of(db, library_id) == 'magazine'
    CategoryService.edit_library('general', library_id, 'Change', '/books/c', content_kind='')
    assert _kind_of(db, library_id) == 'unspecified'


def test_libraries_list_carries_the_kind_code_and_display_name(db):
    _add_library('Comics', content_kind='manga')
    _add_library('Plain')

    libraries = {lib['name']: lib for lib in CategoryService.get_libraries('general')}

    assert libraries['Comics']['content_kind'] == 'manga'
    assert libraries['Comics']['content_kind_name'] == '만화'
    assert libraries['Plain']['content_kind'] == 'unspecified'
    assert libraries['Plain']['content_kind_name'] == ''


def test_admin_can_add_rename_and_delete_a_custom_kind(db):
    assert CategoryService.add_library_kind('general', 'Webtoon', ' 웹툰 ') == 'webtoon'
    CategoryService.edit_library_kind('general', 'webtoon', '웹툰(세로)')

    names = {kind['code']: kind['name'] for kind in CategoryService.get_library_kinds('general')}
    assert names['webtoon'] == '웹툰(세로)'
    CategoryService.delete_library_kind('general', 'webtoon')
    assert 'webtoon' not in {kind['code'] for kind in CategoryService.get_library_kinds('general')}


@pytest.mark.parametrize('code', ['', '1abc', 'Has Space', 'x' * 25, 'unspecified', '한글'])
def test_invalid_kind_codes_are_rejected(db, code):
    with pytest.raises(ValueError):
        CategoryService.add_library_kind('general', code, '이름')


def test_duplicate_kind_code_or_name_is_rejected(db):
    with pytest.raises(ValueError, match='같은 코드'):
        CategoryService.add_library_kind('general', 'manga', '다른 이름')
    with pytest.raises(ValueError, match='같은 이름'):
        CategoryService.add_library_kind('general', 'comics', '만화')
    with pytest.raises(ValueError, match='같은 이름'):
        CategoryService.edit_library_kind('general', 'novel', '도서')


def test_kind_name_length_is_limited(db):
    with pytest.raises(ValueError, match='25자'):
        CategoryService.add_library_kind('general', 'long', '가' * 26)


def test_builtin_kinds_cannot_be_deleted_but_can_be_renamed(db):
    with pytest.raises(ValueError, match='기본 속성'):
        CategoryService.delete_library_kind('general', 'manga')

    CategoryService.edit_library_kind('general', 'manga', '코믹스')

    assert {k['code']: k['name'] for k in CategoryService.get_library_kinds('general')}['manga'] == '코믹스'


def test_a_kind_in_use_cannot_be_deleted_and_the_message_says_how_many(db):
    CategoryService.add_library_kind('general', 'webtoon', '웹툰')
    _add_library('One', content_kind='webtoon')
    _add_library('Two', content_kind='webtoon')

    with pytest.raises(ValueError, match='2개 카테고리'):
        CategoryService.delete_library_kind('general', 'webtoon')


def test_deleting_or_renaming_an_unknown_kind_reports_not_found(db):
    with pytest.raises(ValueError, match='찾을 수 없습니다'):
        CategoryService.delete_library_kind('general', 'ghost')
    with pytest.raises(ValueError, match='찾을 수 없습니다'):
        CategoryService.edit_library_kind('general', 'ghost', '유령')


def test_ensure_library_kind_creates_a_missing_kind_and_never_duplicates(db):
    assert CategoryService.ensure_library_kind('general', 'webtoon', '웹툰') == 'webtoon'
    assert CategoryService.ensure_library_kind('general', 'webtoon', '다른 이름') == 'webtoon'

    kinds = [k for k in CategoryService.get_library_kinds('general') if k['code'] == 'webtoon']
    assert len(kinds) == 1 and kinds[0]['name'] == '웹툰' and kinds[0]['is_builtin'] == 0


def test_ensure_library_kind_handles_name_collisions_and_bad_codes(db):
    assert CategoryService.ensure_library_kind('general', 'comics', '만화') == 'comics'
    names = {k['code']: k['name'] for k in CategoryService.get_library_kinds('general')}
    assert names['comics'] == '만화 (comics)'

    assert CategoryService.ensure_library_kind('general', 'Bad Code!', '이름') == 'unspecified'
    assert CategoryService.ensure_library_kind('general', '', '이름') == 'unspecified'
    assert CategoryService.ensure_library_kind('general', 'unspecified', '이름') == 'unspecified'


# ── 가져오기 도구 ───────────────────────────────────────────────────────────────────────

def test_import_resolves_known_missing_and_invalid_kinds(db):
    cursor = db.cursor()

    assert import_category.resolve_content_kind(cursor, {'content_kind': 'manga'}) == 'manga'
    assert import_category.resolve_content_kind(cursor, {'content_kind': 'webtoon', 'content_kind_name': '웹툰'}) == 'webtoon'
    assert db.execute("SELECT name FROM library_kinds WHERE code = 'webtoon'").fetchone()[0] == '웹툰'
    assert import_category.resolve_content_kind(cursor, {'content_kind': 'Bad Code'}) == 'unspecified'
    assert import_category.resolve_content_kind(cursor, {}) == 'unspecified'


def test_import_falls_back_to_unspecified_when_the_table_is_missing():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row

    assert import_category.resolve_content_kind(connection.cursor(), {'content_kind': 'webtoon'}) == 'unspecified'


# ── MariaDB (가짜 커서: 플레이스홀더/파라미터 순서만 확인) ───────────────────────────────

class FakeCursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.rowcount = 1

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows=()):
        self.cursor_instance = FakeCursor(rows)
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


def test_mariadb_repository_uses_its_own_placeholders_and_keeps_kind_on_edit():
    connection = FakeConnection()
    with patch.object(mariadb_repository.database, 'get_connection', return_value=connection):
        mariadb_repository.CategoryRepository.add_library_kind('general', 'webtoon', '웹툰')
        mariadb_repository.CategoryRepository.edit_library(
            'general', 3, 'n', '/p', 0, None, 'fa-book', '#fff', 0, None, None, None, '4:3', 0, None
        )

    add_query, add_params = connection.cursor_instance.calls[0]
    edit_query, edit_params = connection.cursor_instance.calls[1]
    assert '%s' in add_query and '?' not in add_query
    assert 'FROM library_kinds) kinds' in add_query  # MariaDB는 같은 테이블 서브쿼리에 파생 테이블이 필요하다
    assert add_params == ('webtoon', '웹툰')
    assert 'content_kind = COALESCE(%s, content_kind)' in edit_query
    assert edit_params[-2:] == (None, 3)  # content_kind=None(유지), library_id


# ── 라우트 ──────────────────────────────────────────────────────────────────────────────

def _client(role='admin'):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-library-kinds')
    app.register_blueprint(library_bp)
    app.register_blueprint(media_library_routes_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['role'] = role
        session['is_default_password'] = 0
    return client


def test_kind_management_routes_require_an_admin(db):
    client = _client(role='user')

    for action in ('add', 'edit', 'delete'):
        response = client.post(f'/api/media/library-kinds/{action}', data={'type': 'general', 'code': 'x', 'name': 'x'})
        assert response.status_code == 403


def test_admin_kind_routes_add_rename_and_delete(db):
    client = _client()

    added = client.post('/api/media/library-kinds/add', data={'type': 'general', 'code': 'webtoon', 'name': '웹툰'})
    duplicate = client.post('/api/media/library-kinds/add', data={'type': 'general', 'code': 'webtoon', 'name': '다른'})
    renamed = client.post('/api/media/library-kinds/edit', data={'type': 'general', 'code': 'webtoon', 'name': '웹툰2'})
    builtin = client.post('/api/media/library-kinds/delete', data={'type': 'general', 'code': 'manga'})
    deleted = client.post('/api/media/library-kinds/delete', data={'type': 'general', 'code': 'webtoon'})

    assert added.get_json()['success'] is True
    assert duplicate.status_code == 400 and '이미' in duplicate.get_json()['error']
    assert renamed.get_json()['success'] is True
    assert builtin.status_code == 400 and '기본 속성' in builtin.get_json()['error']
    assert deleted.get_json()['success'] is True


def test_libraries_response_includes_kinds_for_plugins(db):
    _add_library('Comics', content_kind='manga')

    body = _client().get('/api/media/libraries?type=general').get_json()

    assert body['success'] is True
    assert [k['code'] for k in body['kinds']] == ['manga', 'novel', 'book', 'magazine']
    assert body['libraries'][0]['content_kind'] == 'manga'


def test_libraries_response_survives_a_failing_kind_lookup(db):
    """속성 테이블이 아직 없는 DB에서도 카테고리 목록이 500이 되면 안 된다."""
    _add_library('Comics')

    with patch('api.routes.media_library_routes.CategoryService.get_library_kinds', side_effect=RuntimeError('no table')):
        response = _client().get('/api/media/libraries?type=general')

    assert response.status_code == 200
    assert response.get_json()['kinds'] == []
    assert response.get_json()['libraries'][0]['name'] == 'Comics'


def _post_library(client, endpoint, data):
    with patch.object(library_routes, 'validate_library_paths', side_effect=lambda paths, **_k: (
        [p.strip() for p in str(paths).splitlines() if p.strip()], None
    )), patch.object(library_routes, 'detect_library_media_mismatch', return_value=None), \
            patch.object(library_routes, 'SchedulerService'), \
            patch('services.scanner_queue.scanner_queue.enqueue', return_value=True):
        return client.post(endpoint, data=data)


def test_creating_a_library_without_a_kind_still_works_for_existing_callers(db):
    response = _post_library(_client(), '/api/media/libraries/add', {
        'type': 'general', 'name': 'Legacy Caller', 'physical_path': '/books/legacy',
    })

    assert response.status_code == 200, response.get_json()
    assert db.execute("SELECT content_kind FROM libraries WHERE name = 'Legacy Caller'").fetchone()[0] == 'unspecified'


def test_creating_a_library_with_an_unknown_kind_returns_400(db):
    response = _post_library(_client(), '/api/media/libraries/add', {
        'type': 'general', 'name': 'Bad Kind', 'physical_path': '/books/bad', 'content_kind': 'nope',
    })

    assert response.status_code == 400
    assert '알 수 없는 속성' in response.get_json()['error']


def test_editing_without_the_kind_field_keeps_it_and_with_the_field_changes_it(db):
    library_id = _add_library('Editable', content_kind='book')
    client = _client()
    base = {'type': 'general', 'id': str(library_id), 'name': 'Editable', 'physical_path': '/books/Editable'}

    kept = _post_library(client, '/api/media/libraries/edit', dict(base))
    changed = _post_library(client, '/api/media/libraries/edit', {**base, 'content_kind': 'magazine'})

    assert kept.status_code == 200, kept.get_json()
    assert changed.status_code == 200, changed.get_json()
    assert _kind_of(db, library_id) == 'magazine'
