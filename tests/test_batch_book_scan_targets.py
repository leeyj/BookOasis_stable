import sqlite3
import unittest

from services.batch_book_scan_targets import resolve_batch_book_scan_targets


class BatchBookScanTargetsTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            'CREATE TABLE books ('
            'id INTEGER PRIMARY KEY, library_id INTEGER, title TEXT, '
            'series_name TEXT, is_deleted INTEGER DEFAULT 0)'
        )
        self.connection.executemany(
            'INSERT INTO books (id, library_id, title, series_name, is_deleted) VALUES (?, ?, ?, ?, ?)',
            [
                (1, 2, 'Series 01', 'Series', 0),
                (2, 2, 'Series 02', 'Series', 0),
                (3, 3, 'Series 03 other library', 'Series', 0),
                (4, 2, 'Other series 01', 'Other series', 0),
                (5, 2, 'Standalone', '', 0),
                (6, 2, 'Deleted volume', 'Series', 1),
                (7, 2, 'Series 04', 'Series', 0),
            ],
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def scan_ids(self, book_ids, scope):
        rows = resolve_batch_book_scan_targets(self.connection.cursor(), book_ids, scope)
        return [int(row['id']) for row in rows]

    def test_series_scope_includes_all_active_volumes_in_the_same_library(self):
        # 다른 라이브러리(3)의 같은 시리즈명과 삭제된 권(6)은 제외된다.
        self.assertEqual(self.scan_ids([1], 'series'), [1, 2, 7])

    def test_series_scope_expands_each_selected_card_and_keeps_standalone_books(self):
        self.assertEqual(self.scan_ids([1, 4, 5], 'series'), [1, 2, 4, 5, 7])

    def test_book_scope_preserves_single_book_behavior(self):
        self.assertEqual(self.scan_ids([1], 'book'), [1])

    def test_standalone_anchor_is_not_expanded(self):
        self.assertEqual(self.scan_ids([5], 'series'), [5])

    def test_missing_book_and_invalid_scope_are_rejected(self):
        with self.assertRaises(LookupError):
            self.scan_ids([999], 'series')
        with self.assertRaises(LookupError):
            self.scan_ids([6], 'series')  # 삭제된 도서는 앵커가 될 수 없다
        with self.assertRaises(ValueError):
            self.scan_ids([1], 'all')


if __name__ == '__main__':
    unittest.main()
