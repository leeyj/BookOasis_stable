# -*- coding: utf-8 -*-
"""
trash_repository_shared.py – mariadb/sqlite(향후 mssql 포함) 공용 휴지통(is_deleted=1) 도서
복구 및 물리적 일괄 삭제 SQL 로직. 방언 차이는 플레이스홀더 문자(`%s` 또는 `?`) 하나로만 흡수하며,
그 외 SQL 문법(LIMIT/TOP, AUTO_INCREMENT 등 방언 전용 구문)은 이 파일에서 사용하지 않는다.
"""
import database


def get_deleted_books(db_type):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, b.title, b.file_path, b.deleted_at, b.library_id, l.name AS library_name
        FROM books b
        LEFT JOIN libraries l ON b.library_id = l.id
        WHERE COALESCE(b.is_deleted, 0) = 1
        ORDER BY b.deleted_at DESC, b.title ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def restore_books(db_type, book_ids, placeholder):
    if not book_ids:
        return True
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    try:
        for i in range(0, len(book_ids), 900):
            chunk = book_ids[i:i + 900]
            placeholders = ','.join([placeholder] * len(chunk))
            cursor.execute(f"""
                UPDATE books
                SET is_deleted = 0, deleted_at = NULL
                WHERE id IN ({placeholders}) AND is_deleted = 1
            """, chunk)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_deleted_book_ids_by_library(db_type, library_id, placeholder):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(f"SELECT id FROM books WHERE library_id = {placeholder} AND COALESCE(is_deleted, 0) = 1", (library_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r['id'] for r in rows]


def get_all_deleted_book_ids(db_type):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM books WHERE COALESCE(is_deleted, 0) = 1")
    rows = cursor.fetchall()
    conn.close()
    return [r['id'] for r in rows]


def fetch_book_covers(db_type, book_ids, placeholder):
    if not book_ids:
        return []
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    placeholders = ','.join([placeholder] * len(book_ids))
    cursor.execute(f"SELECT cover_image FROM books WHERE id IN ({placeholders})", book_ids)
    rows = cursor.fetchall()
    conn.close()
    return [r['cover_image'] for r in rows if r['cover_image']]


def check_cover_reference_count(db_type, cover_image, placeholder):
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(1) AS cnt FROM books WHERE cover_image = {placeholder}", (cover_image,))
    row = cursor.fetchone()
    conn.close()
    return row['cnt'] if row else 0


def hard_delete_books_transaction(db_type, book_ids, target_covers, placeholder):
    if not book_ids:
        return []
    conn = database.get_connection(db_type)
    cursor = conn.cursor()
    try:
        placeholders = ','.join([placeholder] * len(book_ids))

        # 실제로 휴지통(is_deleted=1) 상태인 id만 1회 조회로 확정 -> 이후 서브쿼리 없이 바로 삭제
        cursor.execute(f"SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1", book_ids)
        confirmed_ids = [row['id'] for row in cursor.fetchall()]
        if not confirmed_ids:
            conn.commit()
            return []
        confirmed_placeholders = ','.join([placeholder] * len(confirmed_ids))

        cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
        cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
        cursor.execute(f"DELETE FROM user_favorites WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
        cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
        cursor.execute(f"DELETE FROM books WHERE id IN ({confirmed_placeholders})", confirmed_ids)

        # 커버 참조 카운트를 건별 SELECT 반복 대신 단일 GROUP BY 조회로 일괄 확인 (트랜잭션 점유 시간 단축)
        unreferenced_covers = []
        if target_covers:
            cover_placeholders = ','.join([placeholder] * len(target_covers))
            cursor.execute(
                f"SELECT cover_image, COUNT(1) AS cnt FROM books WHERE cover_image IN ({cover_placeholders}) GROUP BY cover_image",
                target_covers
            )
            referenced_counts = {row['cover_image']: row['cnt'] for row in cursor.fetchall()}
            unreferenced_covers = [c for c in target_covers if not referenced_counts.get(c)]

        conn.commit()
        return unreferenced_covers
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
