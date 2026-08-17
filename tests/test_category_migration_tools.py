import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import export_category, import_category


SCHEMA = """
CREATE TABLE libraries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, physical_path TEXT,
    cron_schedule TEXT, last_scanned_at TEXT, scan_status TEXT DEFAULT 'ready',
    is_remote INTEGER DEFAULT 0, vfs_refresh_before_scan INTEGER DEFAULT 0,
    rclone_rc_url TEXT, icon TEXT, color TEXT, hide_cover INTEGER DEFAULT 0,
    group_id INTEGER DEFAULT NULL, sort_order INTEGER DEFAULT 0
);
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT, library_id INTEGER, title TEXT,
    series_name TEXT, author TEXT, isbn TEXT, file_path TEXT UNIQUE,
    file_format TEXT, total_pages INTEGER, has_offsets INTEGER DEFAULT 0,
    cover_image TEXT, publisher TEXT, link TEXT, score INTEGER, release_date TEXT,
    summary TEXT, genre TEXT, tags TEXT, is_favorite INTEGER DEFAULT 0,
    cover_updated_at TEXT, created_at TEXT, is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT, metadata_locked INTEGER DEFAULT 0, series_alias TEXT,
    title_alias TEXT, file_mtime REAL DEFAULT 0, file_size INTEGER DEFAULT 0
);
CREATE TABLE book_offsets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER, page_idx INTEGER,
    filename TEXT, local_header_offset INTEGER, compress_size INTEGER,
    file_size INTEGER, compress_type INTEGER
);
CREATE TABLE user_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER, user_id INTEGER,
    pages_read INTEGER, is_completed INTEGER, last_read_at TEXT,
    last_epub_cfi TEXT, last_epub_href TEXT, last_epub_spine_index INTEGER,
    last_epub_percent INTEGER, last_epub_fingerprint TEXT,
    last_epub_updated_at TEXT, UNIQUE(book_id, user_id)
);
CREATE TABLE user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, book_id INTEGER,
    created_at TEXT, UNIQUE(user_id, book_id)
);
CREATE TABLE series_summary (
    library_id INTEGER, series_key TEXT, representative_book_id INTEGER,
    series_book_count INTEGER, sort_series_name TEXT,
    PRIMARY KEY(library_id, series_key)
);
CREATE TABLE series_summary_state (
    id INTEGER PRIMARY KEY, is_ready INTEGER, refreshed_at TEXT
);
CREATE TABLE audiobooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, library_id INTEGER, title TEXT,
    sort_title TEXT, web_id TEXT, author TEXT, publisher TEXT, code TEXT,
    poster TEXT, premiered TEXT, ratings REAL, author_intro TEXT,
    description TEXT, folder_name TEXT, folder_path TEXT UNIQUE,
    total_duration REAL, total_tracks INTEGER, file_type TEXT,
    is_favorite INTEGER, created_at TEXT, updated_at TEXT,
    is_deleted INTEGER DEFAULT 0, deleted_at TEXT
);
CREATE TABLE audiobook_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, audiobook_id INTEGER,
    track_number INTEGER, track_code TEXT, filename TEXT,
    file_path TEXT UNIQUE, file_mtime REAL, file_size INTEGER,
    duration REAL, format TEXT
);
CREATE TABLE audiobook_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, audiobook_id INTEGER, user_id INTEGER,
    current_track_id INTEGER, current_time REAL, total_progress_pct REAL,
    playback_rate REAL, is_completed INTEGER, last_listened_at TEXT,
    UNIQUE(audiobook_id, user_id)
);
CREATE TABLE audiobook_track_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, audiobook_id INTEGER,
    track_id INTEGER, user_id INTEGER, current_time REAL,
    progress_pct REAL, is_completed INTEGER, updated_at TEXT,
    UNIQUE(audiobook_id, track_id, user_id)
);
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, library_id INTEGER, title TEXT,
    sort_title TEXT, web_id TEXT, genres TEXT, poster TEXT, backdrop TEXT,
    premiered TEXT, description TEXT, folder_name TEXT, folder_path TEXT UNIQUE,
    total_duration REAL, total_episodes INTEGER, is_favorite INTEGER DEFAULT 0,
    created_at TEXT, updated_at TEXT, is_deleted INTEGER DEFAULT 0, deleted_at TEXT
);
CREATE TABLE video_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER,
    episode_number INTEGER, episode_code TEXT, title TEXT, filename TEXT,
    file_path TEXT UNIQUE, file_mtime REAL, file_size INTEGER, duration REAL,
    width INTEGER, height INTEGER, premiered TEXT, format TEXT,
    needs_transcode INTEGER DEFAULT 0, subtitle_path TEXT
);
CREATE TABLE video_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER, user_id INTEGER,
    current_episode_id INTEGER, current_time REAL, total_progress_pct REAL,
    playback_rate REAL, is_completed INTEGER, last_watched_at TEXT,
    UNIQUE(video_id, user_id)
);
CREATE TABLE video_episode_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER,
    episode_id INTEGER, user_id INTEGER, current_time REAL,
    progress_pct REAL, is_completed INTEGER, updated_at TEXT,
    UNIQUE(video_id, episode_id, user_id)
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


class CategoryMigrationToolsTest(unittest.TestCase):
    def test_book_category_v2_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._run_book_category_v2_round_trip(Path(temp_dir))

    def _run_book_category_v2_round_trip(self, tmp_path):
        source_db = tmp_path / "source.db"
        target_db = tmp_path / "target.db"
        source = connect(source_db)
        source.executescript(SCHEMA)
        source.execute(
            """
            INSERT INTO libraries (
                name, physical_path, scan_status, is_remote,
                vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover,
                group_id, sort_order
            ) VALUES ('Source', ?, 'ready', 1, 1, 'http://localhost:5572', 'fa-book', '#123456', 1, 7, 3)
            """,
            (str(tmp_path / "source_media"),),
        )
        source.execute(
            """
            INSERT INTO books (
                library_id, title, series_name, file_path, file_format, total_pages,
                series_alias, title_alias, created_at
            ) VALUES (1, 'Book', 'Series', ?, 'zip', 100, 'Series Alias', 'Title Alias', '2026-08-08 10:00:00')
            """,
            (str(tmp_path / "source_media" / "book.zip"),),
        )
        source.execute(
            "INSERT INTO user_progress (book_id, user_id, pages_read, is_completed) VALUES (1, 1, 95, 1)"
        )
        source.execute(
            "INSERT INTO user_favorites (user_id, book_id, created_at) VALUES (1, 1, '2026-08-08 11:00:00')"
        )
        source.commit()
        source.close()

        target = connect(target_db)
        target.executescript(SCHEMA)
        target.execute(
            "INSERT INTO series_summary_state (id, is_ready, refreshed_at) VALUES (1, 1, '2026-08-08 09:00:00')"
        )
        target.commit()
        target.close()

        package_path = tmp_path / "category.oasis.zip"
        with mock.patch.object(export_category, "BASE_DIR", str(tmp_path / "source_root")), mock.patch.object(
            export_category,
            "get_db_connection",
            side_effect=lambda _db_type: connect(source_db),
        ):
            self.assertTrue(
                export_category.export_single_category("general", 1, str(package_path))
            )

        with zipfile.ZipFile(package_path) as package:
            manifest = json.loads(package.read("manifest.json"))
        self.assertEqual(manifest["export_version"], "2.0")
        self.assertEqual(manifest["user_progress_count"], 1)

        with mock.patch.object(import_category, "BASE_DIR", str(tmp_path / "target_root")), mock.patch.object(
            import_category,
            "get_db_connection",
            side_effect=lambda _db_type: connect(target_db),
        ):
            import_category.import_category(
                str(package_path),
                [str(tmp_path / "target_media")],
                db_type="general",
                name="Imported",
            )

        result = connect(target_db)
        book = result.execute(
            "SELECT series_alias, title_alias FROM books WHERE title = 'Book'"
        ).fetchone()
        progress = result.execute(
            "SELECT pages_read, is_completed FROM user_progress"
        ).fetchone()
        favorite_count = result.execute("SELECT COUNT(*) FROM user_favorites").fetchone()[0]
        summary_state = result.execute(
            "SELECT is_ready FROM series_summary_state WHERE id = 1"
        ).fetchone()[0]
        imported_library = result.execute(
            "SELECT group_id, sort_order FROM libraries WHERE name = 'Imported'"
        ).fetchone()
        result.close()

        self.assertEqual(tuple(book), ("Series Alias", "Title Alias"))
        self.assertEqual(tuple(progress), (95, 1))
        self.assertEqual(favorite_count, 1)
        self.assertEqual(summary_state, 0)
        self.assertEqual(tuple(imported_library), (7, 3))

    def test_audiobook_category_v2_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            source_db = tmp_path / "source_audio.db"
            target_db = tmp_path / "target_audio.db"
            source = connect(source_db)
            source.executescript(SCHEMA)
            source.execute(
                "INSERT INTO libraries (name, physical_path) VALUES ('Audio', ?)",
                (str(tmp_path / "source_audio"),),
            )
            source.execute(
                """
                INSERT INTO audiobooks (
                    library_id, title, web_id, folder_name, folder_path,
                    total_duration, total_tracks, file_type, is_deleted
                ) VALUES (1, 'Audiobook', 'WEB-1', 'Audiobook', ?, 100, 1, 'multi', 0)
                """,
                (str(tmp_path / "source_audio" / "Audiobook"),),
            )
            source.execute(
                """
                INSERT INTO audiobook_tracks (
                    audiobook_id, track_number, filename, file_path,
                    duration, format
                ) VALUES (1, 1, '01.mp3', ?, 100, 'mp3')
                """,
                (str(tmp_path / "source_audio" / "Audiobook" / "01.mp3"),),
            )
            source.execute(
                """
                INSERT INTO audiobook_progress (
                    audiobook_id, user_id, current_track_id, current_time,
                    total_progress_pct, playback_rate, is_completed
                ) VALUES (1, 1, 1, 95, 95, 1, 0)
                """
            )
            source.execute(
                """
                INSERT INTO audiobook_track_progress (
                    audiobook_id, track_id, user_id, current_time,
                    progress_pct, is_completed
                ) VALUES (1, 1, 1, 95, 95, 1)
                """
            )
            source.commit()
            source.close()

            target = connect(target_db)
            target.executescript(SCHEMA)
            target.commit()
            target.close()

            package_path = tmp_path / "audio.oasis.zip"
            with mock.patch.object(export_category, "BASE_DIR", str(tmp_path / "source_root")), mock.patch.object(
                export_category,
                "get_db_connection",
                side_effect=lambda _db_type: connect(source_db),
            ):
                self.assertTrue(
                    export_category.export_single_category("audiobook", 1, str(package_path))
                )

            with mock.patch.object(import_category, "BASE_DIR", str(tmp_path / "target_root")), mock.patch.object(
                import_category,
                "get_db_connection",
                side_effect=lambda _db_type: connect(target_db),
            ):
                import_category.import_category(
                    str(package_path),
                    [str(tmp_path / "target_audio")],
                    db_type="audiobook",
                    name="Imported Audio",
                )

            result = connect(target_db)
            audiobook = result.execute(
                "SELECT web_id FROM audiobooks WHERE title = 'Audiobook'"
            ).fetchone()
            track = result.execute(
                "SELECT filename FROM audiobook_tracks WHERE track_number = 1"
            ).fetchone()
            progress = result.execute(
                "SELECT progress_pct, is_completed FROM audiobook_track_progress"
            ).fetchone()
            result.close()

            self.assertEqual(audiobook['web_id'], 'WEB-1')
            self.assertEqual(track['filename'], '01.mp3')
            self.assertEqual(tuple(progress), (95.0, 1))

    def test_video_category_v2_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            source_db = tmp_path / "source_video.db"
            target_db = tmp_path / "target_video.db"
            source = connect(source_db)
            source.executescript(SCHEMA)
            source.execute(
                "INSERT INTO libraries (name, physical_path) VALUES ('Video', ?)",
                (str(tmp_path / "source_video"),),
            )
            source.execute(
                """
                INSERT INTO videos (
                    library_id, title, web_id, folder_name, folder_path,
                    total_duration, total_episodes, is_deleted
                ) VALUES (1, 'Course', 'WEB-V1', 'Course', ?, 200, 1, 0)
                """,
                (str(tmp_path / "source_video" / "Course"),),
            )
            source.execute(
                """
                INSERT INTO video_episodes (
                    video_id, episode_number, filename, file_path,
                    duration, format
                ) VALUES (1, 1, 'S01E01.mp4', ?, 200, 'mp4')
                """,
                (str(tmp_path / "source_video" / "Course" / "S01E01.mp4"),),
            )
            source.execute(
                """
                INSERT INTO video_progress (
                    video_id, user_id, current_episode_id, current_time,
                    total_progress_pct, playback_rate, is_completed
                ) VALUES (1, 1, 1, 95, 95, 1, 0)
                """
            )
            source.execute(
                """
                INSERT INTO video_episode_progress (
                    video_id, episode_id, user_id, current_time,
                    progress_pct, is_completed
                ) VALUES (1, 1, 1, 95, 95, 1)
                """
            )
            source.commit()
            source.close()

            target = connect(target_db)
            target.executescript(SCHEMA)
            target.commit()
            target.close()

            package_path = tmp_path / "video.oasis.zip"
            with mock.patch.object(export_category, "BASE_DIR", str(tmp_path / "source_root")), mock.patch.object(
                export_category,
                "get_db_connection",
                side_effect=lambda _db_type: connect(source_db),
            ):
                self.assertTrue(
                    export_category.export_single_category("video", 1, str(package_path))
                )

            with zipfile.ZipFile(package_path) as package:
                manifest = json.loads(package.read("manifest.json"))
            self.assertEqual(manifest["media_kind"], "video")
            self.assertEqual(manifest["videos_count"], 1)
            self.assertEqual(manifest["video_episodes_count"], 1)

            with mock.patch.object(import_category, "BASE_DIR", str(tmp_path / "target_root")), mock.patch.object(
                import_category,
                "get_db_connection",
                side_effect=lambda _db_type: connect(target_db),
            ):
                import_category.import_category(
                    str(package_path),
                    [str(tmp_path / "target_video")],
                    db_type="video",
                    name="Imported Video",
                )

            result = connect(target_db)
            video = result.execute(
                "SELECT web_id FROM videos WHERE title = 'Course'"
            ).fetchone()
            episode = result.execute(
                "SELECT id, filename FROM video_episodes WHERE episode_number = 1"
            ).fetchone()
            progress = result.execute(
                "SELECT progress_pct, is_completed FROM video_episode_progress"
            ).fetchone()
            video_progress = result.execute(
                "SELECT current_episode_id FROM video_progress"
            ).fetchone()
            result.close()

            self.assertEqual(video['web_id'], 'WEB-V1')
            self.assertEqual(episode['filename'], 'S01E01.mp4')
            self.assertEqual(tuple(progress), (95.0, 1))
            self.assertEqual(video_progress['current_episode_id'], episode['id'])


if __name__ == "__main__":
    unittest.main()