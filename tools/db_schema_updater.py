# -*- coding: utf-8 -*-
"""
db_schema_updater.py - 데이터베이스 스키마 단일 관리(Single Source of Truth) 및 동기화 도구
"""
import os
import sys
import sqlite3
import re
import html

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k not in os.environ:
                    os.environ[k] = v

try:
    import database
    from database import (
        DB_GENERAL_PATH,
        DB_ADULT_PATH,
        DB_AUDIOBOOK_PATH,
        DB_VIDEO_PATH,
        init_databases,
        get_connection,
        auto_migrate_schema,
        cleanup_legacy_fts_index,
        _SCHEMA_SQL,
        _INDEXES_SQL
    )
except ImportError as e:
    print(f"[오류] database.py 모듈을 임포트할 수 없습니다: {e}")
    sys.exit(1)

# ==============================================================================
# MariaDB 중앙 스키마 정의 (Single Source of Truth)
# ==============================================================================
MARIADB_CENTRAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    icon VARCHAR(100) DEFAULT 'fa-folder',
    color VARCHAR(50) DEFAULT '#a855f7',
    sort_order INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS libraries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    physical_path TEXT NOT NULL,
    cron_schedule VARCHAR(255) DEFAULT NULL,
    schedule_enabled TINYINT(1) NOT NULL DEFAULT 1,
    last_scanned_at DATETIME DEFAULT NULL,
    scan_status VARCHAR(50) DEFAULT 'ready',
    is_remote INT DEFAULT 0,
    vfs_refresh_before_scan INT DEFAULT 0,
    rclone_rc_url TEXT DEFAULT NULL,
    icon VARCHAR(100) DEFAULT 'fa-book',
    color VARCHAR(50) DEFAULT '#94a3b8',
    hide_cover INT DEFAULT 0,
    group_id BIGINT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    gdrive_copy_remote VARCHAR(255) DEFAULT NULL,
    gdrive_view_local_mirror_path TEXT DEFAULT NULL,
    INDEX idx_libraries_group_id (group_id),
    INDEX idx_libraries_group_order (group_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS plugin_group_assignments (
    plugin_id VARCHAR(255) PRIMARY KEY,
    group_id BIGINT NOT NULL,
    sort_order INT DEFAULT 0,
    INDEX idx_plugin_group_assignments_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scanner_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_key VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    kwargs TEXT,
    stage TEXT,
    worker_pid INT DEFAULT NULL,
    enqueue_at VARCHAR(50),
    started_at VARCHAR(50),
    finished_at VARCHAR(50),
    error_message TEXT,
    cancel_requested INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS books (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    series_name VARCHAR(500),
    author VARCHAR(500),
    isbn VARCHAR(100),
    file_path TEXT NOT NULL,
    file_format VARCHAR(50) NOT NULL,
    total_pages INT NOT NULL DEFAULT 0,
    has_offsets INT DEFAULT 0,
    cover_image TEXT,
    publisher VARCHAR(255),
    link TEXT,
    score INT,
    release_date VARCHAR(100),
    summary TEXT,
    genre VARCHAR(255),
    tags TEXT,
    is_favorite INT DEFAULT 0,
    cover_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    metadata_locked INT DEFAULT 0,
    series_alias VARCHAR(500),
    title_alias VARCHAR(500),
    file_mtime DOUBLE DEFAULT 0.0,
    file_size BIGINT DEFAULT 0,
    cover_align VARCHAR(10) DEFAULT 'center',
    UNIQUE KEY uq_books_file_path (file_path(500)),
    INDEX idx_books_series_name (series_name(255)),
    INDEX idx_books_series_alias (series_alias(255)),
    INDEX idx_books_library_id (library_id),
    INDEX idx_books_title (title(255)),
    INDEX idx_books_isbn (isbn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS series_summary (
    library_id BIGINT NOT NULL,
    series_key VARCHAR(500) NOT NULL,
    representative_book_id BIGINT NOT NULL,
    series_book_count BIGINT NOT NULL DEFAULT 0,
    sort_series_name VARCHAR(500) NOT NULL DEFAULT '',
    PRIMARY KEY (library_id, series_key),
    INDEX idx_series_summary_order (library_id, sort_series_name, representative_book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS series_summary_state (
    id TINYINT NOT NULL PRIMARY KEY,
    is_ready TINYINT NOT NULL DEFAULT 0,
    refreshed_at DATETIME DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobooks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    sort_title VARCHAR(500),
    web_id VARCHAR(100),
    author VARCHAR(500),
    publisher VARCHAR(255),
    code VARCHAR(255),
    poster TEXT,
    premiered VARCHAR(100),
    ratings DOUBLE DEFAULT 0.0,
    author_intro TEXT,
    description TEXT,
    folder_name VARCHAR(500) NOT NULL,
    folder_path TEXT NOT NULL,
    total_duration DOUBLE DEFAULT 0.0,
    total_tracks INT DEFAULT 1,
    file_type VARCHAR(50) DEFAULT 'multi',
    is_favorite INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    UNIQUE KEY uq_audiobooks_folder_path (folder_path(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_tracks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    track_number INT NOT NULL,
    track_code VARCHAR(100),
    title VARCHAR(500),
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_mtime DOUBLE DEFAULT 0.0,
    file_size BIGINT DEFAULT 0,
    duration DOUBLE DEFAULT 0.0,
    format VARCHAR(50) DEFAULT 'mp3',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tracks_file_path (file_path(500)),
    INDEX idx_tracks_audiobook (audiobook_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    current_track_id BIGINT,
    `current_time` DOUBLE DEFAULT 0.0,
    total_progress_pct DOUBLE DEFAULT 0.0,
    playback_rate DOUBLE DEFAULT 1.0,
    is_completed INT DEFAULT 0,
    last_listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_audiobook_user_progress (audiobook_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS audiobook_track_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    track_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    `current_time` DOUBLE DEFAULT 0.0,
    progress_pct DOUBLE DEFAULT 0.0,
    is_completed INT DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_audiobook_track_user_progress (audiobook_id, track_id, user_id),
    INDEX idx_audiobook_track_progress_lookup (audiobook_id, user_id, track_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS videos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    sort_title VARCHAR(500),
    web_id VARCHAR(100),
    genres VARCHAR(500),
    poster TEXT,
    backdrop TEXT,
    premiered VARCHAR(100),
    description TEXT,
    folder_name VARCHAR(500) NOT NULL,
    folder_path TEXT NOT NULL,
    total_duration DOUBLE DEFAULT 0.0,
    total_episodes INT DEFAULT 0,
    is_favorite INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    UNIQUE KEY uq_videos_folder_path (folder_path(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS video_episodes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT NOT NULL,
    episode_number INT NOT NULL,
    episode_code VARCHAR(50),
    title VARCHAR(500),
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_mtime DOUBLE DEFAULT 0.0,
    file_size BIGINT DEFAULT 0,
    duration DOUBLE DEFAULT 0.0,
    width INT DEFAULT 0,
    height INT DEFAULT 0,
    premiered VARCHAR(100),
    format VARCHAR(50) DEFAULT 'mp4',
    needs_transcode INT DEFAULT 0,
    subtitle_path TEXT,
    container_verified INT DEFAULT 0,
    UNIQUE KEY uq_video_episodes_file_path (file_path(500)),
    INDEX idx_video_episodes_video_id (video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS video_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    current_episode_id BIGINT,
    `current_time` DOUBLE DEFAULT 0.0,
    total_progress_pct DOUBLE DEFAULT 0.0,
    playback_rate DOUBLE DEFAULT 1.0,
    is_completed INT DEFAULT 0,
    last_watched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_video_user_progress (video_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS video_episode_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT NOT NULL,
    episode_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL DEFAULT 1,
    `current_time` DOUBLE DEFAULT 0.0,
    progress_pct DOUBLE DEFAULT 0.0,
    is_completed INT DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_video_episode_user_progress (video_id, episode_id, user_id),
    INDEX idx_video_episode_progress_lookup (video_id, user_id, episode_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_progress (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    pages_read INT DEFAULT 0,
    is_completed INT DEFAULT 0,
    last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_epub_cfi TEXT,
    last_epub_href TEXT,
    last_epub_spine_index INT,
    last_epub_percent INT DEFAULT 0,
    last_epub_fingerprint VARCHAR(255),
    last_epub_updated_at DATETIME,
    UNIQUE KEY uq_user_book_progress (book_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_reading_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    pages_read_delta INT NOT NULL,
    duration_seconds INT DEFAULT 0,
    read_date DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS book_annotations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    format VARCHAR(20) NOT NULL,
    chapter_idx INT,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    quote TEXT NOT NULL,
    prefix TEXT,
    suffix TEXT,
    color VARCHAR(20) DEFAULT '#fbbf24',
    note TEXT,
    plugin_marker VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_book_annotations_book_user (book_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS epub_bookmarks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    format VARCHAR(20) NOT NULL,
    chapter_idx INT NOT NULL,
    percent INT DEFAULT 0,
    label VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_epub_bookmarks_book_user (book_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_favorite (user_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS book_offsets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    page_idx INT,
    filename VARCHAR(500),
    local_header_offset BIGINT,
    compress_size BIGINT,
    file_size BIGINT,
    compress_type INT,
    data_offset BIGINT,
    INDEX idx_offsets_book (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS gdrive_book_copies (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL UNIQUE,
    library_id BIGINT NOT NULL,
    source_file_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    local_path TEXT,
    error_message TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_gdrive_book_copies_library (library_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(255) PRIMARY KEY,
    `value` TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scan_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_key VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    kwargs TEXT,
    enqueue_at VARCHAR(50),
    started_at VARCHAR(50),
    finished_at VARCHAR(50),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS scanner_progress (
    library_id VARCHAR(100),
    folder_path VARCHAR(500) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS folder_mtimes (
    folder_path VARCHAR(500) PRIMARY KEY,
    dir_mtime DOUBLE,
    meta_mtime DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_default_password INT DEFAULT 1,
    has_adult_access INT DEFAULT 1,
    has_audiobook_access INT DEFAULT 1,
    has_video_access INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS user_category_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    library_id BIGINT NOT NULL,
    has_access INT DEFAULT 1,
    UNIQUE KEY uq_user_cat_perm (user_id, library_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS collections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    color VARCHAR(50) DEFAULT '#7c3aed',
    cover_image TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_collections_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS collection_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    collection_id BIGINT NOT NULL,
    book_id BIGINT DEFAULT NULL,
    series_name VARCHAR(500) DEFAULT NULL,
    audiobook_id BIGINT DEFAULT NULL,
    video_id BIGINT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_coll_book (collection_id, book_id),
    UNIQUE KEY uq_coll_series (collection_id, series_name(255)),
    UNIQUE KEY uq_coll_audiobook (collection_id, audiobook_id),
    UNIQUE KEY uq_coll_video (collection_id, video_id),
    INDEX idx_collection_items_coll (collection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS plugin_load_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plugin_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT DEFAULT NULL,
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_plugin_load_events_plugin_time (plugin_id, occurred_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
"""


def _backfill_audiobook_last_listened_at_sqlite(conn):
    """SQLite audiobook_progress의 last_listened_at 누락분 보정"""
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE audiobook_progress
            SET last_listened_at = COALESCE(
                (SELECT a.updated_at FROM audiobooks a WHERE a.id = audiobook_progress.audiobook_id),
                CURRENT_TIMESTAMP
            )
            WHERE (last_listened_at IS NULL OR TRIM(COALESCE(last_listened_at, '')) = '')
              AND (COALESCE(current_time, 0) > 0 OR COALESCE(is_completed, 0) = 1)
        """)
        conn.commit()
        changed = cur.rowcount or 0
        if changed > 0:
            print(f"  [+] SQLite audiobook_progress last_listened_at 보정 완료: {changed}건")
    except Exception as e:
        print(f"  [경고] SQLite audiobook_progress last_listened_at 보정 실패: {e}")


def _backfill_html_entities_video_titles_sqlite(conn):
    """videos.title/description, video_episodes.title에 남아있는 미해제 HTML 엔티티
    (예: '&lt;강좌명&gt;')를 1회성으로 정리한다.

    show.yaml을 생성하는 외부(커뮤니티) 스크래핑 도구 상당수가 강좌 플랫폼 웹페이지에서
    긁어온 제목/설명의 HTML 엔티티를 디코딩하지 않고 그대로 저장해, 이미 스캔된 기존
    데이터에 '&lt;', '&amp;', '&#x27;' 같은 원문이 섞여 있는 경우가 있었다. video_scanner.py의
    show.yaml 파싱 단계는 이제 html.unescape()를 적용하지만, 그건 앞으로의 신규 스캔에만
    적용되므로 이미 저장된 기존 행은 별도로 여기서 보정해야 한다."""
    try:
        cur = conn.cursor()
        changed = 0
        cur.execute("SELECT id, title, description FROM videos WHERE title LIKE '%&%;%' OR description LIKE '%&%;%'")
        for row in cur.fetchall():
            new_title = html.unescape(row['title'] or '')
            new_desc = html.unescape(row['description'] or '')
            if new_title != row['title'] or new_desc != row['description']:
                cur.execute("UPDATE videos SET title = ?, description = ? WHERE id = ?", (new_title, new_desc, row['id']))
                changed += 1
        conn.commit()

        ep_changed = 0
        cur.execute("SELECT id, title FROM video_episodes WHERE title LIKE '%&%;%'")
        for row in cur.fetchall():
            new_title = html.unescape(row['title'] or '')
            if new_title != row['title']:
                cur.execute("UPDATE video_episodes SET title = ? WHERE id = ?", (new_title, row['id']))
                ep_changed += 1
        conn.commit()

        if changed > 0 or ep_changed > 0:
            print(f"  [+] SQLite video HTML 엔티티 제목 보정 완료: videos {changed}건, video_episodes {ep_changed}건")
    except Exception as e:
        print(f"  [경고] SQLite video HTML 엔티티 제목 보정 실패: {e}")


def _backfill_html_entities_video_titles_mariadb():
    """videos.title/description, video_episodes.title의 미해제 HTML 엔티티를 1회성으로 정리한다
    (SQLite 버전과 동일한 이유 — 위 _backfill_html_entities_video_titles_sqlite 참고)."""
    try:
        from tools.migrator_sqlite_to_mariadb import connect_mariadb
        conn = connect_mariadb('media_video')
        cur = conn.cursor()
        changed = 0
        cur.execute("SELECT id, title, description FROM videos WHERE title LIKE '%&%;%' OR description LIKE '%&%;%'")
        for row in cur.fetchall():
            new_title = html.unescape(row['title'] or '')
            new_desc = html.unescape(row['description'] or '')
            if new_title != row['title'] or new_desc != row['description']:
                cur.execute("UPDATE videos SET title = %s, description = %s WHERE id = %s", (new_title, new_desc, row['id']))
                changed += 1
        conn.commit()

        ep_changed = 0
        cur.execute("SELECT id, title FROM video_episodes WHERE title LIKE '%&%;%'")
        for row in cur.fetchall():
            new_title = html.unescape(row['title'] or '')
            if new_title != row['title']:
                cur.execute("UPDATE video_episodes SET title = %s WHERE id = %s", (new_title, row['id']))
                ep_changed += 1
        conn.commit()

        if changed > 0 or ep_changed > 0:
            print(f"  [+] MariaDB video HTML 엔티티 제목 보정 완료: videos {changed}건, video_episodes {ep_changed}건")
        conn.close()
    except Exception as e:
        print(f"  [경고] MariaDB video HTML 엔티티 제목 보정 실패: {e}")


def _backfill_audiobook_last_listened_at_mariadb():
    """MariaDB audiobook_progress의 last_listened_at 누락분 보정"""
    try:
        from tools.migrator_sqlite_to_mariadb import connect_mariadb
        conn = connect_mariadb('media_audiobook')
        cur = conn.cursor()
        cur.execute("""
            UPDATE audiobook_progress p
            LEFT JOIN audiobooks a ON a.id = p.audiobook_id
            SET p.last_listened_at = COALESCE(a.updated_at, CURRENT_TIMESTAMP)
            WHERE (p.last_listened_at IS NULL OR TRIM(CAST(p.last_listened_at AS CHAR)) = '' OR p.last_listened_at = '0000-00-00 00:00:00')
              AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
        """)
        conn.commit()
        changed = cur.rowcount or 0
        if changed > 0:
            print(f"  [+] MariaDB audiobook_progress last_listened_at 보정 완료: {changed}건")
        conn.close()
    except Exception as e:
        print(f"  [경고] MariaDB audiobook_progress last_listened_at 보정 실패: {e}")

    col_collations = [
        ('media_general', 'books', 'file_path', 'VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL'),
        ('media_adult', 'books', 'file_path', 'VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL'),
        ('media_audiobook', 'audiobooks', 'folder_path', 'VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL'),
    ]
    for db_name, tbl, col_name, col_def in col_collations:
        try:
            conn = connect_mariadb(db_name)
            cur = conn.cursor()
            cur.execute(f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col_name}` {col_def}")
            conn.commit()
            conn.close()
        except Exception:
            pass


def _ensure_mariadb_columns():
    """기존 MariaDB 데이터베이스의 테이블에 누락된 필수 컬럼 자동 ALTER TABLE 보강"""
    from tools.migrator_sqlite_to_mariadb import connect_mariadb

    # 구형 tracks 테이블 RENAME 처리
    try:
        conn = connect_mariadb('media_audiobook')
        cur = conn.cursor()
        cur.execute("SHOW TABLES LIKE 'tracks'")
        has_old = bool(cur.fetchone())
        cur.execute("SHOW TABLES LIKE 'audiobook_tracks'")
        has_new = bool(cur.fetchone())
        if has_old and not has_new:
            cur.execute("RENAME TABLE `tracks` TO `audiobook_tracks`")
            conn.commit()
            print("  [+] MariaDB 구형 테이블 `tracks` ➔ `audiobook_tracks` 자동 RENAME 완료.")
        conn.close()
    except Exception as e:
        print(f"  [!] MariaDB 구형 테이블 RENAME 검사 중 오류: {e}")

    required_columns = [
        ('media_general', 'libraries', 'group_id', 'BIGINT DEFAULT NULL'),
        ('media_adult', 'libraries', 'group_id', 'BIGINT DEFAULT NULL'),
        ('media_audiobook', 'libraries', 'group_id', 'BIGINT DEFAULT NULL'),
        ('media_general', 'libraries', 'sort_order', 'INT DEFAULT 0'),
        ('media_adult', 'libraries', 'sort_order', 'INT DEFAULT 0'),
        ('media_audiobook', 'libraries', 'sort_order', 'INT DEFAULT 0'),
        ('media_general', 'libraries', 'gdrive_copy_remote', 'VARCHAR(255) DEFAULT NULL'),
        ('media_adult', 'libraries', 'gdrive_copy_remote', 'VARCHAR(255) DEFAULT NULL'),
        ('media_audiobook', 'libraries', 'gdrive_copy_remote', 'VARCHAR(255) DEFAULT NULL'),
        ('media_general', 'libraries', 'gdrive_view_local_mirror_path', 'TEXT'),
        ('media_adult', 'libraries', 'gdrive_view_local_mirror_path', 'TEXT'),
        ('media_audiobook', 'libraries', 'gdrive_view_local_mirror_path', 'TEXT'),
        ('media_audiobook', 'audiobooks', 'code', 'VARCHAR(255)'),
        ('media_audiobook', 'audiobooks', 'poster', 'TEXT'),
        ('media_audiobook', 'audiobooks', 'premiered', 'VARCHAR(100)'),
        ('media_audiobook', 'audiobooks', 'ratings', 'VARCHAR(50)'),
        ('media_audiobook', 'audiobooks', 'author_intro', 'TEXT'),
        ('media_audiobook', 'audiobooks', 'folder_name', 'VARCHAR(500)'),
        ('media_audiobook', 'audiobooks', 'file_type', 'VARCHAR(50)'),
        ('media_audiobook', 'audiobooks', 'deleted_at', 'DATETIME DEFAULT NULL'),
        ('media_audiobook', 'audiobook_tracks', 'track_code', 'VARCHAR(100)'),
        ('media_audiobook', 'audiobook_tracks', 'filename', 'VARCHAR(500)'),
        ('media_audiobook', 'audiobook_tracks', 'file_mtime', 'DOUBLE DEFAULT 0.0'),
        ('media_audiobook', 'audiobook_tracks', 'format', 'VARCHAR(50)'),
        ('media_general', 'books', 'series_alias', 'VARCHAR(500)'),
        ('media_general', 'books', 'title_alias', 'VARCHAR(500)'),
        ('media_general', 'books', 'file_mtime', 'DOUBLE DEFAULT 0.0'),
        ('media_general', 'books', 'file_size', 'BIGINT DEFAULT 0'),
        ('media_general', 'books', 'cover_align', "VARCHAR(10) DEFAULT 'center'"),
        ('media_adult', 'books', 'series_alias', 'VARCHAR(500)'),
        ('media_adult', 'books', 'title_alias', 'VARCHAR(500)'),
        ('media_adult', 'books', 'file_mtime', 'DOUBLE DEFAULT 0.0'),
        ('media_adult', 'books', 'file_size', 'BIGINT DEFAULT 0'),
        ('media_adult', 'books', 'cover_align', "VARCHAR(10) DEFAULT 'center'"),
        ('media_general', 'collections', 'updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('media_adult', 'collections', 'updated_at', 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('media_general', 'users', 'has_video_access', 'INT DEFAULT 1'),
        ('media_adult', 'users', 'has_video_access', 'INT DEFAULT 1'),
        ('media_audiobook', 'users', 'has_video_access', 'INT DEFAULT 1'),
        ('media_general', 'collection_items', 'video_id', 'BIGINT DEFAULT NULL'),
        ('media_adult', 'collection_items', 'video_id', 'BIGINT DEFAULT NULL'),
        ('media_audiobook', 'collection_items', 'video_id', 'BIGINT DEFAULT NULL'),
        ('media_video', 'video_episodes', 'needs_transcode', 'INT DEFAULT 0'),
        ('media_video', 'video_episodes', 'subtitle_path', 'TEXT'),
        ('media_video', 'video_episodes', 'container_verified', 'INT DEFAULT 0'),
        ('media_general', 'epub_bookmarks', 'percent', 'INT DEFAULT 0'),
        ('media_adult', 'epub_bookmarks', 'percent', 'INT DEFAULT 0'),
        ('media_general', 'book_offsets', 'data_offset', 'BIGINT DEFAULT NULL'),
        ('media_adult', 'book_offsets', 'data_offset', 'BIGINT DEFAULT NULL'),
    ]

    for db_name, tbl, col_name, col_def in required_columns:
        try:
            conn = connect_mariadb(db_name)
            cur = conn.cursor()
            cur.execute(f"SHOW COLUMNS FROM `{tbl}` WHERE Field = %s", (col_name,))
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE `{tbl}` ADD COLUMN `{col_name}` {col_def}")
                conn.commit()
                print(f"  [+] MariaDB 누락 컬럼 자동 보강 완료: `{db_name}`.`{tbl}`.{col_name}")
            conn.close()
        except Exception as e:
            print(f"  [!] MariaDB 컬럼 보강 실패: `{db_name}`.`{tbl}`.{col_name} ({col_def}) -> {e}")

    # 구버전(테이블명이 `tracks`였던 시절)부터 계속 업그레이드해온 DB는 audiobook_tracks.title이
    # 그 시절 정의(NOT NULL, 기본값 없음) 그대로 남아있을 수 있다. 현재 앱은 트랙을 filename으로
    # 표시하며 INSERT 시 title을 채우지 않으므로, 이런 구형 컬럼이 남아있는 DB에서는 신규 오디오북을
    # 추가할 때마다 (1364, "Field 'title' doesn't have a default value")로 저장이 실패한다.
    legacy_column_relaxations = [
        ('media_audiobook', 'audiobook_tracks', 'title', 'VARCHAR(500) NULL'),
    ]
    for db_name, tbl, col_name, new_col_def in legacy_column_relaxations:
        try:
            conn = connect_mariadb(db_name)
            cur = conn.cursor()
            cur.execute(f"SHOW COLUMNS FROM `{tbl}` WHERE Field = %s", (col_name,))
            row = cur.fetchone()
            if row and str(row.get('Null')).upper() == 'NO' and row.get('Default') is None:
                cur.execute(f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col_name}` {new_col_def}")
                conn.commit()
                print(f"  [+] MariaDB 구형 스키마 보정 완료: `{db_name}`.`{tbl}`.{col_name} (NOT NULL 제약 해제)")
            conn.close()
        except Exception as e:
            print(f"  [!] MariaDB 구형 컬럼 제약 보정 실패: `{db_name}`.`{tbl}`.{col_name} -> {e}")


def _ensure_mariadb_indexes():
    from tools.migrator_sqlite_to_mariadb import connect_mariadb

    required_indexes = [
        ('media_general', 'books', 'idx_books_lib_del_series', 'CREATE INDEX idx_books_lib_del_series ON books (library_id, is_deleted, series_name(255), id)'),
        ('media_general', 'books', 'idx_books_lib_del_title', 'CREATE INDEX idx_books_lib_del_title ON books (library_id, is_deleted, title(255), id)'),
        ('media_adult', 'books', 'idx_books_lib_del_series', 'CREATE INDEX idx_books_lib_del_series ON books (library_id, is_deleted, series_name(255), id)'),
        ('media_adult', 'books', 'idx_books_lib_del_title', 'CREATE INDEX idx_books_lib_del_title ON books (library_id, is_deleted, title(255), id)'),
        ('media_audiobook', 'audiobooks', 'idx_audiobooks_lib_del', 'CREATE INDEX idx_audiobooks_lib_del ON audiobooks (library_id, is_deleted, title(255), id)'),
        ('media_video', 'videos', 'idx_videos_lib_del', 'CREATE INDEX idx_videos_lib_del ON videos (library_id, is_deleted, title(255), id)'),
        ('media_general', 'libraries', 'idx_libraries_group_id', 'CREATE INDEX idx_libraries_group_id ON libraries (group_id)'),
        ('media_adult', 'libraries', 'idx_libraries_group_id', 'CREATE INDEX idx_libraries_group_id ON libraries (group_id)'),
        ('media_audiobook', 'libraries', 'idx_libraries_group_id', 'CREATE INDEX idx_libraries_group_id ON libraries (group_id)'),
        ('media_general', 'libraries', 'idx_libraries_group_order', 'CREATE INDEX idx_libraries_group_order ON libraries (group_id, sort_order)'),
        ('media_adult', 'libraries', 'idx_libraries_group_order', 'CREATE INDEX idx_libraries_group_order ON libraries (group_id, sort_order)'),
        ('media_audiobook', 'libraries', 'idx_libraries_group_order', 'CREATE INDEX idx_libraries_group_order ON libraries (group_id, sort_order)'),
        ('media_general', 'books', 'idx_books_series_name', 'CREATE INDEX idx_books_series_name ON books (series_name(255))'),
        ('media_general', 'books', 'idx_books_series_alias', 'CREATE INDEX idx_books_series_alias ON books (series_alias(255))'),
        ('media_general', 'books', 'idx_books_library_id', 'CREATE INDEX idx_books_library_id ON books (library_id)'),
        ('media_general', 'books', 'idx_books_title', 'CREATE INDEX idx_books_title ON books (title(255))'),
        ('media_general', 'books', 'idx_books_isbn', 'CREATE INDEX idx_books_isbn ON books (isbn)'),
        ('media_adult', 'books', 'idx_books_series_name', 'CREATE INDEX idx_books_series_name ON books (series_name(255))'),
        ('media_adult', 'books', 'idx_books_series_alias', 'CREATE INDEX idx_books_series_alias ON books (series_alias(255))'),
        ('media_adult', 'books', 'idx_books_library_id', 'CREATE INDEX idx_books_library_id ON books (library_id)'),
        ('media_adult', 'books', 'idx_books_title', 'CREATE INDEX idx_books_title ON books (title(255))'),
        ('media_adult', 'books', 'idx_books_isbn', 'CREATE INDEX idx_books_isbn ON books (isbn)'),
    ]

    for db_name, tbl, idx_name, idx_sql in required_indexes:
        try:
            conn = connect_mariadb(db_name)
            cur = conn.cursor()
            cur.execute(f"SHOW INDEX FROM `{tbl}` WHERE Key_name = %s", (idx_name,))
            if not cur.fetchone():
                cur.execute(idx_sql)
                conn.commit()
                print(f"  [+] MariaDB 고속 성능 인덱스 생성 완료: `{db_name}`.`{tbl}`.{idx_name}")
            conn.close()
        except Exception as e:
            print(f"  [!] MariaDB 인덱스 생성 실패: `{db_name}`.`{tbl}`.{idx_name} -> {e}")


def run_schema_update():
    print("=" * 60)
    print(" 데이터베이스 최신 스키마 강제 업데이트 및 동기화 도구")
    print("=" * 60)

    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    if engine in ('mariadb', 'mysql'):
        print("[+] MariaDB 데이터베이스 엔진 모드 구동")
        try:
            from tools.migrator_sqlite_to_mariadb import ensure_mariadb_databases, init_schema, DB_MAP
            ensure_mariadb_databases(reset=False)
            for db_type, config in DB_MAP.items():
                dbname = config['mariadb_db']
                init_schema(db_type, dbname)
            _ensure_mariadb_columns()
            _ensure_mariadb_indexes()
            _backfill_audiobook_last_listened_at_mariadb()
            _backfill_html_entities_video_titles_mariadb()
            print("[+] MariaDB 데이터베이스, 스키마 및 고속 복합 인덱스 검사 완료.")
        except Exception as ex:
            print(f"[!] MariaDB 스키마 검사 중 경고: {ex}")
        return

    # 1. DB 파일 존재 및 경로 확인
    db_paths = {
        '일반 DB (media_general)': DB_GENERAL_PATH,
        '성인 DB (media_adult)': DB_ADULT_PATH,
        '오디오북 DB (media_audiobook)': DB_AUDIOBOOK_PATH,
        '영상 강좌 DB (media_video)': DB_VIDEO_PATH
    }

    for db_name, db_path in db_paths.items():
        print(f"[*] {db_name} 경로 확인: {db_path}")
        if not os.path.exists(db_path):
            print(f"    -> [안내] DB 파일이 아직 존재하지 않습니다. 새로 생성될 예정입니다.")
        else:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"    -> [확인] DB 파일 존재함 (크기: {size_mb:.2f} MB)")

    print("\n[*] 1단계: 데이터베이스 기본 초기화 및 기본 마이그레이션 실행 중...")
    try:
        init_databases()
        print(" -> [성공] 데이터베이스 기본 초기화 완료.")
    except Exception as e:
        print(f" -> [실패] 데이터베이스 초기화 중 오류 발생: {e}")

    print("\n[*] 2단계: 개별 데이터베이스 강제 스키마 갱신 및 WAL 정리 시작...")

    # 예전엔 database.py 소스 텍스트를 정규식(re.search)으로 긁어 schema/indexes_schema
    # 변수를 찾았으나, 이는 database.py의 정확한 변수명에 암묵적으로 의존하는 취약한 결합이었다
    # (실제로 database.py의 init_databases() 리팩터링 중 지역 변수 schema/indexes_schema가
    # 모듈 상수 _SCHEMA_SQL/_INDEXES_SQL로 이름이 바뀌면서 이 정규식이 아무 것도 매칭하지
    # 못해 SQLite 모드의 자동 컬럼 보강/인덱스 생성이 조용히 스킵되는 회귀가 발생했었다).
    # database.py에서 직접 import해서 항상 실제 값과 동기화되도록 수정.
    schema_text = _SCHEMA_SQL
    indexes_text = _INDEXES_SQL

    for db_key, db_path in [('general', DB_GENERAL_PATH), ('adult', DB_ADULT_PATH), ('audiobook', DB_AUDIOBOOK_PATH), ('video', DB_VIDEO_PATH)]:
        if not os.path.exists(db_path):
            continue

        print(f"\n[+] {db_key.upper()} DB 상세 점검 및 마이그레이션:")
        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            print(f"  - DB 연결 및 무결성 확인 중...")
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            print(f"    -> integrity_check 결과: {integrity}")

            if integrity != 'ok':
                print(f"    -> [경고] 무결성 이상이 감지되었습니다! 스키마 동기화에 영향이 있을 수 있습니다.")

            if schema_text:
                print(f"  - 스키마 내 누락 컬럼 자동 탐지 및 추가 중...")
                auto_migrate_schema(conn, schema_text)
                conn.commit()

            if db_key == 'audiobook':
                print(f"  - audiobook_progress last_listened_at 누락분 보정 중...")
                _backfill_audiobook_last_listened_at_sqlite(conn)

            if db_key == 'video':
                print(f"  - video/video_episodes HTML 엔티티 제목 보정 중...")
                _backfill_html_entities_video_titles_sqlite(conn)

            if indexes_text:
                print(f"  - 스키마 내 누락 인덱스 자동 생성 중...")
                for query in indexes_text.split(';'):
                    query = query.strip()
                    if query:
                        try:
                            cursor.execute(query)
                        except sqlite3.OperationalError as idx_err:
                            if "already exists" not in str(idx_err).lower():
                                print(f"    -> 인덱스 생성 에러 ({query[:30]}...): {idx_err}")
                conn.commit()

            print(f"  - 구형 FTS5 가상 테이블 및 그림자 세그먼트 정리 중...")
            try:
                from database import cleanup_legacy_fts_index
                cleanup_legacy_fts_index(conn)
                print(f"    -> 구형 FTS5 가상 테이블 정리 완료.")
            except Exception as fts_err:
                print(f"    -> FTS5 정리 통과: {fts_err}")

            print(f"  - WAL 체크포인트(TRUNCATE) 수행 중...")
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            print(f"    -> WAL 체크포인트 완료 및 임시 저널 파일 병합 완료.")

        except Exception as db_err:
            print(f"  - [오류] {db_key.upper()} DB 작업 중 문제 발생: {db_err}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    print("\n[*] 3단계: WAL 체크포인트 마감 완료 (SQLite C-Engine 세션 동기화 정돈 완료).")

    print("\n" + "=" * 60)
    print(" 데이터베이스 스키마 및 마이그레이션 동기화가 성공적으로 완료되었습니다!")
    print(" 서비스를 재시작해 주시기 바랍니다.")
    print("=" * 60)

if __name__ == '__main__':
    run_schema_update()
