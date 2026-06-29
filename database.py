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

class PooledConnection(sqlite3.Connection):
    def init_pool(self, pool):
        self._pool = pool
        self._is_returned = False

    def close(self):
        """커넥션을 닫지 않고 풀로 반환합니다."""
        if hasattr(self, '_pool') and self._pool:
            if not self._is_returned:
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

    def get_connection(self):
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
                except sqlite3.OperationalError:
                    pass
                conn.row_factory = sqlite3.Row
                conn.init_pool(self)
                self.allocated += 1
                return conn

        # 3. 자리가 생길 때까지 대기
        try:
            conn = self.pool.get(block=True, timeout=30.0)
            conn._is_returned = False
            return conn
        except queue.Empty:
            raise sqlite3.OperationalError("Database connection pool exhausted. Timeout waiting for connection.")

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
            print(f"[SQLiteConnectionPool] 풀 리사이징: {self.max_size} -> {new_size} (대상: {self.db_path})")
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

_pools = {'general': None, 'adult': None}
_pools_lock = threading.Lock()

def _get_pool_size_raw():
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
                return max(1, min(50, val))
        conn.close()
    except Exception:
        pass
    return 5

def get_connection(db_type='general'):
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
            
    return pool.get_connection()

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
            print(f"[DB-Migration Warning] 테이블 {table_name} 정보 조회 실패 (신규 테이블 생성 전일 수 있음): {e}")
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
                    print(f"[DB-Migration] 동적 스키마 컬럼 추가 완료: {table_name}.{col_name} ({col_def_clean.strip()})")
                except Exception as e:
                    print(f"[DB-Migration ERROR] 동적 컬럼 추가 실패 ({alter_query}): {e}")

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
        rclone_rc_url TEXT DEFAULT NULL
    );

    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        library_id INTEGER REFERENCES libraries(id),
        title TEXT NOT NULL,
        series_name TEXT,
        author TEXT,
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        pages_read INTEGER DEFAULT 0,
        is_completed INTEGER DEFAULT 0,
        last_read_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_reading_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER REFERENCES books(id),
        user_id INTEGER NOT NULL,
        pages_read_delta INTEGER NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        read_date DATE DEFAULT CURRENT_DATE
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
    CREATE INDEX IF NOT EXISTS idx_book_offsets_book_id ON book_offsets(book_id);
    CREATE INDEX IF NOT EXISTS idx_books_series_name ON books(series_name);
    CREATE INDEX IF NOT EXISTS idx_books_library_id ON books(library_id);
    CREATE INDEX IF NOT EXISTS idx_books_is_favorite ON books(is_favorite);
    CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);
    CREATE INDEX IF NOT EXISTS idx_user_progress_book_user ON user_progress(book_id, user_id);
    CREATE INDEX IF NOT EXISTS idx_user_reading_log_user_date ON user_reading_log(user_id, read_date);

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS scanner_progress (
        library_id TEXT,
        folder_path TEXT PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_default_password INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    for db_type in ['general', 'adult']:
        conn = get_connection(db_type)
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()
        
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
                        print(f"[DB-Migration] .env 로드 에러: {env_err}")
                
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ALADIN', ?)", (aladin_val,))
                conn.commit()
                print(f"[DB-Migration] {db_type} DB - ALADIN 설정 초기 이식 완료: {aladin_val}")
            
            default_settings = [
                ('BOOK_THUMBNAIL_WIDTH', '160'),
                ('PAGE_LIMIT', '60'),
                ('VIEWER_FONT_SIZE', '18'),
                ('VIEWER_FONT_FAMILY', 'sans-serif'),
                ('DB_POOL_SIZE', '25'),
                ('SCANNER_WRITE_LOG', '1'),
                ('LAZY_SCAN_CRON', '0 3 * * *'),
                ('SYSTEM_MEM_LIMIT', '1536.0'),
                ('PROCESS_RSS_LIMIT', '2048.0'),
                ('RECENT_BOOKS_LIMIT', '30'),
                ('RCLONE_RC_URL', 'http://localhost:5572')
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
                cursor.execute("INSERT INTO users (username, password_hash, role, is_default_password) VALUES ('admin', ?, 'admin', 1)", (admin_hash,))
                conn.commit()
                print(f"[DB-Migration] {db_type} DB - admin/admin 초기 계정 생성 완료")
        except Exception as e:
            print(f"[DB-Migration ERROR] settings/users 초기 이식 실패: {e}")
        # 동적 스키마 자동 마이그레이터 구동 (테이블에 신규 필드가 추가되면 런타임에 동적으로 감지하여 ALTER TABLE 자동 수행)
        try:
            auto_migrate_schema(conn, schema)
        except Exception as migrate_err:
            print(f"[DB-Migration ERROR] 동적 스키마 자동 마이그레이션 도중 예외 발생: {migrate_err}")
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
            print(f"[DB-Migration ERROR] libraries is_remote 자동 판별 보정 실패: {migration_err}")

        # 서버 재시작 시 고착된(Stuck) 스캔 상태 초기화 방어코드
        try:
            cursor.execute("UPDATE libraries SET scan_status = 'ready' WHERE scan_status = 'scanning'")
            conn.commit()
        except Exception as reset_err:
            print(f"[DB-Migration ERROR] 스캔 상태 초기화 실패: {reset_err}")

        conn.close()

# DB 튜닝 진행 중 전역 상태 딕셔너리
_tuning_status = {
    'general': False,
    'adult': False
}

def is_db_tuning(db_type='general'):
    """현재 데이터베이스가 튜닝(VACUUM 등) 작업 중인지 반환"""
    return _tuning_status.get(db_type, False)

def optimize_database(db_type='general'):
    """
    데이터베이스 최적화를 수행합니다:
    1. ANALYZE를 실행해 질의 최적화 통계 갱신
    2. REINDEX를 실행해 인덱스 트리 재정렬
    3. 별도 커넥션 세션으로 VACUUM을 구동하여 삭제된 빈 물리 공간 파편화 회수
    """
    global _tuning_status
    if _tuning_status.get(db_type, False):
        print(f"[optimize_database] 이미 {db_type} 데이터베이스 최적화가 진행 중입니다.")
        return False, "이미 최적화 작업이 진행 중입니다."
        
    _tuning_status[db_type] = True
    print(f"[*] [{db_type}] 데이터베이스 최적화 엔진 기동 시작...")
    
    try:
        # 1. ANALYZE & REINDEX는 풀 커넥션을 통해 안전하게 실행
        conn = get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("ANALYZE;")
        cursor.execute("REINDEX;")
        conn.commit()
        conn.close()
        
        # 2. VACUUM은 트랜잭션 외부(autocommit) 모드에서 수행해야 하므로 
        # 커넥션 풀을 타지 않는 독립 물리 커넥션으로 수행
        db_path = DB_ADULT_PATH if db_type == 'adult' else DB_GENERAL_PATH
        conn_vacuum = sqlite3.connect(db_path, timeout=60.0)
        conn_vacuum.isolation_level = None  # autocommit 설정
        conn_vacuum.execute("VACUUM;")
        conn_vacuum.close()
        
        print(f"[+] [{db_type}] 데이터베이스 파편화 회수 및 최적화 튜닝 최종 성공!")
        return True, "최적화 완료"
    except Exception as e:
        print(f"[!] [{db_type}] 데이터베이스 최적화 작업 중 오류: {e}")
        return False, str(e)
    finally:
        _tuning_status[db_type] = False

if __name__ == '__main__':
    init_databases()
    print("Databases initialized successfully.")
