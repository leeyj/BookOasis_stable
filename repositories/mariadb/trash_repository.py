# -*- coding: utf-8 -*-
"""
trash_repository.py – MariaDB 전용 휴지통(is_deleted=1) 도서 복구 및 물리적 일괄 삭제 데이터 액세스 레이어
"""
import database

class TrashRepository:
    @staticmethod
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

    @staticmethod
    def restore_books(db_type, book_ids):
        if not book_ids:
            return True
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            for i in range(0, len(book_ids), 900):
                chunk = book_ids[i:i+900]
                placeholders = ','.join(['%s'] * len(chunk))
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

    @staticmethod
    def get_deleted_book_ids_by_library(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE library_id = %s AND COALESCE(is_deleted, 0) = 1", (library_id,))
        rows = cursor.fetchall()
        conn.close()
        return [r['id'] for r in rows]

    @staticmethod
    def get_all_deleted_book_ids(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE COALESCE(is_deleted, 0) = 1")
        rows = cursor.fetchall()
        conn.close()
        return [r['id'] for r in rows]

    @staticmethod
    def fetch_book_covers(db_type, book_ids):
        if not book_ids:
            return []
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(book_ids))
        cursor.execute(f"SELECT cover_image FROM books WHERE id IN ({placeholders})", book_ids)
        rows = cursor.fetchall()
        conn.close()
        return [r['cover_image'] for r in rows if r['cover_image']]

    @staticmethod
    def check_cover_reference_count(db_type, cover_image):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) AS cnt FROM books WHERE cover_image = %s", (cover_image,))
        row = cursor.fetchone()
        conn.close()
        return row['cnt'] if row else 0

    @staticmethod
    def hard_delete_books_transaction(db_type, book_ids, target_covers):
        if not book_ids:
            return []
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            placeholders = ','.join(['%s'] * len(book_ids))

            # 실제로 휴지통(is_deleted=1) 상태인 id만 1회 조회로 확정 -> 이후 서브쿼리 없이 바로 삭제
            cursor.execute(f"SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1", book_ids)
            confirmed_ids = [row['id'] for row in cursor.fetchall()]
            if not confirmed_ids:
                conn.commit()
                return []
            confirmed_placeholders = ','.join(['%s'] * len(confirmed_ids))

            cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
            cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
            cursor.execute(f"DELETE FROM user_favorites WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
            cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN ({confirmed_placeholders})", confirmed_ids)
            cursor.execute(f"DELETE FROM books WHERE id IN ({confirmed_placeholders})", confirmed_ids)

            # 커버 참조 카운트를 건별 SELECT 반복 대신 단일 GROUP BY 조회로 일괄 확인 (트랜잭션 점유 시간 단축)
            unreferenced_covers = []
            if target_covers:
                cover_placeholders = ','.join(['%s'] * len(target_covers))
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
