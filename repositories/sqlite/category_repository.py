# -*- coding: utf-8 -*-
"""
category_repository.py – 카테고리(도서관) 관리, 이관 및 커버 스캔 관련 데이터 액세스 레이어
"""
import database

class CategoryRepository:
    @staticmethod
    def get_all_libraries(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM libraries ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_libraries_by_user_permissions(db_type, user_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT l.* FROM libraries l
            JOIN user_category_permissions p ON l.id = p.library_id
            WHERE p.user_id = ? AND p.has_access = 1
            ORDER BY l.name ASC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries 
                (name, physical_path, scan_status, is_remote, rclone_rc_url, icon, color, hide_cover) 
                VALUES (?, ?, 'ready', ?, ?, ?, ?, ?)
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover)
            )
            lib_id = cursor.lastrowid
            conn.commit()
            return lib_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE libraries 
                SET name = ?, physical_path = ?, is_remote = ?, rclone_rc_url = ?, icon = ?, color = ?, hide_cover = ?
                WHERE id = ?
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, library_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def delete_library(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            # 1. 도서 권한 삭제
            cursor.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            # 2. 관련 도서들 정보 연쇄 소거
            cursor.execute("SELECT id FROM books WHERE library_id = ?", (library_id,))
            books = cursor.fetchall()
            for b in books:
                bid = b['id']
                cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (bid,))
                cursor.execute("DELETE FROM user_progress WHERE book_id = ?", (bid,))
                cursor.execute("DELETE FROM user_reading_log WHERE book_id = ?", (bid,))
                cursor.execute("DELETE FROM user_favorites WHERE book_id = ?", (bid,))
            
            cursor.execute("DELETE FROM books WHERE library_id = ?", (library_id,))
            # 3. 라이브러리 레코드 소거
            cursor.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_library_by_id(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM libraries WHERE id = ?", (library_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def check_duplicate_name(db_type, name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM libraries WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return row['id'] if row else None

    @staticmethod
    def insert_library_raw(db_type, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries 
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover)
            )
            lib_id = cursor.lastrowid
            conn.commit()
            return lib_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_books_by_library_raw(db_type, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books WHERE library_id = ?", (library_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def move_library_transaction(from_type, to_type, library_id, new_lib_name, new_lib_data, books_data):
        """한 RDBMS DB에서 다른 DB로 라이브러리와 관련 도서, 메타데이터, 로그, 오프셋 정보를 원자적 이관"""
        conn_src = database.get_connection(from_type)
        conn_dst = database.get_connection(to_type)
        
        cursor_src = conn_src.cursor()
        cursor_dst = conn_dst.cursor()
        
        try:
            # 1. 목적지 DB에 카테고리 삽입
            cursor_dst.execute(
                """INSERT INTO libraries 
                   (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_lib_name, new_lib_data["physical_path"], new_lib_data["cron_schedule"], new_lib_data["last_scanned_at"], 
                 new_lib_data["scan_status"], new_lib_data["is_remote"], new_lib_data["vfs_refresh_before_scan"], 
                 new_lib_data["rclone_rc_url"], new_lib_data["icon"], new_lib_data["color"], new_lib_data["hide_cover"])
            )
            new_lib_id = cursor_dst.lastrowid
            
            book_id_map = {}
            for book in books_data:
                old_book_id = book["id"]
                # 2. 목적지 DB에 도서 삽입
                cursor_dst.execute(
                    """INSERT INTO books 
                       (library_id, title, series_name, author, file_path, file_format, total_pages, has_offsets, cover_image, 
                        publisher, link, score, release_date, summary, genre, tags, is_favorite, cover_updated_at, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_lib_id, book["title"], book["series_name"], book["author"], book["file_path"], book["file_format"],
                     book["total_pages"], book["has_offsets"], book["cover_image"], book["publisher"], book["link"],
                     book["score"], book["release_date"], book["summary"], book["genre"], book["tags"], book["is_favorite"],
                     book["cover_updated_at"], book["created_at"])
                )
                new_book_id = cursor_dst.lastrowid
                book_id_map[old_book_id] = new_book_id
                
                # 3. 진척도(user_progress) 복제
                cursor_src.execute("SELECT * FROM user_progress WHERE book_id = ?", (old_book_id,))
                progs = cursor_src.fetchall()
                for p in progs:
                    cursor_dst.execute(
                        "INSERT INTO user_progress (book_id, user_id, pages_read, is_completed, last_read_at) VALUES (?, ?, ?, ?, ?)",
                        (new_book_id, p["user_id"], p["pages_read"], p["is_completed"], p["last_read_at"])
                    )
                    
                # 4. 독서 일일 로그(user_reading_log) 복제
                cursor_src.execute("SELECT * FROM user_reading_log WHERE book_id = ?", (old_book_id,))
                logs = cursor_src.fetchall()
                for l in logs:
                    cursor_dst.execute(
                        "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?, ?, ?, ?, ?)",
                        (new_book_id, l["user_id"], l["pages_read_delta"], l["duration_seconds"], l["read_date"])
                    )
                    
                # 5. 압축파일 오프셋(book_offsets) 복제
                cursor_src.execute("SELECT * FROM book_offsets WHERE book_id = ?", (old_book_id,))
                offsets = cursor_src.fetchall()
                for o in offsets:
                    cursor_dst.execute(
                        "INSERT INTO book_offsets (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (new_book_id, o["page_idx"], o["filename"], o["local_header_offset"], o["compress_size"], o["file_size"], o["compress_type"])
                    )
            
            # 6. 사용자별 카테고리 권한(user_category_permissions) 복제
            cursor_src.execute("SELECT * FROM user_category_permissions WHERE library_id = ?", (library_id,))
            perms = cursor_src.fetchall()
            for perm in perms:
                cursor_dst.execute(
                    "INSERT INTO user_category_permissions (user_id, library_id, has_access) VALUES (?, ?, ?)",
                    (perm["user_id"], new_lib_id, perm["has_access"])
                )
                
            # 7. 소스 DB에서 해당 데이터들 역순 소거
            for old_book_id in book_id_map.keys():
                cursor_src.execute("DELETE FROM book_offsets WHERE book_id = ?", (old_book_id,))
                cursor_src.execute("DELETE FROM user_progress WHERE book_id = ?", (old_book_id,))
                cursor_src.execute("DELETE FROM user_reading_log WHERE book_id = ?", (old_book_id,))
                cursor_src.execute("DELETE FROM user_favorites WHERE book_id = ?", (old_book_id,))
                
            cursor_src.execute("DELETE FROM books WHERE library_id = ?", (library_id,))
            cursor_src.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            cursor_src.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            
            # 8. 양쪽 트랜잭션 커밋 완료
            conn_dst.commit()
            conn_src.commit()
            return True
        except Exception as e:
            conn_dst.rollback()
            conn_src.rollback()
            raise e
        finally:
            conn_src.close()
            conn_dst.close()

    @staticmethod
    def get_libraries_name_and_path(db_type):
        """중복 경로 매핑을 위한 라이브러리 전체의 name, physical_path 조회"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT name, physical_path FROM libraries")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_library_scan_status(db_type, library_id, status):
        """라이브러리 스캔 상태(scan_status) 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET scan_status = ? WHERE id = ?", (status, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_library_scan_success(db_type, library_id, end_str):
        """라이브러리 스캔 완료 상태 갱신"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET scan_status = 'ready', 
                    last_scanned_at = ? 
                WHERE id = ?
            """, (end_str, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
