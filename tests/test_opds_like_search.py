import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repositories.sqlite.opds_repository import OpdsRepository


def _create_search_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            title TEXT,
            series_name TEXT,
            author TEXT,
            file_path TEXT,
            cover_image TEXT,
            summary TEXT,
            library_id INTEGER,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE user_category_permissions (
            user_id INTEGER,
            library_id INTEGER,
            has_access INTEGER
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO books
            (id, title, series_name, author, file_path, library_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, '마법사의 돌', '해리 포터', 'J. K. 롤링', '/books/1.epub', 10),
            (2, '100% 사용법', 'SQLite', '홍길동', '/books/2.epub', 10),
            (3, '100X 사용법', 'SQLite', '홍길동', '/books/3.epub', 20),
        ],
    )
    conn.execute(
        "INSERT INTO user_category_permissions (user_id, library_id, has_access) VALUES (7, 10, 1)"
    )
    conn.commit()
    conn.close()


def _connection_factory(path):
    def connect(_db_type):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    return connect


class OpdsLikeSearchTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'opds.db'
        _create_search_db(self.db_path)
        self.connection_patch = patch(
            'repositories.sqlite.opds_repository.database.get_connection',
            _connection_factory(self.db_path),
        )
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def test_search_matches_all_terms_across_fields(self):
        books, total = OpdsRepository.search_books_like(
            'general', '해리 롤링', limit=20, offset=0, user_id=1, role='admin'
        )

        self.assertEqual(total, 1)
        self.assertEqual([book['id'] for book in books], [1])

    def test_search_treats_like_wildcards_as_text(self):
        books, total = OpdsRepository.search_books_like(
            'general', '100%', limit=20, offset=0, user_id=1, role='admin'
        )

        self.assertEqual(total, 1)
        self.assertEqual([book['id'] for book in books], [2])

    def test_search_honors_user_library_permissions(self):
        books, total = OpdsRepository.search_books_like(
            'general', '사용법', limit=20, offset=0, user_id=7, role='user'
        )

        self.assertEqual(total, 1)
        self.assertEqual([book['id'] for book in books], [2])


if __name__ == '__main__':
    unittest.main()