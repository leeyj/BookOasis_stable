# -*- coding: utf-8 -*-
import os
import sqlite3
import threading
import queue
import sys
import re

# DB 파일이 저장될 경로 설정 (media_server/db/ 하위)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'db')
os.makedirs(DB_DIR, exist_ok=True)

DB_GENERAL_PATH = os.path.join(DB_DIR, 'media_general.db')
DB_ADULT_PATH = os.path.join(DB_DIR, 'media_adult.db')
SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get('SQLITE_BUSY_TIMEOUT_MS', '60000') or '60000')

class PooledConnection(sqlite3.Connection):
    def init_pool(self, pool):
        self._pool = pool
        self._is_returned = False

    def close(self):
        """커넥션을 닫지 않고 풀로 반환합니다."""
        if hasattr(self, '_pool') and self._pool:
            if not self._is_returned:
                try:
                    # sqlite3 기본 close()처럼 미완료 트랜잭션을 정리해
                    # 재사용 커넥션이 오래된 읽기 스냅샷을 유지하지 않도록 합니다.
                    self.rollback()
                except sqlite3.ProgrammingError:
                    pass
                except sqlite3.OperationalError:
                    pass
                self._is_returned = True
                self._pool.release_connection(self)
        else:
            super().close()

    def force_close(self):
        """물리적으로 커넥션을 닫습니다."""
        super().close()

class SQLiteConnectionPool:
    def __init__(self, db_path, max_size):
        self.db_path = db_path
        self.max_size = max_size
        self.pool = queue.Queue(maxsize=max_size)
        self.allocated = 0
        self.lock = threading.Lock()

    def get_connection(self, wait_timeout=30.0):
        # 1. 풀에 유휴 커넥션이 있는지 확인
        try:
            conn = self.pool.get_nowait()
            conn._is_returned = False
            return conn
        except queue.Empty:
            pass

        # 2. 최대 크기 미만인 경우 새로 연결 생성
        with self.lock:
            if self.allocated < self.max_size:
                conn = sqlite3.connect(self.db_path, timeout=30.0, factory=PooledConnection, check_same_thread=False)
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute("PRAGMA foreign_keys = ON;")
                    conn.execute(f"PRAGMA busy_timeout = {max(1000, SQLITE_BUSY_TIMEOUT_MS)};")
                except sqlite3.OperationalError:
                    pass
                conn.row_factory = sqlite3.Row
                conn.init_pool(self)
                self.allocated += 1
                return conn

        # 3. 자리가 생길 때까지 대기
        try:
            conn = self.pool.get(block=True, timeout=max(0.01, float(wait_timeout)))
            conn._is_returned = False
            return conn
        except queue.Empty:
            raise sqlite3.OperationalError(f"Database connection pool exhausted. Timeout waiting for connection ({wait_timeout}s).")

    def release_connection(self, conn):
        with self.lock:
            # 리사이징으로 풀 크기가 줄어든 경우 초과분은 물리적으로 닫음
            if self.allocated > self.max_size:
                try:
                    conn.force_close()
                except Exception:
                    pass
                self.allocated -= 1
                return

        try:
            self.pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.force_close()
            except Exception:
                pass
            with self.lock:
                self.allocated -= 1

    def resize(self, new_size):
        with self.lock:
            if new_size == self.max_size:
                return
            print(f"[SQLiteConnectionPool] Pool resizing: {self.max_size} -> {new_size} (Target: {self.db_path})")
            self.max_size = new_size
            new_pool = queue.Queue(maxsize=new_size)
            
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    if new_pool.full():
                        try:
                            conn.force_close()
                        except Exception:
                            pass
                        self.allocated -= 1
                    else:
                        new_pool.put_nowait(conn)
                except queue.Empty:
                    break
            self.pool = new_pool

    def get_stats(self):
        with self.lock:
            allocated = self.allocated
            max_size = self.max_size
            idle = self.pool.qsize()

        in_use = max(0, allocated - idle)
        util_pct = (in_use / max_size * 100.0) if max_size > 0 else 0.0
        return {
            'allocated': allocated,
            'idle': idle,
            'in_use': in_use,
            'max_size': max_size,
            'utilization_pct': util_pct,
        }

    def shutdown(self):
        """풀의 모든 유휴 커넥션에 대해 WAL 체크포인트를 수행하고 물리적으로 닫습니다."""
        closed_count = 0
        checkpoint_done = False
        with self.lock:
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    # 첫 번째 커넥션에서만 WAL 체크포인트 수행
                    if not checkpoint_done:
                        try:
                            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                            checkpoint_done = True
                            print(f"[DB-Shutdown] WAL 체크포인트 완료: {self.db_path}")
                        except Exception as ckpt_err:
                            print(f"[DB-Shutdown] WAL 체크포인트 실패 (무시하고 계속): {ckpt_err}")
                    try:
                        conn.force_close()
                        closed_count += 1
                    except Exception:
                        pass
                except queue.Empty:
                    break
            self.allocated = max(0, self.allocated - closed_count)
        print(f"[DB-Shutdown] 커넥션 {closed_count}개 정리 완료: {self.db_path}")

_pools = {'general': None, 'adult': None}
_pools_lock = threading.Lock()
_shutdown_in_progress = False

_cached_pool_size = None
_pool_size_cache_lock = threading.Lock()

def invalidate_pool_size_cache():
    """DB 풀 크기 캐시를 무효화하여 다음 커넥션 요청 시 DB에서 다시 로드하도록 합니다."""
    global _cached_pool_size
    with _pool_size_cache_lock:
        _cached_pool_size = None

def shutdown_all_pools():
    """서버 종료 시 모든 DB 커넥션 풀을 안전하게 종료합니다. (WAL 체크포인트 포함)"""
    global _shutdown_in_progress
    if _shutdown_in_progress:
        return  # 중복 호출 방지
    _shutdown_in_progress = True
    
    print("[DB-Shutdown] 모든 DB 커넥션 풀 종료 시작...")
    with _pools_lock:
        for db_type, pool in _pools.items():
            if pool is not None:
                try:
                    pool.shutdown()
                except Exception as e:
                    print(f"[DB-Shutdown] {db_type} 풀 종료 중 오류: {e}")
    print("[DB-Shutdown] 모든 DB 커넥션 풀 종료 완료.")

def _get_pool_size_raw():
    global _cached_pool_size
    with _pool_size_cache_lock:
        if _cached_pool_size is not None:
            return _cached_pool_size

    db_path = DB_GENERAL_PATH
    if not os.path.exists(db_path):
        return 5
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if cursor.fetchone():
            cursor.execute("SELECT value FROM settings WHERE key = 'DB_POOL_SIZE'")
            row = cursor.fetchone()
            if row:
                conn.close()
                val = int(row[0])
                val = max(1, min(50, val))
                with _pool_size_cache_lock:
                    _cached_pool_size = val
                return val
        conn.close()
    except Exception:
        pass
    
    # 캐시 갱신 실패 혹은 기본값 반환 시에도 캐싱 처리하여 다음 연결 시 불필요한 반복 쿼리 방지
    with _pool_size_cache_lock:
        _cached_pool_size = 5
    return 5

def get_connection(db_type='general', wait_timeout=30.0):
    """SQLite 데이터베이스 연결 반환 (커넥션 풀 적용)"""
    global _pools
    db_path = DB_ADULT_PATH if db_type == 'adult' else DB_GENERAL_PATH
    
    pool_size = _get_pool_size_raw()
    
    with _pools_lock:
        pool = _pools.get(db_type)
        if pool is None:
            pool = SQLiteConnectionPool(db_path, pool_size)
            _pools[db_type] = pool
        elif pool.max_size != pool_size:
            pool.resize(pool_size)
            
    return pool.get_connection(wait_timeout=wait_timeout)

def get_pool_stats(db_type='general'):
    """현재 커넥션 풀 상태 스냅샷을 반환합니다."""
    with _pools_lock:
        pool = _pools.get(db_type)

    if pool is None:
        return {
            'initialized': False,
            'allocated': 0,
            'idle': 0,
            'in_use': 0,
            'max_size': _get_pool_size_raw(),
            'utilization_pct': 0.0,
        }

    stats = pool.get_stats()
    stats['initialized'] = True
    return stats

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
    
    for table_name, cols in table_cols.items():
        # 1. 해당 테이블의 실존 컬럼 정보 조회
        try:
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
                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def_clean}"
                try:
                    cursor.execute(alter_query)
                    conn.commit()
                    print(f"[DB-Migration] Dynamic schema column added: {table_name}.{col_name} ({col_def_clean.strip()})")
                except Exception as e:
                    print(f"[DB-Migration ERROR] Failed to add dynamic column ({alter_query}): {e}")


def ensure_books_search_index(conn):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS books_search USING fts5(
                title,
                series_name,
                author,
                summary,
                content='books',
                content_rowid='id',
                tokenize='unicode61'
            )
            """
        )

        # 운영 안정성을 위해 FTS 실시간 동기화 트리거는 기본적으로 비활성화합니다.
        # 검색 인덱스는 스케줄러 배치 작업에서 주기적으로 재빌드합니다.
        cursor.executescript(
            """
            DROP TRIGGER IF EXISTS books_search_ai;
            DROP TRIGGER IF EXISTS books_search_ad;
            DROP TRIGGER IF EXISTS books_search_au;
            """
        )

        cursor.execute("SELECT COUNT(*) FROM books")
        books_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM books_search")
        search_count = cursor.fetchone()[0]
        if books_count != search_count:
            cursor.execute("INSERT INTO books_search(books_search) VALUES ('rebuild')")
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.rollback()
        if 'fts5' in str(e).lower() or 'no such module' in str(e).lower():
            print(f"[DB-Migration Warning] FTS5 unavailable; OPDS search falls back to LIKE queries: {e}")
            return
        raise

def startup_db_sanity_check():
    """
    앱 초기 기동 시 DB 파일 및 WAL/SHM 파일 무결성을 검증합니다.
    - integrity_check 실패 또는 WAL 파일 손상 감지 시 WAL/SHM 파일을 자동 제거합니다.
    - 메인 DB 파일 자체의 손상은 경고 로그만 출력하고 서버 기동은 계속합니다.
    """
    db_map = {
        'general': DB_GENERAL_PATH,
        'adult'  : DB_ADULT_PATH,
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
                # WAL 체크포인트 수행 후 임시 파일 정리
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
                for extra in [wal_path, shm_path]:
                    if os.path.exists(extra):
                        try:
                            os.remove(extra)
                            print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 정리 완료")
                        except Exception as rm_err:
                            print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 제거 실패: {rm_err}")
                print(f"[DB-Sanity] {db_type} DB — 무결성 정상, WAL 체크포인트 완료")
            else:
                # integrity_check 실패 → WAL/SHM만 제거 시도 (메인 DB는 보존)
                conn.close()
                print(f"[DB-Sanity] {db_type} DB — 무결성 이상 감지: {result[:3]}")
                print(f"[DB-Sanity] {db_type} DB — 손상된 WAL/SHM 파일 제거 시도...")
                for extra in [wal_path, shm_path]:
                    if os.path.exists(extra):
                        try:
                            os.remove(extra)
                            print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 제거 완료")
                        except Exception as rm_err:
                            print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 제거 실패: {rm_err}")
                print(f"[DB-Sanity] {db_type} DB — WAL/SHM 제거 후 서버 기동을 계속합니다.")
                print(f"[DB-Sanity] 지속적인 오류 발생 시 tools/db_recovery.py 를 실행하세요.")

        except sqlite3.DatabaseError as e:
            # 메인 DB 파일 자체가 열리지 않는 경우
            print(f"[DB-Sanity] {db_type} DB — DB 접속 실패: {e}")
            print(f"[DB-Sanity] {db_type} DB — WAL/SHM 강제 제거 시도...")
            for extra in [wal_path, shm_path]:
                if os.path.exists(extra):
                    try:
                        os.remove(extra)
                        print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 제거 완료")
                    except Exception as rm_err:
                        print(f"[DB-Sanity] {db_type} DB — {os.path.basename(extra)} 제거 실패: {rm_err}")
        except Exception as e:
            print(f"[DB-Sanity] {db_type} DB — 예기치 못한 오류 (무시하고 계속): {e}")


def init_databases():
    """두 데이터베이스(일반, 성인)의 테이블 스키마 초기화"""
    schema = """
    CREATE TABLE IF NOT EXISTS libraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        physical_path TEXT NOT NULL,
        cron_schedule TEXT DEFAULT NULL,
        last_scanned_at DATETIME DEFAULT NULL,
        scan_status TEXT DEFAULT 'ready',
        is_remote INTEGER DEFAULT 0,
        vfs_refresh_before_scan INTEGER DEFAULT 0,
        rclone_rc_url TEXT DEFAULT NULL,
        icon TEXT DEFAULT 'fa-book',
        color TEXT DEFAULT '#94a3b8',
        hide_cover INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS scanner_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        task_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'pending',
        kwargs TEXT,
        stage TEXT,
        enqueue_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        started_at DATETIME DEFAULT NULL,
        finished_at DATETIME DEFAULT NULL,
        error_message TEXT
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
        file_mtime REAL DEFAULT 0.0,
        file_size INTEGER DEFAULT 0
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
        compress_type INTEGER
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

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_default_password INTEGER DEFAULT 1,
        has_adult_access INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_category_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        library_id INTEGER NOT NULL,
        has_access INTEGER DEFAULT 1,
        UNIQUE(user_id, library_id)
    );
    """

    indexes_schema = """
    CREATE INDEX IF NOT EXISTS idx_book_offsets_book_id ON book_offsets(book_id);
    CREATE INDEX IF NOT EXISTS idx_book_offsets_book_page ON book_offsets(book_id, page_idx);
    CREATE INDEX IF NOT EXISTS idx_books_series_name ON books(series_name);
    CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
    CREATE INDEX IF NOT EXISTS idx_books_is_favorite ON books(is_favorite);
    CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
    CREATE INDEX IF NOT EXISTS idx_books_series_lib_title ON books(series_name, library_id, title);
    CREATE INDEX IF NOT EXISTS idx_books_library_active_series ON books(library_id, COALESCE(is_deleted, 0), COALESCE(series_name, ''));
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_progress_book_user ON user_progress(book_id, user_id);
    CREATE INDEX IF NOT EXISTS idx_user_progress_last_read ON user_progress(user_id, last_read_at DESC);
    CREATE INDEX IF NOT EXISTS idx_user_progress_last_read_book ON user_progress(last_read_at DESC, book_id);
    CREATE INDEX IF NOT EXISTS idx_user_reading_log_user_date ON user_reading_log(user_id, read_date);
    CREATE INDEX IF NOT EXISTS idx_user_favorites_user_book ON user_favorites(user_id, book_id);
    CREATE INDEX IF NOT EXISTS idx_user_favorites_book ON user_favorites(book_id);
    CREATE INDEX IF NOT EXISTS idx_user_category_permissions_lookup ON user_category_permissions(user_id, library_id, has_access);
    """
    
    # 기동 전 WAL/SHM 무결성 자동 검증 및 정리
    startup_db_sanity_check()

    for db_type in ['general', 'adult']:
        conn = get_connection(db_type)
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()

        # 신규 표현식 인덱스 생성 전에 누락 컬럼을 먼저 보강해야 구버전 DB에서도 안전합니다.
        try:
            auto_migrate_schema(conn, schema)
        except Exception as migrate_err:
            print(f"[DB-Migration ERROR] Exception during pre-index schema auto-migration: {migrate_err}")
        
        # [마이그레이션] user_progress 중복 레코드 정리 및 고유 인덱스 설정 준비
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_progress'")
            if cursor.fetchone():
                # 1. 중복 레코드 삭제 (가장 최근 것 1개만 남김)
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
        
        # 테이블 생성 완료 후 별도 트랜잭션으로 인덱스 일괄 생성하여 SQLite OperationalError 예방
        cursor.executescript(indexes_schema)
        conn.commit()

        try:
            ensure_books_search_index(conn)
        except Exception as search_idx_err:
            print(f"[DB-Migration ERROR] books_search index setup failed: {search_idx_err}")
        
        # settings 테이블 초기값 주입 (ALADIN TTBKey)
        try:
            cursor.execute("SELECT value FROM settings WHERE key = 'ALADIN'")
            if not cursor.fetchone():
                # os.getenv 등을 위해 .env 파싱도 대비
                aladin_val = os.environ.get('ALADIN', '')
                if not aladin_val:
                    # 간단하게 env 파일 읽기 헬퍼
                    try:
                        env_path = os.path.join(BASE_DIR, '.env')
                        if os.path.exists(env_path):
                            with open(env_path, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip().startswith('ALADIN='):
                                        aladin_val = line.split('=', 1)[1].strip()
                                        break
                    except Exception as env_err:
                        print(f"[DB-Migration] .env load error: {env_err}")
                
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ALADIN', ?)", (aladin_val,))
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
                ('TAG_FILTER_SEARCH_SCOPE_ALL', '0'),
                ('SIDEBAR_TOP_CONTROLS', '0'),
                ('HDD_AGGRESSIVE_WARMUP', '0'),
                ('RCLONE_RC_URL', 'http://localhost:5572'),
                ('FTS_REBUILD_CRON', '30 4 * * *')
            ]
            for k, v in default_settings:
                cursor.execute("SELECT value FROM settings WHERE key = ?", (k,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))
            conn.commit()

            # 초기 admin 계정 시딩
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                from werkzeug.security import generate_password_hash
                admin_hash = generate_password_hash('admin')
                cursor.execute("INSERT INTO users (username, password_hash, role, is_default_password, has_adult_access) VALUES ('admin', ?, 'admin', 1, 1)", (admin_hash,))
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
        # 기존 라이브러리에 대한 원격 드라이브 자동 판별 보정
        try:
            cursor.execute("SELECT id, physical_path, is_remote FROM libraries")
            libs = cursor.fetchall()
            for lib in libs:
                if lib['is_remote'] == 0:
                    from utils.drive_helper import is_remote_path
                    if is_remote_path(lib['physical_path']):
                        cursor.execute("UPDATE libraries SET is_remote = 1 WHERE id = ?", (lib['id'],))
            conn.commit()
        except Exception as migration_err:
            print(f"[DB-Migration ERROR] libraries is_remote auto-detection fallback failed: {migration_err}")

        # 서버 재시작 시 고착된(Stuck) 스캔 상태 초기화 및 자동 복원(Auto-Resume) 연계 방어코드
        try:
            # 1. 취소 중이던 상태는 복원하지 않고 ready로 초기화하여 재스캔 구동 보장
            cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE scan_status = 'cancelling'")
            # 2. 스캔 중이던 상태는 interrupted로 보정하여 scheduler가 기동 시 Auto-Resume(자동 재스캔)을 구동하게 함
            cursor.execute("UPDATE libraries SET scan_status = 'interrupted' WHERE scan_status = 'scanning'")
            # 3. 큐 태스크 중 이미 running 중이던 작업만 실패 처리하고 pending(대기 중) 태스크는 이어서 수행하도록 유지
            cursor.execute("""
                UPDATE scanner_tasks 
                SET status = 'failed', 
                    error_message = 'Interrupted by server restart',
                    finished_at = CURRENT_TIMESTAMP
                WHERE status = 'running'
            """)
            conn.commit()
            print("[DB-Migration] Stuck scan states cleaned up. Pending queue and Auto-Resume chain preserved.")
        except Exception as reset_err:
            print(f"[DB-Migration ERROR] Scan status reset failed: {reset_err}")

        conn.close()

# DB 튜닝 레이어 서비스 위임 (하위 호환성 유지)
from services.db_tuning_service import is_db_tuning, optimize_database

if __name__ == '__main__':
    init_databases()
    print("Databases initialized successfully.")
