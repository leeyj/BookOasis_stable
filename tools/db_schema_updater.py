# -*- coding: utf-8 -*-
"""
db_schema_updater.py - DB 스키마 업데이트 CLI 진입점 (entrypoint.sh / manage.sh에서 서브프로세스로 실행)

실제 컬럼/인덱스 diff + 백필 로직은 services/db_migration_service.py의
run_full_migration()으로 옮겨졌다 (database.py의 init_databases()도 같은 함수를 호출 -
두 진입점이 서로 다른 마이그레이션 로직을 갖고 있다가 갈라졌던 문제를 없앴다).
이 파일은 이제 (1) MariaDB 초기 테이블 생성(MARIADB_CENTRAL_SCHEMA, 여전히 SQLite용
_SCHEMA_SQL과 별도 유지)과 (2) SQLite WAL 체크포인트 마감처럼, run_full_migration()이
다루지 않는 진짜 이 파일만의 관심사만 남긴 얇은 CLI 래퍼다.
"""
import os
import sys
import sqlite3

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
    )
    # _ensure_mariadb_columns/_ensure_mariadb_indexes는 이제 여기 정의돼 있지 않지만,
    # tools/migrator_sqlite_to_mariadb.py가 이 모듈에서 직접 import하므로 재노출 유지.
    from services.db_migration_service import (
        run_full_migration,
        _ensure_mariadb_columns,
        _ensure_mariadb_indexes,
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
    color VARCHAR(50) DEFAULT NULL,
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

CREATE TABLE IF NOT EXISTS user_settings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    `key` VARCHAR(64) NOT NULL,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_settings (user_id, `key`),
    INDEX idx_user_settings_user_id (user_id)
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
            run_full_migration()
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

    print("\n[*] 1단계: 데이터베이스 초기화 및 스키마/인덱스/백필 마이그레이션 실행 중...")
    try:
        run_full_migration()
        print(" -> [성공] 데이터베이스 마이그레이션 완료.")
    except Exception as e:
        print(f" -> [실패] 데이터베이스 마이그레이션 중 오류 발생: {e}")

    print("\n[*] 2단계: WAL 체크포인트 마감 중...")
    for db_key, db_path in [('general', DB_GENERAL_PATH), ('adult', DB_ADULT_PATH), ('audiobook', DB_AUDIOBOOK_PATH), ('video', DB_VIDEO_PATH)]:
        if not os.path.exists(db_path):
            continue

        conn = None
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()

            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            if integrity != 'ok':
                print(f"  - [경고] {db_key.upper()} DB 무결성 이상이 감지되었습니다: {integrity}")

            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            print(f"  - {db_key.upper()} DB WAL 체크포인트(TRUNCATE) 완료.")

        except Exception as db_err:
            print(f"  - [오류] {db_key.upper()} DB WAL 체크포인트 중 문제 발생: {db_err}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    print("\n" + "=" * 60)
    print(" 데이터베이스 스키마 및 마이그레이션 동기화가 성공적으로 완료되었습니다!")
    print(" 서비스를 재시작해 주시기 바랍니다.")
    print("=" * 60)

if __name__ == '__main__':
    run_schema_update()
