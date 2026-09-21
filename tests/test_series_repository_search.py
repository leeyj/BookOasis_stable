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
                series_alias TEXT,
                title TEXT,
                title_alias TEXT,
                author TEXT,
                isbn TEXT,
                publisher TEXT,
                link TEXT,
                score REAL,
                release_date TEXT,
                summary TEXT,
                localized_series TEXT,
                cover_artist TEXT,
                teams TEXT,
                locations TEXT,
                characters TEXT,
                file_path TEXT,
                file_format TEXT,
                cover_image TEXT,
                cover_updated_at TEXT,
                cover_align TEXT DEFAULT 'center',
                created_at TEXT,
                genre TEXT,
                tags TEXT,
                books_lv TEXT,
                publication_status TEXT,
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
            INSERT INTO books (
                id, series_name, title, author, file_path, file_format, library_id
            ) VALUES (
                2, '무림 이야기', '첫 번째 권', '도굴왕 작가',
                '/books/무림/001.zip', 'zip', 10
            );
            INSERT INTO books (
                id, series_name, title, author, file_path, file_format, library_id
            ) VALUES (
                3, '예상과 다른 시리즈', '[연재] 도굴왕 002', '산지직송',
                '/books/도굴왕/002.zip', 'zip', 10
            );
            INSERT INTO books (
                id, series_name, title, author, cover_artist, file_path, file_format, library_id
            ) VALUES (
                4, '삽화 테스트', '아무 책', '다른 저자', '도굴왕 그림작가',
                '/books/삽화/001.zip', 'zip', 10
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

    def test_episode_title_match_reports_matched_title(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='도굴왕', user_id=1, role='admin'
        )

        self.assertEqual(rows[0]['matched_title'], '[연재] 도굴왕 001')

    def test_matched_title_is_none_without_search(self):
        rows = SeriesRepository.fetch_books_for_grouping('general', 10, user_id=1, role='admin')

        self.assertTrue(all(row['matched_title'] is None for row in rows))

    def test_series_entries_carry_match_info_only_for_episode_matches(self):
        from services.series_service import _build_series_entries

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='도굴왕', user_id=1, role='admin'
        )
        entries = _build_series_entries('general', rows, '도굴왕')
        self.assertEqual(entries[0]['match_info']['field'], 'episode')
        self.assertEqual(entries[0]['match_info']['count'], 2)

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='무림', user_id=1, role='admin'
        )
        entries = _build_series_entries('general', rows, '무림')
        self.assertNotIn('match_info', entries[0])

    def test_topic_prefix_matches_genre_and_tags_only(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE books SET genre = '슬라임물', tags = '이세계' WHERE id = 2")
        conn.commit()
        conn.close()

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='주제:이세계', user_id=1, role='admin'
        )
        self.assertEqual([row['id'] for row in rows], [2])

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='주제:도굴왕', user_id=1, role='admin'
        )
        self.assertEqual(rows, [])

    def test_natural_search_does_not_match_author(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='도굴왕 작가', user_id=1, role='admin'
        )

        self.assertEqual(rows, [])

    def test_author_prefix_searches_author_only(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='작가:도굴왕', user_id=1, role='admin'
        )

        self.assertEqual([row['id'] for row in rows], [2])

    def test_cover_artist_prefix_searches_cover_artist_only(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, search_query='그림작가:도굴왕', user_id=1, role='admin'
        )
        totals = SeriesRepository.fetch_grouping_totals(
            'general', 10, search_query='그림작가:도굴왕', user_id=1, role='admin'
        )

        self.assertEqual([row['id'] for row in rows], [4])
        self.assertEqual(totals['total_book_count'], 1)

    def test_category_totals_are_queried_separately_from_page_rows(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, user_id=1, role='admin', limit=1, offset=0
        )
        totals = SeriesRepository.fetch_grouping_totals(
            'general', 10, user_id=1, role='admin'
        )

        self.assertEqual(len(rows), 1)
        self.assertNotIn('total_series_count', rows[0])
        self.assertEqual(totals['total_series_count'], 3)
        self.assertEqual(totals['total_book_count'], 4)

    def test_list_rows_do_not_compute_has_metadata(self):
        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, user_id=1, role='admin'
        )
        self.assertTrue(rows)
        self.assertTrue(all(row['has_metadata'] is None for row in rows))

    def test_series_metadata_presence_checks_all_volumes_when_opted_in(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE books SET author = '' WHERE id IN (1, 3)")
        conn.execute("UPDATE books SET cover_artist = 'Illustrator' WHERE id = 3")
        conn.commit()
        conn.close()

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, user_id=1, role='admin', include_has_metadata=True
        )
        series = next(row for row in rows if row['series_name'] == '예상과 다른 시리즈')
        self.assertEqual(series['has_metadata'], 1)

        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE books SET cover_artist = NULL WHERE id = 3")
        conn.commit()
        conn.close()

        rows = SeriesRepository.fetch_books_for_grouping(
            'general', 10, user_id=1, role='admin', include_has_metadata=True
        )
        series = next(row for row in rows if row['series_name'] == '예상과 다른 시리즈')
        self.assertEqual(series['has_metadata'], 0)


if __name__ == '__main__':
    unittest.main()
