# -*- coding: utf-8 -*-
import database

class TrashService:
    @staticmethod
    def get_deleted_books(db_type):
        """물리적으로 사라져서 휴지통(is_deleted=1)에 들어있는 도서 목록을 카테고리 정보와 함께 조회"""
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
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
        
        return [
            {
                'id': r['id'],
                'title': r['title'],
                'file_path': r['file_path'],
                'deleted_at': r['deleted_at'],
                'library_id': r['library_id'],
                'library_name': r['library_name'] or '미지정 카테고리'
            }
            for r in rows
        ]

    @staticmethod
    def restore_books(db_type, book_ids):
        """휴지통에 들어있는 특정 도서 목록을 다시 일반 상태(is_deleted=0)로 복구"""
        if not book_ids:
            return True
            
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
            print(f"[TrashService ERROR] Failed to restore books: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def empty_trash(db_type, library_id=None, book_ids=None):
        """휴지통 비우기 (일괄 또는 선택적 영구 삭제)"""
        import os
        conn = database.get_connection(db_type)
        conn.row_factory = database.sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 1. 대상 도서 ID 목록 확보
            if book_ids:
                target_ids = book_ids
            elif library_id:
                cursor.execute("SELECT id FROM books WHERE library_id = ? AND COALESCE(is_deleted, 0) = 1", (library_id,))
                target_ids = [r['id'] for r in cursor.fetchall()]
            else:
                cursor.execute("SELECT id FROM books WHERE COALESCE(is_deleted, 0) = 1")
                target_ids = [r['id'] for r in cursor.fetchall()]
                
            if not target_ids:
                return True
                
            # 1.5. 물리적 커버 이미지 파일 소거 준비
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            covers_dir = os.path.join(base_dir, 'covers')
            
            # 2. 관련 진척도 및 로그 데이터 하드 딜리트
            for i in range(0, len(target_ids), 900):
                chunk = target_ids[i:i+900]
                placeholders = ','.join(['?'] * len(chunk))
                
                # 2.1. 삭제 대상 도서들의 커버 이미지 정보 사전 로드
                cursor.execute(f"SELECT cover_image FROM books WHERE id IN ({placeholders})", chunk)
                cover_rows = cursor.fetchall()
                target_covers = sorted({r['cover_image'] for r in cover_rows if r['cover_image']})
                
                cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({placeholders})", chunk)
                cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({placeholders})", chunk)
                cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN ({placeholders})", chunk)
                cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders})", chunk)
                
                # 2.2. 로컬 정적 커버 파일 삭제는 "남은 참조수=0"인 경우에만 수행
                for cover_img in target_covers:
                    cursor.execute("SELECT COUNT(1) AS cnt FROM books WHERE cover_image = ?", (cover_img,))
                    row_cnt = cursor.fetchone()
                    if (row_cnt['cnt'] or 0) > 0:
                        continue

                    cover_path = os.path.join(covers_dir, cover_img)
                    if os.path.exists(cover_path) and os.path.isfile(cover_path):
                        try:
                            os.remove(cover_path)
                            print(f"[TrashService] Physically deleted unreferenced cover: {cover_path}")
                        except Exception as ex_file:
                            print(f"[TrashService WARNING] Failed to delete cover file '{cover_path}': {ex_file}")
                
            conn.commit()
            print(f"[TrashService] Successfully hard deleted {len(target_ids)} books from DB and storage.")
            return True
        except Exception as e:
            print(f"[TrashService ERROR] Failed to empty trash: {e}")
            return False
        finally:
            conn.close()
