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

from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA as MARIADB_SCHEMA_DDL


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
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;")
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
    """SQLite 테이블 스키마 정보를 동적으로 조회하여 MariaDB에 해당 테이블이 없으면 자동 생성"""
    if table_name.startswith('books_search') or table_name.startswith('sqlite_') or table_name.startswith('lost_and_found'):
        return

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
        else:
            m_type = 'TEXT'

        if is_pk:
            col_defs.append(f"`{name}` {m_type} AUTO_INCREMENT PRIMARY KEY")
        else:
            col_defs.append(f"`{name}` {m_type}")

    col_str = ",\n  ".join(col_defs)
    ddl = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n  {col_str}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;"
    ma_cur = ma_conn.cursor()
    try:
        ma_cur.execute(ddl)
        ma_conn.commit()
    except Exception as e:
        print(f"  [!] Dynamic DDL Create Warning for table `{table_name}`: {e}")

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

