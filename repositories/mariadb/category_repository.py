# -*- coding: utf-8 -*-
"""
category_repository.py – MariaDB 전용 카테고리(도서관) 관리 및 커버 스캔 데이터 액세스 레이어
"""
import database

class CategoryRepository:
    @staticmethod
    def get_library_groups(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, icon, color, sort_order FROM library_groups ORDER BY sort_order ASC, name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def add_library_group(db_type, name, icon='fa-folder', color='#a855f7'):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO library_groups (name, icon, color, sort_order) VALUES (%s, %s, %s, COALESCE((SELECT next_order FROM (SELECT MAX(sort_order) + 1 AS next_order FROM library_groups) grouped), 0))",
                (name, icon, color)
            )
            group_id = cursor.lastrowid
            conn.commit()
            return group_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def edit_library_group(db_type, group_id, name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE library_groups SET name = %s WHERE id = %s", (name, group_id))
            if cursor.rowcount == 0:
                raise ValueError('그룹을 찾을 수 없습니다.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_library_group(db_type, group_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET group_id = NULL WHERE group_id = %s", (group_id,))
            cursor.execute("DELETE FROM library_groups WHERE id = %s", (group_id,))
            if cursor.rowcount == 0:
                raise ValueError('그룹을 찾을 수 없습니다.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_all_libraries(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM libraries ORDER BY sort_order ASC, name ASC")
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
            WHERE p.user_id = %s AND p.has_access = 1
            ORDER BY l.sort_order ASC, l.name ASC
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def move_libraries(db_type, items):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.executemany(
                "UPDATE libraries SET group_id = %s, sort_order = %s WHERE id = %s",
                [(item['group_id'], item['sort_order'], item['id']) for item in items]
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries 
                (name, physical_path, scan_status, is_remote, rclone_rc_url, icon, color, hide_cover, group_id) 
                VALUES (%s, %s, 'ready', %s, %s, %s, %s, %s, %s)
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id)
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
    def edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE libraries 
                SET name = %s, physical_path = %s, is_remote = %s, rclone_rc_url = %s, icon = %s, color = %s, hide_cover = %s, group_id = %s
                WHERE id = %s
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, library_id)
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
            cursor.execute("DELETE FROM user_category_permissions WHERE library_id = %s", (library_id,))
            try:
                cursor.execute("DELETE FROM series WHERE library_id = %s", (library_id,))
            except Exception:
                pass

            cursor.execute(
                """
                DELETE FROM audiobook_progress
                WHERE audiobook_id IN (SELECT id FROM audiobooks WHERE library_id = %s)
                   OR current_track_id IN (
                       SELECT t.id
                       FROM audiobook_tracks t
                       JOIN audiobooks a ON a.id = t.audiobook_id
                       WHERE a.library_id = %s
                   )
                """,
                (library_id, library_id)
            )
            cursor.execute(
                "DELETE FROM audiobook_tracks WHERE audiobook_id IN (SELECT id FROM audiobooks WHERE library_id = %s)",
                (library_id,)
            )
            cursor.execute("DELETE FROM audiobooks WHERE library_id = %s", (library_id,))
            
            cursor.execute("DELETE FROM book_offsets WHERE book_id IN (SELECT id FROM books WHERE library_id = %s)", (library_id,))
            cursor.execute("DELETE FROM user_progress WHERE book_id IN (SELECT id FROM books WHERE library_id = %s)", (library_id,))
            cursor.execute("DELETE FROM user_reading_log WHERE book_id IN (SELECT id FROM books WHERE library_id = %s)", (library_id,))
            cursor.execute("DELETE FROM user_favorites WHERE book_id IN (SELECT id FROM books WHERE library_id = %s)", (library_id,))
            cursor.execute("DELETE FROM books WHERE library_id = %s", (library_id,))
            
            cursor.execute("SELECT physical_path FROM libraries WHERE id = %s", (library_id,))
            lib_row = cursor.fetchone()
            if lib_row and lib_row['physical_path']:
                phys_path = lib_row['physical_path'].rstrip('/\\')
                cursor.execute("DELETE FROM folder_mtimes WHERE folder_path = %s OR folder_path LIKE %s", (phys_path, phys_path + '/%'))
            
            cursor.execute("DELETE FROM scanner_progress WHERE library_id = %s", (str(library_id),))
            try:
                cursor.execute("DELETE FROM scanner_tasks WHERE task_key LIKE %s", (f"%_{library_id}",))
            except Exception:
                pass
            cursor.execute("DELETE FROM libraries WHERE id = %s", (library_id,))
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
        cursor.execute("SELECT * FROM libraries WHERE id = %s", (library_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def check_duplicate_name(db_type, name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM libraries WHERE name = %s", (name,))
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        cursor.execute("SELECT * FROM books WHERE library_id = %s", (library_id,))
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
            cursor_dst.execute(
                """INSERT INTO libraries 
                   (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (new_lib_name, new_lib_data["physical_path"], new_lib_data["cron_schedule"], new_lib_data["last_scanned_at"], 
                 new_lib_data["scan_status"], new_lib_data["is_remote"], new_lib_data["vfs_refresh_before_scan"], 
                 new_lib_data["rclone_rc_url"], new_lib_data["icon"], new_lib_data["color"], new_lib_data["hide_cover"])
            )
            new_lib_id = cursor_dst.lastrowid
            
            book_id_map = {}
            for book in books_data:
                old_book_id = book["id"]
                cursor_dst.execute(
                    """INSERT INTO books 
                       (library_id, title, series_name, author, file_path, file_format, total_pages, has_offsets, cover_image, 
                        publisher, link, score, release_date, summary, genre, tags, is_favorite, cover_updated_at, created_at) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (new_lib_id, book["title"], book["series_name"], book["author"], book["file_path"], book["file_format"],
                     book["total_pages"], book["has_offsets"], book["cover_image"], book["publisher"], book["link"],
                     book["score"], book["release_date"], book["summary"], book["genre"], book["tags"], book["is_favorite"],
                     book["cover_updated_at"], book["created_at"])
                )
                new_book_id = cursor_dst.lastrowid
                book_id_map[old_book_id] = new_book_id
                
                cursor_src.execute("SELECT * FROM user_progress WHERE book_id = %s", (old_book_id,))
                progs = cursor_src.fetchall()
                for p in progs:
                    cursor_dst.execute(
                        "INSERT INTO user_progress (book_id, user_id, pages_read, is_completed, last_read_at) VALUES (%s, %s, %s, %s, %s)",
                        (new_book_id, p["user_id"], p["pages_read"], p["is_completed"], p["last_read_at"])
                    )
                    
                cursor_src.execute("SELECT * FROM user_reading_log WHERE book_id = %s", (old_book_id,))
                logs = cursor_src.fetchall()
                for l in logs:
                    cursor_dst.execute(
                        "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (%s, %s, %s, %s, %s)",
                        (new_book_id, l["user_id"], l["pages_read_delta"], l["duration_seconds"], l["read_date"])
                    )
                    
                cursor_src.execute("SELECT * FROM book_offsets WHERE book_id = %s", (old_book_id,))
                offsets = cursor_src.fetchall()
                for o in offsets:
                    cursor_dst.execute(
                        "INSERT INTO book_offsets (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (new_book_id, o["page_idx"], o["filename"], o["local_header_offset"], o["compress_size"], o["file_size"], o["compress_type"])
                    )
            
            cursor_src.execute("SELECT * FROM user_category_permissions WHERE library_id = %s", (library_id,))
            perms = cursor_src.fetchall()
            for perm in perms:
                cursor_dst.execute(
                    "INSERT INTO user_category_permissions (user_id, library_id, has_access) VALUES (%s, %s, %s)",
                    (perm["user_id"], new_lib_id, perm["has_access"])
                )
                
            for old_book_id in book_id_map.keys():
                cursor_src.execute("DELETE FROM book_offsets WHERE book_id = %s", (old_book_id,))
                cursor_src.execute("DELETE FROM user_progress WHERE book_id = %s", (old_book_id,))
                cursor_src.execute("DELETE FROM user_reading_log WHERE book_id = %s", (old_book_id,))
                cursor_src.execute("DELETE FROM user_favorites WHERE book_id = %s", (old_book_id,))
                
            cursor_src.execute("DELETE FROM books WHERE library_id = %s", (library_id,))
            cursor_src.execute("DELETE FROM user_category_permissions WHERE library_id = %s", (library_id,))
            cursor_src.execute("DELETE FROM libraries WHERE id = %s", (library_id,))
            
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
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT name, physical_path FROM libraries")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def update_library_scan_status(db_type, library_id, status):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET scan_status = %s WHERE id = %s", (status, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def check_user_category_access(db_type, user_id, library_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                role = user_row['role'] if isinstance(user_row, dict) else user_row[0]
                if role == 'admin':
                    return True

            cursor.execute(
                "SELECT 1 FROM user_category_permissions WHERE user_id = %s AND library_id = %s AND has_access = 1",
                (user_id, library_id)
            )
            row = cursor.fetchone()
            return row is not None
        except Exception:
            return True
        finally:
            conn.close()

    @staticmethod
    def update_library_scan_success(db_type, library_id, end_str):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET scan_status = 'ready', 
                    last_scanned_at = %s 
                WHERE id = %s
            """, (end_str, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_schedule(db_type, library_id, cron_schedule, vfs_refresh_before_scan, rclone_rc_url):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET cron_schedule = %s, 
                    vfs_refresh_before_scan = %s, 
                    rclone_rc_url = %s 
                WHERE id = %s
            """, (cron_schedule, vfs_refresh_before_scan, rclone_rc_url, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
