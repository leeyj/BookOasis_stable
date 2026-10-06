import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories.sqlite.series_repository import SeriesRepository


class SeriesFilterModeTest(unittest.TestCase):
    """장르/태그 다중 선택 시 AND(기본)/OR 결합 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'series.db'
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE books (
                id INTEGER PRIMARY KEY, series_name TEXT, series_alias TEXT, title TEXT,
                title_alias TEXT, author TEXT, isbn TEXT, publisher TEXT, link TEXT,
                score REAL, release_date TEXT, summary TEXT, localized_series TEXT,
                cover_artist TEXT, teams TEXT, locations TEXT, characters TEXT,
                file_path TEXT, file_format TEXT, cover_image TEXT, cover_updated_at TEXT,
                cover_align TEXT DEFAULT 'center', created_at TEXT, genre TEXT, tags TEXT,
                books_lv TEXT, publication_status TEXT, library_id INTEGER,
                metadata_locked INTEGER DEFAULT 0, is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE user_favorites (user_id INTEGER, book_id INTEGER);
            CREATE TABLE user_category_permissions (user_id INTEGER, library_id INTEGER, has_access INTEGER);
            INSERT INTO books (id, series_name, title, file_path, file_format, library_id, genre, tags)
                VALUES (1, 'A', 'a1', '/a/1.zip', 'zip', 10, 'GL', '15금');
            INSERT INTO books (id, series_name, title, file_path, file_format, library_id, genre, tags)
                VALUES (2, 'B', 'b1', '/b/1.zip', 'zip', 10, 'GL', '');
            INSERT INTO books (id, series_name, title, file_path, file_format, library_id, genre, tags)
                VALUES (3, 'C', 'c1', '/c/1.zip', 'zip', 10, '', '15금');
            INSERT INTO books (id, series_name, title, file_path, file_format, library_id, genre, tags)
                VALUES (4, 'D', 'd1', '/d/1.zip', 'zip', 10, '로맨스', '');
            """
        )
        conn.commit()
        conn.close()

        def connect(_db_type):
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        self.connection_patch = patch('repositories.sqlite.series_repository.database.get_connection', connect)
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def _ids(self, **kwargs):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, genre_filters=['GL'], tag_filters=['15금'], user_id=1, role='admin', **kwargs
        )
        return sorted(row['id'] for row in rows)

    def test_default_is_and(self):
        self.assertEqual(self._ids(), [1])

    def test_or_matches_any(self):
        self.assertEqual(self._ids(filter_mode='or'), [1, 2, 3])

    def test_totals_follow_mode(self):
        and_totals = SeriesRepository.fetch_grouping_totals(
            'general', 10, genre_filters=['GL'], tag_filters=['15금'], user_id=1, role='admin')
        or_totals = SeriesRepository.fetch_grouping_totals(
            'general', 10, genre_filters=['GL'], tag_filters=['15금'], user_id=1, role='admin', filter_mode='or')
        self.assertEqual(and_totals['total_series_count'], 1)
        self.assertEqual(or_totals['total_series_count'], 3)


if __name__ == '__main__':
    unittest.main()
