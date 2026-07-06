# -*- coding: utf-8 -*-
"""One-shot normalization tool for legacy EPUB progress data.

Usage:
  python tools/normalize_epub_progress.py           # dry-run
  python tools/normalize_epub_progress.py --apply   # apply updates

What it normalizes:
- books.total_pages for EPUB -> 100
- user_progress.pages_read for EPUB -> 0..100 percent semantics
- user_progress.last_epub_percent fallback fill when missing/invalid
"""

import argparse
import database


def clamp_percent(value):
    try:
        n = int(value)
    except Exception:
        return 0
    return max(0, min(100, n))


def normalize_db(db_type: str, apply_changes: bool):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()

    # 1) Normalize books.total_pages for EPUB
    cursor.execute("SELECT id, total_pages FROM books WHERE lower(file_format) = 'epub'")
    book_rows = cursor.fetchall()
    book_updates = []
    for row in book_rows:
        if row['total_pages'] != 100:
            book_updates.append((row['id'], row['total_pages'], 100))

    # 2) Normalize user_progress rows joined with EPUB books
    cursor.execute(
        """
        SELECT p.id, p.book_id, p.user_id, p.pages_read, p.last_epub_percent, b.total_pages
        FROM user_progress p
        JOIN books b ON b.id = p.book_id
        WHERE lower(b.file_format) = 'epub'
        """
    )
    progress_rows = cursor.fetchall()

    progress_updates = []
    for row in progress_rows:
        pages_read = row['pages_read'] if row['pages_read'] is not None else 0
        last_percent = row['last_epub_percent']

        if last_percent is not None and 0 <= int(last_percent) <= 100:
            normalized = clamp_percent(last_percent)
        else:
            total_pages = row['total_pages'] if row['total_pages'] and row['total_pages'] > 0 else 100
            if total_pages == 100:
                normalized = clamp_percent(pages_read)
            else:
                # legacy page semantics -> convert to percent
                normalized = clamp_percent(round((float(pages_read) / float(total_pages)) * 100))

        # Small non-zero reads should not collapse to zero
        if pages_read > 0 and normalized == 0:
            normalized = 1

        current_percent = clamp_percent(last_percent) if last_percent is not None else None
        if pages_read != normalized or current_percent != normalized:
            progress_updates.append((row['id'], row['book_id'], row['user_id'], pages_read, last_percent, normalized))

    print(f"[normalize] db={db_type}")
    print(f"  books to update(total_pages -> 100): {len(book_updates)}")
    print(f"  user_progress to update(percent semantics): {len(progress_updates)}")

    if not apply_changes:
        conn.close()
        return

    for book_id, old_total, new_total in book_updates:
        cursor.execute("UPDATE books SET total_pages = ? WHERE id = ?", (new_total, book_id))

    for progress_id, _book_id, _user_id, _old_read, _old_percent, normalized in progress_updates:
        cursor.execute(
            """
            UPDATE user_progress
            SET pages_read = ?,
                last_epub_percent = ?
            WHERE id = ?
            """,
            (normalized, normalized, progress_id)
        )

    conn.commit()
    conn.close()
    print(f"  applied updates: books={len(book_updates)}, progress={len(progress_updates)}")


def main():
    parser = argparse.ArgumentParser(description='Normalize legacy EPUB progress to percent semantics')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()

    for db_type in ('general', 'adult'):
        normalize_db(db_type, args.apply)


if __name__ == '__main__':
    main()
