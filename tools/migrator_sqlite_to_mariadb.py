# -*- coding: utf-8 -*-
"""
migrator_sqlite_to_mariadb.py - SQLite to MariaDB 1-Click 자동 데이터 이전 도구

BookOasis 미디어 서버의 3개 SQLite 데이터베이스(media_general.db, media_adult.db, media_audiobook.db)의
모든 테이블 및 레코드를 MariaDB 엔터프라이즈 데이터베이스로 고속 대량 이전합니다.
"""

import os
import sys
import time
import sqlite3

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.insert(0, MEDIA_SERVER_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(MEDIA_SERVER_DIR, '.env'))

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    print("[Error] PyMySQL 패키지가 필요합니다: pip install PyMySQL")
    sys.exit(1)

MARIADB_HOST = os.environ.get('MARIADB_HOST', '127.0.0.1')
MARIADB_PORT = int(os.environ.get('MARIADB_PORT', '3306') or '3306')
MARIADB_USER = os.environ.get('MARIADB_USER', 'root')
MARIADB_PASSWORD = os.environ.get('MARIADB_PASSWORD', '')
MARIADB_DATABASE_PREFIX = os.environ.get('MARIADB_DATABASE_PREFIX', 'media_')

DB_MAP = {
    'general': {
        'sqlite_path': os.path.join(MEDIA_SERVER_DIR, 'db', 'media_general.db'),
        'mariadb_db': f"{MARIADB_DATABASE_PREFIX}general"
    },
    'adult': {
        'sqlite_path': os.path.join(MEDIA_SERVER_DIR, 'db', 'media_adult.db'),
        'mariadb_db': f"{MARIADB_DATABASE_PREFIX}adult"
    },
    'audiobook': {
        'sqlite_path': os.path.join(MEDIA_SERVER_DIR, 'db', 'media_audiobook.db'),
        'mariadb_db': f"{MARIADB_DATABASE_PREFIX}audiobook"
    }
}

MARIADB_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS libraries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    physical_path TEXT NOT NULL,
    cron_schedule VARCHAR(255) DEFAULT NULL,
    last_scanned_at DATETIME DEFAULT NULL,
    scan_status VARCHAR(50) DEFAULT 'ready',
    is_remote INT DEFAULT 0,
    vfs_refresh_before_scan INT DEFAULT 0,
    rclone_rc_url TEXT DEFAULT NULL,
    icon VARCHAR(100) DEFAULT 'fa-book',
    color VARCHAR(50) DEFAULT '#94a3b8',
    hide_cover INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS scanner_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_key VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    kwargs TEXT,
    stage TEXT,
    worker_pid INT DEFAULT NULL,
    enqueue_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME DEFAULT NULL,
    finished_at DATETIME DEFAULT NULL,
    error_message TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS books (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    series_name VARCHAR(500),
    author VARCHAR(500),
    isbn VARCHAR(100),
    file_path VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
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
    UNIQUE KEY uq_books_file_path (file_path(500)),
    INDEX idx_books_lib_del_series (library_id, is_deleted, series_name(255), id),
    INDEX idx_books_lib_del_title (library_id, is_deleted, title(255), id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audiobooks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    library_id BIGINT,
    title VARCHAR(500) NOT NULL,
    sort_title VARCHAR(500),
    web_id VARCHAR(100),
    author VARCHAR(500),
    publisher VARCHAR(255),
    reader VARCHAR(500),
    code VARCHAR(255),
    poster TEXT,
    premiered VARCHAR(100),
    ratings VARCHAR(50),
    author_intro TEXT,
    description TEXT,
    folder_name VARCHAR(500),
    folder_path VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    cover_image TEXT,
    is_favorite INT DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    deleted_at DATETIME DEFAULT NULL,
    total_tracks INT DEFAULT 0,
    total_duration INT DEFAULT 0,
    release_date VARCHAR(100),
    series_name VARCHAR(500),
    series_index DOUBLE DEFAULT 0,
    metadata_locked INT DEFAULT 0,
    file_type VARCHAR(50),
    UNIQUE KEY uq_audiobooks_folder_path (folder_path(500)),
    INDEX idx_audiobooks_lib_del (library_id, is_deleted, title(255), id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audiobook_tracks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    audiobook_id BIGINT NOT NULL,
    track_number INT DEFAULT 0,
    track_code VARCHAR(100),
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(500),
    file_path VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    file_mtime DOUBLE DEFAULT 0.0,
    duration INT DEFAULT 0,
    file_size BIGINT DEFAULT 0,
    format VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_audiobook_tracks_file_path (file_path(500)),
    INDEX idx_audiobook_tracks_audiobook_id (audiobook_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_reading_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    pages_read_delta INT NOT NULL,
    duration_seconds INT DEFAULT 0,
    read_date DATE DEFAULT (CURRENT_DATE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_favorite (user_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS book_offsets (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    page_idx INT,
    filename VARCHAR(500),
    local_header_offset BIGINT,
    compress_size BIGINT,
    file_size BIGINT,
    compress_type INT,
    INDEX idx_offsets_book (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(255) PRIMARY KEY,
    `value` TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS scanner_progress (
    library_id VARCHAR(100),
    folder_path VARCHAR(500) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS folder_mtimes (
    folder_path VARCHAR(500) PRIMARY KEY,
    dir_mtime DOUBLE,
    meta_mtime DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_default_password INT DEFAULT 1,
    has_adult_access INT DEFAULT 1,
    has_audiobook_access INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_category_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    library_id BIGINT NOT NULL,
    has_access INT DEFAULT 1,
    UNIQUE KEY uq_user_cat_perm (user_id, library_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT NULL,
    color VARCHAR(50) DEFAULT '#7c3aed',
    cover_image TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_collections_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collection_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    collection_id BIGINT NOT NULL,
    book_id BIGINT DEFAULT NULL,
    series_name VARCHAR(500) DEFAULT NULL,
    audiobook_id BIGINT DEFAULT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_coll_book (collection_id, book_id),
    UNIQUE KEY uq_coll_series (collection_id, series_name(255)),
    UNIQUE KEY uq_coll_audiobook (collection_id, audiobook_id),
    INDEX idx_collection_items_coll (collection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def connect_mariadb(db_name=None):
    return pymysql.connect(
        host=MARIADB_HOST,
        port=MARIADB_PORT,
        user=MARIADB_USER,
        password=MARIADB_PASSWORD,
        database=db_name,
        charset='utf8mb4',
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )


import argparse

def ensure_mariadb_databases(reset=False):
    print(f"[MariaDB Setup] Host={MARIADB_HOST}:{MARIADB_PORT}, User={MARIADB_USER}")
    conn = connect_mariadb(db_name=None)
    cursor = conn.cursor()
    for db_type, config in DB_MAP.items():
        dbname = config['mariadb_db']
        if reset:
            cursor.execute(f"DROP DATABASE IF EXISTS `{dbname}`;")
            print(f"  [!] 기존 MariaDB 데이터베이스 초기화(삭제) 완료: `{dbname}`")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print(f"  [+] 데이터베이스 확인/생성 완료: `{dbname}`")
    conn.close()


def init_schema(db_type, db_name):
    conn = connect_mariadb(db_name=db_name)
    cursor = conn.cursor()
    statement_blocks = [stmt.strip() for stmt in MARIADB_SCHEMA_DDL.split(';') if stmt.strip()]
    for stmt in statement_blocks:
        try:
            cursor.execute(stmt)
        except Exception as e:
            print(f"  [!] Schema DDL Execute Warning: {e}")
    conn.commit()
    conn.close()


def ensure_table_exists_in_mariadb(ma_conn, table_name, sq_conn):
    """SQLite 테이블 스키마 정보를 동적으로 조회하여 MariaDB에 해당 테이블이 없으면 자동 생성하고, 기존 테이블의 누락 컬럼은 ALTER TABLE로 자동 보강"""
    if table_name.startswith('books_search') or table_name.startswith('sqlite_') or table_name.startswith('lost_and_found'):
        return

    ma_cur = ma_conn.cursor()

    # 0. 구형 tracks 테이블 존재 및 audiobook_tracks 미존재 시 자동 테이블명 변경
    if table_name == 'audiobook_tracks':
        try:
            ma_cur.execute("SHOW TABLES LIKE 'tracks'")
            has_old_tracks = bool(ma_cur.fetchone())
            ma_cur.execute("SHOW TABLES LIKE 'audiobook_tracks'")
            has_new_tracks = bool(ma_cur.fetchone())
            if has_old_tracks and not has_new_tracks:
                ma_cur.execute("RENAME TABLE `tracks` TO `audiobook_tracks`")
                ma_conn.commit()
                print("  [+] MariaDB 구형 테이블 `tracks` ➔ `audiobook_tracks` 자동 변경 완료.")
        except Exception as e:
            print(f"  [!] RENAME TABLE tracks Warning: {e}")

    cols = []
    try:
        sq_cur = sq_conn.cursor()
        sq_cur.execute(f"PRAGMA table_info(`{table_name}`)")
        cols = sq_cur.fetchall()
    except Exception as ex:
        print(f"  [!] PRAGMA table_info skipped for table `{table_name}`: {ex}")
        return

    if not cols:
        return

    col_defs = []
    col_type_map = {}
    for c in cols:
        name = c['name']
        col_type = (c['type'] or 'TEXT').upper()
        is_pk = c['pk']

        if 'INT' in col_type:
            m_type = 'BIGINT'
        elif 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
            m_type = 'DOUBLE'
        elif 'BLOB' in col_type:
            m_type = 'LONGBLOB'
        elif 'DATETIME' in col_type or 'DATE' in col_type:
            m_type = 'DATETIME'
        else:
            m_type = 'TEXT'

        col_type_map[name] = m_type

        if is_pk:
            if m_type == 'TEXT':
                m_type = 'VARCHAR(500)'
            col_defs.append(f"`{name}` {m_type} PRIMARY KEY")
        else:
            col_defs.append(f"`{name}` {m_type}")

    col_str = ",\n  ".join(col_defs)
    ddl = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n  {col_str}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
    try:
        ma_cur.execute(ddl)
        ma_conn.commit()
    except Exception as e:
        print(f"  [!] Dynamic DDL Create Warning for table `{table_name}`: {e}")

    # MariaDB 기존 테이블의 누락 컬럼 자동 ALTER TABLE 추가 보강
    try:
        ma_cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        ma_cols = set(r['Field'] for r in ma_cur.fetchall())
        for c in cols:
            col_name = c['name']
            if col_name not in ma_cols:
                m_type = col_type_map.get(col_name, 'TEXT')
                alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {m_type}"
                try:
                    ma_cur.execute(alter_sql)
                    ma_conn.commit()
                    print(f"  [+] MariaDB 기존 테이블 `{table_name}` 누락 컬럼 `{col_name}`({m_type}) ALTER TABLE 자동 추가 완료.")
                except Exception as alter_err:
                    print(f"  [!] ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` Warning: {alter_err}")
    except Exception as show_err:
        print(f"  [!] SHOW COLUMNS Warning for table `{table_name}`: {show_err}")

def migrate_single_db(db_type):
    config = DB_MAP[db_type]
    sqlite_path = config['sqlite_path']
    mariadb_db = config['mariadb_db']

    if not os.path.exists(sqlite_path):
        print(f"  [-] SQLite DB 파일 없음 ({sqlite_path}); 스킵합니다.")
        return

    print(f"\n==========================================")
    print(f"🚀 [{db_type.upper()}] SQLite ➔ MariaDB 데이터 펌핑 시작")
    print(f"   SQLite: {sqlite_path}")
    print(f"   MariaDB: {mariadb_db}")
    print(f"==========================================")

    init_schema(db_type, mariadb_db)

    sq_conn = sqlite3.connect(sqlite_path)
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()

    ma_conn = connect_mariadb(db_name=mariadb_db)
    ma_cur = ma_conn.cursor()

    sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'books_search%' AND name NOT LIKE 'lost_and_found%'")
    tables = [r['name'] for r in sq_cur.fetchall()]

    start_time = time.perf_counter()
    total_migrated_rows = 0

    ma_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
    try:
        ma_cur.execute("SET sql_mode = '';")
    except Exception:
        pass

    def _clean_val(v):
        if v == '':
            return None
        return v

    for table in tables:
        ensure_table_exists_in_mariadb(ma_conn, table, sq_conn)
        sq_cur.execute(f"SELECT * FROM `{table}`")
        rows = sq_cur.fetchall()
        if not rows:
            continue

        cols = [description[0] for description in sq_cur.description]
        col_names_str = ", ".join([f"`{c}`" for c in cols])
        placeholders = ", ".join(["%s"] * len(cols))

        insert_sql = f"REPLACE INTO `{table}` ({col_names_str}) VALUES ({placeholders})"

        batch_data = []
        for r in rows:
            batch_data.append(tuple(_clean_val(r[c]) for c in cols))

        ma_cur.executemany(insert_sql, batch_data)
        ma_conn.commit()
        cnt = len(batch_data)
        total_migrated_rows += cnt
        print(f"  [+] 테이블 `{table}`: {cnt:,}개 행 이관 완료")

    ma_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
    ma_conn.close()
    sq_conn.close()

    elapsed = time.perf_counter() - start_time
    print(f"✨ [{db_type.upper()}] 이관 마감: 총 {total_migrated_rows:,}개 행 이전 완료 (소요시간: {elapsed:.2f}초)")


def main():
    parser = argparse.ArgumentParser(description="BookOasis SQLite to MariaDB Migrator Tool")
    parser.add_argument('--reset', '--fresh', action='store_true', help="기존 MariaDB 데이터베이스를 완전히 삭제(초기화) 후 처음부터 깨끗이 이관합니다.")
    args = parser.parse_args()

    print("==================================================")
    print("  BookOasis SQLite ➔ MariaDB 1-Click 자동 마이그레이터")
    if args.reset:
        print("  ⚠️ [--reset 모드] 기존 MariaDB DB를 완전히 삭제 후 처음부터 이관합니다.")
    print("==================================================")

    try:
        ensure_mariadb_databases(reset=args.reset)
    except Exception as err:
        print(f"\n[오류] MariaDB 서버 접속 실패: {err}")
        print("  .env 파일의 MARIADB_HOST, MARIADB_PORT, MARIADB_USER, MARIADB_PASSWORD 설정을 확인하세요.")
        sys.exit(1)

    for db_type in DB_MAP:
        migrate_single_db(db_type)

    print("\n==================================================")
    print("🎉 모든 데이터베이스 이관이 완료되었습니다!")
    print("   .env 파일에서 DB_ENGINE=mariadb 로 설정 후 미디어 서버를 시작하세요.")
    print("==================================================")


if __name__ == '__main__':
    main()

