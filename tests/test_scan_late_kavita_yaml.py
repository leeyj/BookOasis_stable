"""이미 스캔된 작품 폴더에 나중에 kavita.yaml을 추가한 경우의 회귀 테스트.

- 일반(force=False) 폴더 스캔이 새 메타 파일을 감지해 파일 단위 스킵을 풀어야 한다.
- 도서 상세의 "재스캔"(scan_single_book) 저장 쿼리가 tags/genre 등을 실제로 반영해야 한다.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from repositories.sqlite import book_scan_repository as sqlite_repository
from tools.scanner import tasks
from tools.scanner.path_utils import canonical_path, join_canonical

KAVITA_YAML = "Tags:\n  - 판타지\n  - 역사\nGenres:\n  - 드라마\n"


class LateKavitaYamlFolderTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = canonical_path(self.temp_dir.name)
        self.book = join_canonical(self.root, '001.txt')
        with open(self.book, 'w', encoding='utf-8') as handle:
            handle.write('본문')

    def _run(self, files, db_folder_mtimes):
        stat = os.stat(self.book)
        db_files_cache = {self.book: (stat.st_mtime, stat.st_size)}
        with (
            patch.object(tasks, 'get_series_cover_fallback', return_value=None),
            patch.object(tasks, 'get_folder_banner', return_value=None),
        ):
            return tasks.process_folder_task(
                self.root, files, False, {self.book}, {self.book}, db_folder_mtimes,
                is_remote=False, library_id=1, db_files_cache=db_files_cache,
            )

    def test_unchanged_folder_without_metadata_is_still_skipped(self):
        dir_mtime = os.path.getmtime(self.root)
        self.assertIsNone(self._run(['001.txt'], {self.root: (dir_mtime, 0.0)}))

    def test_yaml_added_after_scan_lifts_per_file_skip(self):
        # 첫 스캔 당시 메타 파일이 없어 meta_mtime=0.0으로 기록된 폴더
        cached = {self.root: (os.path.getmtime(self.root), 0.0)}
        with open(join_canonical(self.root, 'kavita.yaml'), 'w', encoding='utf-8') as handle:
            handle.write(KAVITA_YAML)

        res = self._run(['001.txt', 'kavita.yaml'], cached)

        self.assertIsNotNone(res)
        self.assertIn('판타지', res['merged_meta']['tags'])
        self.assertEqual([item['skip'] for item in res['results']], [False])

    def test_yaml_already_recorded_keeps_fast_skip(self):
        yaml_path = join_canonical(self.root, 'kavita.yaml')
        with open(yaml_path, 'w', encoding='utf-8') as handle:
            handle.write(KAVITA_YAML)
        cached = {self.root: (os.path.getmtime(self.root), os.path.getmtime(yaml_path))}

        self.assertIsNone(self._run(['001.txt', 'kavita.yaml'], cached))


class SingleBookRescanWritesTagsTests(unittest.TestCase):
    def test_update_book_scanned_metadata_persists_tags_and_genre(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, 'books.db')

        def connect():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

        conn = connect()
        conn.execute(
            "CREATE TABLE books (id INTEGER PRIMARY KEY, library_id INTEGER, series_name TEXT, cover_image TEXT,"
            " cover_updated_at TEXT, author TEXT, isbn TEXT, publisher TEXT, link TEXT, score REAL, summary TEXT,"
            " release_date TEXT, genre TEXT, tags TEXT, books_lv TEXT, publication_status TEXT, metadata_locked INTEGER)"
        )
        conn.execute("INSERT INTO books (id, library_id, series_name, tags) VALUES (1, 1, 'S', '')")
        conn.commit()
        conn.close()
        meta = {'author': '', 'isbn': '', 'publisher': '', 'link': '', 'score': 0, 'summary': '',
                'release_date': '', 'genre': '드라마', 'tags': '판타지, 역사', 'books_lv': 'Teen',
                'publication_status': '2'}

        with patch.object(sqlite_repository.database, 'get_connection', side_effect=lambda _db: connect()):
            sqlite_repository.BookScanRepository.update_book_scanned_metadata('general', 1, 'S', None, meta)

        conn = connect()
        self.addCleanup(conn.close)
        row = conn.execute("SELECT genre, tags, books_lv, publication_status FROM books WHERE id = 1").fetchone()
        self.assertEqual(tuple(row), ('드라마', '판타지, 역사', 'Teen', '2'))


if __name__ == '__main__':
    unittest.main()
