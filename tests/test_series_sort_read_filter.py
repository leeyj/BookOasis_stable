import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories.series_list_options import (
    build_order_by,
    build_read_series_filter,
    normalize_read_filter,
    normalize_sort,
)
from repositories.sqlite.series_repository import SeriesRepository


class SeriesListOptionsTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_sort('COUNT_DESC'), 'count_desc')
        self.assertEqual(normalize_sort('weird'), 'asc')
        self.assertEqual(normalize_read_filter('only_read'), 'only_read')
        self.assertEqual(normalize_read_filter('x'), '')

    def test_existing_orders_unchanged(self):
        cols = dict(lib_col='s.library_id', name_col='s.sort_series_name', date_col='s.latest_added',
                    count_col='s.series_book_count', id_col='s.representative_book_id')
        self.assertEqual(build_order_by('asc', **cols),
                         's.library_id ASC, s.sort_series_name ASC, s.representative_book_id ASC')
        self.assertEqual(build_order_by('desc', **cols),
                         's.library_id ASC, s.sort_series_name DESC, s.representative_book_id ASC')
        self.assertEqual(build_order_by('date_desc', **cols), 's.latest_added DESC, s.representative_book_id ASC')

    def test_read_filter_without_read_series(self):
        self.assertEqual(build_read_series_filter('only_read', {}, lib_col='l', key_col='k', placeholder='?'),
                         ('1 = 0', []))
        self.assertEqual(build_read_series_filter('exclude_read', {}, lib_col='l', key_col='k', placeholder='?'),
                         (None, []))


class SeriesSortReadFilterRepositoryTest(unittest.TestCase):
    """폴더 이름순/도서 수순 정렬과 '읽은 도서' 필터 (모든 권 완독 = 읽음)"""

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
            CREATE TABLE user_progress (book_id INTEGER, user_id INTEGER, pages_read INTEGER, is_completed INTEGER);

            -- [Z] 가: 2권 (모두 완독), 나: 3권 (1권만 완독), [A] 다: 1권 (기록 없음)
            INSERT INTO books (id, series_name, title, file_path, file_format, library_id, created_at) VALUES
                (1, '[Z] 가', 'g1', '/g/1.zip', 'zip', 10, '2026-01-01'),
                (2, '[Z] 가', 'g2', '/g/2.zip', 'zip', 10, '2026-01-02'),
                (3, '나', 'n1', '/n/1.zip', 'zip', 10, '2026-01-03'),
                (4, '나', 'n2', '/n/2.zip', 'zip', 10, '2026-01-04'),
                (5, '나', 'n3', '/n/3.zip', 'zip', 10, '2026-01-05'),
                (6, '[A] 다', 'd1', '/d/1.zip', 'zip', 10, '2026-01-06');
            INSERT INTO user_progress (book_id, user_id, pages_read, is_completed) VALUES
                (1, 7, 10, 1), (2, 7, 10, 1), (3, 7, 10, 1), (4, 7, 2, 0),
                (6, 8, 10, 1);
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
        self.user_patch = patch(
            'repositories.sqlite.user_repository.UserRepository.get_user_favorite_book_ids',
            return_value=set(),
        )
        self.user_patch.start()

    def tearDown(self):
        self.user_patch.stop()
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def _enable_summary(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE series_summary (
                library_id INTEGER NOT NULL, series_key VARCHAR(500) NOT NULL,
                representative_book_id INTEGER NOT NULL, series_book_count INTEGER NOT NULL DEFAULT 0,
                sort_series_name VARCHAR(500) NOT NULL DEFAULT '', latest_added VARCHAR(50) NOT NULL DEFAULT '',
                PRIMARY KEY (library_id, series_key)
            );
            CREATE TABLE series_summary_state (id INTEGER PRIMARY KEY, is_ready INTEGER NOT NULL DEFAULT 0, refreshed_at DATETIME);
            INSERT INTO series_summary VALUES
                (10, '[Z] 가', 1, 2, '[Z] 가', '2026-01-02'),
                (10, '나', 3, 3, '나', '2026-01-05'),
                (10, '[A] 다', 6, 1, '[A] 다', '2026-01-06');
            INSERT INTO series_summary_state (id, is_ready) VALUES (1, 1);
            """
        )
        conn.commit()
        conn.close()

    def _names(self, **kwargs):
        rows = SeriesRepository.fetch_books_for_grouping('general', 10, user_id=7, role='admin', **kwargs)
        return [row['series_name'] for row in rows]

    def test_fully_read_series_keys(self):
        self.assertEqual(SeriesRepository.fetch_fully_read_series_keys('general', 7), {10: {'[Z] 가'}})
        self.assertEqual(SeriesRepository.fetch_fully_read_series_keys('general', 8), {10: {'[A] 다'}})
        self.assertEqual(SeriesRepository.fetch_fully_read_series_keys('general', 99), {})

    def _check_sort_and_filter(self):
        read_keys = SeriesRepository.fetch_fully_read_series_keys('general', 7)
        self.assertEqual(self._names(sort='folder_asc'), ['[A] 다', '[Z] 가', '나'])
        self.assertEqual(self._names(sort='folder_desc'), ['나', '[Z] 가', '[A] 다'])
        self.assertEqual(self._names(sort='count_desc'), ['나', '[Z] 가', '[A] 다'])
        self.assertEqual(self._names(sort='count_asc'), ['[A] 다', '[Z] 가', '나'])
        self.assertEqual(self._names(sort='folder_asc', read_filter='only_read', read_keys=read_keys), ['[Z] 가'])
        self.assertEqual(self._names(sort='folder_asc', read_filter='exclude_read', read_keys=read_keys),
                         ['[A] 다', '나'])
        self.assertEqual(self._names(sort='count_desc', read_filter='exclude_read', read_keys=read_keys, limit=1),
                         ['나'])

    def test_group_by_path(self):
        self._check_sort_and_filter()

    def test_summary_path(self):
        self._enable_summary()
        # fetch_books_for_grouping은 요약 경로 오류를 삼키고 GROUP BY로 폴백하므로 직접 호출해 확인한다
        read_keys = SeriesRepository.fetch_fully_read_series_keys('general', 7)
        rows = SeriesRepository._fetch_summary_rows(
            'general', 10, 7, 'admin', None, None, 7, sort='count_desc',
            read_filter='exclude_read', read_keys=read_keys,
        )
        self.assertEqual([row['series_name'] for row in rows], ['나', '[A] 다'])
        self._check_sort_and_filter()

    def test_summary_totals_with_read_filter(self):
        self._enable_summary()
        read_keys = SeriesRepository.fetch_fully_read_series_keys('general', 7)
        totals = lambda rf: SeriesRepository._fetch_summary_totals(
            'general', 10, 7, 'admin', read_filter=rf, read_keys=read_keys)
        self.assertEqual(totals(''), {'total_series_count': 3, 'total_book_count': 6})
        self.assertEqual(totals('only_read'), {'total_series_count': 1, 'total_book_count': 2})
        self.assertEqual(totals('exclude_read'), {'total_series_count': 2, 'total_book_count': 4})

    def test_count_sort_ties_follow_representative_id(self):
        # 권수가 같으면 대표 도서 ID 순 (정렬 방향과 같은 방향 - 인덱스 한 방향 스캔용)
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO books (id, series_name, title, file_path, file_format, library_id, created_at) "
                     "VALUES (7, '라', 'r1', '/r/1.zip', 'zip', 10, '2026-01-07')")
        conn.commit()
        conn.close()
        self.assertEqual(self._names(sort='count_desc'), ['나', '[Z] 가', '라', '[A] 다'])
        self.assertEqual(self._names(sort='count_asc'), ['[A] 다', '라', '[Z] 가', '나'])


    def _set_scores(self):
        conn = sqlite3.connect(self.db_path)
        # 대표 도서 점수: [Z] 가(rep 1)=80, 나(rep 3)=없음, [A] 다(rep 6)=95
        conn.executescript("""
            UPDATE books SET score = 80 WHERE id = 1;
            UPDATE books SET score = 95 WHERE id = 6;
            CREATE INDEX IF NOT EXISTS idx_books_score ON books(score, id);
            CREATE INDEX IF NOT EXISTS idx_books_library_score ON books(library_id, score, id);
        """)
        conn.commit()
        conn.close()

    def _check_score_sort(self):
        read_keys = SeriesRepository.fetch_fully_read_series_keys('general', 7)
        self.assertEqual(self._names(sort='score_desc'), ['[A] 다', '[Z] 가', '나'])
        self.assertEqual(self._names(sort='score_desc', limit=1), ['[A] 다'])
        self.assertEqual(self._names(sort='score_desc', read_filter='exclude_read', read_keys=read_keys), ['[A] 다', '나'])

    def test_score_sort_group_by_path(self):
        self._set_scores()
        self._check_score_sort()

    def test_score_sort_summary_path_reads_books_by_score_index(self):
        self._set_scores()
        self._enable_summary()
        rows = SeriesRepository._fetch_summary_rows('general', 10, 7, 'admin', 2, 0, 7, sort='score_desc')
        self.assertEqual([row['series_name'] for row in rows], ['[A] 다', '[Z] 가'])
        self._check_score_sort()
        # 읽는 순서를 books → series_summary로 고정해 (library_id, score, id) 인덱스로 정렬 없이 읽는다
        conn = sqlite3.connect(self.db_path)
        plan = ' | '.join(str(r[-1]) for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT b.id FROM books b CROSS JOIN series_summary s ON s.representative_book_id = b.id "
            "WHERE b.library_id = 10 ORDER BY b.score DESC, b.id DESC LIMIT 61"
        ))
        conn.close()
        self.assertIn('idx_books_library_score', plan)
        self.assertNotIn('TEMP B-TREE', plan)


if __name__ == '__main__':
    unittest.main()