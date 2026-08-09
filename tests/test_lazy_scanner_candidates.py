import sqlite3
from unittest.mock import patch

from tools.lazy_scanner import _fetch_lazy_scan_candidates, _open_database_connection


def test_mariadb_connection_does_not_require_local_database_file():
    expected_connection = object()

    with patch('tools.lazy_scanner.database.is_mariadb_mode', return_value=True), patch(
        'tools.lazy_scanner.database.get_connection', return_value=expected_connection
    ) as get_connection, patch('tools.lazy_scanner.os.path.exists') as path_exists:
        connection = _open_database_connection('general')

    assert connection is expected_connection
    get_connection.assert_called_once_with('general', wait_timeout=60.0)
    path_exists.assert_not_called()


def test_sqlite_connection_is_skipped_when_database_file_is_missing():
    with patch('tools.lazy_scanner.database.is_mariadb_mode', return_value=False), patch(
        'tools.lazy_scanner.database.get_db_path', return_value='missing.db'
    ), patch('tools.lazy_scanner.os.path.exists', return_value=False), patch(
        'tools.lazy_scanner.database.get_connection'
    ) as get_connection:
        connection = _open_database_connection('general')

    assert connection is None
    get_connection.assert_not_called()


def test_failed_cover_is_retried_on_next_lazy_scan():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE books (
            id INTEGER,
            file_path TEXT,
            series_name TEXT,
            file_format TEXT,
            cover_image TEXT,
            library_id INTEGER,
            total_pages INTEGER,
            has_offsets INTEGER,
            metadata_locked INTEGER
        )
    """)
    connection.executemany(
        'INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (1, 'missing.pdf', 'Missing', 'pdf', None, 1, 1, 1, 0),
            (2, 'failed.pdf', 'Failed', 'pdf', 'NO_COVER', 1, 1, 1, 0),
            (3, 'ready.pdf', 'Ready', 'pdf', 'ready.webp', 1, 1, 1, 0),
            (4, 'text.txt', 'Text', 'txt', None, 1, 1, 1, 0),
            (5, 'invalid.cbz', 'Invalid', 'cbz', 'NO_COVER', 1, 0, -1, 0),
            (6, 'offset-failed.cbz', 'Offset failed', 'cbz', 'ready.webp', 1, 0, -1, 0),
        ],
    )

    candidates = _fetch_lazy_scan_candidates(connection.cursor())

    assert [book['id'] for book in candidates] == [1, 2, 5]