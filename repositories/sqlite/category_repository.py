# -*- coding: utf-8 -*-
"""
category_repository.py – 카테고리(도서관) 관리, 이관 및 커버 스캔 관련 데이터 액세스 레이어
"""
import database
from repositories import category_data_shared


def _dynamic_insert(cursor, table, row, overrides=None, exclude=('id',), cache=None):
    """row(dict형 행)의 실제 컬럼을 그대로 사용해 INSERT 문을 동적으로 조립하고 새 id를 반환한다.
    카테고리 DB 이동(prepare_library_transfer 등)에서 컬럼을 하드코딩하면 스키마에 새 컬럼이
    추가될 때마다 이관 로직을 잊지 않고 같이 고쳐야 하는 문제가 반복적으로 발생했다
    ([[project_category_move_stale_columns_fix]] 등) — 이 헬퍼로 그 클래스의 버그를 근본적으로 차단한다.
    exclude는 항상 대상 DB가 새로 채번하도록 제외한다(PK를 그대로 복사하면 두 DB의
    AUTOINCREMENT 시퀀스가 서로 독립적이라 목적지에 이미 존재하는 id와 충돌할 수 있다)."""
    data = dict(row)
    for key in exclude:
        data.pop(key, None)
    if overrides:
        data.update(overrides)
    if cache is not None:
        # 오래 운영한 DB는 일반·성인 DB 스키마가 어긋나 있을 수 있다(한쪽에만 있는 컬럼) - 대상 DB에 있는
        # 컬럼만 넣어 'Unknown column'으로 이관 전체가 실패하지 않게 하고, 빠진 컬럼은 한 번만 남긴다.
        if table not in cache:
            cache[table] = _table_columns(cursor, table)
            dropped = sorted(set(data) - cache[table])
            if dropped:
                print(f"[CategoryRepository WARNING] move: columns missing in target {table}, skipped: {dropped}")
        data = {k: v for k, v in data.items() if k in cache[table]}
    columns = list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))
    col_list = ', '.join(columns)
    cursor.execute(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
        tuple(data[c] for c in columns)
    )
    return cursor.lastrowid

def _table_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row['name'] for row in cursor.fetchall()}


class CategoryRepository:
    @staticmethod
    def get_library_groups(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, icon, color, sort_order FROM library_groups ORDER BY sort_order ASC, name ASC")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def add_library_group(db_type, name, icon='fa-folder', color=None):
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
    def get_library_kinds(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code, name, is_builtin, sort_order FROM library_kinds ORDER BY sort_order ASC, name ASC")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def add_library_kind(db_type, code, name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO library_kinds (code, name, is_builtin, sort_order) VALUES (?, ?, 0, COALESCE((SELECT MAX(sort_order) + 1 FROM library_kinds), 0))",
                (code, name)
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def edit_library_kind(db_type, code, name):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE library_kinds SET name = ? WHERE code = ?", (name, code))
            if cursor.rowcount == 0:
                raise ValueError('속성을 찾을 수 없습니다.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_library_kind(db_type, code):
        """기본 속성이나 사용 중인 속성은 삭제하지 않는다(사용 중이면 몇 개 카테고리가 쓰는지 알려 준다)."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT is_builtin FROM library_kinds WHERE code = ?", (code,))
            row = cursor.fetchone()
            if not row:
                raise ValueError('속성을 찾을 수 없습니다.')
            if int(row['is_builtin'] or 0) == 1:
                raise ValueError('기본 속성은 삭제할 수 없습니다. 이름만 바꿀 수 있습니다.')
            cursor.execute("SELECT COUNT(*) AS used FROM libraries WHERE content_kind = ?", (code,))
            used = int(cursor.fetchone()['used'] or 0)
            if used > 0:
                raise ValueError(f'{used}개 카테고리가 이 속성을 사용 중이라 삭제할 수 없습니다.')
            cursor.execute("DELETE FROM library_kinds WHERE code = ?", (code,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_plugin_group_assignments(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT plugin_id, group_id, sort_order FROM plugin_group_assignments")
            rows = cursor.fetchall()
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
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM libraries WHERE COALESCE(pending_delete, 0) = 0 ORDER BY sort_order ASC, name ASC")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_libraries_by_user_permissions(db_type, user_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT l.* FROM libraries l
                JOIN user_category_permissions p ON l.id = p.library_id
                WHERE p.user_id = ? AND p.has_access = 1 AND COALESCE(l.pending_delete, 0) = 0
                ORDER BY l.sort_order ASC, l.name ASC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
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
    def add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None, gdrive_copy_remote=None, gdrive_view_local_mirror_path=None, cover_aspect_ratio='4:3', hide_title=0, content_kind='unspecified'):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries
                (name, physical_path, scan_status, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title, content_kind)
                VALUES (?, ?, 'ready', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title, content_kind)
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
    def edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id=None, gdrive_copy_remote=None, gdrive_view_local_mirror_path=None, cover_aspect_ratio='4:3', hide_title=0, content_kind=None):
        """content_kind=None이면 기존 속성을 유지한다(인자를 생략한 호출이 값을 지우지 않도록)."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE libraries
                SET name = ?, physical_path = ?, is_remote = ?, rclone_rc_url = ?, icon = ?, color = ?, hide_cover = ?, group_id = ?, gdrive_copy_remote = ?, gdrive_view_local_mirror_path = ?, cover_aspect_ratio = ?, hide_title = ?, content_kind = COALESCE(?, content_kind)
                WHERE id = ?
                """,
                (name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title, content_kind, library_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # 카테고리 삭제는 세 단계로 나뉜다(2026-10-20 커뮤니티 제보: 요청 안에서 전부 지우다 리버스 프록시
    # 60초 타임아웃(504)에 걸렸다). 1) 요청 안에서 표시만 하고 목록·요약·권한에서 빼낸다 2) 스캐너 큐
    # (library_delete)가 도서를 나눠 지운다 3) 남은 카테고리 단위 기록과 카테고리 행을 지운다.

    @staticmethod
    def mark_library_pending_delete(db_type, library_id):
        """1단계: 카테고리 규모와 무관한 짧은 문장만 실행한다. 이름 뒤에 표시를 붙여, 지워지는 동안
        같은 이름으로 새 카테고리를 만들어도 UNIQUE 제약에 걸리지 않게 한다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM libraries WHERE id = ?", (library_id,))
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute(
                "UPDATE libraries SET pending_delete = 1, name = ? WHERE id = ?",
                (f"{row['name']} [deleting #{library_id}]", library_id)
            )
            try:
                cursor.execute("DELETE FROM series_summary WHERE library_id = ?", (library_id,))
            except Exception:
                pass
            cursor.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_pending_delete_library_ids(db_type):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM libraries WHERE pending_delete = 1")
            rows = cursor.fetchall()
        return [int(row['id']) for row in rows]

    @staticmethod
    def delete_library_chunk(db_type, library_id, batch_size=900):
        """2단계: 도서·오디오북·영상을 batch_size개씩 종속 데이터와 함께 지우고 커밋한다.
        (지운 항목 수, 지울 TTS 음성 폴더 rel_dir 목록, 지운 도서 id 목록)을 돌려주며 수가 0이면 남은 게 없다.
        중간에 끊겨도 다음 호출이 남은 것부터 이어간다. IN (SELECT …) 대신 미리 뽑은 id 목록으로 지워
        트랜잭션과 락을 짧게 유지한다.
        구버전 SQLite의 바인딩 변수 한도(999)를 넘지 않게 기본 묶음을 900으로 둔다."""
        batch_size = min(int(batch_size), 900)
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            deleted = 0
            rel_dirs = []
            cursor.execute("SELECT id FROM books WHERE library_id = ? LIMIT ?", (library_id, batch_size))
            book_ids = [row['id'] for row in cursor.fetchall()]
            if book_ids:
                rel_dirs = category_data_shared.purge_book_dependents(cursor, book_ids, '?')
                cursor.execute(f"DELETE FROM books WHERE id IN ({','.join(['?'] * len(book_ids))})", book_ids)
                deleted += len(book_ids)

            # 오디오북은 트랙이 많아 한 번에 적게 지운다. progress.current_track_id FK는 RESTRICT라
            # 다른 오디오북 행이 이 트랙을 잘못 가리키는 경우까지 먼저 정리한다.
            cursor.execute("SELECT id FROM audiobooks WHERE library_id = ? LIMIT ?", (library_id, max(1, batch_size // 10)))
            ids = [row['id'] for row in cursor.fetchall()]
            if ids:
                ph = ','.join(['?'] * len(ids))
                cursor.execute(
                    f"""
                    DELETE FROM audiobook_progress
                    WHERE audiobook_id IN ({ph})
                       OR current_track_id IN (SELECT id FROM audiobook_tracks WHERE audiobook_id IN ({ph}))
                    """,
                    ids + ids
                )
                cursor.execute(f"DELETE FROM audiobook_tracks WHERE audiobook_id IN ({ph})", ids)
                cursor.execute(f"DELETE FROM audiobooks WHERE id IN ({ph})", ids)
                deleted += len(ids)

            cursor.execute("SELECT id FROM videos WHERE library_id = ? LIMIT ?", (library_id, max(1, batch_size // 10)))
            ids = [row['id'] for row in cursor.fetchall()]
            if ids:
                ph = ','.join(['?'] * len(ids))
                for table in ('video_episode_progress', 'video_progress', 'video_episodes'):
                    cursor.execute(f"DELETE FROM {table} WHERE video_id IN ({ph})", ids)
                cursor.execute(f"DELETE FROM videos WHERE id IN ({ph})", ids)
                deleted += len(ids)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        # KOReader 문서 매핑은 중앙(general) DB에 있다
        if book_ids:
            with database.connection('general') as gconn:
                gcursor = gconn.cursor()
                category_data_shared.forget_kosync(gcursor, db_type, book_ids, '?')
                gconn.commit()
        return deleted, rel_dirs, book_ids

    @staticmethod
    def delete_library_finalize(db_type, library_id):
        """3단계: 도서가 모두 지워진 뒤 카테고리 단위 기록과 카테고리 행을 지운다."""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            for table in ('series', 'series_summary'):
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE library_id = ?", (library_id,))
                except Exception:
                    pass
            cursor.execute("SELECT physical_path FROM libraries WHERE id = ?", (library_id,))
            lib_row = cursor.fetchone()
            if lib_row and lib_row['physical_path']:
                phys_path = lib_row['physical_path'].rstrip('/\\')
                cursor.execute("DELETE FROM folder_mtimes WHERE folder_path = ? OR folder_path LIKE ?", (phys_path, phys_path + '/%'))
            cursor.execute("DELETE FROM scanner_progress WHERE library_id = ?", (str(library_id),))
            cursor.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        # 작업 기록(scanner_tasks)은 general DB에 있다. 예전 LIKE '%_{id}'는 '_'가 와일드카드라
        # id=1을 지우면 11·21번 카테고리 기록까지 지웠다 - 이 카테고리의 키만 정확히 지운다.
        try:
            with database.connection('general') as gconn:
                gcursor = gconn.cursor()
                gcursor.execute(
                    "DELETE FROM scanner_tasks WHERE task_key IN (?, ?) AND status NOT IN ('pending', 'running', 'exit_pending')",
                    (f"library_scan_{db_type}_{library_id}", f"cover_scan_{db_type}_{library_id}")
                )
                gconn.commit()
        except Exception:
            pass

    @staticmethod
    def get_library_by_id(db_type, library_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM libraries WHERE id = ?", (library_id,))
            row = cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def check_duplicate_name(db_type, name):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM libraries WHERE name = ?", (name,))
            row = cursor.fetchone()
        return row['id'] if row else None

    @staticmethod
    def insert_library_raw(db_type, name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote=None, gdrive_view_local_mirror_path=None, cover_aspect_ratio='4:3', hide_title=0):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO libraries
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title)
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
    def prepare_library_transfer(from_type, to_type, library_id, lib_row):
        """1단계. 대상 카테고리 id를 돌려준다."""
        conn_src = database.get_connection(from_type)
        conn_dst = database.get_connection(to_type)
        cursor_src = conn_src.cursor()
        cursor_dst = conn_dst.cursor()
        columns_cache = {}
        target_id = None
        try:
            # group_id는 원본 DB의 그룹 번호라 대상 DB에서는 엉뚱한 그룹(또는 없는 그룹)을 가리킨다 - 미분류로 옮긴다.
            target_id = _dynamic_insert(cursor_dst, 'libraries', lib_row,
                                        overrides={'group_id': None, 'pending_delete': 3, 'transfer_target_id': None,
                                                   'scan_status': 'ready'},
                                        cache=columns_cache)
            cursor_src.execute("SELECT * FROM user_category_permissions WHERE library_id = ?", (library_id,))
            for row in cursor_src.fetchall():
                _dynamic_insert(cursor_dst, 'user_category_permissions', dict(row), overrides={'library_id': target_id}, cache=columns_cache)
            conn_dst.commit()

            cursor_src.execute(
                "UPDATE libraries SET pending_delete = 2, transfer_target_id = ?, name = ? WHERE id = ?",
                (target_id, f"{lib_row['name']} [moving #{library_id}]", library_id)
            )
            try:
                cursor_src.execute("DELETE FROM series_summary WHERE library_id = ?", (library_id,))
            except Exception:
                pass
            cursor_src.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            conn_src.commit()
            return target_id
        except Exception:
            conn_src.rollback()
            conn_dst.rollback()
            if target_id is not None:
                # 대상만 커밋된 채 원본 표시에 실패했다 - 숨긴 대상 카테고리를 치운다
                try:
                    cursor_dst.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (target_id,))
                    cursor_dst.execute("DELETE FROM libraries WHERE id = ? AND pending_delete = 3", (target_id,))
                    conn_dst.commit()
                except Exception:
                    conn_dst.rollback()
            raise
        finally:
            conn_src.close()
            conn_dst.close()

    @staticmethod
    def rollback_library_transfer(from_type, to_type, library_id, target_id):
        """아무 도서도 옮기기 전에 충돌로 멈출 때: 원본을 되살리고 숨긴 대상 카테고리를 지운다."""
        conn_src = database.get_connection(from_type)
        conn_dst = database.get_connection(to_type)
        cursor_src = conn_src.cursor()
        cursor_dst = conn_dst.cursor()
        try:
            cursor_dst.execute("SELECT name FROM libraries WHERE id = ?", (target_id,))
            target = cursor_dst.fetchone()
            cursor_dst.execute("SELECT * FROM user_category_permissions WHERE library_id = ?", (target_id,))
            perms = [dict(row) for row in cursor_dst.fetchall()]
            for row in perms:
                _dynamic_insert(cursor_src, 'user_category_permissions', row, overrides={'library_id': library_id})
            if target:
                cursor_src.execute(
                    "UPDATE libraries SET pending_delete = 0, transfer_target_id = NULL, name = ? WHERE id = ?",
                    (target['name'], library_id)
                )
            else:
                cursor_src.execute("UPDATE libraries SET pending_delete = 0, transfer_target_id = NULL WHERE id = ?", (library_id,))
            conn_src.commit()
            cursor_dst.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (target_id,))
            cursor_dst.execute("DELETE FROM libraries WHERE id = ? AND pending_delete = 3", (target_id,))
            conn_dst.commit()
        except Exception:
            conn_src.rollback()
            conn_dst.rollback()
            raise
        finally:
            conn_src.close()
            conn_dst.close()

    @staticmethod
    def count_transferred_books(to_type, target_id):
        with database.connection(to_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS n FROM books WHERE library_id = ?", (target_id,))
            row = cursor.fetchone()
        return int(row['n'] if row else 0)

    @staticmethod
    def has_active_tts_jobs(db_type, library_id):
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS n FROM tts_pregen_jobs j JOIN books b ON b.id = j.book_id "
                "WHERE b.library_id = ? AND j.status IN ('queued', 'running')",
                (library_id,)
            )
            row = cursor.fetchone()
        return int(row['n'] if row else 0) > 0

    @staticmethod
    def transfer_library_chunk(from_type, to_type, library_id, target_id, batch_size=500):
        """2단계: 원본 도서 batch_size권을 종속 데이터와 함께 대상에 복사·커밋한 뒤 원본에서 지우고 커밋한다.
        (옮긴 권수, 지울 TTS 음성 폴더 rel_dir 목록)을 돌려주며 0이면 남은 게 없다. 대상 커밋 뒤 원본 정리 전에
        끊겨도 다음 호출이 같은 file_path를 알아보고 복사를 건너뛰어 중복이 생기지 않는다."""
        conn_src = database.get_connection(from_type)
        conn_dst = database.get_connection(to_type)
        cursor_src = conn_src.cursor()
        cursor_dst = conn_dst.cursor()
        try:
            cursor_src.execute("SELECT * FROM books WHERE library_id = ? ORDER BY id LIMIT ?", (library_id, batch_size))
            books = [dict(row) for row in cursor_src.fetchall()]
            if not books:
                return 0, []
            id_map = category_data_shared.copy_books_to_target(
                cursor_src, cursor_dst, books, target_id, '?', _table_columns, {}
            )
            conn_dst.commit()

            with database.connection('general') as gconn:
                gcursor = gconn.cursor()
                category_data_shared.retarget_kosync(gcursor, from_type, to_type, id_map, '?')
                gconn.commit()

            old_ids = [int(book['id']) for book in books]
            rel_dirs = category_data_shared.purge_book_dependents(cursor_src, old_ids, '?')
            cursor_src.execute(f"DELETE FROM books WHERE id IN ({','.join(['?'] * len(old_ids))})", old_ids)
            conn_src.commit()
            return len(books), rel_dirs
        except Exception:
            conn_src.rollback()
            conn_dst.rollback()
            raise
        finally:
            conn_src.close()
            conn_dst.close()

    @staticmethod
    def finish_library_transfer(to_type, target_id):
        """3단계: 대상 카테고리를 공개한다(원본 행 정리는 delete_library_finalize)."""
        conn = database.get_connection(to_type)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE libraries SET pending_delete = 0 WHERE id = ? AND pending_delete = 3", (target_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_pending_transfers(db_type):
        """이동 중(pending_delete=2)인 원본 카테고리 [{id, transfer_target_id}] - 워커 시작 시 재등록용."""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, transfer_target_id FROM libraries WHERE pending_delete = 2")
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_libraries_name_and_path(db_type):
        """중복 경로 매핑을 위한 라이브러리 전체의 name, physical_path 조회"""
        with database.connection(db_type) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, physical_path FROM libraries")
            rows = cursor.fetchall()
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
        except Exception as e:
            # 확인을 못 하면 막는다(fail-closed). 예전엔 허용이라 DB 오류 때 권한 없는 카테고리가 열렸다.
            print(f"[CategoryAccess] check failed, denying: db_type={db_type} user_id={user_id} library_id={library_id} error={e}")
            return False
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

    @staticmethod
    def update_schedule_enabled(db_type, library_id, enabled):
        """라이브러리 스케줄 ON/OFF - 크론 표현식 자체는 건드리지 않고 자동 실행 여부만 토글"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE libraries
                SET schedule_enabled = ?
                WHERE id = ?
            """, (1 if enabled else 0, library_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

