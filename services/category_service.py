# -*- coding: utf-8 -*-
import database
from repositories.category_repository import CategoryRepository

class CategoryService:
    @staticmethod
    def get_libraries(db_type, user_id=None, role=None):
        if user_id and role != 'admin':
            rows = CategoryRepository.get_libraries_by_user_permissions(db_type, user_id)
        else:
            rows = CategoryRepository.get_all_libraries(db_type)
            
        return [{
            'id': r['id'], 
            'name': r['name'], 
            'physical_path': r['physical_path'],
            'is_remote': r['is_remote'] or 0,
            'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
            'rclone_rc_url': r['rclone_rc_url'] or '',
            'icon': r['icon'] or 'fa-book',
            'color': r['color'] or '#94a3b8',
            'hide_cover': r['hide_cover'] or 0,
        } for r in rows]

    @staticmethod
    def _clean_physical_path(raw_path):
        if not raw_path: return ""
        lines = [line.strip() for line in str(raw_path).replace('\r', '').split('\n')]
        return '\n'.join([line for line in lines if line])

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 100자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        return CategoryRepository.add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover)

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0):
        # 이름 방어 로직: 양끝 공백 제거, 빈 이름 거부, 최대 25자 제한
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        CategoryRepository.edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover)

    @staticmethod
    def delete_library(db_type, library_id):
        # 관련 리포트 파일 연쇄 영구 소거
        try:
            from utils.report_helper import delete_all_reports
            delete_all_reports(library_id)
        except Exception as e:
            print(f"[CategoryService ERROR] Bulk report file removal failed: {e}")

        CategoryRepository.delete_library(db_type, library_id)

        # 대량 삭제(Delete) 완료 후 물리 공간 회수 및 DB 성능 향상을 위해 백그라운드로 튜닝 구동
        import threading
        t = threading.Thread(target=database.optimize_database, args=(db_type,))
        t.daemon = True
        t.start()

    @staticmethod
    def move_library(from_type, to_type, library_id):
        """한 DB(from_type)의 카테고리를 다른 DB(to_type)로 데이터 무결성을 보존하며 완전히 이전합니다."""
        if from_type == to_type:
            raise ValueError("동일한 라이브러리 타입 간에는 이동할 수 없습니다.")
            
        conn_src = database.get_connection(from_type)
        conn_dst = database.get_connection(to_type)
        
        # Row 팩토리를 일시적으로 살리거나 dict 형태로 편하게 접근하기 위해 cursor 획득
        cursor_src = conn_src.cursor()
        cursor_dst = conn_dst.cursor()
        
        try:
            # 1. 원본 카테고리 정보 조회
            cursor_src.execute("SELECT * FROM libraries WHERE id = ?", (library_id,))
            lib = cursor_src.fetchone()
            if not lib:
                raise ValueError("이전할 원본 카테고리를 찾을 수 없습니다.")
                
            # [제약 조건] 스캔 상태 검증: 현재 카테고리가 스캔 중인 경우 이전 차단
            if lib["scan_status"] == "scanning":
                raise ValueError("현재 카테고리가 백그라운드 스캔 중입니다. 스캔이 완료된 후 다시 시도해 주세요.")
                
            # [제약 조건] 스캐너 큐 상태 검증: 현재 카테고리 스캔 작업이 실행/대기 중인 경우 이전 차단
            from services.scanner_queue import scanner_queue
            q_status = scanner_queue.get_queue_status()
            running = q_status.get('running')
            if running and running.get('type') in ('library_scan', 'cover_scan'):
                kwargs = running.get('kwargs', {})
                if kwargs.get('db_type') == from_type and int(kwargs.get('library_id', 0)) == int(library_id):
                    raise ValueError("현재 카테고리에 대한 백그라운드 스캔이 진행 중입니다. 완료 후 다시 시도해 주세요.")
                    
            for item in q_status.get('pending', []):
                if item.get('type') in ('library_scan', 'cover_scan'):
                    kwargs = item.get('kwargs', {})
                    if kwargs.get('db_type') == from_type and int(kwargs.get('library_id', 0)) == int(library_id):
                        raise ValueError("현재 카테고리에 대한 스캔 작업이 큐에서 대기 중입니다. 완료 후 다시 시도해 주세요.")
                        
            # 2. 목적지 DB의 카테고리명 중복 검증
            cursor_dst.execute("SELECT id FROM libraries WHERE name = ?", (lib["name"],))
            if cursor_dst.fetchone():
                raise ValueError(f"이동하려는 대상에 이미 동일한 이름('{lib['name']}')의 카테고리가 존재합니다.")
                
            # 3. 목적지 DB에 카테고리 삽입
            cursor_dst.execute(
                """INSERT INTO libraries 
                         (name, physical_path, cron_schedule, last_scanned_at, scan_status, is_remote, vfs_refresh_before_scan, rclone_rc_url, icon, color, hide_cover) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (lib["name"], lib["physical_path"], lib["cron_schedule"], lib["last_scanned_at"], lib["scan_status"], 
                      lib["is_remote"], lib["vfs_refresh_before_scan"], lib["rclone_rc_url"], lib["icon"], lib["color"], lib["hide_cover"])
            )
            new_lib_id = cursor_dst.lastrowid
            
            # 4. 소스 DB에서 해당 카테고리의 모든 도서(books) 목록 조회
            cursor_src.execute("SELECT * FROM books WHERE library_id = ?", (library_id,))
            books = cursor_src.fetchall()
            
            book_id_map = {}
            for book in books:
                old_book_id = book["id"]
                # 5. 목적지 DB에 도서 삽입
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
                
                # 6. 진척도(user_progress) 복제
                cursor_src.execute("SELECT * FROM user_progress WHERE book_id = ?", (old_book_id,))
                progs = cursor_src.fetchall()
                for p in progs:
                    cursor_dst.execute(
                        "INSERT INTO user_progress (book_id, user_id, pages_read, is_completed, last_read_at) VALUES (?, ?, ?, ?, ?)",
                        (new_book_id, p["user_id"], p["pages_read"], p["is_completed"], p["last_read_at"])
                    )
                    
                # 7. 독서 일일 로그(user_reading_log) 복제
                cursor_src.execute("SELECT * FROM user_reading_log WHERE book_id = ?", (old_book_id,))
                logs = cursor_src.fetchall()
                for l in logs:
                    cursor_dst.execute(
                        "INSERT INTO user_reading_log (book_id, user_id, pages_read_delta, duration_seconds, read_date) VALUES (?, ?, ?, ?, ?)",
                        (new_book_id, l["user_id"], l["pages_read_delta"], l["duration_seconds"], l["read_date"])
                    )
                    
                # 8. 압축파일 오프셋(book_offsets) 복제
                cursor_src.execute("SELECT * FROM book_offsets WHERE book_id = ?", (old_book_id,))
                offsets = cursor_src.fetchall()
                for o in offsets:
                    cursor_dst.execute(
                        "INSERT INTO book_offsets (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (new_book_id, o["page_idx"], o["filename"], o["local_header_offset"], o["compress_size"], o["file_size"], o["compress_type"])
                    )
            
            # 9. 사용자별 카테고리 권한(user_category_permissions) 복제
            cursor_src.execute("SELECT * FROM user_category_permissions WHERE library_id = ?", (library_id,))
            perms = cursor_src.fetchall()
            for perm in perms:
                cursor_dst.execute(
                    "INSERT INTO user_category_permissions (user_id, library_id, has_access) VALUES (?, ?, ?)",
                    (perm["user_id"], new_lib_id, perm["has_access"])
                )
                
            # 10. 소스 DB에서 해당 데이터들 역순 소거
            for old_book_id in book_id_map.keys():
                cursor_src.execute("DELETE FROM book_offsets WHERE book_id = ?", (old_book_id,))
                cursor_src.execute("DELETE FROM user_progress WHERE book_id = ?", (old_book_id,))
                cursor_src.execute("DELETE FROM user_reading_log WHERE book_id = ?", (old_book_id,))
                
            cursor_src.execute("DELETE FROM books WHERE library_id = ?", (library_id,))
            cursor_src.execute("DELETE FROM user_category_permissions WHERE library_id = ?", (library_id,))
            cursor_src.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
            
            # 11. 양쪽 트랜잭션 커밋 완료
            conn_dst.commit()
            conn_src.commit()
            
            # 12. 이관 후 구 DB의 디스크 공간 회수를 위해 백그라운드로 튜닝 구동
            import threading
            t = threading.Thread(target=database.optimize_database, args=(from_type,))
            t.daemon = True
            t.start()
            
            return True
        except Exception as e:
            conn_dst.rollback()
            conn_src.rollback()
            raise e
        finally:
            try: conn_src.close()
            except: pass
            try: conn_dst.close()
            except: pass

    @staticmethod
    def check_duplicate_path_warnings():
        """일반도서와 성인도서의 카테고리 경로들을 전수 조사하여 중복된 물리 경로가 존재하는 경우 경고 문자열 목록을 반환합니다."""
        warnings = []
        conn_gen = None
        conn_ad = None
        try:
            import database
            conn_gen = database.get_connection('general')
            conn_ad = database.get_connection('adult')
            
            cur_gen = conn_gen.cursor()
            cur_ad = conn_ad.cursor()
            
            cur_gen.execute("SELECT name, physical_path FROM libraries")
            libs_gen = cur_gen.fetchall()
            
            cur_ad.execute("SELECT name, physical_path FROM libraries")
            libs_ad = cur_ad.fetchall()
            
            # 경로 파싱 도우미 (윈도우/리눅스 경로 표준화 및 소문자 정렬)
            def parse_paths(raw_path):
                if not raw_path: return []
                return [line.strip().replace('\\', '/').lower().rstrip('/') for line in str(raw_path).replace('\r', '').split('\n') if line.strip()]
                
            path_map_gen = {}
            for lib in libs_gen:
                paths = parse_paths(lib["physical_path"])
                for p in paths:
                    if p:
                        path_map_gen[p] = lib["name"]
                        
            for lib in libs_ad:
                paths = parse_paths(lib["physical_path"])
                for p in paths:
                    if p and p in path_map_gen:
                        gen_name = path_map_gen[p]
                        warnings.append(
                            f"등록한 카테고리에 중복된 경로가 (일반/성인) 카테고리에 존재합니다. 검토해주세요. "
                            f"(일반도서 {gen_name} 카테고리 | 성인도서 {lib['name']} 카테고리 중복)"
                        )
        except Exception as e:
            print(f"[Warning Check ERROR] Failed to check duplicate paths: {e}")
        finally:
            if conn_gen:
                try: conn_gen.close()
                except: pass
            if conn_ad:
                try: conn_ad.close()
                except: pass
            
        return warnings

