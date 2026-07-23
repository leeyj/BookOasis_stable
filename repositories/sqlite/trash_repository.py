# -*- coding: utf-8 -*-
"""
trash_repository.py – 휴지통(is_deleted=1) 도서 복구 및 물리적 일괄 삭제 데이터 액세스 레이어
"""
import database

class TrashRepository:
    @staticmethod
    def get_deleted_books(db_type):
        """휴지통(is_deleted=1) 내 도서 목록 및 도서관 정보 조회"""
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
        """선택 도서 복구 (is_deleted=0)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            for i in range(0, len(book_ids), 900):
                chunk = book_ids[i:i+900]
                placeholders = ','.join(['?'] * len(chunk))
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
        """특정 라이브러리 내 삭제된 도서 ID 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE library_id = ? AND COALESCE(is_deleted, 0) = 1", (library_id,))
        rows = cursor.fetchall()
        conn.close()
        return [r['id'] for r in rows]

    @staticmethod
    def get_all_deleted_book_ids(db_type):
        """휴지통 내 모든 도서 ID 목록 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM books WHERE COALESCE(is_deleted, 0) = 1")
        rows = cursor.fetchall()
        conn.close()
        return [r['id'] for r in rows]

    @staticmethod
    def fetch_book_covers(db_type, book_ids):
        """여러 도서의 커버 이미지 정보 일괄 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(book_ids))
        cursor.execute(f"SELECT cover_image FROM books WHERE id IN ({placeholders})", book_ids)
        rows = cursor.fetchall()
        conn.close()
        return [r['cover_image'] for r in rows if r['cover_image']]

    @staticmethod
    def check_cover_reference_count(db_type, cover_image):
        """특정 커버 이미지를 쓰고 있는 도서 레코드 수 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) AS cnt FROM books WHERE cover_image = ?", (cover_image,))
        row = cursor.fetchone()
        conn.close()
        return row['cnt'] if row else 0

    @staticmethod
    def hard_delete_books_transaction(db_type, book_ids, target_covers):
        """도서 정보 및 종속된 진척도, 활동로그, 오프셋 정보 일괄 물리 삭제 트랜잭션 (is_deleted=1 엄격 지정)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            placeholders = ','.join(['?'] * len(book_ids))
            
            # 1. 휴지통(is_deleted=1) 상태인 도서의 종속 데이터 및 책 레코드 물리 삭제
            cursor.execute(f"DELETE FROM user_progress WHERE book_id IN (SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1)", book_ids)
            cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN (SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1)", book_ids)
            cursor.execute(f"DELETE FROM user_favorites WHERE book_id IN (SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1)", book_ids)
            cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN (SELECT id FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1)", book_ids)
            cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders}) AND COALESCE(is_deleted, 0) = 1", book_ids)
            
            # 2. 커버 이미지 참조 여부를 필터링하여 살아있는 도서(is_deleted=0)가 쓰지 않는 파일 목록만 추려 반환
            unreferenced_covers = []
            for cover_img in target_covers:
                cursor.execute("SELECT COUNT(1) AS cnt FROM books WHERE cover_image = ?", (cover_img,))
                row_cnt = cursor.fetchone()
                if not row_cnt or (row_cnt['cnt'] or 0) == 0:
                    unreferenced_covers.append(cover_img)
            
            conn.commit()
            return unreferenced_covers
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
