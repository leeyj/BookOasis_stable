# -*- coding: utf-8 -*-
"""
gdrive_view_copy_service.py – gdrive 공유 카테고리 책을 "열 때" 그 책 한 권만 서버사이드로
관리자 자신의 드라이브에 복사(files.copy)해 로컬 rclone 마운트 경로로 바꿔치기한다.

기존 gdrive:// 가상 경로 Range/전체다운로드 스트리밍(utils/drive_helper.py)은 공용
GDRIVE_API_KEY를 쓰기 때문에, 여러 명이 동시에 여러 책을 열면 그만큼 Range 요청이
겹쳐 Google의 "automated queries" 403 차단을 다시 유발할 위험이 있다. 한 번 복사해두면
그 뒤로는 완전히 평범한 로컬 파일이라 이 위험 자체가 사라진다 (책 단위, 열 때 1회).

파일 하나가 처음 열릴 때만 복사가 발생하고, 그 사이 같은 책에 대한 동시 요청은 전부
같은 락에서 대기했다가 복사 결과를 그대로 재사용한다 (동시 요청이 늘어도 복사 API
호출은 책 1권당 최대 1번).
"""
import os
import shutil
import threading
import time

from repositories.gdrive_book_copy_repository import GdriveBookCopyRepository
from utils.drive_helper import is_gdrive_url, split_gdrive_file_id
from utils.rclone_gdrive_copy import (
    rclone_copy_file_by_id,
    rclone_ensure_ignore_marker,
    compute_relative_dest_path,
)

# 뷰캐시 사본 보관 기간(시간). 만료되면 로컬 파일을 지우고 다음 열람 시 재복사한다.
# LRU 등 정교한 정책은 쓰지 않는다 — 소수 사용자 규모에서는 하루 지나서 다시 복사되는
# 부하가 무시할 만한 수준이라는 게 사용자의 판단.
VIEW_COPY_TTL_HOURS = 24

_book_copy_locks = {}
_book_copy_locks_mutex = threading.Lock()


def _get_book_copy_lock(db_type, book_id):
    key = (db_type, book_id)
    with _book_copy_locks_mutex:
        if key not in _book_copy_locks:
            _book_copy_locks[key] = threading.Lock()
        return _book_copy_locks[key]


def _wait_for_local_visibility(local_path, db_type, library, already_refreshed=False, timeout=6.0, interval=0.5):
    """복사 직후 rclone VFS 마운트가 새 파일을 아직 못 봤을 수 있어(디렉토리 캐시 TTL),
    rc vfs/refresh 시도(디렉토리 경로 추정이 리모트 마운트 구성에 따라 어긋날 수 있어
    최선의 노력일 뿐 신뢰할 수 없음)와 별개로 os.path.exists()를 짧게 폴링해 실제로
    파일이 보이는지 직접 확인한다 — 이게 최종적으로 신뢰 가능한 유일한 신호다."""
    if os.path.exists(local_path):
        return True

    if not already_refreshed:
        try:
            from tools.scanner.vfs import refresh_vfs_paths, resolve_rc_urls
            rc_urls = resolve_rc_urls(db_type, library)
            refresh_vfs_paths([os.path.dirname(local_path)], rc_urls)
        except Exception as vfs_err:
            print(f"[GdriveViewCopy] VFS 캐시 갱신 시도 실패(무시하고 계속): {vfs_err}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(local_path):
            return True
        time.sleep(interval)
    return os.path.exists(local_path)


def _split_gdrive_source_path(base_path):
    """'gdrive:/<folder_id>/<rel...>/<filename>' 형태의 경로를 (rel_folder, filename)으로 분리한다.
    folder_id는 항상 스킴 바로 뒤 첫 세그먼트다 (tools/scanner/engine.py의
    v_root = canonical_path(f"gdrive://{folder_id}/{rel_f}") 구성 규칙 참조)."""
    without_scheme = base_path.split('gdrive:', 1)[-1].replace('\\', '/').lstrip('/')
    parts = [p for p in without_scheme.split('/') if p]
    if len(parts) < 2:
        return '', parts[-1] if parts else ''
    filename = parts[-1]
    rel_folder = '/'.join(parts[1:-1])
    return rel_folder, filename


def _resolve_drive_cache_root_subpath(remote, mount_root, db_type, library):
    """"_bookoasis_view_cache"를 rclone 'remote:path' 문법 기준으로 리모트 루트 아래
    어느 상대경로에 둘지 계산한다 (예: '' 또는 'tempview').

    관리자가 "로컬 마운트 루트" 필드에 순수 마운트 지점이 아니라 그 하위 폴더까지
    포함한 전체 경로(예: '/mount/root/tempview')를 넣어둔 경우 — Drive 루트가
    지저분해지지 않게 원하는 폴더 안에 정리해서 담고 싶어서인 경우가 많다 — 그
    의도를 실제로 반영한다. 순수 마운트 지점을 라이브로 재감지해 저장된 값과
    비교하고, 차이가 나는 만큼(예: 'tempview')을 그대로 반환한다. rclone의
    'remote:path' 주소 체계는 로컬 마운트가 실제로 보여주는 경로와 항상 일치하므로
    (root_folder_id/마운트 서브경로 스코핑도 rclone 스스로 반영), REST API로 Drive
    폴더 id를 직접 추론하던 예전 방식과 달리 로컬/Drive가 서로 어긋날 수 없다
    (2026-08-23, 로컬/Drive 경로가 서로 다른 곳을 가리키던 버그의 근본 수정)."""
    try:
        from tools.scanner.vfs import detect_mount_root, resolve_rc_urls
        rc_urls = resolve_rc_urls(db_type, library)
        pure_mount_root = detect_mount_root(remote, None, rc_urls)
    except Exception as e:
        print(f"[GdriveViewCopy] 순수 마운트 루트 재감지 실패(무시, 리모트 루트 바로 아래에 캐시를 둠): {e}")
        return ''

    if not pure_mount_root:
        return ''

    extra_subpath = compute_relative_dest_path(mount_root, pure_mount_root)
    if not extra_subpath:
        return ''

    print(f"[GdriveViewCopy] 마운트 루트에 지정된 하위 폴더 감지됨: '{extra_subpath}' — 그 안에 캐시를 정리합니다")
    return extra_subpath


def resolve_viewable_path(db_type, book_id, file_path, library):
    """gdrive:// 가상 경로를, 이미 복사된 로컬 경로(또는 아직 미지원인 경우 원본)로 바꿔 반환한다.
    gdrive 경로가 아니거나 book_id/library가 없으면 file_path를 그대로 반환한다(no-op)."""
    if not file_path or not is_gdrive_url(file_path) or book_id is None or not library:
        return file_path

    remote = library.get('gdrive_copy_remote')
    mount_root = library.get('gdrive_view_local_mirror_path')
    library_id = library.get('id')
    if not remote or not mount_root:
        # 개인 리모트가 등록되지 않은 gdrive 카테고리 — 이 책은 복사 대상이 아니다
        # (요구사항 1의 하드 게이트는 카테고리 생성 단계에서 막지만, 과거에 생성된
        # 카테고리가 남아있을 가능성을 대비해 여기서도 안전하게 원본 스트리밍으로 폴백).
        return file_path

    # 뷰어 사전복사 전용 캐시 위치는 관리자가 직접 정하지 않는다 — "복사 목적지 경로"를
    # 손으로 입력/유지해야 하면 이 서비스가 Drive 쪽과 로컬 쪽 두 경로를 각각 계산하면서
    # 어긋나기 쉽다(오늘 겪은 버그의 근본 원인). 대신 카테고리별로 결정적인 서브경로를
    # 하나만 써서, Drive 쪽/로컬 쪽 둘 다 "리모트 루트 + 이 서브경로"로 동일하게 계산한다
    # — 카테고리마다 격리되어 있어 다른 카테고리나 관리자가 수동으로 쓰는 폴더와 충돌하지
    # 않고, mount_root(리모트 전체가 마운트된 지점)만 정확하면 절대 어긋날 수 없다.
    view_cache_subpath = f"_bookoasis_view_cache/lib_{library_id}"
    mirror_root = os.path.join(mount_root, *view_cache_subpath.split('/'))

    def _resolve_existing(existing):
        """이미 'copied'/'unsupported' 상태인 기존 레코드를 재복사 없이 처리한다.
        None을 반환하면 호출부는 아직 미해결 상태(또는 설정 변경으로 무효화된 기록)로
        보고 새 복사를 진행해야 한다."""
        if not existing:
            return None
        if existing['status'] == 'copied' and existing.get('local_path'):
            local_path = existing['local_path']
            # 카테고리 수정에서 "리모트 로컬 마운트 루트"를 나중에 바꾸면 예전에 그 설정으로
            # 저장해둔 local_path는 더 이상 유효한 위치가 아니다 — 현재 mirror_root(자동
            # 계산된 캐시 경로) 아래에 있는 경로가 아니면 이 기록은 무효로 보고 처음부터
            # 다시 복사한다(신뢰할 수 없는 옛 경로를 영원히 재사용하는 걸 막음).
            norm_local = os.path.normpath(local_path)
            norm_mirror = os.path.normpath(mirror_root)
            if not (norm_local == norm_mirror or norm_local.startswith(norm_mirror + os.sep)):
                print(f"[GdriveViewCopy] 저장된 복사 경로가 현재 설정과 어긋나 무효화(book_id={book_id}): {local_path} (현재 mirror_root={mirror_root})")
                return None
            # Drive 쪽 복사 자체는 이미 끝났으므로 절대 재복사하지 않는다 — 로컬 마운트에
            # 아직 안 보이는 것뿐일 수 있어 짧게만 재확인한다(못 보여도 이번 요청만
            # 원본 스트리밍으로 폴백, 다음 요청이 다시 확인).
            if _wait_for_local_visibility(local_path, db_type, library):
                return local_path
            return file_path
        if existing['status'] == 'unsupported':
            return file_path
        return None

    existing = GdriveBookCopyRepository.get_by_book_id(db_type, book_id)
    resolved = _resolve_existing(existing)
    if resolved is not None:
        return resolved

    lock = _get_book_copy_lock(db_type, book_id)
    with lock:
        # 락 대기 중 다른 요청이 먼저 끝냈을 수 있으므로 재확인
        existing = GdriveBookCopyRepository.get_by_book_id(db_type, book_id)
        resolved = _resolve_existing(existing)
        if resolved is not None:
            return resolved

        base_path, source_file_id = split_gdrive_file_id(file_path)
        if not source_file_id:
            return file_path

        rel_folder, filename = _split_gdrive_source_path(base_path)

        try:
            # rclone CLI가 소스(공유 폴더 file_id)와 목적지(내 드라이브) 사이의 실제
            # 서버사이드 복사를 대신 수행한다(utils/rclone_gdrive_copy.py의
            # rclone_copy_file_by_id 참조) — REST API로 Drive 폴더 id를 직접 관리하던
            # 예전 방식은 root_folder_id/마운트 서브경로 스코핑을 우리가 다시 구현해야
            # 했고 실제로 여러 번 어긋났다(2026-08-23). rclone의 'remote:path' 문법은
            # 로컬 마운트가 실제로 보여주는 경로와 항상 같은 걸 가리키므로 이 문제가
            # 원천적으로 사라진다.
            drive_cache_root_subpath = _resolve_drive_cache_root_subpath(remote, mount_root, db_type, library)
            drive_view_cache_root = f"{drive_cache_root_subpath}/_bookoasis_view_cache" if drive_cache_root_subpath else "_bookoasis_view_cache"
            drive_lib_subpath = f"{drive_view_cache_root}/lib_{library_id}"
            drive_dest_dir = f"{drive_lib_subpath}/{rel_folder}" if rel_folder else drive_lib_subpath

            # _bookoasis_view_cache 루트 폴더 자체에 .bookoasisignore 마커를 심어둬서,
            # 일반/레이지 스캐너가 이 캐시 폴더를 별개의 로컬 소스로 잘못 재스캔해
            # 책을 중복 등록하지 않게 한다 (로컬 마운트로 자연스레 반영될 때까지는
            # 스캐너가 아직 못 볼 수 있지만, 매 복사 시도마다 확인하므로 결국 반영된다).
            rclone_ensure_ignore_marker(f"{remote}:{drive_view_cache_root}/.bookoasisignore")

            rclone_copy_file_by_id(remote, source_file_id, f"{remote}:{drive_dest_dir}/{filename}")

            local_path = os.path.join(mirror_root, rel_folder, filename) if rel_folder else os.path.join(mirror_root, filename)

            # Drive API의 files.copy는 구글 데이터센터 내부에서 즉시 끝나지만, mirror_root를
            # 서빙하는 rclone VFS 마운트는 자체 디렉토리 캐시(TTL 수 분)를 갖고 있어 새로
            # 복사된 파일이 로컬에 곧바로 보이지 않을 수 있다. rc vfs/refresh를 먼저 시도하고
            # (디렉토리 경로 추정이 마운트 구성에 따라 어긋나 항상 성공한다고 보장 못함),
            # 최종적으로는 os.path.exists() 직접 폴링 결과만 신뢰한다.
            visible = _wait_for_local_visibility(local_path, db_type, library)

            # Drive 쪽 복사 자체는 성공했으므로, 로컬에 아직 안 보여도 'copied'로 기록해
            # 다음 요청이 재복사 API를 또 호출하지 않게 한다 — 안 보이면 그 다음 요청이
            # _resolve_existing()에서 짧게 재확인만 한다.
            GdriveBookCopyRepository.upsert_copied(db_type, book_id, library_id, source_file_id, local_path)
            if visible:
                print(f"[GdriveViewCopy] 책 단위 사전복사 완료 (book_id={book_id}): {filename}")
                return local_path
            print(f"[GdriveViewCopy] 복사는 성공했지만 로컬 마운트에 아직 반영 안 됨, 이번 요청은 원본 스트리밍 폴백 (book_id={book_id}): {filename}")
            return file_path
        except ValueError as e:
            # files.copy 자체가 거부된 경우(보기 전용 공유 등) — 이 책은 영구히 기존
            # gdrive:// 스트리밍으로 폴백한다 (요구사항 2), 매번 재시도하지 않도록 기록.
            print(f"[GdriveViewCopy] 복사 불가로 원본 스트리밍 폴백 (book_id={book_id}): {e}")
            GdriveBookCopyRepository.upsert_unsupported(db_type, book_id, library_id, source_file_id, str(e))
            return file_path
        except Exception as e:
            # 네트워크/일시적 오류 — DB에 기록하지 않고 이번 요청만 원본 스트리밍으로 폴백,
            # 다음 열람 시 다시 시도한다.
            print(f"[GdriveViewCopy] 일시적 오류로 이번 요청은 원본 스트리밍 폴백 (book_id={book_id}): {e}")
            return file_path


def cleanup_stale_view_copies(db_type, older_than_hours=VIEW_COPY_TTL_HOURS):
    """VIEW_COPY_TTL_HOURS(기본 24시간)보다 오래된 'copied' 사본을 로컬에서 지우고
    DB 기록도 삭제한다. 다음에 그 책을 열람하면 자연스럽게 다시 복사된다(재복사
    부하는 감수하기로 한 단순 고정 TTL 정책 — LRU 등은 의도적으로 쓰지 않음).
    스케줄러 인터벌 잡에서 db_type별로 호출된다."""
    stale_rows = GdriveBookCopyRepository.get_stale_copied(db_type, older_than_hours)
    for row in stale_rows:
        local_path = row.get('local_path')
        book_id = row.get('book_id')
        try:
            if local_path and os.path.isdir(local_path):
                shutil.rmtree(local_path, ignore_errors=True)
            elif local_path and os.path.isfile(local_path):
                os.remove(local_path)
        except OSError as err:
            # 파일이 이미 없거나(리모트 마운트 재연결 등) 삭제 실패해도 DB 기록은
            # 정리한다 — 다음 열람 때 재복사하면 자연히 정상 상태로 복구된다.
            print(f"[GdriveViewCopy] TTL 정리 중 로컬 파일 삭제 실패(무시, book_id={book_id}): {err}")

        GdriveBookCopyRepository.delete_by_book_id(db_type, book_id)

    if stale_rows:
        print(f"[GdriveViewCopy] TTL 정리 완료 ({db_type}): {len(stale_rows)}건 삭제 (기준: {older_than_hours}시간)")
