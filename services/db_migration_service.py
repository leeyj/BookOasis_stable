# -*- coding: utf-8 -*-
"""
db_migration_service.py - DB 스키마 마이그레이션/백필 레이어 (Single Source of Truth)

이전엔 이 로직이 database.py("커넥션 풀링"과 함께)와
tools/db_schema_updater.py(MariaDB 전용 수작업 컬럼/인덱스 리스트)에
각각 따로 존재해, 새 컬럼을 추가할 때 두 곳을 손으로 동기화해야 하는
구조였다 (실제로 한 번 조용히 갈라져 MariaDB 제로데이트 백필이 한쪽에만
있던 적 있음). 이 모듈이 그 둘을 하나로 합친 결과물이다.

- SQLite용 초기 테이블 생성 DDL(_SCHEMA_SQL/_INDEXES_SQL)과 MariaDB용 초기 생성
  DDL(tools/db_schema_updater.py의 MARIADB_CENTRAL_SCHEMA)은 의도적으로 지금처럼
  별도로 유지한다 (다이얼렉트 변환 계층까지 통합하는 건 범위 밖).
- 컬럼/인덱스 diff + 백필 같은 "부족한 스키마 생성" 레이어만 여기에 모음.
- 진입점은 run_full_migration() 하나이며, database.init_databases()와
  tools/db_schema_updater.py 둘 다 이 함수를 호출한다.
"""
import os
import re
import html
import sqlite3
# database는 의도적으로 모듈 최상단이 아니라 각 함수 본문에서 지연 import한다 -
# database.py가 하단에서 이 모듈의 run_full_migration을 다시 import해 되돌아오므로,
# 이 파일이 (database.py를 거치지 않고) 최초 진입점으로 직접 import될 경우 최상단
# import database가 순환 참조로 깨진다 (실제로 재현/확인함).


def parse_schema_columns(schema_text):
    """schema SQL 정의 문자열로부터 각 테이블과 그 안의 컬럼 정의(컬럼명, 컬럼타입) 매핑 딕셔너리를 파싱하여 추출"""
    table_pattern = re.compile(r'CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);', re.DOTALL | re.IGNORECASE)
    
    table_cols = {}
    for table_match in table_pattern.finditer(schema_text):
        table_name = table_match.group(1)
        body = table_match.group(2)
        
        cols = []
        for line in body.split('\n'):
            line = line.strip()
            if not line or line.upper().startswith(('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CREATE INDEX', 'CONSTRAINT')):
                continue
            
            # 주석 제거
            if line.startswith('--') or line.startswith('#'):
                continue
                
            # 컬럼명과 나머지 정의 추출
            col_match = re.match(r'^(\w+)\s+(.+)$', line)
            if col_match:
                col_name = col_match.group(1)
                col_def = col_match.group(2).rstrip(',')
                
                # PRIMARY KEY이거나 REFERENCES ID인 경우 기본 키이므로 마이그레이션 대상에서 제외
                if 'PRIMARY KEY' in col_def.upper() and col_name.upper() == 'ID':
                    continue
                cols.append((col_name, col_def))
        table_cols[table_name] = cols
    return table_cols

def auto_migrate_schema(conn, schema_text):
    """실제 DB 테이블의 스키마와 정의된 스키마를 비교하여 결손된 컬럼이 있으면 ALTER TABLE을 동적으로 자동 실행"""
    table_cols = parse_schema_columns(schema_text)
    cursor = conn.cursor()
    is_mariadb = hasattr(conn, '_conn') or type(conn).__name__.startswith('Mariadb') or type(conn).__name__.startswith('PooledMariaDB')
    
    for table_name, cols in table_cols.items():
        # 1. 해당 테이블의 실존 컬럼 정보 조회
        try:
            if is_mariadb:
                cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                rows = cursor.fetchall()
                existing_cols = set()
                for r in rows:
                    if isinstance(r, dict) or hasattr(r, 'get'):
                        val = r.get('Field') or r.get('field') or r.get('COLUMN_NAME') or r.get('name')
                        if val:
                            existing_cols.add(str(val).lower())
                    else:
                        existing_cols.add(str(r[0]).lower())
            else:
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_cols = {row['name'].lower() for row in cursor.fetchall()}
        except Exception as e:
            print(f"[DB-Migration Warning] Failed to get info for table {table_name} (may be before table creation): {e}")
            continue
            
        if not existing_cols:
            continue
            
        # 2. 선언된 컬럼이 실제 DB에 존재하는지 확인하고 없으면 ALTER TABLE 수행
        for col_name, col_def in cols:
            if col_name.lower() not in existing_cols:
                # SQLite ALTER TABLE ADD COLUMN은 DEFAULT CURRENT_TIMESTAMP / CURRENT_DATE / CURRENT_TIME 등의 동적 기본값을 지원하지 않음 (상수만 가능)
                # 따라서 동적 기본값 정의는 제거하여 추가함
                col_def_clean = re.sub(r'(?i)DEFAULT\s+(CURRENT_TIMESTAMP|CURRENT_DATE|CURRENT_TIME)', '', col_def)

                # 레거시 데이터가 있는 테이블에 NOT NULL 컬럼을 추가할 때는
                # MariaDB/SQLite 모두 DEFAULT가 없으면 ALTER가 실패할 수 있으므로 안전 기본값을 보강합니다.
                upper_def = col_def_clean.upper()
                has_not_null = 'NOT NULL' in upper_def
                has_default = 'DEFAULT' in upper_def
                if has_not_null and not has_default:
                    if re.search(r'\b(INT|INTEGER|BIGINT|SMALLINT|TINYINT|NUMERIC|DECIMAL|REAL|FLOAT|DOUBLE)\b', upper_def):
                        default_literal = '1' if col_name.lower() == 'user_id' else '0'
                    elif re.search(r'\b(CHAR|TEXT|CLOB|VARCHAR)\b', upper_def):
                        default_literal = "''"
                    else:
                        default_literal = '0'
                    col_def_clean = f"{col_def_clean} DEFAULT {default_literal}"

                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def_clean}"
                try:
                    cursor.execute(alter_query)
                    conn.commit()
                    print(f"[DB-Migration] Dynamic schema column added: {table_name}.{col_name} ({col_def_clean.strip()})")
                except Exception as e:
                    print(f"[DB-Migration ERROR] Failed to add dynamic column ({alter_query}): {e}")


def cleanup_legacy_fts_index(conn):
    """기존 FTS5 가상 테이블 및 그림자 테이블(shadow tables)을 소거하여 DB 락 및 손상 위험 차단"""
    cursor = conn.cursor()
    try:
        cursor.executescript(
            """
            DROP TRIGGER IF EXISTS books_search_ai;
            DROP TRIGGER IF EXISTS books_search_ad;
            DROP TRIGGER IF EXISTS books_search_au;
            DROP TABLE IF EXISTS books_search;
            DROP TABLE IF EXISTS books_search_data;
            DROP TABLE IF EXISTS books_search_idx;
            DROP TABLE IF EXISTS books_search_content;
            DROP TABLE IF EXISTS books_search_docsize;
            DROP TABLE IF EXISTS books_search_config;
            """
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DB-Cleanup] Legacy FTS5 table cleanup skipped: {e}")

def startup_db_sanity_check():
    """
    앱 초기 기동 시 DB 파일 및 WAL/SHM 파일 무결성을 검증합니다.
    - integrity_check 실패 또는 WAL 파일 손상 감지 시 WAL/SHM 파일을 자동 제거합니다.
    - 메인 DB 파일 자체의 손상은 경고 로그만 출력하고 서버 기동은 계속합니다.
    """
    import database
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    if engine in ('mariadb', 'mysql'):
        return
    db_map = {
        'general'  : database.DB_GENERAL_PATH,
        'adult'    : database.DB_ADULT_PATH,
        'audiobook': database.DB_AUDIOBOOK_PATH,
        'video'    : database.DB_VIDEO_PATH,
    }
    for db_type, db_path in db_map.items():
        if not os.path.exists(db_path):
            continue  # 아직 생성 전 (최초 기동)

        wal_path = db_path + '-wal'
        shm_path = db_path + '-shm'
        has_wal  = os.path.exists(wal_path)
        has_shm  = os.path.exists(shm_path)

        # WAL/SHM 파일이 없으면 검사 불필요
        if not has_wal and not has_shm:
            continue

        print(f"[DB-Sanity] {db_type} DB — WAL/SHM 파일 감지, 무결성 검증 시작...")
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            result = conn.execute("PRAGMA integrity_check;").fetchall()
            integrity_ok = (len(result) == 1 and result[0][0] == 'ok')

            if integrity_ok:
                # WAL 체크포인트 수행 (SQLite C-Engine이 스스로 마감하도록 맡김)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
                print(f"[DB-Sanity] {db_type} DB — 무결성 정상, WAL 체크포인트 마감 완료")
            else:
                conn.close()
                print(f"[DB-Sanity] {db_type} DB — 무결성 이상 감지: {result[:3]}")
                print(f"[DB-Sanity] 지속적인 오류 발생 시 tools/db_recovery.py 를 실행하세요.")

        except sqlite3.DatabaseError as e:
            print(f"[DB-Sanity] {db_type} DB — DB 접속 실패: {e}")
        except Exception as e:
            print(f"[DB-Sanity] {db_type} DB — 예기치 못한 오류 (무시하고 계속): {e}")


# 4개 미디어 세션(general/adult/audiobook/video) 공용 스키마.
# init_databases()에서만 쓰이는 값이라 예전엔 그 함수 안의 지역 변수였지만, 순수 SQL
# 텍스트 361줄이 로직 코드 사이에 섞여 있어 함수 전체를 읽기 어렵게 만들고 있었다.
# 모듈 레벨 상수로 분리해 init_databases()를 실제 로직만 남도록 정리한다 (동작 변화 없음).
_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS library_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        icon TEXT DEFAULT 'fa-folder',
        color TEXT DEFAULT NULL,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS libraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        physical_path TEXT NOT NULL,
        cron_schedule TEXT DEFAULT NULL,
        schedule_enabled INTEGER NOT NULL DEFAULT 1,
        last_scanned_at DATETIME DEFAULT NULL,
        scan_status TEXT DEFAULT 'ready',
        is_remote INTEGER DEFAULT 0,
        vfs_refresh_before_scan INTEGER DEFAULT 0,
        rclone_rc_url TEXT DEFAULT NULL,
        icon TEXT DEFAULT 'fa-book',
        color TEXT DEFAULT '#94a3b8',
        hide_cover INTEGER DEFAULT 0,
        group_id INTEGER DEFAULT NULL,
        sort_order INTEGER DEFAULT 0,
        gdrive_copy_remote TEXT DEFAULT NULL,
        gdrive_view_local_mirror_path TEXT DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS plugin_group_assignments (
        plugin_id TEXT PRIMARY KEY,
        group_id INTEGER NOT NULL,
        sort_order INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS scanner_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        task_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'pending',
        kwargs TEXT,
        stage TEXT,
        worker_pid INTEGER DEFAULT NULL,
        enqueue_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        started_at DATETIME DEFAULT NULL,
        finished_at DATETIME DEFAULT NULL,
        error_message TEXT,
        cancel_requested INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        library_id INTEGER REFERENCES libraries(id),
        title TEXT NOT NULL,
        series_name TEXT,
        author TEXT,
        isbn TEXT,
        file_path TEXT NOT NULL UNIQUE,
        file_format TEXT NOT NULL,
        total_pages INTEGER NOT NULL,
        has_offsets INTEGER DEFAULT 0,
        cover_image TEXT,
        publisher TEXT,
        link TEXT,
        score INTEGER,
        release_date TEXT,
        summary TEXT,
        genre TEXT,
        tags TEXT,
        is_favorite INTEGER DEFAULT 0,
        cover_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_deleted INTEGER DEFAULT 0,
        deleted_at DATETIME DEFAULT NULL,
        metadata_locked INTEGER DEFAULT 0,
        series_alias TEXT,
        title_alias TEXT,
        file_mtime REAL DEFAULT 0.0,
        file_size INTEGER DEFAULT 0,
        cover_align TEXT DEFAULT 'center'
    );

    CREATE TABLE IF NOT EXISTS series_summary (
        library_id INTEGER NOT NULL,
        series_key VARCHAR(500) NOT NULL,
        representative_book_id INTEGER NOT NULL,
        series_book_count INTEGER NOT NULL DEFAULT 0,
        sort_series_name VARCHAR(500) NOT NULL DEFAULT '',
        PRIMARY KEY (library_id, series_key)
    );

    CREATE TABLE IF NOT EXISTS series_summary_state (
        id INTEGER PRIMARY KEY,
        is_ready INTEGER NOT NULL DEFAULT 0,
        refreshed_at DATETIME DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS audiobooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        library_id INTEGER REFERENCES libraries(id),
        title TEXT NOT NULL,
        sort_title TEXT,
        web_id TEXT,
        author TEXT,
        publisher TEXT,
        code TEXT,
        poster TEXT,
        premiered TEXT,
        ratings REAL DEFAULT 0.0,
        author_intro TEXT,
        description TEXT,
        folder_name TEXT NOT NULL,
        folder_path TEXT NOT NULL UNIQUE,
        total_duration REAL DEFAULT 0.0,
        total_tracks INTEGER DEFAULT 1,
        file_type TEXT DEFAULT 'multi',
        is_favorite INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_deleted INTEGER DEFAULT 0,
        deleted_at DATETIME DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS audiobook_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
        track_number INTEGER NOT NULL,
        track_code TEXT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        file_mtime REAL DEFAULT 0.0,
        file_size INTEGER DEFAULT 0,
        duration REAL DEFAULT 0.0,
        format TEXT DEFAULT 'mp3'
    );

    CREATE TABLE IF NOT EXISTS audiobook_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL DEFAULT 1,
        current_track_id INTEGER REFERENCES audiobook_tracks(id),
        current_time REAL DEFAULT 0.0,
        total_progress_pct REAL DEFAULT 0.0,
        playback_rate REAL DEFAULT 1.0,
        is_completed INTEGER DEFAULT 0,
        last_listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(audiobook_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS audiobook_track_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audiobook_id INTEGER REFERENCES audiobooks(id) ON DELETE CASCADE,
        track_id INTEGER REFERENCES audiobook_tracks(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL DEFAULT 1,
        current_time REAL DEFAULT 0.0,
        progress_pct REAL DEFAULT 0.0,
        is_completed INTEGER DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(audiobook_id, track_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        library_id INTEGER REFERENCES libraries(id),
        title TEXT NOT NULL,
        sort_title TEXT,
        web_id TEXT,
        genres TEXT,
        poster TEXT,
        backdrop TEXT,
        premiered TEXT,
        description TEXT,
        folder_name TEXT NOT NULL,
        folder_path TEXT NOT NULL UNIQUE,
        total_duration REAL DEFAULT 0.0,
        total_episodes INTEGER DEFAULT 0,
        is_favorite INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_deleted INTEGER DEFAULT 0,
        deleted_at DATETIME DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS video_episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        episode_number INTEGER NOT NULL,
        episode_code TEXT,
        title TEXT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL UNIQUE,
        file_mtime REAL DEFAULT 0.0,
        file_size INTEGER DEFAULT 0,
        duration REAL DEFAULT 0.0,
        width INTEGER DEFAULT 0,
        height INTEGER DEFAULT 0,
        premiered TEXT,
        format TEXT DEFAULT 'mp4',
        needs_transcode INTEGER DEFAULT 0,
        subtitle_path TEXT,
        container_verified INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS video_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL DEFAULT 1,
        current_episode_id INTEGER REFERENCES video_episodes(id),
        current_time REAL DEFAULT 0.0,
        total_progress_pct REAL DEFAULT 0.0,
        playback_rate REAL DEFAULT 1.0,
        is_completed INTEGER DEFAULT 0,
        last_watched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(video_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS video_episode_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        episode_id INTEGER REFERENCES video_episodes(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL DEFAULT 1,
        current_time REAL DEFAULT 0.0,
        progress_pct REAL DEFAULT 0.0,
        is_completed INTEGER DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(video_id, episode_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS user_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        pages_read INTEGER DEFAULT 0,
        is_completed INTEGER DEFAULT 0,
        last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_epub_cfi TEXT,
        last_epub_href TEXT,
        last_epub_spine_index INTEGER,
        last_epub_percent INTEGER DEFAULT 0,
        last_epub_fingerprint TEXT,
        last_epub_updated_at DATETIME
    );

    CREATE TABLE IF NOT EXISTS book_annotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        format TEXT NOT NULL,
        chapter_idx INTEGER,
        start_offset INTEGER NOT NULL,
        end_offset INTEGER NOT NULL,
        quote TEXT NOT NULL,
        prefix TEXT,
        suffix TEXT,
        color TEXT DEFAULT '#fbbf24',
        note TEXT,
        plugin_marker TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS epub_bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        format TEXT NOT NULL,
        chapter_idx INTEGER NOT NULL,
        percent INTEGER DEFAULT 0,
        label TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_reading_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        pages_read_delta INTEGER NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        read_date DATE DEFAULT CURRENT_DATE
    );

    CREATE TABLE IF NOT EXISTS user_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER REFERENCES books(id),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, book_id)
    );

    CREATE TABLE IF NOT EXISTS book_offsets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        page_idx INTEGER,
        filename TEXT,
        local_header_offset INTEGER,
        compress_size INTEGER,
        file_size INTEGER,
        compress_type INTEGER,
        data_offset INTEGER
    );

    CREATE TABLE IF NOT EXISTS gdrive_book_copies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL UNIQUE REFERENCES books(id),
        library_id INTEGER NOT NULL,
        source_file_id TEXT NOT NULL,
        status TEXT NOT NULL,
        local_path TEXT,
        error_message TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS scanner_progress (
        library_id TEXT,
        folder_path TEXT PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS folder_mtimes (
        folder_path TEXT PRIMARY KEY,
        dir_mtime REAL,
        meta_mtime REAL
    );

    CREATE TABLE IF NOT EXISTS scan_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        task_key TEXT,
        status TEXT NOT NULL,
        kwargs TEXT,
        enqueue_at TEXT,
        started_at TEXT,
        finished_at TEXT,
        error_message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS scanner_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        task_key TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        kwargs TEXT,
        enqueue_at TEXT,
        started_at TEXT,
        finished_at TEXT,
        stage TEXT,
        worker_pid INTEGER,
        error_message TEXT,
        cancel_requested INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_default_password INTEGER DEFAULT 1,
        has_adult_access INTEGER DEFAULT 1,
        has_audiobook_access INTEGER DEFAULT 1,
        has_video_access INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_category_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        library_id INTEGER NOT NULL,
        has_access INTEGER DEFAULT 1,
        UNIQUE(user_id, library_id)
    );

    CREATE TABLE IF NOT EXISTS user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, key)
    );

    CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT NULL,
        color TEXT DEFAULT '#7c3aed',
        cover_image TEXT DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS collection_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        book_id INTEGER DEFAULT NULL REFERENCES books(id) ON DELETE CASCADE,
        series_name TEXT DEFAULT NULL,
        audiobook_id INTEGER DEFAULT NULL REFERENCES audiobooks(id) ON DELETE CASCADE,
        video_id INTEGER DEFAULT NULL,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(collection_id, book_id),
        UNIQUE(collection_id, series_name),
        UNIQUE(collection_id, audiobook_id),
        UNIQUE(collection_id, video_id)
    );

    CREATE TABLE IF NOT EXISTS plugin_load_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plugin_id TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT DEFAULT NULL,
        occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """

_INDEXES_SQL = """
    CREATE INDEX IF NOT EXISTS idx_audiobook_tracks_audiobook_id ON audiobook_tracks(audiobook_id);
    CREATE INDEX IF NOT EXISTS idx_audiobook_track_progress_lookup ON audiobook_track_progress(audiobook_id, user_id, track_id);
    CREATE INDEX IF NOT EXISTS idx_audiobooks_library_id ON audiobooks(library_id);
    CREATE INDEX IF NOT EXISTS idx_audiobooks_title ON audiobooks(title);
    CREATE INDEX IF NOT EXISTS idx_video_episodes_video_id ON video_episodes(video_id);
    CREATE INDEX IF NOT EXISTS idx_video_episode_progress_lookup ON video_episode_progress(video_id, user_id, episode_id);
    CREATE INDEX IF NOT EXISTS idx_videos_library_id ON videos(library_id);
    CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title);
    CREATE INDEX IF NOT EXISTS idx_book_offsets_book_id ON book_offsets(book_id);
    CREATE INDEX IF NOT EXISTS idx_book_offsets_book_page ON book_offsets(book_id, page_idx);
    CREATE INDEX IF NOT EXISTS idx_gdrive_book_copies_library_id ON gdrive_book_copies(library_id);
    CREATE INDEX IF NOT EXISTS idx_books_series_name ON books(series_name);
    CREATE INDEX IF NOT EXISTS idx_books_series_alias ON books(series_alias);
    CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
    CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
    CREATE INDEX IF NOT EXISTS idx_libraries_group_id ON libraries(group_id);
    CREATE INDEX IF NOT EXISTS idx_libraries_group_order ON libraries(group_id, sort_order);
    CREATE INDEX IF NOT EXISTS idx_plugin_group_assignments_group_id ON plugin_group_assignments(group_id);
    CREATE INDEX IF NOT EXISTS idx_books_is_favorite ON books(is_favorite);
    CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
    CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);
    CREATE INDEX IF NOT EXISTS idx_books_library_active_series ON books(library_id, COALESCE(is_deleted, 0), COALESCE(series_name, ''));
    CREATE INDEX IF NOT EXISTS idx_series_summary_order ON series_summary(library_id, sort_series_name, representative_book_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_progress_book_user ON user_progress(book_id, user_id);
    CREATE INDEX IF NOT EXISTS idx_user_progress_last_read ON user_progress(user_id, last_read_at DESC);
    CREATE INDEX IF NOT EXISTS idx_user_progress_last_read_book ON user_progress(last_read_at DESC, book_id);
    CREATE INDEX IF NOT EXISTS idx_user_reading_log_user_date ON user_reading_log(user_id, read_date);
    CREATE INDEX IF NOT EXISTS idx_user_reading_log_book_user_date ON user_reading_log(book_id, user_id, read_date);
    CREATE INDEX IF NOT EXISTS idx_user_favorites_user_book ON user_favorites(user_id, book_id);
    CREATE INDEX IF NOT EXISTS idx_user_favorites_book ON user_favorites(book_id);
    CREATE INDEX IF NOT EXISTS idx_user_category_permissions_lookup ON user_category_permissions(user_id, library_id, has_access);
    CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
    CREATE INDEX IF NOT EXISTS idx_collections_user ON collections(user_id);
    CREATE INDEX IF NOT EXISTS idx_collection_items_coll ON collection_items(collection_id);
    CREATE INDEX IF NOT EXISTS idx_plugin_load_events_plugin_time ON plugin_load_events(plugin_id, occurred_at DESC);
    CREATE INDEX IF NOT EXISTS idx_book_annotations_book_user ON book_annotations(book_id, user_id);
    CREATE INDEX IF NOT EXISTS idx_epub_bookmarks_book_user ON epub_bookmarks(book_id, user_id);
    """


def _connect_and_init_schema(db_type, schema):
    """DB 연결 후 기본 스키마를 적용한다.

    연결 자체가 실패하면(예: MariaDB 계정에 새로 추가된 DB에 대한 GRANT가 아직 없는
    경우 "Access denied ... to database 'media_X'") 여기서 예외가 그대로 전파되어
    gunicorn 워커 부팅 자체가 실패하고 서버 전체가 죽는다. 한 DB의 권한 설정이 아직
    안 됐다고 나머지 DB(및 앱 전체)까지 마비시킬 이유는 없으므로, 실패 시 (None, None)을
    반환해 호출부가 이 DB만 건너뛰고 다음 DB로 계속 진행하게 한다
    (docs/move_to_mariadb.md FAQ Q1 참고).
    """
    # DB 연결 자체가 실패하면(예: MariaDB 계정에 새로 추가된 DB에 대한 GRANT가 아직
    # 없는 경우 "Access denied ... to database 'media_X'") 여기서 예외가 그대로
    # 전파되어 gunicorn 워커 부팅 자체가 실패하고 서버 전체가 죽는다. 한 DB의 권한
    # 설정이 아직 안 됐다고 나머지 DB(및 앱 전체)까지 마비시킬 이유는 없으므로,
    # 이 DB만 건너뛰고 다음 DB로 계속 진행한다 (docs/move_to_mariadb.md FAQ Q1 참고).
    import database
    conn = None
    try:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()
    except Exception as conn_err:
        print(f"[DB-Migration ERROR] '{db_type}' DB 연결/초기화 실패로 이 DB를 건너뜁니다: {conn_err}")
        db_engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', ''))
        if 'access denied' in str(conn_err).lower() or 'mariadb' in db_engine.lower():
            mariadb_user = os.environ.get('MARIADB_USER', 'bookoasis')
            db_prefix = os.environ.get('MARIADB_DATABASE_PREFIX', 'media_')
            print(
                "[DB-Migration ERROR] MariaDB 권한 문제로 보입니다. "
                f"'{mariadb_user}' 계정에 '{db_prefix}{db_type}' 권한이 없을 수 있습니다. "
                "MariaDB에 root로 접속해 아래 SQL을 실행하세요 (docker-compose.mariadb.yml 사용 중이면 "
                "'mariadb-grant-repair' 서비스가 다음 `docker-compose up` 시 자동으로 재실행합니다):"
            )
            print(
                f"  CREATE DATABASE IF NOT EXISTS {db_prefix}{db_type} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;\n"
                f"  GRANT ALL PRIVILEGES ON {db_prefix}{db_type}.* TO '{mariadb_user}'@'%';\n"
                "  FLUSH PRIVILEGES;"
            )
            print("[DB-Migration ERROR] 자세한 내용은 docs/move_to_mariadb.md FAQ Q1을 참고하세요.")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return None, None

    return conn, cursor


def _migrate_schema_and_dedupe_progress(conn, cursor, db_type, schema):
    """누락 컬럼 자동 보강 + user_progress 중복 레코드 정리(고유 인덱스 적용 준비)."""
    # 신규 표현식 인덱스 생성 전에 누락 컬럼을 먼저 보강해야 구버전 DB에서도 안전합니다.
    try:
        auto_migrate_schema(conn, schema)
    except Exception as migrate_err:
        print(f"[DB-Migration ERROR] Exception during pre-index schema auto-migration: {migrate_err}")
    
    # [마이그레이션] user_progress 중복 레코드 정리 및 고유 인덱스 설정 준비
    try:
        is_mariadb = hasattr(conn, '_conn') or type(conn).__name__.startswith('Mariadb') or type(conn).__name__.startswith('PooledMariaDB')
        if is_mariadb:
            cursor.execute("SHOW TABLES LIKE 'user_progress'")
            has_user_progress = bool(cursor.fetchone())
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_progress'")
            has_user_progress = bool(cursor.fetchone())

        if has_user_progress:
            # 1. 중복 레코드 삭제 (가장 최근 것 1개만 남김)
            if is_mariadb:
                cursor.execute("""
                    DELETE up1 FROM user_progress up1
                    INNER JOIN user_progress up2 
                    ON up1.book_id = up2.book_id AND up1.user_id = up2.user_id
                    WHERE up1.id < up2.id
                """)
            else:
                cursor.execute("""
                    DELETE FROM user_progress
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM user_progress
                        GROUP BY book_id, user_id
                    )
                """)
            conn.commit()

            # 2. 기존 일반 인덱스가 있다면 삭제하여 UNIQUE로 변경 가능하도록 준비
            if is_mariadb:
                cursor.execute("SHOW INDEX FROM user_progress WHERE Key_name = 'idx_user_progress_book_user'")
                idx_rows = cursor.fetchall()
                if idx_rows:
                    first_row = idx_rows[0]
                    non_unique = first_row.get('Non_unique', 1) if isinstance(first_row, dict) else 1
                    if non_unique == 1:
                        cursor.execute("DROP INDEX idx_user_progress_book_user ON user_progress")
                        conn.commit()
                        print(f"[DB-Migration] {db_type} MariaDB - Dropped non-unique index idx_user_progress_book_user")
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_progress_book_user'")
                if cursor.fetchone():
                    cursor.execute("PRAGMA index_list('user_progress')")
                    is_unique = False
                    for idx in cursor.fetchall():
                        if idx['name'] == 'idx_user_progress_book_user' and idx['unique'] == 1:
                            is_unique = True
                            break
                    if not is_unique:
                        cursor.execute("DROP INDEX idx_user_progress_book_user")
                        conn.commit()
                        print(f"[DB-Migration] {db_type} DB - Dropped non-unique index idx_user_progress_book_user")
    except Exception as dup_err:
        print(f"[DB-Migration ERROR] user_progress duplicates cleanup failed: {dup_err}")
    


def _create_indexes_and_cleanup_fts(conn, cursor, indexes_schema):
    """인덱스 일괄 생성 + 레거시 FTS5 가상 테이블 정리."""
    # 테이블 생성 완료 후 별도 트랜잭션으로 인덱스 일괄 생성하여 SQLite OperationalError 예방
    cursor.executescript(indexes_schema)
    conn.commit()

    try:
        cleanup_legacy_fts_index(conn)
    except Exception as search_idx_err:
        print(f"[DB-Cleanup] Legacy FTS5 cleanup notice: {search_idx_err}")
    


def _seed_settings_and_admin(conn, cursor, db_type):
    """설정 초기값(ALADIN 등) 주입, 최초 admin 계정 생성, 레거시 즐겨찾기 마이그레이션."""
    import database
    # settings 테이블 초기값 주입 (ALADIN TTBKey)
    try:
        cursor.execute("SELECT `value` FROM settings WHERE `key` = 'ALADIN'")
        if not cursor.fetchone():
            # os.getenv 등을 위해 .env 파싱도 대비
            aladin_val = os.environ.get('ALADIN', '')
            if not aladin_val:
                # 간단하게 env 파일 읽기 헬퍼
                try:
                    env_path = os.path.join(database.BASE_DIR, '.env')
                    if os.path.exists(env_path):
                        with open(env_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.strip().startswith('ALADIN='):
                                    aladin_val = line.split('=', 1)[1].strip()
                                    break
                except Exception as env_err:
                    print(f"[DB-Migration] .env load error: {env_err}")
            
            cursor.execute("INSERT OR REPLACE INTO settings (`key`, `value`) VALUES ('ALADIN', ?)", (aladin_val,))
            conn.commit()
            print(f"[DB-Migration] {db_type} DB - Initial ALADIN setting migrated: {aladin_val}")
        
        default_settings = [
            ('BOOK_THUMBNAIL_WIDTH', '160'),
            ('PAGE_LIMIT', '60'),
            ('VIEWER_FONT_SIZE', '18'),
            ('VIEWER_FONT_FAMILY', 'sans-serif'),
            ('DB_POOL_SIZE', '49'),
            ('SCANNER_WRITE_LOG', '1'),
            ('LAZY_SCAN_CRON', '0 3 * * *'),
            ('SYSTEM_MEM_LIMIT', '1536.0'),
            ('PROCESS_RSS_LIMIT', '2048.0'),
            ('RECENT_BOOKS_LIMIT', '30'),
            ('AUDIO_MINI_PLAYER_MODE', 'mini'),
            ('AUDIO_RIGHT_DOCK_DIM_ENABLED', '0'),
            ('TAG_FILTER_SEARCH_SCOPE_ALL', '0'),
            ('HDD_AGGRESSIVE_WARMUP', '0'),
            ('RCLONE_RC_URL', 'http://localhost:5572,http://host.docker.internal:5572'),
            ('LAZY_SCAN_MAX_FILE_SIZE_MB', '300'),
            ('LAZY_SCAN_MAX_BATCH_SIZE_MB', '1024'),
            ('SCAN_IGNORE_PATTERNS', "@eaDir/\n#recycle/\n*.tmp\n*.sample.cbz\n.DS_Store\nThumbs.db\ndesktop.ini"),
        ]
        for k, v in default_settings:
            cursor.execute("SELECT `value` FROM settings WHERE `key` = ?", (k,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO settings (`key`, `value`) VALUES (?, ?)", (k, v))
        
        # 기존 DB의 SCAN_IGNORE_PATTERNS 값 중 @eaDir, #recycle 끝에 /가 없는 구형 설정 자동 마이그레이션
        cursor.execute("SELECT `value` FROM settings WHERE `key` = 'SCAN_IGNORE_PATTERNS'")
        sig_row = cursor.fetchone()
        if sig_row and sig_row[0]:
            curr_val = sig_row[0]
            new_lines = []
            changed = False
            for line in curr_val.splitlines():
                stripped = line.strip()
                if stripped in ('@eaDir', '#recycle', '.git', '.svn'):
                    new_lines.append(stripped + '/')
                    changed = True
                else:
                    new_lines.append(line)
            if changed:
                cursor.execute("UPDATE settings SET `value` = ? WHERE `key` = 'SCAN_IGNORE_PATTERNS'", ('\n'.join(new_lines),))

        # 기존 DB의 RCLONE_RC_URL이 예전 기본값(localhost 단독)에서 손대지 않은 상태라면
        # host.docker.internal 폴백 후보를 추가해 마이그레이션한다 — 도커 사용자 대다수가
        # 컨테이너 안에서 'localhost'가 자기 자신을 가리켜 RC 연결이 실패하는 문제
        # (2026-08-24 커뮤니티 피드백)를 설정 변경 없이 자동으로 완화한다. 사용자가 이미
        # 직접 값을 바꿔둔 경우는 건드리지 않는다.
        cursor.execute("SELECT `value` FROM settings WHERE `key` = 'RCLONE_RC_URL'")
        rc_row = cursor.fetchone()
        if rc_row and rc_row[0] == 'http://localhost:5572':
            cursor.execute(
                "UPDATE settings SET `value` = ? WHERE `key` = 'RCLONE_RC_URL'",
                ('http://localhost:5572,http://host.docker.internal:5572',)
            )

        conn.commit()

        # 초기 admin 계정 시딩
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            from werkzeug.security import generate_password_hash
            admin_hash = generate_password_hash('admin')
            cursor.execute("INSERT INTO users (username, password_hash, role, is_default_password, has_adult_access, has_audiobook_access) VALUES ('admin', ?, 'admin', 1, 1, 1)", (admin_hash,))
            conn.commit()
            print(f"[DB-Migration] {db_type} DB - admin/admin initial account created")

        # Legacy books.is_favorite -> user_favorites 1회 시드
        # 기존 전역 즐겨찾기 데이터를 모든 사용자 초기값으로 복제한 뒤, 이후부터는 계정별로 독립 운용
        cursor.execute("SELECT COUNT(*) FROM user_favorites")
        favorite_rows = cursor.fetchone()[0]
        if favorite_rows == 0:
            cursor.execute("SELECT COUNT(*) FROM books WHERE COALESCE(is_favorite, 0) = 1")
            legacy_fav_count = cursor.fetchone()[0]
            if legacy_fav_count > 0:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_favorites (user_id, book_id, created_at)
                    SELECT u.id, b.id, CURRENT_TIMESTAMP
                    FROM users u
                    JOIN books b ON COALESCE(b.is_favorite, 0) = 1
                """)
                conn.commit()
                print(f"[DB-Migration] {db_type} DB - migrated legacy favorites into user_favorites for all users")
    except Exception as e:
        print(f"[DB-Migration ERROR] Initial settings/users migration failed: {e}")


def _seed_category_permissions(conn, cursor):
    """기존 사용자 x 라이브러리 조합에 대해 카테고리 접근 권한을 일괄 1로 시딩한다."""
    # 권한 테이블 초기 데이터 시딩 (기존 사용자 및 라이브러리가 있을 때 권한 일괄 1로 주입)
    try:
        cursor.execute("SELECT id FROM users")
        u_ids = [r['id'] for r in cursor.fetchall()]
        cursor.execute("SELECT id FROM libraries")
        l_ids = [r['id'] for r in cursor.fetchall()]
        
        for uid in u_ids:
            for lid in l_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_category_permissions (user_id, library_id, has_access)
                    VALUES (?, ?, 1)
                """, (uid, lid))
        conn.commit()
    except Exception as seed_err:
        print(f"[DB-Migration ERROR] user_category_permissions seeding failed: {seed_err}")


def _backfill_library_group_default_color(conn, cursor):
    """그룹 색상을 고르는 UI가 아직 없어 지금까지 모든 그룹이 스키마 기본값 '#a855f7'로
    저장돼 테마를 켜도 사이드바 그룹 아이콘만 항상 보라색으로 고정되던 문제를 보정한다.
    색을 NULL로 되돌리면 프런트가 자체적으로 var(--app-accent)(현재 테마 강조색)를
    fallback으로 사용하므로 앞으로는 테마를 따라간다. 리터럴 기본값과 정확히 일치하는
    행만 건드리므로(향후 색상 선택 UI가 생겨도) 반복 실행해도 안전하다."""
    try:
        cursor.execute("UPDATE library_groups SET color = NULL WHERE color = '#a855f7'")
        conn.commit()
        if (cursor.rowcount or 0) > 0:
            print(f"[DB-Migration] library_groups - reset hardcoded default color on {cursor.rowcount} rows")
    except Exception as color_backfill_err:
        print(f"[DB-Migration ERROR] library_groups default color backfill failed: {color_backfill_err}")


def _rebuild_series_summary_if_needed(conn, db_type):
    """MariaDB 환경에서 시리즈 요약 테이블이 아직 준비 안 됐으면 최초 1회 생성한다.

    주의: is_remote 는 운영자가 UI에서 관리하는 의도값이다. 과거에는 서버 기동 시
    physical_path 기반 자동 판별로 0 -> 1 보정을 수행했지만, SMB/CIFS/NFS 같은 NAS
    마운트나 사용자가 수동 해제한 라이브러리까지 다시 체크되는 부작용이 있어 더 이상
    startup 단계에서 덮어쓰지 않는다.
    """
    # 주의: is_remote 는 운영자가 UI에서 관리하는 의도값이다.
    # 과거에는 서버 기동 시 physical_path 기반 자동 판별로 0 -> 1 보정을 수행했지만,
    # SMB/CIFS/NFS 같은 NAS 마운트나 사용자가 수동 해제한 라이브러리까지 다시 체크되는
    # 부작용이 있어 더 이상 startup 단계에서 덮어쓰지 않는다.

    try:
        is_mariadb = hasattr(conn, '_conn') or type(conn).__name__.startswith(('Mariadb', 'PooledMariaDB'))
        if is_mariadb and db_type != 'audiobook':
            from repositories.mariadb.series_repository import SeriesRepository
            if SeriesRepository.rebuild_summary(db_type, only_if_unready=True):
                print(f"[DB-Migration] {db_type} DB - initial series summary created")
    except Exception as summary_err:
        print(f"[DB-Migration ERROR] {db_type} series summary initialization failed: {summary_err}")


def _backfill_audiobook_last_listened_at(conn, cursor, db_type):
    """오디오북 진행률 레거시 데이터 중 last_listened_at 누락분을 1회성으로 보정한다.
    MariaDB는 NULL 대신 '0000-00-00 00:00:00' 제로데이트 sentinel도 쓸 수 있어 그 경우까지
    함께 검사한다 (예전에는 이 sentinel 처리가 tools/db_schema_updater.py 쪽에만 있고
    이쪽 database.py 유래 버전에는 빠져 있었다 - 통합하면서 반영)."""
    if db_type != 'audiobook':
        return
    try:
        is_mariadb = hasattr(conn, '_conn') or type(conn).__name__.startswith(('Mariadb', 'PooledMariaDB'))
        if is_mariadb:
            cursor.execute("""
                UPDATE audiobook_progress p
                LEFT JOIN audiobooks a ON a.id = p.audiobook_id
                SET p.last_listened_at = COALESCE(a.updated_at, CURRENT_TIMESTAMP)
                WHERE (p.last_listened_at IS NULL OR TRIM(CAST(p.last_listened_at AS CHAR)) = '' OR p.last_listened_at = '0000-00-00 00:00:00')
                  AND (COALESCE(p.current_time, 0) > 0 OR COALESCE(p.is_completed, 0) = 1)
            """)
        else:
            cursor.execute("""
                UPDATE audiobook_progress
                SET last_listened_at = COALESCE(
                    (SELECT a.updated_at FROM audiobooks a WHERE a.id = audiobook_progress.audiobook_id),
                    CURRENT_TIMESTAMP
                )
                WHERE (last_listened_at IS NULL OR TRIM(COALESCE(last_listened_at, '')) = '')
                  AND (COALESCE(current_time, 0) > 0 OR COALESCE(is_completed, 0) = 1)
            """)
        conn.commit()
        if (cursor.rowcount or 0) > 0:
            print(f"[DB-Migration] audiobook DB - backfilled last_listened_at rows: {cursor.rowcount}")
    except Exception as audio_backfill_err:
        print(f"[DB-Migration ERROR] audiobook_progress last_listened_at backfill failed: {audio_backfill_err}")


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


def _fix_mariadb_column_collations():
    """일부 컬럼의 charset/collation을 utf8mb4/utf8mb4_bin으로 강제 보정한다
    (경로/파일명 비교가 대소문자 구분 바이너리여야 하는 컬럼들)."""
    from tools.migrator_sqlite_to_mariadb import connect_mariadb
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


def run_full_migration():
    """4개 미디어 세션(general/adult/audiobook/video)의 스키마를 최신 상태로 동기화한다.

    database.py의 init_databases()와 tools/db_schema_updater.py 양쪽에서 호출되는
    단일 진입점이다 - 예전엔 두 곳이 각자 다른(그리고 실제로 서로 갈라진 적이 있는)
    마이그레이션 로직을 갖고 있었다. 지금은 이 함수 하나가 유일한 "부족한 스키마
    생성/백필" 로직이라, 앞으로 스키마를 바꿀 땐 이 파일(과 _SCHEMA_SQL/_INDEXES_SQL)만
    고치면 두 진입점 모두에 자동으로 반영된다."""
    import database

    startup_db_sanity_check()

    for db_type in ['general', 'adult', 'audiobook', 'video']:
        conn, cursor = _connect_and_init_schema(db_type, _SCHEMA_SQL)
        if conn is None:
            continue

        _migrate_schema_and_dedupe_progress(conn, cursor, db_type, _SCHEMA_SQL)
        _create_indexes_and_cleanup_fts(conn, cursor, _INDEXES_SQL)
        _seed_settings_and_admin(conn, cursor, db_type)
        _seed_category_permissions(conn, cursor)
        _backfill_audiobook_last_listened_at(conn, cursor, db_type)
        _backfill_library_group_default_color(conn, cursor)
        if db_type == 'video' and not database.is_mariadb_mode():
            _backfill_html_entities_video_titles_sqlite(conn)
        _rebuild_series_summary_if_needed(conn, db_type)

        conn.close()

    if database.is_mariadb_mode():
        # MariaDB는 executescript 기반 범용 diff(_migrate_schema_and_dedupe_progress/
        # _create_indexes_and_cleanup_fts)가 다이얼렉트 차이로 신뢰할 수 없는 컬럼/인덱스가
        # 있어, 수작업으로 검증된 목록을 안전망으로 추가 실행한다.
        _ensure_mariadb_columns()
        _ensure_mariadb_indexes()
        _backfill_html_entities_video_titles_mariadb()
        _fix_mariadb_column_collations()
