import sqlite3
from fnmatch import fnmatchcase
from unittest.mock import patch

from repositories.sqlite.reading_progress_repository import ReadingProgressRepository
from services.reading_progress_service import ReadingProgressService


def test_delete_user_progress_by_series_is_scoped_to_user_and_series(tmp_path, monkeypatch):
    db_path = tmp_path / "progress.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            series_name TEXT,
            library_id INTEGER,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE user_progress (book_id INTEGER, user_id INTEGER);
        CREATE TABLE user_reading_log (book_id INTEGER, user_id INTEGER);

        INSERT INTO books (id, series_name, library_id) VALUES
            (1, 'Target', 10),
            (2, 'Target', 10),
            (3, 'Other', 10);
        INSERT INTO user_progress (book_id, user_id) VALUES
            (1, 7), (2, 7), (3, 7), (1, 8);
        INSERT INTO user_reading_log (book_id, user_id) VALUES
            (1, 7), (2, 7), (3, 7), (1, 8);
        """
    )
    conn.commit()
    conn.close()

    def get_connection(_db_type):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(
        "repositories.sqlite.reading_progress_repository.database.get_connection",
        get_connection,
    )

    deleted_ids = ReadingProgressRepository.delete_user_progress_by_series(
        "general", "Target", 10, 7
    )

    conn = get_connection("general")
    progress_rows = conn.execute(
        "SELECT book_id, user_id FROM user_progress ORDER BY user_id, book_id"
    ).fetchall()
    log_rows = conn.execute(
        "SELECT book_id, user_id FROM user_reading_log ORDER BY user_id, book_id"
    ).fetchall()
    conn.close()

    assert deleted_ids == [1, 2]
    assert [tuple(row) for row in progress_rows] == [(3, 7), (1, 8)]
    assert [tuple(row) for row in log_rows] == [(3, 7), (1, 8)]


def test_mark_unread_invalidates_all_user_history_cache_variants():
    with patch.object(
        ReadingProgressRepository,
        'delete_user_progress_by_series',
        return_value=[1, 2],
    ), patch(
        'utils.redis_helper.redis_delete_pattern',
    ) as delete_pattern, patch(
        'services.reading_progress_service.get_redis_client',
        return_value=None,
    ):
        affected_count = ReadingProgressService.mark_unread(
            'general',
            2,
            user_id=7,
            series_name='Target',
            library_id=10,
        )

    assert affected_count == 2
    delete_pattern.assert_called_once_with('cache:history*:general:7:*')
    assert fnmatchcase('cache:history:v8:general:7:30:0', delete_pattern.call_args.args[0])
