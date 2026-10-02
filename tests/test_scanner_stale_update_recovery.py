"""스캔 시작 스냅샷(db_books)에는 있던 도서 row가 write 직전에 사라진 경우의 회귀 테스트.

커뮤니티 제보: partial scan-path가 파일 처리/커버/Flush/API 모두 성공인데 books row가 없던 문제.
- stale update 대상은 insert(upsert)로 재분류되어 row와 offsets가 복구되어야 한다.
- 정상 update/신규 insert 경로는 기존 동작을 유지해야 한다.
- 복구조차 실패하면 scan-path는 성공으로 끝나면 안 된다.
- 7일 휴지통 자동 비우기는 파일이 다시 존재하는 row를 지우지 않아야 한다.
"""
import datetime
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.db_migration_service import _SCHEMA_SQL
from tools.scanner import engine, sync_detector
from tools.scanner.path_utils import canonical_path, join_canonical

EMPTY_META = {k: '' for k in (
    'author', 'isbn', 'publisher', 'link', 'summary', 'release_date', 'genre', 'tags',
    'books_lv', 'publication_status', 'cover_artist', 'teams', 'locations', 'characters',
)}
EMPTY_META['score'] = 0

OFFSETS = [(0, '001.jpg', 0, 10, 10, 0, 30), (1, '002.jpg', 40, 10, 10, 0, 70)]


class _ScanFixture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp_dir.cleanup)
        base = canonical_path(self.temp_dir.name)
        self.db_path = os.path.join(base, 'books.db')
        self.lib_root = join_canonical(base, 'lib')
        self.series_dir = join_canonical(self.lib_root, 'S')
        os.makedirs(self.series_dir)
        self.book = join_canonical(self.series_dir, 'a (단권) [1080x]#170.zip')
        with open(self.book, 'wb') as handle:
            handle.write(b'zip')

        conn = self._connect()
        conn.executescript(_SCHEMA_SQL)
        conn.execute("INSERT INTO libraries (id, name, physical_path) VALUES (1, 'L', ?)", (self.lib_root,))
        conn.commit()
        conn.close()

        for target, value in (
            ('utils.redis_helper.redis_acquire_lock', 'tok'),
            ('utils.redis_helper.redis_release_lock', None),
            ('utils.report_helper.save_scan_report', None),
        ):
            p = patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        # 스캔 끝 문제 기록(services/scan_problem_service.py)이 쓰는 general DB 연결도 이 임시 DB로 돌린다
        # (안 그러면 개발 PC의 실제 DB에 기록이 남는다).
        from contextlib import contextmanager
        import database as database_module

        @contextmanager
        def _temp_connection(*_args, **_kwargs):
            c = self._connect()
            try:
                yield c
            finally:
                c.close()

        for name, value in (
            ('get_connection', lambda *_a, **_k: self._connect()),
            ('connection', _temp_connection),
        ):
            p = patch.object(database_module, name, value)
            p.start()
            self.addCleanup(p.stop)
        for name, value in (
            ('DB_DIR', base),
            ('check_memory_exceeded', lambda **_kw: False),
            ('dispatch_webhook_event', lambda *a, **k: None),
            ('dispatch_standard_book_event', lambda *a, **k: None),
            ('_dispatch_new_books_to_plugin_hooks', lambda *a, **k: None),
        ):
            p = patch.object(engine, name, value)
            p.start()
            self.addCleanup(p.stop)

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_existing(self, **extra):
        cols = {'library_id': 1, 'title': 'old', 'series_name': 'S', 'file_path': self.book,
                'file_format': 'zip', 'total_pages': 0, 'author': 'Kept', 'cover_image': 'old.webp'}
        cols.update(extra)
        conn = self._connect()
        conn.execute(
            f"INSERT INTO books ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            tuple(cols.values()),
        )
        conn.commit()
        conn.close()

    def _fake_task(self, delete_row_first=False):
        def task(root, files, *args, **kwargs):
            if delete_row_first:
                # 다른 스캔(휴지통 자동 비우기 등)이 스냅샷 이후 row를 지운 상황
                c = self._connect()
                c.execute("DELETE FROM books WHERE file_path = ?", (self.book,))
                c.commit()
                c.close()
            return {
                'dir_mtime': os.path.getmtime(root), 'meta_mtime': 0.0,
                'merged_meta': dict(EMPTY_META, author='NewAuthor'),
                'results': [{
                    'full_path': self.book, 'skip': False, 'filename': os.path.basename(self.book),
                    'file_format': 'zip', 'series_name': 'S', 'title': None,
                    'cover_image': 'book_new.webp', 'banner_image': None,
                    'offsets_data': list(OFFSETS), 'offset_only': False,
                    'file_mtime': 1.0, 'file_size': 3,
                }],
            }
        return task

    def _scan(self, task, path_scope=None):
        conn = self._connect()
        self.addCleanup(lambda: conn.close())
        with patch.object(engine, 'process_folder_task', side_effect=task):
            engine._scan_library_internal(
                conn, self.db_path, 1, self.lib_root, False, 'general',
                [self.lib_root], False, 1, [], path_scope=path_scope,
            )

    def _rows(self):
        conn = self._connect()
        try:
            books = conn.execute(
                "SELECT id, cover_image, author, is_deleted, has_offsets, total_pages, library_id, series_name "
                "FROM books WHERE file_path = ?", (self.book,)
            ).fetchall()
            offsets = conn.execute(
                "SELECT COUNT(*) FROM book_offsets WHERE book_id IN (SELECT id FROM books WHERE file_path = ?)",
                (self.book,),
            ).fetchone()[0]
            return books, offsets
        finally:
            conn.close()


class StaleUpdateRecoveryTests(_ScanFixture):
    def test_stale_update_target_is_reinserted_with_offsets(self):
        self._insert_existing()
        self._scan(self._fake_task(delete_row_first=True), path_scope=self.series_dir)

        books, offsets = self._rows()
        self.assertEqual(len(books), 1)
        row = books[0]
        self.assertEqual(row['cover_image'], 'book_new.webp')
        self.assertEqual((row['library_id'], row['series_name'], row['is_deleted']), (1, 'S', 0))
        self.assertEqual((row['has_offsets'], row['total_pages']), (1, 2))
        self.assertEqual(offsets, 2)

    def test_row_deleted_between_recheck_and_update_is_recovered_after_commit(self):
        self._insert_existing()
        real_update = engine.bulk_update_books

        def deleting_update(cur, data, force=False):
            c = self._connect()
            c.execute("DELETE FROM books WHERE file_path = ?", (self.book,))
            c.commit()
            c.close()
            return real_update(cur, data, force=force)

        with patch.object(engine, 'bulk_update_books', deleting_update):
            self._scan(self._fake_task(), path_scope=self.series_dir)

        books, offsets = self._rows()
        self.assertEqual(len(books), 1)
        self.assertEqual((books[0]['cover_image'], books[0]['has_offsets']), ('book_new.webp', 1))
        self.assertEqual(offsets, 2)

    def test_existing_row_keeps_update_path_without_duplicates(self):
        self._insert_existing()
        self._scan(self._fake_task(), path_scope=self.series_dir)

        books, offsets = self._rows()
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]['author'], 'NewAuthor')
        self.assertEqual(offsets, 2)

    def test_metadata_locked_row_is_not_overwritten(self):
        self._insert_existing(metadata_locked=1)
        self._scan(self._fake_task(), path_scope=self.series_dir)

        books, _ = self._rows()
        self.assertEqual((books[0]['author'], books[0]['cover_image']), ('Kept', 'old.webp'))

    def test_new_book_insert_unchanged(self):
        self._scan(self._fake_task())

        books, offsets = self._rows()
        self.assertEqual(len(books), 1)
        self.assertEqual(offsets, 2)

    def test_scan_path_fails_when_row_cannot_be_persisted(self):
        with patch.object(engine, 'bulk_insert_books', lambda *a, **k: None):
            with self.assertRaises(RuntimeError):
                self._scan(self._fake_task(), path_scope=self.series_dir)

    def test_full_scan_reports_missing_row_instead_of_raising(self):
        errors = []
        conn = self._connect()
        self.addCleanup(conn.close)
        with patch.object(engine, 'bulk_insert_books', lambda *a, **k: None), \
                patch.object(engine, 'process_folder_task', side_effect=self._fake_task()):
            engine._scan_library_internal(
                conn, self.db_path, 1, self.lib_root, False, 'general',
                [self.lib_root], False, 1, errors,
            )
        self.assertEqual([e['error_type'] for e in errors], ['DBWriteInvariantError'])


class TrashPurgeSkipsReappearedFilesTests(_ScanFixture):
    def test_purge_restores_rows_whose_file_exists_and_deletes_the_rest(self):
        old = (datetime.datetime.now() - datetime.timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S')
        gone = join_canonical(self.series_dir, 'gone.zip')
        conn = self._connect()
        conn.execute(
            "INSERT INTO books (library_id, title, file_path, file_format, total_pages, is_deleted, deleted_at) VALUES (1, 'a', ?, 'zip', 0, 1, ?)",
            (self.book, old),
        )
        conn.execute(
            "INSERT INTO books (library_id, title, file_path, file_format, total_pages, is_deleted, deleted_at) VALUES (1, 'g', ?, 'zip', 0, 1, ?)",
            (gone, old),
        )
        conn.commit()

        with patch('services.cover_storage_service.get_covers_dir', return_value=self.temp_dir.name):
            ok = sync_detector.handle_deleted_books(
                conn.cursor(), {}, {'/elsewhere/x.zip'}, [self.lib_root], {'/elsewhere/y.zip'}
            )
        conn.commit()

        self.assertTrue(ok)
        rows = {r['file_path']: r['is_deleted'] for r in conn.execute("SELECT file_path, is_deleted FROM books")}
        conn.close()
        self.assertEqual(rows, {self.book: 0})


    def test_rescan_keeps_original_trash_time_so_auto_purge_happens(self):
        """이미 휴지통에 있는 도서가 다시 '사라짐'으로 잡혀도 deleted_at이 갱신되지 않아야 7일 비우기가 동작한다."""
        old = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        gone = join_canonical(self.series_dir, 'gone.zip')
        fresh = join_canonical(self.series_dir, 'fresh.zip')
        legacy = join_canonical(self.series_dir, 'legacy.zip')
        conn = self._connect()
        for title, path, deleted, at in (('g', gone, 1, old), ('f', fresh, 0, None), ('l', legacy, 1, None)):
            conn.execute(
                "INSERT INTO books (library_id, title, file_path, file_format, total_pages, is_deleted, deleted_at) VALUES (1, ?, ?, 'zip', 0, ?, ?)",
                (title, path, deleted, at),
            )
        conn.commit()
        db_books = {r['file_path']: r['id'] for r in conn.execute("SELECT id, file_path FROM books")}

        with patch('services.cover_storage_service.get_covers_dir', return_value=self.temp_dir.name):
            ok = sync_detector.handle_deleted_books(
                conn.cursor(), db_books, {gone, fresh, legacy}, [self.lib_root], {self.book}
            )
        conn.commit()

        self.assertTrue(ok)
        rows = {r['file_path']: (r['is_deleted'], r['deleted_at']) for r in conn.execute("SELECT file_path, is_deleted, deleted_at FROM books")}
        conn.close()
        self.assertEqual(rows[gone], (1, old))                  # 처음 휴지통에 들어간 시각 유지
        self.assertEqual(rows[fresh][0], 1)
        self.assertIsNotNone(rows[fresh][1])                    # 새로 사라진 도서는 지금 시각
        self.assertIsNotNone(rows[legacy][1])                   # 시각이 비어 있던 예전 행은 채움

if __name__ == '__main__':
    unittest.main()
