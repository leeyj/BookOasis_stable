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

from services.schema_mariadb import MARIADB_CENTRAL_SCHEMA as MARIADB_SCHEMA_DDL


def connect_mariadb(db_name=None):
    if pymysql is None:
        raise RuntimeError("The PyMySQL package is required: pip install PyMySQL")
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
            print(f"  [-] {result['db_type']}: source file not found ({result['path']})")
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
        raise RuntimeError(f"SQLite source pre-check failed: {', '.join(invalid)}")
    return results


def confirm_reset(assume_yes=False):
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(
            "This drops all MariaDB general/adult/audiobook DBs. "
            "Type RESET to continue:\n> "
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
                print(f"  [!] Reset (dropped) the existing MariaDB database: `{dbname}`")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;")
            print(f"  [+] Database checked/created: `{dbname}`")
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
            f"{db_type} failed to apply the central schema ({len(errors)} errors): {errors[0]}"
        )


def prepare_mariadb_schemas():
    for db_type, config in DB_MAP.items():
        init_schema(db_type, config['mariadb_db'])

    from services.db_migration_service import _ensure_mariadb_columns, _ensure_mariadb_indexes

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
            print(f"  [+] Added missing column: `{table_name}`.`{name}`")
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
        print(f"  [-] SQLite DB file not found ({sqlite_path}); skipping.")
        return {'db_type': db_type, 'skipped': True, 'rows': 0, 'tables': 0}

    print(f"\n==========================================")
    print(f"🚀 [{db_type.upper()}] Starting SQLite -> MariaDB data transfer")
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
                print("  [!] Both the old `tracks` and the current `audiobook_tracks` exist; skipping the old table.")
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
                    f"`{table}` -> `{target_table}` row count check failed: "
                    f"source={source_count}, target={target_count}"
                )

            total_migrated_rows += migrated_count
            migrated_tables += 1
            print(
                f"  [+] Table `{table}` -> `{target_table}`: migrated {migrated_count:,} rows "
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
    print(f"✨ [{db_type.upper()}] Migration finished: {total_migrated_rows:,} rows moved (took {elapsed:.2f}s)")
    return {
        'db_type': db_type,
        'skipped': False,
        'rows': total_migrated_rows,
        'tables': migrated_tables,
    }


def main():
    parser = argparse.ArgumentParser(description="BookOasis SQLite to MariaDB Migrator Tool")
    parser.add_argument('--reset', '--fresh', action='store_true', help="Drops the existing MariaDB databases completely (reset) and migrates cleanly from scratch.")
    parser.add_argument('--yes', action='store_true', help="Approves the --reset drop confirmation non-interactively.")
    parser.add_argument('--batch-size', type=int, default=1000, help="Rows to send per batch (default: 1000)")
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error('--batch-size must be at least 1.')

    print("==================================================")
    print("  BookOasis SQLite -> MariaDB one-click migrator")
    if args.reset:
        print("  ⚠️ [--reset mode] Drops the existing MariaDB databases completely and migrates from scratch.")
    print("==================================================")

    print("[*] Pre-checking the SQLite sources")
    try:
        preflight_sqlite_sources(require_all=args.reset)
    except Exception as err:
        print(f"\n[ERROR] {err}")
        sys.exit(1)

    if args.reset and not confirm_reset(args.yes):
        print("[CANCELLED] Exiting because the --reset operation was not approved.")
        sys.exit(1)

    try:
        ensure_mariadb_databases(reset=args.reset)
        prepare_mariadb_schemas()
    except Exception as err:
        print(f"\n[ERROR] Failed to connect to the MariaDB server: {err}")
        print("  Check MARIADB_HOST, MARIADB_PORT, MARIADB_USER and MARIADB_PASSWORD in .env.")
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
        print(f"\n[ERROR] Data migration failed: {err}")
        sys.exit(1)

    migrated_rows = sum(report['rows'] for report in reports)
    migrated_tables = sum(report['tables'] for report in reports)

    print("\n==================================================")
    print("🎉 All databases migrated!")
    print(f"   Verified: {migrated_tables} tables, {migrated_rows:,} rows")
    print("   Set DB_ENGINE=mariadb in .env, then start the media server.")
    print("==================================================")


if __name__ == '__main__':
    main()

