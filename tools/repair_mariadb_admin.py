# -*- coding: utf-8 -*-
"""Repair the missing initial admin account on affected MariaDB installs.

This tool only repairs the known first-install failure where all three users
tables are empty. It never resets or overwrites an existing account.

Usage:
  python tools/repair_mariadb_admin.py
  python tools/repair_mariadb_admin.py --apply
"""

import argparse
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database


DB_TYPES = ("general", "adult", "audiobook")


def inspect_users(db_types=DB_TYPES):
    states = []
    for db_type in db_types:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*) AS user_count,
                       SUM(CASE WHEN username = %s THEN 1 ELSE 0 END) AS admin_count
                FROM users
                """,
                ("admin",),
            )
            row = cursor.fetchone()
            states.append(
                {
                    "db_type": db_type,
                    "user_count": int(row["user_count"] or 0),
                    "admin_count": int(row["admin_count"] or 0),
                }
            )
        finally:
            conn.close()
    return states


def is_known_seed_failure(states):
    return tuple(state["db_type"] for state in states) == DB_TYPES and all(
        state["user_count"] == 0
        and state["admin_count"] == 0
        for state in states
    )


def create_initial_admin(db_types=DB_TYPES):
    connections = []
    password_hash = generate_password_hash("admin")
    try:
        for db_type in db_types:
            conn = database.get_connection(db_type)
            connections.append((db_type, conn))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS user_count FROM users")
            row = cursor.fetchone()
            if int(row["user_count"] or 0) != 0:
                raise RuntimeError(f"{db_type}: users table changed during repair")

            cursor.execute(
                """
                INSERT INTO users (
                    username, password_hash, role, is_default_password,
                    has_adult_access, has_audiobook_access
                ) VALUES (%s, %s, 'admin', 1, 1, 1)
                """,
                ("admin", password_hash),
            )

        for _, conn in connections:
            conn.commit()
        return list(db_types)
    except Exception:
        for _, conn in connections:
            conn.rollback()
        raise
    finally:
        for _, conn in connections:
            conn.close()


def print_report(states, apply_mode):
    print("=" * 72)
    print("MariaDB Initial Admin Recovery")
    print("=" * 72)
    print(f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
    for state in states:
        print(
            f"- {state['db_type']}: users={state['user_count']}, "
            f"username_admin={state['admin_count']}"
        )
    print("=" * 72)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Restore admin/admin when MariaDB first-install user seeding failed"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create the initial account (default: dry-run)",
    )
    args = parser.parse_args(argv)

    if not database.is_mariadb_mode():
        print("[ERROR] This recovery tool is only available when DB_ENGINE=mariadb/mysql.")
        return 2

    try:
        states = inspect_users()
    except Exception as exc:
        print(f"[ERROR] Failed to inspect MariaDB users tables: {exc}")
        return 2

    print_report(states, args.apply)
    if not is_known_seed_failure(states):
        print("[STOP] The database does not match the known empty-users failure state.")
        print("[STOP] Existing accounts were not changed or reset.")
        return 1

    if not args.apply:
        print("[DRY-RUN] Recovery is applicable. Re-run with --apply to create admin/admin.")
        return 0

    try:
        created = create_initial_admin()
    except Exception as exc:
        print(f"[ERROR] Recovery failed and open transactions were rolled back: {exc}")
        return 2

    print(f"[APPLY] Initial admin created in: {', '.join(created)}")
    print("[APPLY] Sign in with admin/admin and change the password immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())