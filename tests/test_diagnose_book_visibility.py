import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.diagnose_book_visibility import diagnose


class DiagnoseBookVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'visibility.db'
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);
            CREATE TABLE libraries (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE user_category_permissions (
                user_id INTEGER,
                library_id INTEGER,
                has_access INTEGER
            );
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                title TEXT,
                series_name TEXT,
                author TEXT,
                library_id INTEGER,
                file_path TEXT,
                file_format TEXT,
                is_deleted INTEGER DEFAULT 0
            );
            INSERT INTO users VALUES (1, 'allowed', 'user');
            INSERT INTO users VALUES (2, 'blocked', 'user');
            INSERT INTO libraries VALUES (10, '웹소설_연재');
            INSERT INTO user_category_permissions VALUES (1, 10, 1);
            INSERT INTO user_category_permissions VALUES (2, 10, 0);
            INSERT INTO books VALUES (
                100, '[연재] 도굴왕 001', '[연재] 도굴왕', '산지직송', 10,
                '/books/도굴왕/001.zip', 'zip', 0
            );
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_diagnose(self, user_id):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = diagnose(
                self.db_path,
                '도굴왕',
                user_id=user_id,
                library_id=10,
            )
        return exit_code, output.getvalue()

    def test_reports_visible_for_allowed_user(self):
        exit_code, output = self.run_diagnose(1)

        self.assertEqual(exit_code, 0)
        self.assertIn('[노출] book_id=100', output)

    def test_reports_permission_reason_for_blocked_user(self):
        exit_code, output = self.run_diagnose(2)

        self.assertEqual(exit_code, 1)
        self.assertIn('[제외] book_id=100', output)
        self.assertIn('사용자 카테고리 권한 없음', output)


if __name__ == '__main__':
    unittest.main()