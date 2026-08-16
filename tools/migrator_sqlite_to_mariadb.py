# -*- coding: utf-8 -*-
"""
migrator_sqlite_to_mariadb.py - SQLite to MariaDB 1-Click 자동 데이터 이전 도구

BookOasis 미디어 서버의 4개 SQLite 데이터베이스(media_general.db, media_adult.db, media_audiobook.db, media_video.db)의
모든 테이블 및 레코드를 MariaDB 엔터프라이즈 데이터베이스로 고속 대량 이전합니다.
"""

import os
import sys
import time
import sqlite3
import argparse

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.insert(0, MEDIA_SERVER_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(MEDIA_SERVER_DIR, '.env'))

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    pymysql = None

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
    },
    'video': {
        'sqlite_path': os.path.join(MEDIA_SERVER_DIR, 'db', 'media_video.db'),
        'mariadb_db': f"{MARIADB_DATABASE_PREFIX}video"
    }
}

from tools.db_schema_updater import MARIADB_CENTRAL_SCHEMA as MARIADB_SCHEMA_DDL


def connect_mariadb(db_name=None):
    if pymysql is None:
        raise RuntimeError("PyMySQL 패키지가 필요합니다: pip install PyMySQL")
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


def inspect_sqlite_source(db_type, sqlite_path):
    """SQLite 원본의 존재 여부와 무결성을 변경 없이 검사합니다."""
    if not os.path.isfile(sqlite_path):
        return {
            'db_type': db_type,
            'path': sqlite_path,
            'exists': False,
            'integrity': 'missing',
            'table_count': 0,
        }

    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True, timeout=30.0)
    try:
        integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity = integrity_row[0] if integrity_row else 'unknown'
        table_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
              AND name NOT LIKE 'books_search%'
              AND name NOT LIKE 'lost_and_found%'
            """
        ).fetchone()[0]
        return {
            'db_type': db_type,
            'path': sqlite_path,
            'exists': True,
            'integrity': integrity,
            'table_count': table_count,
        }
    finally:
        conn.close()


def preflight_sqlite_sources(require_all=False):
    results = [
        inspect_sqlite_source(db_type, config['sqlite_path'])
        for db_type, config in DB_MAP.items()
    ]
    invalid = []
    for result in results:
        if not result['exists']:
            print(f"  [-] {result['db_type']}: 원본 파일 없음 ({result['path']})")
            if require_all:
                invalid.append(result['db_type'])
            continue
        print(
            f"  [+] {result['db_type']}: integrity={result['integrity']}, "
            f"tables={result['table_count']}"
        )
        if result['integrity'] != 'ok':
            invalid.append(result['db_type'])

    if invalid:
        raise RuntimeError(f"SQLite 원본 사전검사 실패: {', '.join(invalid)}")
    return results


def confirm_reset(assume_yes=False):
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(
            "MariaDB의 general/adult/audiobook DB를 모두 삭제합니다. "
            "계속하려면 RESET을 입력하세요:\n> "
        ).strip()
    except EOFError:
        return False
    return answer == 'RESET'

def ensure_mariadb_databases(reset=False):
    print(f"[MariaDB Setup] Host={MARIADB_HOST}:{MARIADB_PORT}, User={MARIADB_USER}")
    conn = connect_mariadb(db_name=None)
    try:
        cursor = conn.cursor()
        for db_type, config in DB_MAP.items():
            dbname = config['mariadb_db']
            if reset:
                cursor.execute(f"DROP DATABASE IF EXISTS `{dbname}`;")
                print(f"  [!] 기존 MariaDB 데이터베이스 초기화(삭제) 완료: `{dbname}`")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;")
            print(f"  [+] 데이터베이스 확인/생성 완료: `{dbname}`")
    finally:
        conn.close()


def init_schema(db_type, db_name):
    conn = connect_mariadb(db_name=db_name)
    errors = []
    try:
        cursor = conn.cursor()
        statement_blocks = [stmt.strip() for stmt in MARIADB_SCHEMA_DDL.split(';') if stmt.strip()]
        for stmt in statement_blocks:
            try:
                cursor.execute(stmt)
            except Exception as error:
                errors.append(str(error))
        conn.commit()
    finally:
        conn.close()
    if errors:
        raise RuntimeError(
            f"{db_type} 중앙 스키마 적용 실패 ({len(errors)}건): {errors[0]}"
        )


def prepare_mariadb_schemas():
    for db_type, config in DB_MAP.items():
        init_schema(db_type, config['mariadb_db'])

    from tools.db_schema_updater import _ensure_mariadb_columns, _ensure_mariadb_indexes

    _ensure_mariadb_columns()
    _ensure_mariadb_indexes()


def ensure_table_exists_in_mariadb(ma_conn, table_name, sq_conn, sqlite_table_name=None):
    """SQLite 스키마를 기준으로 MariaDB 테이블과 누락 컬럼을 보강합니다."""
    sqlite_table_name = sqlite_table_name or table_name
    if table_name.startswith('books_search') or table_name.startswith('sqlite_') or table_name.startswith('lost_and_found'):
        return

    cols = []
    try:
        sq_cur = sq_conn.cursor()
        sq_cur.execute(f"PRAGMA table_info(`{sqlite_table_name}`)")
        cols = sq_cur.fetchall()
    except Exception as ex:
        print(f"  [!] PRAGMA table_info skipped for table `{table_name}`: {ex}")
        return

    if not cols:
        return

    def mariadb_type(column):
        col_type = (column['type'] or 'TEXT').upper()
        if 'INT' in col_type:
            return 'BIGINT'
        if 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
            return 'DOUBLE'
        if 'BLOB' in col_type:
            return 'LONGBLOB'
        if column['pk']:
            return 'VARCHAR(500)'
        return 'TEXT'

    primary_keys = sorted(
        (column for column in cols if column['pk']),
        key=lambda column: column['pk'],
    )
    col_defs = []
    for c in cols:
        name = c['name']
        m_type = mariadb_type(c)
        is_integer_primary_key = (
            len(primary_keys) == 1
            and c['pk']
            and 'INT' in (c['type'] or '').upper()
        )
        if is_integer_primary_key:
            col_defs.append(f"`{name}` {m_type} AUTO_INCREMENT PRIMARY KEY")
        else:
            col_defs.append(f"`{name}` {m_type}")

    if primary_keys and not any('PRIMARY KEY' in definition for definition in col_defs):
        key_columns = ', '.join(f"`{column['name']}`" for column in primary_keys)
        col_defs.append(f"PRIMARY KEY ({key_columns})")

    col_str = ",\n  ".join(col_defs)
    ddl = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n  {col_str}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;"
    ma_cur = ma_conn.cursor()
    try:
        ma_cur.execute(ddl)
        ma_cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        existing_columns = {row['Field'] for row in ma_cur.fetchall()}
        for column in cols:
            name = column['name']
            if name in existing_columns:
                continue
            ma_cur.execute(
                f"ALTER TABLE `{table_name}` ADD COLUMN `{name}` {mariadb_type(column)}"
            )
            print(f"  [+] 누락 컬럼 추가: `{table_name}`.`{name}`")
        ma_conn.commit()
    except Exception as e:
        print(f"  [!] Dynamic DDL Create Warning for table `{table_name}`: {e}")

NULLABLE_DATETIME_COLUMNS = {
    'last_scanned_at', 'started_at', 'finished_at', 'deleted_at',
    'last_read_at', 'last_listened_at', 'last_epub_updated_at',
    'cover_updated_at', 'created_at', 'updated_at', 'refreshed_at',
}


def resolve_target_table(db_type, sqlite_table_name):
    if db_type == 'audiobook' and sqlite_table_name == 'tracks':
        return 'audiobook_tracks'
    return sqlite_table_name


def migrate_single_db(db_type, batch_size=1000, expect_exact_count=False):
    config = DB_MAP[db_type]
    sqlite_path = config['sqlite_path']
    mariadb_db = config['mariadb_db']

    if not os.path.exists(sqlite_path):
        print(f"  [-] SQLite DB 파일 없음 ({sqlite_path}); 스킵합니다.")
        return {'db_type': db_type, 'skipped': True, 'rows': 0, 'tables': 0}

    print(f"\n==========================================")
    print(f"🚀 [{db_type.upper()}] SQLite ➔ MariaDB 데이터 펌핑 시작")
    print(f"   SQLite: {sqlite_path}")
    print(f"   MariaDB: {mariadb_db}")
    print(f"==========================================")

    sq_conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True, timeout=30.0)
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()

    ma_conn = connect_mariadb(db_name=mariadb_db)
    ma_cur = ma_conn.cursor()
    start_time = time.perf_counter()
    total_migrated_rows = 0
    migrated_tables = 0

    try:
        sq_cur.execute("BEGIN")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'books_search%' AND name NOT LIKE 'lost_and_found%'")
        tables = [r['name'] for r in sq_cur.fetchall()]

        ma_cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
        try:
            ma_cur.execute("SET sql_mode = '';")
        except Exception:
            pass

        for table in tables:
            if db_type == 'audiobook' and table == 'tracks' and 'audiobook_tracks' in tables:
                print("  [!] 구형 `tracks`와 최신 `audiobook_tracks`가 모두 있어 구형 테이블은 건너뜁니다.")
                continue

            target_table = resolve_target_table(db_type, table)
            ensure_table_exists_in_mariadb(
                ma_conn,
                target_table,
                sq_conn,
                sqlite_table_name=table,
            )
            source_count = sq_cur.execute(f"SELECT COUNT(*) AS count FROM `{table}`").fetchone()['count']
            if source_count == 0:
                continue

            sq_cur.execute(f"SELECT * FROM `{table}`")
            cols = [description[0] for description in sq_cur.description]
            col_names_str = ", ".join(f"`{column}`" for column in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = f"REPLACE INTO `{target_table}` ({col_names_str}) VALUES ({placeholders})"

            migrated_count = 0
            while True:
                rows = sq_cur.fetchmany(batch_size)
                if not rows:
                    break
                batch_data = [
                    tuple(
                        None if row[column] == '' and column in NULLABLE_DATETIME_COLUMNS else row[column]
                        for column in cols
                    )
                    for row in rows
                ]
                ma_cur.executemany(insert_sql, batch_data)
                migrated_count += len(batch_data)

            ma_conn.commit()
            ma_cur.execute(f"SELECT COUNT(*) AS count FROM `{target_table}`")
            target_count = ma_cur.fetchone()['count']
            if target_count < source_count or (expect_exact_count and target_count != source_count):
                raise RuntimeError(
                    f"`{table}` → `{target_table}` 행 수 검증 실패: "
                    f"source={source_count}, target={target_count}"
                )

            total_migrated_rows += migrated_count
            migrated_tables += 1
            print(
                f"  [+] 테이블 `{table}` → `{target_table}`: {migrated_count:,}개 행 이관 완료 "
                f"(target={target_count:,})"
            )
    except Exception:
        ma_conn.rollback()
        raise
    finally:
        try:
            ma_cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
        except Exception:
            pass
        ma_conn.close()
        sq_conn.close()

    elapsed = time.perf_counter() - start_time
    print(f"✨ [{db_type.upper()}] 이관 마감: 총 {total_migrated_rows:,}개 행 이전 완료 (소요시간: {elapsed:.2f}초)")
    return {
        'db_type': db_type,
        'skipped': False,
        'rows': total_migrated_rows,
        'tables': migrated_tables,
    }


def main():
    parser = argparse.ArgumentParser(description="BookOasis SQLite to MariaDB Migrator Tool")
    parser.add_argument('--reset', '--fresh', action='store_true', help="기존 MariaDB 데이터베이스를 완전히 삭제(초기화) 후 처음부터 깨끗이 이관합니다.")
    parser.add_argument('--yes', action='store_true', help="--reset 삭제 확인을 비대화형으로 승인합니다.")
    parser.add_argument('--batch-size', type=int, default=1000, help="한 번에 전송할 행 수 (기본값: 1000)")
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error('--batch-size는 1 이상이어야 합니다.')

    print("==================================================")
    print("  BookOasis SQLite ➔ MariaDB 1-Click 자동 마이그레이터")
    if args.reset:
        print("  ⚠️ [--reset 모드] 기존 MariaDB DB를 완전히 삭제 후 처음부터 이관합니다.")
    print("==================================================")

    print("[*] SQLite 원본 사전검사")
    try:
        preflight_sqlite_sources(require_all=args.reset)
    except Exception as err:
        print(f"\n[오류] {err}")
        sys.exit(1)

    if args.reset and not confirm_reset(args.yes):
        print("[취소] --reset 작업이 승인되지 않아 종료합니다.")
        sys.exit(1)

    try:
        ensure_mariadb_databases(reset=args.reset)
        prepare_mariadb_schemas()
    except Exception as err:
        print(f"\n[오류] MariaDB 서버 접속 실패: {err}")
        print("  .env 파일의 MARIADB_HOST, MARIADB_PORT, MARIADB_USER, MARIADB_PASSWORD 설정을 확인하세요.")
        sys.exit(1)

    try:
        reports = [
            migrate_single_db(
                db_type,
                batch_size=args.batch_size,
                expect_exact_count=args.reset,
            )
            for db_type in DB_MAP
        ]
    except Exception as err:
        print(f"\n[오류] 데이터 이관 실패: {err}")
        sys.exit(1)

    migrated_rows = sum(report['rows'] for report in reports)
    migrated_tables = sum(report['tables'] for report in reports)

    print("\n==================================================")
    print("🎉 모든 데이터베이스 이관이 완료되었습니다!")
    print(f"   검증 완료: {migrated_tables}개 테이블, {migrated_rows:,}개 행")
    print("   .env 파일에서 DB_ENGINE=mariadb 로 설정 후 미디어 서버를 시작하세요.")
    print("==================================================")


if __name__ == '__main__':
    main()

