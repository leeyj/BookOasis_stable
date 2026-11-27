# -*- coding: utf-8 -*-
import re
import database
from repositories.category_repository import CategoryRepository
from tools.scanner.series_cover_fill import WEBTOON_LIBRARY_KIND


def _remove_tts_audio_dirs(db_type, rel_dirs):
    """카테고리 삭제·이동으로 지운 도서의 미리 만든 TTS 음성 폴더를 지운다(행은 이미 커밋됨, 다시 만들 수 있는 캐시)."""
    if not rel_dirs:
        return
    try:
        from services.tts_pregen_service import _remove_book_dir
        for rel_dir in rel_dirs:
            _remove_book_dir(db_type, rel_dir)
    except Exception as e:
        print(f"[CategoryService ERROR] TTS audio folder cleanup failed ({db_type}): {e}")


# Book DBs whose covers share covers/<library_id>/ (ids are numbered per DB, so the same id can exist in both).
BOOK_COVER_DB_TYPES = ('general', 'adult')


def _remove_unused_book_covers(db_type, library_id, started_at):
    """After a book category is deleted, remove the files in covers/<library_id>/ that no row still uses.
    The folder is not removed wholesale: the other book DB may have a category with the same id, and moved
    categories keep their old paths. Files newer than started_at are kept (a scan may be writing them now).
    If either DB can't be checked, nothing is removed. Returns (removed, kept)."""
    import os
    if db_type not in BOOK_COVER_DB_TYPES:
        return 0, 0
    from services.cover_storage_service import get_covers_dir
    folder = os.path.join(get_covers_dir(), str(int(library_id)))
    if not os.path.isdir(folder):
        return 0, 0
    prefix = f'{int(library_id)}/'
    in_use = set()
    for other in BOOK_COVER_DB_TYPES:
        in_use |= {p[len(prefix):] for p in CategoryRepository.get_cover_paths_with_prefix(other, prefix)}
    removed = kept = 0
    for entry in os.scandir(folder):
        if not entry.is_file(follow_symlinks=False):
            kept += 1
            continue
        if entry.name in in_use or entry.stat(follow_symlinks=False).st_mtime >= started_at:
            kept += 1
            continue
        try:
            os.remove(entry.path)
            removed += 1
        except OSError as e:
            kept += 1
            print(f"[CategoryService] cover file cleanup failed ({entry.path}): {e}")
    if not kept:
        try:
            os.rmdir(folder)
        except OSError:
            pass
    return removed, kept


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


UNSPECIFIED_LIBRARY_KIND = 'unspecified'
LIBRARY_KIND_CODE_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,23}$')
MAX_LIBRARY_KIND_NAME_LENGTH = 25
MUSIC_LIBRARY_KIND = 'music'
COVER_ASPECT_RATIOS = ('4:3', '16:9', '1:1')


class CategoryService:
    @staticmethod
    def get_library_kinds(db_type):
        return CategoryRepository.get_library_kinds(db_type)

    @staticmethod
    def is_music_library(library_id):
        """오디오북 세션 카테고리 중 속성이 '음악'인지. 음악 모드(폴더=앨범, 곡 태그 표시, 진행 저장 없음)의 단일 판단식."""
        if not library_id:
            return False
        try:
            lib = CategoryRepository.get_library_by_id('audiobook', int(library_id))
        except Exception:
            return False
        return bool(lib) and str(lib.get('content_kind') or '').strip().lower() == MUSIC_LIBRARY_KIND

    @staticmethod
    def _clean_library_kind_name(name):
        clean_name = str(name or '').strip()
        if not clean_name:
            raise ValueError('속성 이름은 비워둘 수 없습니다.')
        if len(clean_name) > MAX_LIBRARY_KIND_NAME_LENGTH:
            raise ValueError(f'속성 이름은 {MAX_LIBRARY_KIND_NAME_LENGTH}자를 초과할 수 없습니다.')
        return clean_name

    @staticmethod
    def add_library_kind(db_type, code, name):
        clean_code = str(code or '').strip().lower()
        if not LIBRARY_KIND_CODE_PATTERN.match(clean_code) or clean_code == UNSPECIFIED_LIBRARY_KIND:
            raise ValueError('속성 코드는 영문 소문자로 시작하는 소문자·숫자·-·_ 조합 24자 이내여야 합니다(예: webtoon).')
        clean_name = CategoryService._clean_library_kind_name(name)
        existing = CategoryRepository.get_library_kinds(db_type)
        if any(kind['code'] == clean_code for kind in existing):
            raise ValueError('같은 코드의 속성이 이미 있습니다.')
        if any(kind['name'] == clean_name for kind in existing):
            raise ValueError('같은 이름의 속성이 이미 있습니다.')
        CategoryRepository.add_library_kind(db_type, clean_code, clean_name)
        return clean_code

    @staticmethod
    def edit_library_kind(db_type, code, name):
        clean_code = str(code or '').strip().lower()
        clean_name = CategoryService._clean_library_kind_name(name)
        existing = CategoryRepository.get_library_kinds(db_type)
        if any(kind['name'] == clean_name and kind['code'] != clean_code for kind in existing):
            raise ValueError('같은 이름의 속성이 이미 있습니다.')
        CategoryRepository.edit_library_kind(db_type, clean_code, clean_name)

    @staticmethod
    def delete_library_kind(db_type, code):
        CategoryRepository.delete_library_kind(db_type, str(code or '').strip().lower())

    @staticmethod
    def ensure_library_kind(db_type, code, name=None):
        """다른 DB로 카테고리를 옮기거나 가져올 때, 그 DB의 속성 목록에 없는 코드를 사용자 정의 속성으로 만들어
        속성이 조용히 사라지지 않게 한다. 코드 형식이 올바르지 않으면 '미지정'으로 돌려 보낸다."""
        clean_code = str(code or '').strip().lower()
        if clean_code in ('', UNSPECIFIED_LIBRARY_KIND) or not LIBRARY_KIND_CODE_PATTERN.match(clean_code):
            return UNSPECIFIED_LIBRARY_KIND
        existing = CategoryRepository.get_library_kinds(db_type)
        if any(kind['code'] == clean_code for kind in existing):
            return clean_code
        base_name = str(name or '').strip()[:MAX_LIBRARY_KIND_NAME_LENGTH] or clean_code
        used_names = {kind['name'] for kind in existing}
        unique_name = base_name
        if unique_name in used_names:
            unique_name = f"{base_name[:MAX_LIBRARY_KIND_NAME_LENGTH - len(clean_code) - 3]} ({clean_code})"
        CategoryRepository.add_library_kind(db_type, clean_code, unique_name)
        return clean_code

    @staticmethod
    def _normalize_content_kind(db_type, content_kind, keep_when_missing=False):
        """라이브러리에 저장할 속성 코드를 검증한다. None이면(keep_when_missing) 기존 값 유지를 뜻하는 None을 그대로
        돌려주고, 빈 값/'unspecified'는 '미지정'으로, 그 외에는 이 세션의 속성 목록에 있는 코드여야 한다."""
        if content_kind is None:
            return None if keep_when_missing else UNSPECIFIED_LIBRARY_KIND
        value = str(content_kind).strip().lower()
        if value in ('', UNSPECIFIED_LIBRARY_KIND):
            return UNSPECIFIED_LIBRARY_KIND
        if not any(kind['code'] == value for kind in CategoryRepository.get_library_kinds(db_type)):
            raise ValueError(f"알 수 없는 속성입니다: {value}")
        return value

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
    def move_library_groups(db_type, items):
        if not isinstance(items, list) or not items:
            raise ValueError('이동할 그룹 정보가 없습니다.')

        existing_ids = {int(group['id']) for group in CategoryRepository.get_library_groups(db_type)}
        normalized = []
        seen_ids = set()
        for sort_order, item in enumerate(items, start=1):
            try:
                group_id = int(item.get('id'))
            except (AttributeError, TypeError, ValueError):
                raise ValueError('올바르지 않은 그룹입니다.')
            if group_id not in existing_ids or group_id in seen_ids:
                raise ValueError('그룹 이동 정보가 올바르지 않습니다.')
            normalized.append({'id': group_id, 'sort_order': sort_order})
            seen_ids.add(group_id)

        if seen_ids != existing_ids:
            raise ValueError('모든 그룹의 이동 정보가 필요합니다.')
        CategoryRepository.move_library_groups(db_type, normalized)

    @staticmethod
    def get_plugin_group_assignments(db_type):
        rows = CategoryRepository.get_plugin_group_assignments(db_type)
        return {row['plugin_id']: row['group_id'] for row in rows}

    @staticmethod
    def assign_plugin_groups(db_type, items):
        if not isinstance(items, list) or not items:
            raise ValueError('이동할 플러그인 정보가 없습니다.')

        valid_group_ids = {int(group['id']) for group in CategoryRepository.get_library_groups(db_type)}
        normalized = []
        seen_ids = set()
        group_positions = {}
        for item in items:
            plugin_id = str(item.get('plugin_id') or '').strip()
            if not plugin_id or plugin_id in seen_ids:
                raise ValueError('올바르지 않은 플러그인입니다.')
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
            normalized.append({'plugin_id': plugin_id, 'group_id': group_id, 'sort_order': sort_order})
            seen_ids.add(plugin_id)

        CategoryRepository.assign_plugin_groups(db_type, normalized)

    @staticmethod
    def get_libraries(db_type, user_id=None, role=None):
        if user_id and role != 'admin':
            rows = CategoryRepository.get_libraries_by_user_permissions(db_type, user_id)
        else:
            rows = CategoryRepository.get_all_libraries(db_type)

        from services.series_service import SeriesService
        totals_by_library = SeriesService.get_library_totals_bulk(db_type)
        kind_names = {kind['code']: kind['name'] for kind in CategoryRepository.get_library_kinds(db_type)}

        return [{
            'id': r['id'],
            'name': r['name'],
            'physical_path': r['physical_path'],
            'series_count': totals_by_library.get(int(r['id']), {}).get('series_count', 0),
            'book_count': totals_by_library.get(int(r['id']), {}).get('book_count', 0),
            'is_remote': r['is_remote'] or 0,
            'vfs_refresh_before_scan': r['vfs_refresh_before_scan'] or 0,
            'rclone_rc_url': r['rclone_rc_url'] or '',
            'icon': r['icon'] or 'fa-book',
            'color': r['color'] or '#94a3b8',
            'hide_cover': r['hide_cover'] or 0,
            'hide_title': r.get('hide_title') or 0,
            'cover_aspect_ratio': r.get('cover_aspect_ratio') or '4:3',
            'content_kind': r.get('content_kind') or UNSPECIFIED_LIBRARY_KIND,
            'content_kind_name': kind_names.get(r.get('content_kind') or UNSPECIFIED_LIBRARY_KIND, ''),
            'group_id': r.get('group_id'),
            'sort_order': r.get('sort_order') or 0,
            'gdrive_copy_remote': r.get('gdrive_copy_remote') or '',
            'gdrive_view_local_mirror_path': r.get('gdrive_view_local_mirror_path') or '',
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
    def _normalize_cover_aspect_ratio(cover_aspect_ratio):
        """카테고리 그리드 커버 비율. 임의 커스텀 비율은 지원하지 않고 정해진 값(기본/와이드/정사각)만 허용한다."""
        value = str(cover_aspect_ratio or '4:3').strip()
        return value if value in COVER_ASPECT_RATIOS else '4:3'

    @staticmethod
    def _validate_link_remote(remote_name):
        """링크 카테고리 연결 계정 검증(화면 목록과 같은 기준을 서버에서도 적용 - API로 이름을 직접 넣는 경우 대비).
        읽기 전용 리모트도 허용하지만, root_folder_id를 무시하는 리모트는 링크 폴더 대신 드라이브 전체를 스캔하게
        되므로 막는다. rclone 설정을 읽지 못하면(바이너리 없음 등) 검증을 건너뛴다 - 스캔 때 목록 실패로 드러난다."""
        from utils.rclone_gdrive_copy import list_link_category_remotes, remote_ignores_root_folder_id
        remotes = {r['name']: r for r in list_link_category_remotes()}
        if not remotes:
            return
        info = remotes.get(remote_name)
        if not info:
            raise ValueError(f"연결할 리모트 '{remote_name}'를 찾을 수 없거나 구글 드라이브 읽기 권한(drive, drive.readonly)이 없습니다.")
        if not info.get('usable'):
            raise ValueError(f"리모트 '{remote_name}'는 링크 카테고리에 쓸 수 없습니다: {info.get('reason')}")
        if remote_ignores_root_folder_id(remote_name):
            raise ValueError(f"리모트 '{remote_name}'는 폴더 링크 지정(root_folder_id)을 무시하고 드라이브 전체를 보여 주므로 링크 카테고리에 쓸 수 없습니다.")

    @staticmethod
    def _validate_gdrive_requirements(physical_path, gdrive_copy_remote, gdrive_view_local_mirror_path):
        """공유 링크가 포함된 카테고리는 책을 열 때마다 그 1권만 개인 드라이브로
        복사해 보여주는 뷰어 전용 용도로만 쓰인다 — 폴더 전체를 미리 복사해두는
        일괄 복사는 카테고리와 무관한 별개 동작으로 분리됐다(gdrive_copy_service.py,
        환경설정 쪽 "Drive에서 복사해오기"). 그래서 카테고리 저장 시점엔 리모트와,
        책을 서빙할 때 필요한 로컬 마운트 루트만 확보돼 있으면 된다 — 마운트 루트를
        열람 때마다 실시간으로 알아낼 방법이 없어(로컬 디스크 경로를 읽어 서빙해야 함)
        여기서 반드시 막아야 한다."""
        from utils.drive_helper import has_gdrive_share_line, gdrive_link_beta_enabled
        if not has_gdrive_share_line(physical_path):
            return
        if not gdrive_link_beta_enabled():
            # 화면에서만 숨기면 API로 직접 저장할 수 있으므로 서버에서도 막는다.
            raise ValueError('구글 드라이브 공유 링크 카테고리는 클로즈 베타 기능입니다. 서버 .env에 GDRIVE_LINK_BETA=true를 설정해야 사용할 수 있습니다.')
        if not gdrive_copy_remote:
            raise ValueError('구글 드라이브 공유 링크가 포함된 카테고리는 연결할 리모트를 반드시 선택해야 합니다. 개인 rclone Drive 리모트 없이는 사용할 수 없습니다.')
        CategoryService._validate_link_remote(gdrive_copy_remote)
        # 로컬 마운트 루트는 더 이상 필수가 아니다 — 뷰어 사본은 리모트로 서버 로컬 캐시에 직접 받는다
        # (gdrive_view_copy_service.py). 입력된 값은 그대로 저장만 한다.

    @staticmethod
    def add_library(db_type, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0, group_id=None, gdrive_copy_remote=None, gdrive_view_local_mirror_path=None, cover_aspect_ratio='4:3', hide_title=0, content_kind=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        CategoryService._validate_gdrive_requirements(physical_path, gdrive_copy_remote, gdrive_view_local_mirror_path)
        physical_path = CategoryService._clean_physical_path(physical_path)
        group_id = CategoryService._normalize_group_id(db_type, group_id)
        cover_aspect_ratio = CategoryService._normalize_cover_aspect_ratio(cover_aspect_ratio)
        content_kind = CategoryService._normalize_content_kind(db_type, content_kind)
        return CategoryRepository.add_library(db_type, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title, content_kind)

    @staticmethod
    def edit_library(db_type, library_id, name, physical_path, is_remote=0, rclone_rc_url=None, icon='fa-book', color='#94a3b8', hide_cover=0, group_id=None, gdrive_copy_remote=None, gdrive_view_local_mirror_path=None, cover_aspect_ratio='4:3', hide_title=0, content_kind=None):
        name = str(name or '').strip()
        if not name:
            raise ValueError('카테고리 이름은 비워둘 수 없습니다.')
        if len(name) > 25:
            raise ValueError('카테고리 이름은 25자를 초과할 수 없습니다.')
        current = CategoryRepository.get_library_by_id(db_type, library_id)
        if current and int(current.get('pending_delete') or 0):
            raise ValueError("삭제가 진행 중인 카테고리는 수정할 수 없습니다.")
        CategoryService._validate_gdrive_requirements(physical_path, gdrive_copy_remote, gdrive_view_local_mirror_path)
        physical_path = CategoryService._clean_physical_path(physical_path)
        group_id = CategoryService._normalize_group_id(db_type, group_id)
        cover_aspect_ratio = CategoryService._normalize_cover_aspect_ratio(cover_aspect_ratio)
        # content_kind를 넘기지 않으면(None) 기존 속성을 유지한다.
        content_kind = CategoryService._normalize_content_kind(db_type, content_kind, keep_when_missing=True)
        CategoryRepository.edit_library(db_type, library_id, name, physical_path, is_remote, rclone_rc_url, icon, color, hide_cover, group_id, gdrive_copy_remote, gdrive_view_local_mirror_path, cover_aspect_ratio, hide_title, content_kind)
        if content_kind == WEBTOON_LIBRARY_KIND and (current or {}).get('content_kind') != WEBTOON_LIBRARY_KIND:
            CategoryService._fill_webtoon_episode_covers(db_type, library_id)

    @staticmethod
    def _fill_webtoon_episode_covers(db_type, library_id):
        """웹툰 속성으로 바꾸면 재스캔 없이 표지가 빈 회차에 같은 폴더의 대표 표지를 바로 넣는다(DB만, 파일 안 받음)."""
        try:
            from tools.scanner.series_cover_fill import fill_missing_series_covers
            with database.connection(db_type) as conn:
                filled = fill_missing_series_covers(conn.cursor(), library_id)
                conn.commit()
            if filled:
                from services.series_service import SeriesService
                SeriesService.invalidate_all_books_cache(db_type=db_type)
        except Exception as e:
            print(f"[Category] Webtoon episode cover fill skipped (library {library_id}): {e}")

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

        if int(lib.get('pending_delete') or 0):
            raise ValueError("이미 삭제가 진행 중인 카테고리입니다.")

        # 요청 안에서는 표시만 하고 바로 응답한다 - 도서 수에 비례하는 실제 삭제는 스캐너 큐(library_delete)가
        # 나눠 커밋한다. 2026-10-20 커뮤니티 제보: 요청 안에서 전부 지우다 리버스 프록시 60초 타임아웃(504).
        import time
        t_start = time.perf_counter()
        CategoryRepository.mark_library_pending_delete(db_type, library_id)

        try:
            from utils.report_helper import delete_all_reports
            delete_all_reports(library_id, db_type)
        except Exception as e:
            print(f"[CategoryService ERROR] Bulk report file removal failed: {e}")

        try:
            from services.series_service import SeriesService
            SeriesService.invalidate_all_books_cache()
        except Exception as e:
            print(f"[CategoryService ERROR] Books cache invalidation after delete failed: {e}")

        # 등록에 실패해도 카테고리는 숨겨진 채 남고, 워커가 시작할 때 pending_delete 카테고리를 다시 등록한다.
        queued = scanner_queue.enqueue('library_delete', db_type=db_type, library_id=int(library_id))
        print(f"[PERF-PROFILE] delete_library(type={db_type}, lib={library_id}) REQUEST: "
              f"{(time.perf_counter() - t_start) * 1000:.1f}ms | queued={queued}")
        return queued

    @staticmethod
    def run_library_delete_job(db_type, library_id, report_stage=None):
        """스캐너 큐 작업(library_delete): pending_delete로 표시된 카테고리의 데이터를 나눠 지운다.
        중간에 워커가 재시작되면 큐가 작업을 다시 pending으로 돌리고, 남은 것부터 이어서 지운다."""
        import time
        lib = CategoryRepository.get_library_by_id(db_type, library_id)
        if not lib:
            return {'deleted': 0}
        if not int(lib.get('pending_delete') or 0):
            # 표시 없이 들어온 작업으로 카테고리를 지우지 않는다(잘못 등록된 작업 방어).
            raise ValueError(f"카테고리 {library_id}는 삭제 대기 상태가 아닙니다.")

        t_start = time.perf_counter()
        started_at = time.time()
        deleted = 0
        chunks = 0
        while True:
            n, rel_dirs, _book_ids = CategoryRepository.delete_library_chunk(db_type, library_id)
            _remove_tts_audio_dirs(db_type, rel_dirs)
            if not n:
                break
            deleted += n
            chunks += 1
            if report_stage:
                report_stage(f'카테고리 삭제 중 · {deleted:,}개 정리')
        t_chunks = time.perf_counter()

        CategoryRepository.delete_library_finalize(db_type, library_id)
        try:
            # gdrive 링크 카테고리의 메타데이터 미러(스캔 캐시)와 뷰어 사본, 포스터 썸네일도 같이 치운다 — 원본과 무관한 로컬 캐시.
            import shutil
            from utils.drive_helper import gdrive_meta_mirror_dir
            shutil.rmtree(gdrive_meta_mirror_dir(db_type, library_id), ignore_errors=True)
            from services.gdrive_view_copy_service import view_cache_root
            shutil.rmtree(view_cache_root(db_type, library_id), ignore_errors=True)
            # Poster thumbnails (covers/audio|video/<library_id>) are derived from the category's sources too.
            from utils.cover_helper import poster_cache_library_dir
            poster_dir = poster_cache_library_dir(db_type, library_id)
            if poster_dir:
                shutil.rmtree(poster_dir, ignore_errors=True)
        except Exception as e:
            print(f"[CategoryService] gdrive metadata mirror cleanup failed (lib={library_id}): {e}")
        try:
            removed, kept = _remove_unused_book_covers(db_type, library_id, started_at)
            if removed or kept:
                print(f"[CategoryService] book cover cleanup (type={db_type}, lib={library_id}): removed={removed} kept={kept}")
        except Exception as e:
            print(f"[CategoryService] book cover cleanup skipped (type={db_type}, lib={library_id}): {e}")
        from services.problem_service import ProblemService
        ProblemService.on_library_deleted(db_type, library_id)
        try:
            from utils.redis_helper import redis_del
            redis_del(f"status:scan:stage:library_scan_{db_type}_{library_id}")
        except Exception:
            pass
        t_final = time.perf_counter()
        print(f"[PERF-PROFILE] library_delete(type={db_type}, lib={library_id}) TOTAL: {(t_final - t_start) * 1000:.1f}ms "
              f"| Chunks({chunks}, {deleted} rows): {(t_chunks - t_start) * 1000:.1f}ms | Finalize: {(t_final - t_chunks) * 1000:.1f}ms")

        try:
            database.optimize_database(db_type)
        except Exception as e:
            print(f"[CategoryService ERROR] Optimize after library delete failed: {e}")
        return {'deleted': deleted}

    @staticmethod
    def move_library(from_type, to_type, library_id):
        """한 DB(from_type)의 카테고리를 다른 DB(to_type)로 데이터 무결성을 보존하며 완전히 이전합니다."""
        if from_type == to_type:
            raise ValueError("동일한 라이브러리 타입 간에는 이동할 수 없습니다.")
            
        # 1. 원본 카테고리 정보 조회
        lib = CategoryRepository.get_library_by_id(from_type, library_id)
        if not lib:
            raise ValueError("이전할 원본 카테고리를 찾을 수 없습니다.")
        if int(lib.get('pending_delete') or 0):
            raise ValueError("삭제나 이동이 진행 중인 카테고리는 이전할 수 없습니다.")

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
            
        # 2-1. 카테고리 속성: 대상 DB의 속성 목록에 없는 코드는 같은 이름의 사용자 정의 속성으로 만들어 둔다
        # (트랜잭션이 libraries 행을 통째로 복사하므로 content_kind 코드가 그대로 따라간다).
        source_kind = lib.get('content_kind') or UNSPECIFIED_LIBRARY_KIND
        if source_kind != UNSPECIFIED_LIBRARY_KIND:
            source_names = {kind['code']: kind['name'] for kind in CategoryRepository.get_library_kinds(from_type)}
            lib['content_kind'] = CategoryService.ensure_library_kind(to_type, source_kind, source_names.get(source_kind))

        if CategoryRepository.has_active_tts_jobs(from_type, library_id):
            raise ValueError("이 카테고리 도서의 TTS 음성을 만드는 중입니다. 생성이 끝나거나 취소한 뒤 다시 시도해 주세요.")

        # 요청 안에서는 대상에 숨긴 카테고리를 만들고 원본을 숨긴 뒤 바로 응답한다 - 도서 수에 비례하는 실제 이관은
        # 스캐너 큐(library_transfer)가 묶음으로 처리한다(2026-10-20: 4만 권 이동이 요청 안에서 169초 → 프록시 504).
        import time
        t_start = time.perf_counter()
        target_id = CategoryRepository.prepare_library_transfer(from_type, to_type, library_id, lib)
        try:
            from services.series_service import SeriesService
            SeriesService.invalidate_all_books_cache()
        except Exception as e:
            print(f"[CategoryService ERROR] Books cache invalidation after transfer start failed: {e}")
        queued = scanner_queue.enqueue('library_transfer', db_type=from_type, from_type=from_type, to_type=to_type,
                                       library_id=int(library_id), target_library_id=int(target_id))
        print(f"[PERF-PROFILE] move_library({from_type}->{to_type}, lib={library_id} -> {target_id}) REQUEST: "
              f"{(time.perf_counter() - t_start) * 1000:.1f}ms | queued={queued}")
        return queued

    @staticmethod
    def run_library_transfer_job(from_type, to_type, library_id, target_library_id, report_stage=None):
        """스캐너 큐 작업(library_transfer): 이동 중(pending_delete=2)인 원본 카테고리의 도서를 대상 카테고리로
        묶음 단위로 옮긴다. 워커가 재시작되면 남은 묶음부터 이어서 옮긴다(이미 대상에 커밋된 권은 건너뜀)."""
        import time
        from repositories.category_data_shared import TransferConflictError
        lib = CategoryRepository.get_library_by_id(from_type, library_id)
        if not lib:
            # 이미 끝났는데 결과 기록 전에 멈춘 경우 - 대상만 공개되면 된다
            CategoryRepository.finish_library_transfer(to_type, target_library_id)
            return {'moved': 0}
        if int(lib.get('pending_delete') or 0) != 2:
            raise ValueError(f"카테고리 {library_id}는 이동 대기 상태가 아닙니다.")

        t_start = time.perf_counter()
        moved = 0
        chunks = 0
        while True:
            try:
                n, rel_dirs = CategoryRepository.transfer_library_chunk(from_type, to_type, library_id, target_library_id)
            except TransferConflictError:
                # 아무것도 옮기지 않은 상태면 원래대로 되돌리고, 일부 옮긴 뒤라면 표시를 그대로 두어 재시도에 맡긴다
                if CategoryRepository.count_transferred_books(to_type, target_library_id) == 0:
                    CategoryRepository.rollback_library_transfer(from_type, to_type, library_id, target_library_id)
                raise
            _remove_tts_audio_dirs(from_type, rel_dirs)
            if not n:
                break
            moved += n
            chunks += 1
            if report_stage:
                report_stage(f'카테고리 이동 중 · {moved:,}권')
        t_chunks = time.perf_counter()

        # 원본에 남은 오디오북·영상(일반·성인 DB에는 보통 없다)과 카테고리 단위 기록을 정리하고 대상을 공개한다
        while True:
            n, rel_dirs, _book_ids = CategoryRepository.delete_library_chunk(from_type, library_id)
            _remove_tts_audio_dirs(from_type, rel_dirs)
            if not n:
                break
        CategoryRepository.delete_library_finalize(from_type, library_id)
        CategoryRepository.finish_library_transfer(to_type, target_library_id)
        # 구 DB 기준으로 남은 문제 기록은 더 이상 가리키는 대상이 없다 (다음 스캔이 새 DB 기준으로 다시 기록).
        from services.problem_service import ProblemService
        ProblemService.on_library_deleted(from_type, library_id)
        t_final = time.perf_counter()
        print(f"[PERF-PROFILE] library_transfer({from_type}->{to_type}, lib={library_id} -> {target_library_id}) "
              f"TOTAL: {(t_final - t_start) * 1000:.1f}ms | Chunks({chunks}, {moved} books): {(t_chunks - t_start) * 1000:.1f}ms "
              f"| Finalize: {(t_final - t_chunks) * 1000:.1f}ms")

        try:
            database.optimize_database(from_type)
        except Exception as e:
            print(f"[CategoryService ERROR] Optimize after library transfer failed: {e}")
        return {'moved': moved}

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
