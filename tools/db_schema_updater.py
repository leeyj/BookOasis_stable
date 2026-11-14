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
    print(f"[ERROR] Cannot import the database.py module: {e}")
    sys.exit(1)

# MariaDB 중앙 스키마는 services/schema_mariadb.py로 옮겼다. 테스트·migrator 호환을 위해 여기서도 재노출한다.
from services.schema_mariadb import MARIADB_CENTRAL_SCHEMA  # noqa: E402,F401


def run_schema_update():
    print("=" * 60)
    print(" Database schema force-update and sync tool")
    print("=" * 60)

    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    if engine in ('mariadb', 'mysql'):
        print("[+] Running in MariaDB database engine mode")
        try:
            from tools.migrator_sqlite_to_mariadb import ensure_mariadb_databases, init_schema, DB_MAP
            ensure_mariadb_databases(reset=False)
            for db_type, config in DB_MAP.items():
                dbname = config['mariadb_db']
                init_schema(db_type, dbname)
            run_full_migration()
            print("[+] Checked MariaDB databases, schema and composite indexes.")
        except Exception as ex:
            print(f"[!] Warning while checking the MariaDB schema: {ex}")
        return

    # 1. DB 파일 존재 및 경로 확인
    db_paths = {
        'General DB (media_general)': DB_GENERAL_PATH,
        'Adult DB (media_adult)': DB_ADULT_PATH,
        'Audiobook DB (media_audiobook)': DB_AUDIOBOOK_PATH,
        'Video course DB (media_video)': DB_VIDEO_PATH
    }

    for db_name, db_path in db_paths.items():
        print(f"[*] {db_name} path: {db_path}")
        if not os.path.exists(db_path):
            print(f"    -> [INFO] The DB file does not exist yet. It will be created.")
        else:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"    -> [OK] DB file exists (size: {size_mb:.2f} MB)")

    print("\n[*] Step 1: initializing the database and running schema/index/backfill migrations...")
    try:
        run_full_migration()
        print(" -> [OK] Database migration complete.")
    except Exception as e:
        print(f" -> [FAILED] Error during database migration: {e}")

    print("\n[*] Step 2: finishing the WAL checkpoint...")
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
                print(f"  - [WARN] {db_key.upper()} DB integrity problem detected: {integrity}")

            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            print(f"  - {db_key.upper()} DB WAL checkpoint (TRUNCATE) done.")

        except Exception as db_err:
            print(f"  - [ERROR] Problem during {db_key.upper()} DB WAL checkpoint: {db_err}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    print("\n" + "=" * 60)
    print(" Database schema and migration sync completed successfully!")
    print(" Please restart the service.")
    print("=" * 60)

if __name__ == '__main__':
    run_schema_update()
