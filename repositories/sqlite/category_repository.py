# -*- coding: utf-8 -*-
"""
category_repository.py – 카테고리(도서관) 관리, 이관 및 커버 스캔 관련 데이터 액세스 레이어
"""
import database


def _dynamic_insert(cursor, table, row, overrides=None, exclude=('id',)):
    """row(dict형 행)의 실제 컬럼을 그대로 사용해 INSERT 문을 동적으로 조립하고 새 id를 반환한다.
    카테고리 이관(move_library_transaction)에서 컬럼을 하드코딩하면 스키마에 새 컬럼이
    추가될 때마다 이관 로직을 잊지 않고 같이 고쳐야 하는 문제가 반복적으로 발생했다
    ([[project_category_move_stale_columns_fix]] 등) — 이 헬퍼로 그 클래스의 버그를 근본적으로 차단한다.
    exclude는 항상 대상 DB가 새로 채번하도록 제외한다(PK를 그대로 복사하면 두 DB의
    AUTOINCREMENT 시퀀스가 서로 독립적이라 목적지에 이미 존재하는 id와 충돌할 수 있다)."""
    data = dict(row)
    for key in exclude:
        data.pop(key, None)
    if overrides:
        data.update(overrides)
    columns = list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))
    col_list = ', '.join(columns)
    cursor.execute(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
        tuple(data[c] for c in columns)
    )
    return cursor.lastrowid


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
                "INSERT INTO library_groups (name, icon, color, sort_order) VALUES (?, ?, ?, COALESCE((SELECT MAX(sort_order) + 1 FROM library_groups), 0))",
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
            cursor.execute("UPDATE library_groups SET name = ? WHERE id = ?", (name, group_id))
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
            cursor.execute("UPDATE libraries SET group_id = NULL WHERE group_id = ?", (group_id,))
            cursor.execute("DELETE FROM plugin_group_assignments WHERE group_id = ?", (group_id,))
            cursor.execute("DELETE FROM library_groups WHERE id = ?", (group_id,))
            if cursor.rowcount == 0:
                raise ValueError('그룹을 찾을 수 없습니다.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def move_library_groups(db_type, items):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.executemany(
                "UPDATE library_groups SET sort_order = ? WHERE id = ?",
                [(item['sort_order'], item['id']) for item in items]
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_plugin_group_assignments(db_type):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT plugin_id, group_id, sort_order FROM plugin_group_assignments")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def assign_plugin_groups(db_type, items):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            plugin_ids = [item['plugin_id'] for item in items]
            if plugin_ids:
                placeholders = ','.join('?' for _ in plugin_ids)
                cursor.execute(f"DELETE FROM plugin_group_assignments WHERE plugin_id IN ({placeholders})", plugin_ids)
            grouped_items = [(item['plugin_id'], item['group_id'], item['sort_order']) for item in items if item['group_id'] is not None]
            if grouped_items:
                cursor.executemany(
                    "INSERT INTO plugin_group_assignments (plugin_id, group_id, sort_order) VALUES (?, ?, ?)",
                    grouped_items
                )
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
            WHERE p.user_id = ? AND p.has_access = 1
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
                "UPDATE libraries SET group_id = ?, sort_order = ? WHERE id = ?",
                [(item['group_id'], item['sort_order'], item['id']) for item in items]
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None, gdrive_copy_remote=None, gdrive_copy_dest_path=None, gdrive_view_local_mirror_path=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries
                (name, physical_path, scan_status, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_copy_dest_path, gdrive_view_local_mirror_path)
                VALUES (?, ?, 'ready', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_copy_dest_path, gdrive_view_local_mirror_path)
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
    def edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None, gdrive_copy_remote=None, gdrive_copy_dest_path=None, gdrive_view_local_mirror_path=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE libraries
                SET name = ?, physical_path = ?, is_remote = ?, rclone_rc_url = ?, icon = ?, color = ?, hide_cover = ?, group_id = ?, gdrive_copy_remote = ?, gdrive_copy_dest_path = ?, gdrive_view_local_mirror_path = ?
                WHERE id = ?
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_copy_dest_path, gdrive_view_local_mirror_path, library_id)
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
            # 1. 도서 권한 및 시리즈 정보 삭제
            cursor.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            try:
                cursor.execute("DELETE FROM series WHERE library_id = ?", (library_id,))
            except Exception:
                pass

            # 1-1. 오디오북 종속 데이터 정리
            # libraries.id를 audiobooks.library_id가 참조하므로,
            # 라이브러리 삭제 전에 오디오북 하위 데이터를 먼저 제거해야 FK 오류를 방지할 수 있다.
            # progress.current_track_id FK는 기본 RESTRICT 동작이므로,
            # 다른 audiobook_id 행이 동일 track_id를 잘못 참조하는 경우까지 선제 정리한다.
            cursor.execute(
                """
                DELETE FROM audiobook_progress
                WHERE audiobook_id IN (SELECT id FROM audiobooks WHERE library_id = ?)
                   OR current_track_id IN (
                       SELECT t.id
                       FROM audiobook_tracks t
                       JOIN audiobooks a ON a.id = t.audiobook_id
                       WHERE a.library_id = ?
                   )
                """,
                (library_id, library_id)
            )
            cursor.execute(
                "DELETE FROM audiobook_tracks WHERE audiobook_id IN (SELECT id FROM audiobooks WHERE library_id = ?)",
                (library_id,)
            )
            cursor.execute("DELETE FROM audiobooks WHERE library_id = ?", (library_id,))

            # 1-2. 영상 강좌 종속 데이터 정리 (오디오북과 동일하게 books 테이블을 쓰지 않으므로
            # 위 books 일괄 삭제로는 정리되지 않아, 삭제해도 전체보기에 계속 남는 문제가 있었다)
            cursor.execute(
                "DELETE FROM video_episode_progress WHERE video_id IN (SELECT id FROM videos WHERE library_id = ?)",
                (library_id,)
            )
            cursor.execute(
                "DELETE FROM video_progress WHERE video_id IN (SELECT id FROM videos WHERE library_id = ?)",
                (library_id,)
            )
            cursor.execute(
                "DELETE FROM video_episodes WHERE video_id IN (SELECT id FROM videos WHERE library_id = ?)",
                (library_id,)
            )
            cursor.execute("DELETE FROM videos WHERE library_id = ?", (library_id,))

            # 2. 관련 도서 종속 데이터 초고속 서브쿼리 일괄 소거
            cursor.execute("DELETE FROM book_offsets WHERE book_id IN (SELECT id FROM books WHERE library_id = ?)", (library_id,))
            cursor.execute("DELETE FROM user_progress WHERE book_id IN (SELECT id FROM books WHERE library_id = ?)", (library_id,))
            cursor.execute("DELETE FROM user_reading_log WHERE book_id IN (SELECT id FROM books WHERE library_id = ?)", (library_id,))
            cursor.execute("DELETE FROM user_favorites WHERE book_id IN (SELECT id FROM books WHERE library_id = ?)", (library_id,))
            cursor.execute("DELETE FROM books WHERE library_id = ?", (library_id,))
            
            # 3. 라이브러리 레코드 및 스캔 캐시(scanner_progress, folder_mtimes) 소거
            cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
            lib_row = cursor.fetchone()
            if lib_row and lib_row['physical_path']:
                phys_path = lib_row['physical_path'].rstrip('/\\')
                cursor.execute("DELETE FROM folder_mtimes WHERE folder_path = ? OR folder_path LIKE ?", (phys_path, phys_path + '/%'))
            
            cursor.execute("DELETE FROM scanner_progress WHERE library_id = ?", (str(library_id),))
            try:
                cursor.execute("DELETE FROM scanner_tasks WHERE task_key LIKE ?", (f"%_{library_id}",))
            except Exception:
                pass
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
    def insert_library_raw(db_type, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote=None, gdrive_copy_dest_path=None, gdrive_view_local_mirror_path=None):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote, gdrive_copy_dest_path, gdrive_view_local_mirror_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote, gdrive_copy_dest_path, gdrive_view_local_mirror_path)
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
            # 1. 목적지 DB에 카테고리 삽입 — new_lib_data(SELECT * 결과)의 컬럼을 그대로 옮기므로
            # group_id/sort_order를 포함해 스키마의 모든 컬럼이 자동으로 함께 이관된다.
            new_lib_id = _dynamic_insert(cursor_dst, 'libraries', new_lib_data, overrides={'name': new_lib_name})

            book_id_map = {}
            for book in books_data:
                old_book_id = book["id"]
                # 2. 목적지 DB에 도서 삽입 (books의 모든 컬럼 자동 이관)
                new_book_id = _dynamic_insert(cursor_dst, 'books', book, overrides={'library_id': new_lib_id})
                book_id_map[old_book_id] = new_book_id

                # 3. 진척도(user_progress) 복제
                cursor_src.execute("SELECT * FROM user_progress WHERE book_id = ?", (old_book_id,))
                for row in cursor_src.fetchall():
                    _dynamic_insert(cursor_dst, 'user_progress', dict(row), overrides={'book_id': new_book_id})

                # 4. 독서 일일 로그(user_reading_log) 복제
                cursor_src.execute("SELECT * FROM user_reading_log WHERE book_id = ?", (old_book_id,))
                for row in cursor_src.fetchall():
                    _dynamic_insert(cursor_dst, 'user_reading_log', dict(row), overrides={'book_id': new_book_id})

                # 5. 압축파일 오프셋(book_offsets) 복제
                cursor_src.execute("SELECT * FROM book_offsets WHERE book_id = ?", (old_book_id,))
                for row in cursor_src.fetchall():
                    _dynamic_insert(cursor_dst, 'book_offsets', dict(row), overrides={'book_id': new_book_id})

                # 5-1. 즐겨찾기(user_favorites) 복제 — 예전엔 소스에서 삭제만 되고 목적지로
                # 옮기는 코드가 없어 이관할 때마다 즐겨찾기가 조용히 유실되고 있었다.
                cursor_src.execute("SELECT * FROM user_favorites WHERE book_id = ?", (old_book_id,))
                for row in cursor_src.fetchall():
                    _dynamic_insert(cursor_dst, 'user_favorites', dict(row), overrides={'book_id': new_book_id})

            # 6. 사용자별 카테고리 권한(user_category_permissions) 복제
            cursor_src.execute("SELECT * FROM user_category_permissions WHERE library_id = ?", (library_id,))
            for row in cursor_src.fetchall():
                _dynamic_insert(cursor_dst, 'user_category_permissions', dict(row), overrides={'library_id': new_lib_id})

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
    def check_user_category_access(db_type, user_id, library_id):
        """사용자의 특정 카테고리 접근 권한 여부 확인 (admin 계정은 항상 허용)"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            # 1. admin 계정 여부 체크
            cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
            user_row = cursor.fetchone()
            if user_row:
                role = user_row['role'] if isinstance(user_row, dict) else user_row[0]
                if role == 'admin':
                    return True

            # 2. 개별 권한 테이블 점검
            cursor.execute(
                "SELECT 1 FROM user_category_permissions WHERE user_id = ? AND library_id = ? AND has_access = 1",
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

    @staticmethod
    def update_schedule(db_type, library_id, cron_schedule, vfs_refresh_before_scan, rclone_rc_url):
        """라이브러리 주기 스케줄 및 VFS/rclone 설정 업데이트"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries 
                SET cron_schedule = ?, 
                    vfs_refresh_before_scan = ?, 
                    rclone_rc_url = ? 
                WHERE id = ?
            """, (cron_schedule, vfs_refresh_before_scan, rclone_rc_url, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

