# -*- coding: utf-8 -*-
"""
Temporary utility for diagnosing and rebuilding books_search (FTS5).

Usage examples:
  python tools/repair_books_search_temp.py --db-type general --apply
  python tools/repair_books_search_temp.py --db db/media_general.db --apply --no-backup
"""

import argparse
import datetime
import os
import shutil
import sqlite3
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DB_DIR = os.path.join(BASE_DIR, "db")

DB_FILES = {
    "general": os.path.join(DB_DIR, "media_general.db"),
    "adult": os.path.join(DB_DIR, "media_adult.db"),
}


def log(msg):
    print(msg)


def now_stamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def check_integrity(conn):
    rows = conn.execute("PRAGMA integrity_check;").fetchall()
    return len(rows) == 1 and rows[0][0] == "ok", rows


def check_books_search_health(conn):
    try:
        conn.execute("SELECT rowid FROM books_search LIMIT 1;").fetchone()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def rebuild_books_search(conn):
    cur = conn.cursor()

    def _drop_best_effort(sql):
        try:
            cur.execute(sql)
        except Exception:
            pass

    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_ai;")
    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_ad;")
    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_au;")

    # FTS5 shadow tables are ordinary tables; try clearing them first.
    for tbl in (
        "books_search_data",
        "books_search_idx",
        "books_search_content",
        "books_search_docsize",
        "books_search_config",
    ):
        _drop_best_effort(f"DROP TABLE IF EXISTS {tbl};")

    # Normal path.
    try:
        cur.execute("DROP TABLE IF EXISTS books_search;")
    except Exception as drop_err:
        # Fallback: force-remove broken FTS entries from sqlite_master.
        log(f"[WARN] normal DROP books_search failed: {drop_err}")
        log("[WARN] fallback path: force cleanup sqlite_master for books_search")
        cur.execute("PRAGMA writable_schema=ON;")
        cur.execute(
            """
            DELETE FROM sqlite_master
            WHERE name IN (
                'books_search',
                'books_search_data',
                'books_search_idx',
                'books_search_content',
                'books_search_docsize',
                'books_search_config',
                'books_search_ai',
                'books_search_ad',
                'books_search_au'
            );
            """
        )
        cur.execute("PRAGMA writable_schema=OFF;")
        # Force schema reload in the same connection.
        row = cur.execute("PRAGMA schema_version;").fetchone()
        current_ver = int(row[0]) if row else 0
        cur.execute(f"PRAGMA schema_version = {current_ver + 1};")
        conn.commit()

    cur.execute(
        """
        CREATE VIRTUAL TABLE books_search USING fts5(
            title,
            series_name,
            author,
            summary,
            content='books',
            content_rowid='id',
            tokenize='unicode61'
        );
        """
    )
    # 실시간 트리거는 비활성화 정책: 주기적 스케줄러 재빌드로만 유지
    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_ai;")
    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_ad;")
    _drop_best_effort("DROP TRIGGER IF EXISTS books_search_au;")

    cur.execute("INSERT INTO books_search(books_search) VALUES('rebuild');")
    conn.commit()


def backup_db(db_path):
    backup_dir = os.path.join(DB_DIR, "_backup")
    os.makedirs(backup_dir, exist_ok=True)
    dst = os.path.join(backup_dir, f"{os.path.basename(db_path)}.ftsfix.{now_stamp()}.bak")
    shutil.copy2(db_path, dst)
    return dst


def resolve_db_path(args):
    if args.db:
        return os.path.abspath(args.db)
    return DB_FILES[args.db_type]


def main():
    parser = argparse.ArgumentParser(description="Temporary books_search repair tool")
    parser.add_argument("--db-type", choices=["general", "adult"], default="general")
    parser.add_argument("--db", help="Direct DB file path (overrides --db-type)")
    parser.add_argument("--apply", action="store_true", help="Actually rebuild books_search")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup before rebuild")
    args = parser.parse_args()

    db_path = resolve_db_path(args)
    log(f"[INFO] target db: {db_path}")

    if not os.path.exists(db_path):
        log("[ERROR] DB file does not exist.")
        return 2

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)

        integrity_ok, integrity_rows = check_integrity(conn)
        if integrity_ok:
            log("[OK] PRAGMA integrity_check: ok")
        else:
            log(f"[WARN] PRAGMA integrity_check issue: {integrity_rows[:3]}")

        search_ok, search_msg = check_books_search_health(conn)
        if search_ok:
            log("[OK] books_search health: ok")
            if not args.apply:
                log("[DONE] No action applied. Use --apply to force rebuild.")
                return 0
        else:
            log(f"[WARN] books_search health failed: {search_msg}")
            if not args.apply:
                log("[DONE] Check only mode. Re-run with --apply to rebuild.")
                return 1

        if not args.no_backup:
            backup_path = backup_db(db_path)
            log(f"[OK] backup created: {backup_path}")

        log("[INFO] rebuilding books_search...")
        rebuild_books_search(conn)

        search_ok_after, search_msg_after = check_books_search_health(conn)
        if search_ok_after:
            log("[OK] books_search rebuild completed and verified.")
            return 0

        log(f"[ERROR] books_search still unhealthy after rebuild: {search_msg_after}")
        return 1

    except Exception as exc:
        log(f"[ERROR] exception: {exc}")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
