# -*- coding: utf-8 -*-
import database
from repositories.category_repository import CategoryRepository


def _refresh_series_summaries(*db_types):
    from repositories.series_repository import SeriesRepository
    for db_type in dict.fromkeys(db_types):
        if db_type != 'audiobook':
            SeriesRepository.rebuild_summary(db_type)
    from services.series_service import SeriesService
    SeriesService.invalidate_all_books_cache()


def apply_running_scan_status(libraries, db_type, queue_status):
    """큐에서 실행 중인 스캔을 라이브러리 상태 목록에 우선 반영한다."""
    running = (queue_status or {}).get('running')
    if not running or running.get('type') not in ('library_scan', 'cover_scan'):
        return libraries

    kwargs = running.get('kwargs') or {}
    if str(kwargs.get('db_type', 'general')) != str(db_type):
        return libraries

    try:
        running_library_id = int(kwargs.get('library_id'))
    except (TypeError, ValueError):
        return libraries

    for library in libraries:
        try:
            is_running_library = int(library.get('id')) == running_library_id
        except (TypeError, ValueError):
            is_running_library = False
        if is_running_library:
            library['scan_status'] = 'scanning'
            break

    return libraries


class CategoryService:
    @staticmethod
    def get_library_groups(db_type):
        return CategoryRepository.get_library_groups(db_type)

    @staticmethod
    def add_library_group(db_type, name):
        clean_name = str(name or '').strip()
        if not clean_name:
            raise ValueError('그룹 이름은 비워둘 수 없습니다.')
        if len(clean_name) > 25:
            raise ValueError('그룹 이름은 25자를 초과할 수 없습니다.')
        return CategoryRepository.add_library_group(db_type, clean_name)

    @staticmethod
    def edit_library_group(db_type, group_id, name):
        clean_name = str(name or '').strip()
        if not clean_name:
            raise ValueError('그룹 이름은 비워둘 수 없습니다.')
        if len(clean_name) > 25:
            raise ValueError('그룹 이름은 25자를 초과할 수 없습니다.')
        CategoryRepository.edit_library_group(db_type, group_id, clean_name)

    @staticmethod
    def delete_library_group(db_type, group_id):
        CategoryRepository.delete_library_group(db_type, group_id)

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
            'group_id': r.get('group_id'),
            'sort_order': r.get('sort_order') or 0,
        } for r in rows]

    @staticmethod
    def move_libraries(db_type, items):
        if not isinstance(items, list) or not items:
            raise ValueError('이동할 카테고리 정보가 없습니다.')

        existing_ids = {int(library['id']) for library in CategoryRepository.get_all_libraries(db_type)}
        valid_group_ids = {int(group['id']) for group in CategoryRepository.get_library_groups(db_type)}
        normalized = []
        seen_ids = set()
        group_positions = {}
        for item in items:
            try:
                library_id = int(item.get('id'))
            except (AttributeError, TypeError, ValueError):
                raise ValueError('올바르지 않은 카테고리입니다.')
            if library_id not in existing_ids or library_id in seen_ids:
                raise ValueError('카테고리 이동 정보가 올바르지 않습니다.')
            group_id = item.get('group_id')
            if group_id in (None, '', 'null'):
                group_id = None
            else:
                try:
                    group_id = int(group_id)
                except (TypeError, ValueError):
                    raise ValueError('올바르지 않은 그룹입니다.')
                if group_id not in valid_group_ids:
                    raise ValueError('선택한 그룹을 찾을 수 없습니다.')

            position_key = group_id if group_id is not None else 'ungrouped'
            sort_order = group_positions.get(position_key, 1)
            group_positions[position_key] = sort_order + 1
            normalized.append({'id': library_id, 'group_id': group_id, 'sort_order': sort_order})
            seen_ids.add(library_id)

        if seen_ids != existing_ids:
            raise ValueError('모든 카테고리의 이동 정보가 필요합니다.')
        CategoryRepository.move_libraries(db_type, normalized)

    @staticmethod
    def _normalize_group_id(db_type, group_id):
        if group_id in (None, '', 'null'):
            return None
        try:
            normalized = int(group_id)
        except (TypeError, ValueError):
            raise ValueError('올바르지 않은 그룹입니다.')
        valid_ids = {int(group['id']) for group in CategoryRepository.get_library_groups(db_type)}
        if normalized not in valid_ids:
            raise ValueError('선택한 그룹을 찾을 수 없습니다.')
        return normalized

    @staticmethod
    def _clean_physical_path(raw_path):
        if not raw_path: return ""
        lines = [line.strip() for line in str(raw_path).replace('\r', '').split('\n')]
        return '\n'.join([line for line in lines if line])

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0, group_id=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        group_id = CategoryService._normalize_group_id(db_type, group_id)
        return CategoryRepository.add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id)

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0, group_id=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        physical_path = CategoryService._clean_physical_path(physical_path)
        group_id = CategoryService._normalize_group_id(db_type, group_id)
        CategoryRepository.edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id)

    @staticmethod
    def delete_library(db_type, library_id):
        # 1. 카테고리 정보 및 스캔 상태 검증
        lib = CategoryRepository.get_library_by_id(db_type, library_id)
        if not lib:
            raise ValueError("삭제하려는 카테고리를 찾을 수 없습니다.")

        from services.scanner_queue import scanner_queue
        q_status = scanner_queue.get_queue_status() or {}

        def _is_target_scan_task(task_item):
            if not task_item:
                return False
            if task_item.get('type') not in ('library_scan', 'cover_scan'):
                return False
            kwargs = task_item.get('kwargs', {}) or {}
            try:
                return (
                    kwargs.get('db_type') == db_type and
                    int(kwargs.get('library_id', 0)) == int(library_id)
                )
            except (TypeError, ValueError):
                return False

        running = q_status.get('running')
        has_running_scan = _is_target_scan_task(running)
        has_pending_scan = any(_is_target_scan_task(item) for item in q_status.get('pending', []))
        has_active_scan_task = has_running_scan or has_pending_scan

        # [제약 조건] 스캔 상태 검증: 현재 카테고리가 스캔 중인 경우 삭제 차단
        if lib.get("scan_status") in ("scanning", "cancelling"):
            if has_active_scan_task:
                raise ValueError("현재 카테고리가 스캔 진행 중입니다. 스캔이 완료된 후 삭제해 주세요.")
            # 실제 큐에 활성 작업이 없으면 stale 상태로 판단하여 자동 복구
            try:
                CategoryRepository.update_library_scan_status(db_type, library_id, 'ready')
                lib['scan_status'] = 'ready'
            except Exception:
                # 상태 복구에 실패한 경우에는 보수적으로 삭제를 차단
                raise ValueError("카테고리 스캔 상태 복구에 실패했습니다. 잠시 후 다시 시도해 주세요.")

        # [제약 조건] 스캐너 큐 상태 검증: 현재 카테고리 스캔 작업이 실행/대기 중인 경우 삭제 차단
        if has_running_scan:
            raise ValueError("현재 카테고리에 대한 백그라운드 스캔이 진행 중입니다. 스캔 완료 후 다시 시도해 주세요.")

        if has_pending_scan:
            raise ValueError("현재 카테고리에 대한 스캔 작업이 대기열에 존재합니다. 스캔 완료 또는 취소 후 다시 시도해 주세요.")

        gate_token = None
        try:
            from utils.redis_helper import redis_acquire_lock
            gate_token = redis_acquire_lock(f"lock:db_write:{db_type}", ttl=120, wait_timeout=10.0)
        except Exception:
            gate_token = None

        try:
            try:
                from utils.report_helper import delete_all_reports
                delete_all_reports(library_id)
            except Exception as e:
                print(f"[CategoryService ERROR] Bulk report file removal failed: {e}")

            CategoryRepository.delete_library(db_type, library_id)
            try:
                from utils.redis_helper import redis_del
                redis_del(f"status:scan:stage:library_scan_{db_type}_{library_id}")
            except Exception:
                pass
        finally:
            if gate_token:
                try:
                    from utils.redis_helper import redis_release_lock
                    redis_release_lock(f"lock:db_write:{db_type}", gate_token)
                except Exception:
                    pass

            _refresh_series_summaries(db_type)

        import threading
        t = threading.Thread(target=database.optimize_database, args=(db_type,))
        t.daemon = True
        t.start()

    @staticmethod
    def move_library(from_type, to_type, library_id):
        """한 DB(from_type)의 카테고리를 다른 DB(to_type)로 데이터 무결성을 보존하며 완전히 이전합니다."""
        if from_type == to_type:
            raise ValueError("동일한 라이브러리 타입 간에는 이동할 수 없습니다.")
            
        # 1. 원본 카테고리 정보 조회
        lib = CategoryRepository.get_library_by_id(from_type, library_id)
        if not lib:
            raise ValueError("이전할 원본 카테고리를 찾을 수 없습니다.")
            
        # [제약 조건] 스캐너 큐 상태 검증: 현재 카테고리 스캔 작업이 실행/대기 중인 경우 이전 차단
        from services.scanner_queue import scanner_queue
        q_status = scanner_queue.get_queue_status()

        def _is_target_scan_task(task_item):
            if not task_item:
                return False
            if task_item.get('type') not in ('library_scan', 'cover_scan'):
                return False
            kwargs = task_item.get('kwargs', {}) or {}
            try:
                return (
                    kwargs.get('db_type') == from_type and
                    int(kwargs.get('library_id', 0)) == int(library_id)
                )
            except (TypeError, ValueError):
                return False

        running = q_status.get('running')
        has_running_scan = _is_target_scan_task(running)
        has_pending_scan = any(_is_target_scan_task(item) for item in q_status.get('pending', []))
        has_active_scan_task = has_running_scan or has_pending_scan

        # [제약 조건] 스캔 상태 검증: scan_status가 scanning/cancelling이어도
        # 실제 큐에 활성 작업이 없으면 stale 상태로 보고 자동 복구한다.
        if lib.get("scan_status") in ("scanning", "cancelling"):
            if has_active_scan_task:
                raise ValueError("현재 카테고리가 백그라운드 스캔 중입니다. 스캔이 완료된 후 다시 시도해 주세요.")
            try:
                CategoryRepository.update_library_scan_status(from_type, library_id, 'ready')
                lib['scan_status'] = 'ready'
            except Exception:
                raise ValueError("카테고리 스캔 상태 복구에 실패했습니다. 잠시 후 다시 시도해 주세요.")

        if has_running_scan:
            raise ValueError("현재 카테고리에 대한 백그라운드 스캔이 진행 중입니다. 완료 후 다시 시도해 주세요.")

        if has_pending_scan:
            raise ValueError("현재 카테고리에 대한 스캔 작업이 큐에서 대기 중입니다. 완료 후 다시 시도해 주세요.")
                    
        # 2. 목적지 DB의 카테고리명 중복 검증
        if CategoryRepository.check_duplicate_name(to_type, lib["name"]):
            raise ValueError(f"이동하려는 대상에 이미 동일한 이름('{lib['name']}')의 카테고리가 존재합니다.")
            
        # 3. 이관을 위한 소스 DB 도서 데이터 수집
        books = CategoryRepository.get_books_by_library_raw(from_type, library_id)
        
        # 4. 트랜잭션 수행
        CategoryRepository.move_library_transaction(from_type, to_type, library_id, lib["name"], lib, books)
        _refresh_series_summaries(from_type, to_type)
        
        # 5. 이관 후 구 DB의 디스크 공간 회수를 위해 백그라운드로 튜닝 구동
        import threading
        t = threading.Thread(target=database.optimize_database, args=(from_type,))
        t.daemon = True
        t.start()
        
        return True

    @staticmethod
    def check_duplicate_path_warnings():
        """일반도서와 성인도서의 카테고리 경로들을 전수 조사하여 중복된 물리 경로가 존재하는 경우 경고 문자열 목록을 반환합니다."""
        warnings = []
        try:
            libs_gen = CategoryRepository.get_libraries_name_and_path('general')
            libs_ad = CategoryRepository.get_libraries_name_and_path('adult')
            
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
            
        return warnings
