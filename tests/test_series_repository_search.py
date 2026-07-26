import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories.sqlite.series_repository import SeriesRepository


class SeriesRepositorySearchTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'series.db'
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                series_name TEXT,
                title TEXT,
                author TEXT,
                file_path TEXT,
                file_format TEXT,
                cover_image TEXT,
                cover_updated_at TEXT,
                created_at TEXT,
                genre TEXT,
                tags TEXT,
                library_id INTEGER,
                metadata_locked INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE user_favorites (user_id INTEGER, book_id INTEGER);
            CREATE TABLE user_category_permissions (
                user_id INTEGER,
                library_id INTEGER,
                has_access INTEGER
            );
            INSERT INTO books (
                id, series_name, title, author, file_path, file_format, library_id
            ) VALUES (
                1, '예상과 다른 시리즈', '[연재] 도굴왕 001', '산지직송',
                '/books/도굴왕/001.zip', 'zip', 10
            );
            """
        )
        conn.commit()
        conn.close()

        def connect(_db_type):
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        self.connection_patch = patch(
            'repositories.sqlite.series_repository.database.get_connection',
            connect,
        )
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def test_search_matches_book_title(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='도굴왕', user_id=1, role='admin'
        )

        self.assertEqual([row['id'] for row in rows], [1])


if __name__ == '__main__':
    unittest.main()