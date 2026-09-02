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
DB_AUDIOBOOK_PATH = os.path.join(DB_DIR, 'media_audiobook.db')
DB_VIDEO_PATH = os.path.join(DB_DIR, 'media_video.db')
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
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as err:
                    # OperationalError/DatabaseError 가 터진 커넥션은 오염된 커넥션이므로 풀로 돌려보내지 않고 즉시 폐기
                    self._is_returned = True
                    try:
                        super().close()
                    except Exception:
                        pass
                    if hasattr(self, '_pool') and self._pool:
                        with self._pool.lock:
                            self._pool.allocated = max(0, self._pool.allocated - 1)
                    return
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
        while True:
            try:
                conn = self.pool.get_nowait()
                conn._is_returned = False
                # 풀에서 꺼낸 커넥션이 썩었는지(Stale/malformed/disk I/O) 즉시 핑 검사
                try:
                    conn.execute("SELECT 1;")
                    return conn
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as test_err:
                    # 무효화되거나 손상된 썩은 커넥션은 즉시 풀에서 폐기
                    try:
                        conn.force_close()
                    except Exception:
                        pass
                    with self.lock:
                        self.allocated = max(0, self.allocated - 1)
            except queue.Empty:
                break

        # 2. 최대 크기 미만인 경우 새로 연결 생성
        with self.lock:
            if self.allocated < self.max_size:
                conn = sqlite3.connect(self.db_path, timeout=30.0, factory=PooledConnection, check_same_thread=False)
                try:
                    conn.create_function("CONCAT", -1, lambda *args: "".join(str(a) if a is not None else "" for a in args))
                    conn.execute(f"PRAGMA busy_timeout = {max(1000, SQLITE_BUSY_TIMEOUT_MS)};")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute("PRAGMA foreign_keys = ON;")
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

_pools = {'general': None, 'adult': None, 'audiobook': None, 'video': None}
_pools_lock = threading.Lock()
_shutdown_in_progress = False

MARIADB_DB_PREFIX = 'mariadb:media_'

def is_mariadb_mode():
    """현재 DB 엔진이 MariaDB/MySQL인지 확인"""
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    return engine in ('mariadb', 'mysql')

def get_db_path(db_type='general'):
    """db_type에 따른 데이터베이스 파일 경로(SQLite) 또는 MariaDB 식별자 문자열 반환"""
    # MariaDB 모드이면 파일 경로 대신 식별자 문자열 반환 (로그/큐 등에서 SQLite 경로 혼선 방지)
    if is_mariadb_mode():
        return f"{MARIADB_DB_PREFIX}{db_type}"
    if db_type == 'adult':
        return DB_ADULT_PATH
    elif db_type == 'audiobook':
        return DB_AUDIOBOOK_PATH
    elif db_type == 'video':
        return DB_VIDEO_PATH
    return DB_GENERAL_PATH

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
                    print(f"[DB-Shutdown] {db_type} SQLite 풀 종료 중 오류: {e}")
        for db_type, pool in _mariadb_pools.items():
            if pool is not None:
                try:
                    pool.shutdown()
                except Exception as e:
                    print(f"[DB-Shutdown] {db_type} MariaDB 풀 종료 중 오류: {e}")
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
            cursor.execute("SELECT `value` FROM settings WHERE `key` = 'DB_POOL_SIZE'")
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

class DictRow(dict):
    """sqlite3.Row 호환 딕셔너리 서브클래스 (row['col'], row.get('col'), row[0] 인덱싱 지원)"""
    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.values())[item]
        return super().__getitem__(item)

class MariadbCursorWrapper:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def _convert_sql(self, sql):
        if not sql:
            return sql
        # SQLite 전용 PRAGMA 및 raw BEGIN 명령은 MariaDB(PyMySQL)에서 안전 우회 (conn.commit()으로 관리)
        clean_sql = sql.strip().upper()
        if clean_sql.startswith('PRAGMA') or clean_sql in ('BEGIN', 'BEGIN TRANSACTION', 'BEGIN WORK'):
            return "SELECT 1"

        converted = sql

        # 1. ? 바인딩 파라미터를 PyMySQL용 %s로 변환
        if '?' in converted:
            converted = converted.replace('?', '%s')

        # 2. SQLite 전용 구문(INSERT OR IGNORE, INSERT OR REPLACE) 변환
        if 'INSERT OR IGNORE INTO' in converted:
            converted = converted.replace('INSERT OR IGNORE INTO', 'INSERT IGNORE INTO')
        elif 'INSERT OR IGNORE' in converted:
            converted = converted.replace('INSERT OR IGNORE', 'INSERT IGNORE')

        if 'INSERT OR REPLACE INTO' in converted:
            converted = converted.replace('INSERT OR REPLACE INTO', 'REPLACE INTO')
        elif 'INSERT OR REPLACE' in converted:
            converted = converted.replace('INSERT OR REPLACE', 'REPLACE INTO')

        # 3. SQLite ON CONFLICT(file_path) DO UPDATE SET EXCLUDED... ➔ MariaDB ON DUPLICATE KEY UPDATE...
        if 'ON CONFLICT' in converted and 'EXCLUDED' in converted:
            import re
            m = re.search(r'ON\s+CONFLICT\s*\([^)]*\)\s*DO\s+UPDATE\s+SET\s+(.*)', converted, re.DOTALL | re.IGNORECASE)
            if m:
                set_clause = m.group(1)
                set_clause = re.sub(r'EXCLUDED\.([a-zA-Z0-9_]+)', r'VALUES(\1)', set_clause, flags=re.IGNORECASE)
        # 4. SQLite datetime('now', ...) ➔ MariaDB NOW() / DATE_SUB(NOW(), INTERVAL x DAY) 자동 변환
        if 'datetime(' in converted.lower() and 'now' in converted.lower():
            import re
            converted = re.sub(r"datetime\s*\(\s*'now'\s*,\s*'-(\d+)\s+days?'[^)]*\)", r"DATE_SUB(NOW(), INTERVAL \1 DAY)", converted, flags=re.IGNORECASE)
            converted = re.sub(r"datetime\s*\(\s*'now'[^)]*\)", r"NOW()", converted, flags=re.IGNORECASE)

        # 5. MariaDB/MySQL 예약어 key / value 자동 백틱 이스케이프 보안책
        if 'settings' in converted and '`key` ' not in converted:
            import re
            converted = re.sub(r'\bWHERE\s+key\b', 'WHERE `key`', converted, flags=re.IGNORECASE)
            converted = re.sub(r'\bSET\s+key\b', 'SET `key`', converted, flags=re.IGNORECASE)
            converted = re.sub(r'\bSELECT\s+value\b', 'SELECT `value`', converted, flags=re.IGNORECASE)
            converted = re.sub(r'\bSET\s+value\b', 'SET `value`', converted, flags=re.IGNORECASE)

        return converted


    def execute(self, sql, params=None):
        converted_sql = self._convert_sql(sql)
        self._cursor.execute(converted_sql, params)
        return self

    def executemany(self, sql, seq_of_params):
        converted_sql = self._convert_sql(sql)
        self._cursor.executemany(converted_sql, seq_of_params)
        return self

    def executescript(self, script):
        if not script:
            return
        statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
        for stmt in statements:
            try:
                self.execute(stmt)
            except Exception:
                pass

    def fetchone(self):
        row = self._cursor.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return DictRow(row)
        return DictRow(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return [DictRow(row) for row in rows]
        return [DictRow(r) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        try:
            return self._cursor.close()
        except Exception:
            pass

class MariadbConnectionWrapper:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self):
        return MariadbCursorWrapper(self._conn.cursor())

    def executescript(self, script):
        return self.cursor().executescript(script)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        try:
            return self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            return self._conn.close()
        except Exception:
            pass

class PooledMariaDBConnectionWrapper(MariadbConnectionWrapper):
    def __init__(self, raw_conn, pool):
        super().__init__(raw_conn)
        self._pool = pool
        self._is_closed = False

    def close(self):
        if not self._is_closed:
            self._is_closed = True
            if self._pool:
                self._pool.release(self._conn)
            else:
                super().close()

class MariaDBConnectionPool:
    """MariaDB 스레드 세이프 커넥션 풀 (DB_POOL_SIZE 연동)"""
    def __init__(self, db_type, max_size=50):
        self.db_type = db_type
        self.max_size = max_size
        self.pool = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
        self.allocated = 0

    def _create_raw_connection(self):
        import pymysql
        import pymysql.cursors
        host = os.environ.get('MARIADB_HOST', '127.0.0.1')
        port = int(os.environ.get('MARIADB_PORT', '3306') or '3306')
        user = os.environ.get('MARIADB_USER', 'root')
        password = os.environ.get('MARIADB_PASSWORD', '')
        prefix = os.environ.get('MARIADB_DATABASE_PREFIX', 'media_')
        dbname = f"{prefix}{self.db_type}"
        connect_timeout = max(1, int(os.environ.get('MARIADB_CONNECT_TIMEOUT', '10') or '10'))
        read_timeout = max(1, int(os.environ.get('MARIADB_READ_TIMEOUT', '90') or '90'))
        write_timeout = max(1, int(os.environ.get('MARIADB_WRITE_TIMEOUT', '90') or '90'))
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            charset='utf8mb4',
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout
        )

    def get_connection(self, wait_timeout=30.0):
        try:
            conn = self.pool.get(block=True, timeout=0.01)
            try:
                conn.ping(reconnect=True)
                return PooledMariaDBConnectionWrapper(conn, self)
            except Exception:
                with self.lock:
                    self.allocated = max(0, self.allocated - 1)
        except queue.Empty:
            pass

        with self.lock:
            if self.allocated < self.max_size:
                raw_conn = self._create_raw_connection()
                self.allocated += 1
                return PooledMariaDBConnectionWrapper(raw_conn, self)

        try:
            conn = self.pool.get(block=True, timeout=wait_timeout)
            try:
                conn.ping(reconnect=True)
                return PooledMariaDBConnectionWrapper(conn, self)
            except Exception:
                with self.lock:
                    self.allocated = max(0, self.allocated - 1)
                raw_conn = self._create_raw_connection()
                with self.lock:
                    self.allocated += 1
                return PooledMariaDBConnectionWrapper(raw_conn, self)
        except queue.Empty:
            raise TimeoutError(f"MariaDB 커넥션 풀 선점 시간 초과 ({wait_timeout}초)")

    def release(self, raw_conn):
        if raw_conn is None:
            return
        try:
            raw_conn.rollback()
            self.pool.put_nowait(raw_conn)
        except Exception:
            with self.lock:
                self.allocated = max(0, self.allocated - 1)
            try:
                raw_conn.close()
            except Exception:
                pass

    def resize(self, new_size):
        with self.lock:
            self.max_size = new_size
            old_queue = self.pool
            self.pool = queue.Queue(maxsize=new_size)
            while not old_queue.empty():
                try:
                    conn = old_queue.get_nowait()
                    if self.pool.full():
                        try:
                            conn.close()
                        except Exception:
                            pass
                        self.allocated = max(0, self.allocated - 1)
                    else:
                        self.pool.put_nowait(conn)
                except queue.Empty:
                    break

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
        with self.lock:
            while not self.pool.empty():
                try:
                    conn = self.pool.get_nowait()
                    try:
                        conn.close()
                    except Exception:
                        pass
                except queue.Empty:
                    break
            self.allocated = 0

_mariadb_pools = {'general': None, 'adult': None, 'audiobook': None, 'video': None}

def get_mariadb_connection(db_type='general'):
    pool_size = _get_pool_size_raw()
    global _mariadb_pools
    with _pools_lock:
        pool = _mariadb_pools.get(db_type)
        if pool is None:
            pool = MariaDBConnectionPool(db_type, pool_size)
            _mariadb_pools[db_type] = pool
        elif pool.max_size != pool_size:
            pool.resize(pool_size)
    return pool.get_connection()

def get_connection(db_type='general', wait_timeout=30.0):
    """데이터베이스 연결 반환 (SQLite 커넥션 풀 또는 MariaDB 커넥션 풀 지원)"""
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    if engine in ('mariadb', 'mysql'):
        return get_mariadb_connection(db_type)

    global _pools
    db_path = get_db_path(db_type)
    
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
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    with _pools_lock:
        if engine in ('mariadb', 'mysql'):
            pool = _mariadb_pools.get(db_type)
        else:
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

def init_databases():
    """4개 미디어 세션(general/adult/audiobook/video)의 테이블 스키마 초기화 (마이그레이션 레이어에 위임).

    실제 컬럼/인덱스 diff + 백필 로직은 services/db_migration_service.py의
    run_full_migration()에 있다 - 예전엔 이 파일에 커넥션 풀링과 함께 섞여 있었고,
    tools/db_schema_updater.py에도 MariaDB 전용으로 따로 구현돼 있어 새 컬럼을 추가할
    때마다 두 곳을 손으로 동기화해야 했다. 지금은 이 함수와 db_schema_updater.py
    둘 다 run_full_migration() 하나만 호출한다."""
    run_full_migration()


# DB 튜닝 레이어 서비스 위임 (하위 호환성 유지)
from services.db_tuning_service import is_db_tuning, optimize_database
# DB 스키마 마이그레이션/백필 레이어 서비스 위임 (하위 호환성 유지)
from services.db_migration_service import run_full_migration

if __name__ == '__main__':
    init_databases()
    print("Databases initialized successfully.")
