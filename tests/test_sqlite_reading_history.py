import sqlite3
from contextlib import contextmanager

import pytest

from repositories.sqlite import reading_progress_repository as repository_module

Repository = repository_module.ReadingProgressRepository


@pytest.fixture
def connection(monkeypatch):
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY, library_id INTEGER, title TEXT, title_alias TEXT, series_name TEXT,
            series_alias TEXT, cover_image TEXT, cover_updated_at TEXT, file_format TEXT,
            total_pages INTEGER, is_deleted INTEGER DEFAULT 0, metadata_locked INTEGER DEFAULT 0
        );
        CREATE TABLE user_progress (
            user_id INTEGER, book_id INTEGER, pages_read INTEGER, last_read_at TEXT, is_completed INTEGER DEFAULT 0
        );
        CREATE TABLE user_category_permissions (user_id INTEGER, library_id INTEGER, has_access INTEGER);
        CREATE TABLE user_favorites (user_id INTEGER, book_id INTEGER);
        INSERT INTO user_category_permissions VALUES (7, 1, 1);
    """)

    @contextmanager
    def fake_connection(_db_type):
        yield conn

    monkeypatch.setattr(repository_module.database, 'connection', fake_connection)
    yield conn
    conn.close()


def _book(conn, book_id, series, total_pages=10, deleted=0):
    conn.execute(
        "INSERT INTO books (id, library_id, title, series_name, total_pages, is_deleted, file_format) "
        "VALUES (?, 1, ?, ?, ?, ?, 'cbz')",
        (book_id, f'title {book_id}', series, total_pages, deleted),
    )


def _read(conn, book_id, when, pages=5, completed=0):
    conn.execute(
        "INSERT INTO user_progress (user_id, book_id, pages_read, last_read_at, is_completed) VALUES (7, ?, ?, ?, ?)",
        (book_id, pages, when, completed),
    )


def _history(limit=30, hide_completed=False):
    return Repository.fetch_reading_history('general', 7, limit, hide_completed)


def test_one_row_per_series_newest_first_with_history_count(connection):
    for book_id in (1, 2):
        _book(connection, book_id, 'A')
    _book(connection, 3, 'B')
    _read(connection, 1, '2026-01-01 10:00:00')
    _read(connection, 2, '2026-01-03 10:00:00')  # 시리즈 A의 최신 권
    _read(connection, 3, '2026-01-02 10:00:00')

    rows = _history()

    assert [row['id'] for row in rows] == [2, 3]
    assert rows[0]['history_book_count'] == 2


def test_limit_is_respected(connection):
    for book_id in range(1, 6):
        _book(connection, book_id, f'S{book_id}')
        _read(connection, book_id, f'2026-01-0{book_id} 10:00:00')

    assert [row['id'] for row in _history(limit=2)] == [5, 4]


def test_unfinished_siblings_flag_follows_series_state(connection):
    _book(connection, 1, 'A')
    _book(connection, 2, 'A')  # 읽은 적 없는 형제 권
    _book(connection, 3, 'B')
    _book(connection, 4, 'B')
    _read(connection, 1, '2026-01-01 10:00:00', pages=10, completed=1)
    _read(connection, 3, '2026-01-02 10:00:00', pages=10, completed=1)
    _read(connection, 4, '2026-01-03 10:00:00', pages=10, completed=1)  # B는 전부 완독

    flags = {row['id']: row['has_unfinished_siblings'] for row in _history()}

    assert flags == {4: 0, 1: 1}


def test_deleted_sibling_does_not_count_as_unfinished(connection):
    _book(connection, 1, 'A')
    _book(connection, 2, 'A', deleted=1)
    _read(connection, 1, '2026-01-01 10:00:00', pages=10, completed=1)

    assert _history()[0]['has_unfinished_siblings'] == 0


def test_standalone_book_uses_its_own_progress(connection):
    _book(connection, 1, '')
    _book(connection, 2, None)
    _read(connection, 1, '2026-01-01 10:00:00', pages=5)  # 읽는 중
    _read(connection, 2, '2026-01-02 10:00:00', pages=10, completed=1)  # 완독

    flags = {row['id']: row['has_unfinished_siblings'] for row in _history()}

    assert flags == {1: 1, 2: 0}


def test_hide_completed_keeps_only_series_with_unfinished_books(connection):
    _book(connection, 1, 'A')
    _book(connection, 2, 'A')  # 안 읽은 권이 남은 시리즈
    _book(connection, 3, 'B')  # 전부 완독한 시리즈
    _book(connection, 4, '')   # 완독한 단행본
    _read(connection, 1, '2026-01-01 10:00:00', pages=10, completed=1)
    _read(connection, 3, '2026-01-02 10:00:00', pages=10, completed=1)
    _read(connection, 4, '2026-01-03 10:00:00', pages=10, completed=1)

    assert [row['id'] for row in _history(hide_completed=True)] == [1]
    assert [row['id'] for row in _history(hide_completed=False)] == [4, 3, 1]


def test_hide_completed_fills_the_limit_across_batches(connection):
    # 완독 시리즈 60개(배치 50건 초과) 사이에 안 읽은 권이 남은 시리즈가 섞여 있다.
    for index in range(60):
        book_id = index + 1
        _book(connection, book_id, f'done{index}')
        _read(connection, book_id, f'2026-02-{(index % 28) + 1:02d} 10:00:00', pages=10, completed=1)
    for index in range(3):
        book_id = 100 + index
        _book(connection, book_id, f'open{index}')
        _read(connection, book_id, f'2026-01-0{index + 1} 10:00:00', pages=3)

    ids = [row['id'] for row in _history(limit=3, hide_completed=True)]

    assert sorted(ids) == [100, 101, 102]
