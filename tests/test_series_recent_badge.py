"""목록 카드 "NEW / +N권" 배지(SeriesService.annotate_recent_additions) 회귀 테스트."""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from repositories.sqlite import series_repository as sqlite_series_repository
from services import series_service
from services.series_service import SeriesService


class RecentAdditionsBadgeTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, 'books.db')

        def connect(_db_type=None):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

        conn = connect()
        conn.execute(
            "CREATE TABLE books (id INTEGER PRIMARY KEY, library_id INTEGER, series_name TEXT, title TEXT,"
            " is_deleted INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        old = "datetime('now', '-30 days')"
        new = "datetime('now', '-1 days')"
        rows = []
        # 라이브러리 1: 연재 시리즈(10권 중 2권 신규), 완전 신규 시리즈(2권), 오래된 시리즈, 신규 단행본
        rows += [(1, '연재물', f'{i}권', old) for i in range(8)]
        rows += [(1, '연재물', f'{i}권', new) for i in (8, 9)]
        rows += [(1, '신작', f'{i}권', new) for i in range(2)]
        rows += [(1, '옛날작', f'{i}권', old) for i in range(10)]
        rows += [(1, '', '단행본', new)]
        # 라이브러리 2: 방금 처음 스캔한 카테고리(전부 신규) -> 배지 끔
        rows += [(2, '초기등록', f'{i}권', new) for i in range(5)]
        for lib_id, series, title, ts in rows:
            conn.execute(
                f"INSERT INTO books (library_id, series_name, title, created_at) VALUES (?, ?, ?, {ts})",
                (lib_id, series, title),
            )
        conn.commit()
        self.recent_ts = conn.execute(f"SELECT {new}").fetchone()[0]
        self.old_ts = conn.execute(f"SELECT {old}").fetchone()[0]
        conn.close()

        patches = [
            patch.object(sqlite_series_repository.database, 'get_connection', side_effect=connect),
            patch.object(series_service, 'SeriesRepository', sqlite_series_repository.SeriesRepository),
            patch.object(SeriesService, 'get_library_totals_bulk', return_value={
                1: {'book_count': 23}, 2: {'book_count': 5},
            }),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        series_service._RECENT_ADDED_CACHE.clear()
        self.addCleanup(series_service._RECENT_ADDED_CACHE.clear)

    def _entry(self, lib_id, name, count, latest):
        return {'library_id': lib_id, 'series_name': name, 'book_count': count, 'latest_added': latest}

    def test_badges(self):
        entries = [
            self._entry(1, '연재물', 10, self.recent_ts),
            self._entry(1, '신작', 2, self.recent_ts),
            self._entry(1, '옛날작', 10, self.old_ts),
            self._entry(1, '기타 단행본', 1, self.recent_ts),
            self._entry(2, '초기등록', 5, self.recent_ts),
        ]
        out = {e['series_name']: e for e in SeriesService.annotate_recent_additions('general', entries)}

        self.assertEqual(out['연재물']['recent_added_count'], 2)
        self.assertFalse(out['연재물']['is_new_series'])
        self.assertEqual(out['신작']['recent_added_count'], 2)
        self.assertTrue(out['신작']['is_new_series'])
        self.assertNotIn('recent_added_count', out['옛날작'])
        self.assertTrue(out['기타 단행본']['is_new_series'])
        self.assertNotIn('recent_added_count', out['초기등록'])
        # 캐시된 원본 entry는 건드리지 않는다
        self.assertNotIn('recent_added_count', entries[0])

    def test_non_book_types_untouched(self):
        entries = [self._entry(1, '연재물', 10, self.recent_ts)]
        self.assertIs(SeriesService.annotate_recent_additions('audiobook', entries), entries)


class SummaryRebuildNullCreatedAtTests(unittest.TestCase):
    """created_at이 NULL인 행 하나 때문에 series_summary 재생성 전체가 롤백되던 회귀 방지."""

    def test_rebuild_survives_null_created_at(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, 'books.db')

        def connect(_db_type=None):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

        conn = connect()
        conn.executescript("""
            CREATE TABLE books (id INTEGER PRIMARY KEY, library_id INTEGER, series_name TEXT, title TEXT,
                                cover_image TEXT, is_deleted INTEGER DEFAULT 0, created_at DATETIME);
            CREATE TABLE series_summary (library_id INTEGER, series_key TEXT, representative_book_id INTEGER,
                                         series_book_count INTEGER NOT NULL DEFAULT 0,
                                         sort_series_name TEXT NOT NULL DEFAULT '',
                                         latest_added VARCHAR(50) NOT NULL DEFAULT '');
            CREATE TABLE series_summary_state (id INTEGER PRIMARY KEY, is_ready INTEGER, refreshed_at TEXT);
            INSERT INTO books (library_id, series_name, title, created_at) VALUES (80, '정상', '1권', '2026-09-29 02:00:00');
            INSERT INTO books (library_id, series_name, title, created_at) VALUES (80, '날짜없음', '1권', NULL);
        """)
        conn.commit()
        conn.close()

        with patch.object(sqlite_series_repository.database, 'get_connection', side_effect=connect):
            self.assertTrue(sqlite_series_repository.SeriesRepository.rebuild_summary('general'))

        conn = connect()
        rows = {r['series_key']: r['latest_added'] for r in conn.execute("SELECT * FROM series_summary")}
        conn.close()
        self.assertEqual(rows, {'정상': '2026-09-29 02:00:00', '날짜없음': ''})


class BooksCreatedAtBackfillTests(unittest.TestCase):
    def test_backfill_fills_null_created_at_only(self):
        from services.db_migration_service import _backfill_books_created_at

        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE books (id INTEGER PRIMARY KEY, cover_updated_at DATETIME, created_at DATETIME);
            INSERT INTO books VALUES (1, '2026-07-18 14:22:34', NULL);
            INSERT INTO books VALUES (2, NULL, NULL);
            INSERT INTO books VALUES (3, '2026-07-01 00:00:00', '2026-07-18 12:00:00');
        """)

        _backfill_books_created_at(conn, cursor, 'general')

        rows = dict(conn.execute("SELECT id, created_at FROM books").fetchall())
        self.assertEqual(rows[1], '2026-07-18 14:22:34')
        self.assertTrue(rows[2])
        self.assertEqual(rows[3], '2026-07-18 12:00:00')
        conn.close()

    def test_backfill_skips_non_book_dbs(self):
        from services.db_migration_service import _backfill_books_created_at

        conn = sqlite3.connect(':memory:')
        # books 테이블이 없는 audiobook DB에서도 조용히 넘어가야 한다(쿼리 자체를 안 보냄)
        _backfill_books_created_at(conn, conn.cursor(), 'audiobook')
        conn.close()


if __name__ == '__main__':
    unittest.main()
