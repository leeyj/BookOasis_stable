# -*- coding: utf-8 -*-
"""
repair_scan_status.py

Emergency CLI to recover stale library scan_status values.

What it does:
- Reads active scanner tasks from general DB (status in running/pending)
- Extracts (db_type, library_id) pairs from task kwargs
- Scans libraries in selected DB(s)
- Finds stale states where scan_status is scanning/cancelling but no active task exists
- Dry-run by default; use --apply to update stale rows to ready

Usage examples:
  python tools/repair_scan_status.py
  python tools/repair_scan_status.py --apply
  python tools/repair_scan_status.py --db audiobook --apply
  python tools/repair_scan_status.py --db general --library-id 12 --apply
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import database
except Exception as exc:
    print(f"[ERROR] failed to import database module: {exc}")
    sys.exit(2)


TARGET_STATUSES = {"scanning", "cancelling"}


def _parse_task_target(task_row):
    kwargs_raw = task_row.get("kwargs")
    if not kwargs_raw:
        return None

    try:
        kwargs = json.loads(kwargs_raw)
    except Exception:
        return None

    db_type = str(kwargs.get("db_type") or "").strip().lower()
    library_id = kwargs.get("library_id")
    if db_type not in {"general", "adult", "audiobook"}:
        return None
    try:
        library_id = int(library_id)
    except Exception:
        return None
    return (db_type, library_id)


def load_active_scan_targets():
    conn = database.get_connection("general")
    conn.row_factory = database.sqlite3.Row if hasattr(database, "sqlite3") else conn.row_factory
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT task_type, status, kwargs
            FROM scanner_tasks
            WHERE status IN ('running', 'pending')
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    active = set()
    for row in rows:
        row_d = dict(row)
        if row_d.get("task_type") not in ("library_scan", "cover_scan"):
            continue
        target = _parse_task_target(row_d)
        if target:
            active.add(target)
    return active


def iter_target_dbs(db_selector):
    if db_selector == "all":
        return ["general", "adult", "audiobook"]
    return [db_selector]


def find_stale_libraries(db_types, active_targets, library_id=None, include_interrupted=False):
    stale = []
    target_statuses = set(TARGET_STATUSES)
    if include_interrupted:
        target_statuses.add("interrupted")

    for db_type in db_types:
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            if library_id is None:
                cursor.execute("SELECT id, name, scan_status FROM libraries ORDER BY id ASC")
            else:
                cursor.execute(
                    "SELECT id, name, scan_status FROM libraries WHERE id = ? ORDER BY id ASC",
                    (int(library_id),),
                )
            rows = cursor.fetchall()
        finally:
            conn.close()

        for row in rows:
            rec = dict(row)
            status = str(rec.get("scan_status") or "").strip().lower()
            lib_id = int(rec.get("id"))
            key = (db_type, lib_id)
            if status in target_statuses and key not in active_targets:
                stale.append(
                    {
                        "db_type": db_type,
                        "library_id": lib_id,
                        "name": rec.get("name") or "",
                        "from_status": status,
                    }
                )
    return stale


def apply_repair(stale_rows):
    updated = 0
    for row in stale_rows:
        db_type = row["db_type"]
        lib_id = row["library_id"]
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE libraries SET scan_status = 'ready' WHERE id = ?",
                (lib_id,),
            )
            conn.commit()
            updated += cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return updated


def print_report(active_targets, stale_rows, apply_mode, include_interrupted):
    print("=" * 80)
    print("Scan Status Emergency Recovery")
    print("=" * 80)
    print(f"Mode               : {'APPLY' if apply_mode else 'DRY-RUN'}")
    print(f"Include interrupted: {'yes' if include_interrupted else 'no'}")
    print(f"Active scan targets: {len(active_targets)}")
    if active_targets:
        for db_type, library_id in sorted(active_targets):
            print(f"  - active task: {db_type}/{library_id}")

    print("-" * 80)
    print(f"Stale libraries found: {len(stale_rows)}")
    for row in stale_rows:
        print(
            f"  - {row['db_type']}/{row['library_id']} "
            f"name='{row['name']}' status='{row['from_status']}' -> ready"
        )
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Recover stale libraries.scan_status when no active scan task exists"
    )
    parser.add_argument(
        "--db",
        choices=["all", "general", "adult", "audiobook"],
        default="all",
        help="target DB scope",
    )
    parser.add_argument(
        "--library-id",
        type=int,
        default=None,
        help="optional single library id filter",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply changes (default: dry-run)",
    )
    parser.add_argument(
        "--include-interrupted",
        action="store_true",
        help="also recover interrupted -> ready when no active task",
    )
    args = parser.parse_args()

    active_targets = load_active_scan_targets()
    db_types = iter_target_dbs(args.db)
    stale_rows = find_stale_libraries(
        db_types=db_types,
        active_targets=active_targets,
        library_id=args.library_id,
        include_interrupted=args.include_interrupted,
    )

    print_report(
        active_targets=active_targets,
        stale_rows=stale_rows,
        apply_mode=args.apply,
        include_interrupted=args.include_interrupted,
    )

    if not args.apply:
        print("[DRY-RUN] no changes were applied. Re-run with --apply to update scan_status.")
        return 0

    if not stale_rows:
        print("[APPLY] nothing to update.")
        return 0

    updated = apply_repair(stale_rows)
    print(f"[APPLY] updated rows: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
