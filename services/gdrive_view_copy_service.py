# -*- coding: utf-8 -*-
"""
gdrive_view_copy_service.py – gdrive 공유 카테고리 책을 "열 때" 그 책 한 권만 카테고리에 연결된
로그인 rclone 리모트로 이 서버의 로컬 임시 폴더에 내려받아, 그 로컬 파일로 바꿔치기한다.

예전에는 관리자 드라이브로 서버사이드 복사(files.copy)한 뒤 rclone 마운트에 그 파일이 보일
때까지 기다렸는데, 마운트 디렉토리 캐시 때문에 새 폴더가 몇 초~몇 분 안 보여 대부분 실패했고
(2026-10-22 .21 실측: 첫 페이지 22.5초 후 결국 API 키 익명 다운로드로 폴백), 그 폴백은 대형
공유 폴더에서 Google 403으로 차단되는 바로 그 경로였다. 지금은 Drive에 아무것도 쓰지 않고
마운트도 거치지 않는다 (20MB 회차 1개 약 5초, 다음 권은 뷰어가 미리 받아둔다).

파일 하나가 처음 열릴 때만 다운로드가 발생하고, 그 사이 같은 책에 대한 동시 요청은 전부
같은 락에서 대기했다가 결과를 그대로 재사용한다 (책 1권당 다운로드 최대 1번).
"""
import os
import shutil
import threading
import time

from repositories.gdrive_book_copy_repository import GdriveBookCopyRepository
from utils.drive_helper import MEDIA_SERVER_DIR, is_gdrive_url, split_gdrive_file_id
from utils.gdrive_beta_log import beta_log
from utils.rclone_gdrive_copy import rclone_download_file_by_id, rclone_download_folder_images

# 뷰캐시 사본 보관 기간(시간). 만료되면 로컬 파일을 지우고 다음 열람 시 다시 받는다.
VIEW_COPY_TTL_HOURS = 24
# 뷰캐시 전체 상한(GB). TTL 정리 후에도 넘으면 오래된 파일부터 지운다 (웹툰 1화 ~20MB).
VIEW_CACHE_MAX_BYTES = int(float(os.getenv('GDRIVE_VIEW_CACHE_MAX_GB', '5') or '5') * 1024 ** 3)

_book_copy_locks = {}
_book_copy_locks_mutex = threading.Lock()


def _get_book_copy_lock(db_type, book_id):
    key = (db_type, book_id)
    with _book_copy_locks_mutex:
        if key not in _book_copy_locks:
            _book_copy_locks[key] = threading.Lock()
        return _book_copy_locks[key]


def view_cache_root(db_type=None, library_id=None):
    """뷰어용 로컬 사본 위치. 인자 없이 부르면 전체 루트 (카테고리 삭제 시 카테고리 폴더째 지운다)."""
    base = os.path.join(MEDIA_SERVER_DIR, 'cache', 'gdrive_view')
    if db_type is None:
        return base
    return os.path.join(base, f'{db_type}_lib_{library_id}')


def _is_imgdir(path):
    """이미지 폴더 책(가상 파일 '__folder__.imgdir')인지 — 이 경우 사본은 파일이 아니라 폴더다."""
    return (path or '').lower().endswith('.imgdir')


def _entry_size(path):
    """사본 하나(파일, 또는 이미지 폴더 책이면 폴더 전체)의 바이트 수."""
    try:
        if os.path.isdir(path):
            return sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(path) for f in fs)
        return os.path.getsize(path)
    except OSError:
        return 0


def _touch(path):
    """rclone은 원격 수정 시각을 그대로 남기므로, 용량 상한 정리가 '최근에 연 순서'로 동작하게 지금 시각으로 갱신한다."""
    try:
        os.utime(path, None)
    except OSError:
        pass


def resolve_viewable_path(db_type, book_id, file_path, library):
    """gdrive:// 가상 경로를, 로컬에 내려받은 사본 경로(실패 시 원본)로 바꿔 반환한다.
    gdrive 경로가 아니거나 book_id/library가 없으면 file_path를 그대로 반환한다(no-op)."""
    if not file_path or not is_gdrive_url(file_path) or book_id is None or not library:
        return file_path

    remote = library.get('gdrive_copy_remote')
    if not remote:
        # 로그인 리모트가 없는 옛 gdrive 카테고리 — 원본(API 키) 스트리밍으로 폴백.
        return file_path

    cache_dir = view_cache_root(db_type, library.get('id'))

    def _resolve_existing(existing):
        """이미 받은 사본이 현재 캐시 위치에 실제로 있으면 그 경로를, 아니면 None(새로 받기)."""
        if not existing or existing['status'] != 'copied' or not existing.get('local_path'):
            return None
        local_path = existing['local_path']
        # 예전 방식(드라이브 복사 + 마운트 경로)으로 기록된 사본이나 정리된 파일은 새로 받는다.
        if not os.path.normpath(local_path).startswith(os.path.normpath(cache_dir) + os.sep):
            return None
        target = os.path.dirname(local_path) if _is_imgdir(local_path) else local_path
        if not (os.path.isdir(target) if _is_imgdir(local_path) else os.path.isfile(target)):
            return None
        _touch(target)
        return local_path

    resolved = _resolve_existing(GdriveBookCopyRepository.get_by_book_id(db_type, book_id))
    if resolved:
        # 표지 생성 지원 전에 받아 둔 사본이나 한 번 실패한 책도, 다시 열 때 표지가 비어 있으면 만든다.
        _fill_cover_from_local_copy(db_type, book_id, file_path, resolved, library.get('id'))
        return resolved

    lock = _get_book_copy_lock(db_type, book_id)
    with lock:
        # 락 대기 중 다른 요청이 먼저 끝냈을 수 있으므로 재확인
        resolved = _resolve_existing(GdriveBookCopyRepository.get_by_book_id(db_type, book_id))
        if resolved:
            return resolved

        base_path, source_file_id = split_gdrive_file_id(file_path)
        if not source_file_id:
            return file_path

        # 파일명은 Drive file_id + 원래 확장자 — 한글 긴 회차명이 파일시스템 이름 길이 한도를 넘지 않게.
        # 이미지 폴더 책은 source_file_id가 폴더 ID이고, 그 폴더 이미지를 <폴더ID>/ 아래로 통째 받는다.
        kind = 'imgdir' if _is_imgdir(base_path) else (os.path.splitext(base_path)[1].lower().lstrip('.') or 'file')
        t0 = time.time()
        try:
            if _is_imgdir(base_path):
                from utils.drive_helper import GDRIVE_IMAGE_EXTENSIONS
                local_dir = os.path.join(cache_dir, source_file_id)
                rclone_download_folder_images(remote, source_file_id, local_dir, GDRIVE_IMAGE_EXTENSIONS)
                local_path = os.path.join(local_dir, os.path.basename(base_path))
                _touch(local_dir)
            else:
                ext = os.path.splitext(base_path)[1].lower()
                local_path = os.path.join(cache_dir, f'{source_file_id}{ext}')
                rclone_download_file_by_id(remote, source_file_id, local_path)
                _touch(local_path)
        except Exception as e:
            # 네트워크/권한 오류 — 기록하지 않고 이번 요청만 원본 스트리밍으로 폴백, 다음 열람 때 다시 시도.
            print(f"[GdriveViewCopy] Download failed; streaming the original for this request (book_id={book_id}): {e}")
            beta_log('view.download_failed', db=db_type, lib=library.get('id'), book=book_id, kind=kind,
                     took=time.time() - t0, err=e)
            return file_path

        GdriveBookCopyRepository.upsert_copied(db_type, book_id, library.get('id'), source_file_id, local_path)
        print(f"[GdriveViewCopy] Downloaded for viewing (book_id={book_id}): {os.path.basename(base_path)}")
        beta_log('view.download', db=db_type, lib=library.get('id'), book=book_id, kind=kind,
                 mb=_entry_size(os.path.dirname(local_path) if _is_imgdir(local_path) else local_path) / 1e6,
                 took=time.time() - t0)
        _fill_cover_from_local_copy(db_type, book_id, file_path, local_path, library.get('id'))
        return local_path


def _fill_cover_from_local_copy(db_type, book_id, file_path, local_path, library_id):
    """표지가 없는 책(kavita.yaml 없는 폴더 등)이면 방금 받은 로컬 사본의 첫 페이지로 표지를 만든다.
    스캔 때 표지를 얻으려고 Drive의 zip을 뒤지면 대형 공유 폴더에서 차단 위험이 크므로, 이미 받은
    사본이 있는 '열 때'에만 만든다 — 추가 네트워크 요청 없음. 실패해도 열람에는 영향이 없다."""
    try:
        from repositories import BookRepository
        row = BookRepository.get_book_cover_image(db_type, book_id)
        if not row or row.get('cover_image'):
            return
        if _is_imgdir(local_path):
            from tools.scanner.cover import get_imgdir_cover
            cover = get_imgdir_cover(os.path.dirname(local_path), file_path, library_id=library_id)
            if cover and BookRepository.fill_missing_cover(db_type, book_id, cover):
                print(f"[GdriveViewCopy] Cover created from the first image on open (book_id={book_id}): {cover}")
                beta_log('view.cover_on_open', db=db_type, lib=library_id, book=book_id, kind='imgdir')
            return
        if local_path.lower().endswith('.pdf'):
            from services.cover_storage_service import get_covers_dir, cover_filename_for
            from tools.scanner.cover import render_pdf_cover
            # 표지 파일 이름은 원래 DB 경로(file_path) 기준 — 스캔 때 만들어지는 표지와 같은 규칙.
            cover_name = cover_filename_for(file_path)
            dest_dir = os.path.join(get_covers_dir(), str(library_id))
            os.makedirs(dest_dir, exist_ok=True)
            if render_pdf_cover(local_path, os.path.join(dest_dir, cover_name)):
                cover = f"{library_id}/{cover_name}"
                if BookRepository.fill_missing_cover(db_type, book_id, cover):
                    print(f"[GdriveViewCopy] Cover created from the first PDF page on open (book_id={book_id}): {cover}")
                    beta_log('view.cover_on_open', db=db_type, lib=library_id, book=book_id, kind='pdf')
            return
        if not local_path.lower().endswith(('.zip', '.cbz', '.epub')):
            return
        from tools.scanner.cover import get_series_cover_fallback
        # 표지 파일 이름은 원래 DB 경로(file_path) 기준 — 스캔 때 만들어지는 표지와 같은 규칙.
        cover = get_series_cover_fallback(
            os.path.basename(os.path.dirname(local_path)) or 'gdrive', os.path.dirname(local_path),
            filename=os.path.basename(local_path), file_path=file_path, library_id=library_id)
        if cover and BookRepository.fill_missing_cover(db_type, book_id, cover):
            print(f"[GdriveViewCopy] Cover created from the first page on open (book_id={book_id}): {cover}")
            beta_log('view.cover_on_open', db=db_type, lib=library_id, book=book_id, kind='archive')
    except Exception as e:
        print(f"[GdriveViewCopy] Cover from local copy failed (ignored, book_id={book_id}): {e}")
        beta_log('view.cover_on_open_failed', db=db_type, lib=library_id, book=book_id, err=e)


def prefetch_in_background(db_type, book_id, file_path, library):
    """다음 권 등을 뷰어가 넘기기 전에 미리 받아둔다 (실패는 조용히 무시 — 열 때 다시 시도)."""
    def _run():
        t0 = time.time()
        try:
            resolved = resolve_viewable_path(db_type, book_id, file_path, library)
            beta_log('view.prefetch', db=db_type, lib=(library or {}).get('id'), book=book_id,
                     ok=resolved != file_path, took=time.time() - t0)
        except Exception as e:
            print(f"[GdriveViewCopy] Prefetch failed (ignored, book_id={book_id}): {e}")
            beta_log('view.prefetch', db=db_type, lib=(library or {}).get('id'), book=book_id, ok=False,
                     took=time.time() - t0, err=e)
    threading.Thread(target=_run, name=f'gdrive-view-prefetch-{book_id}', daemon=True).start()


def _enforce_cache_size_limit(max_bytes=VIEW_CACHE_MAX_BYTES):
    """뷰캐시 전체가 상한을 넘으면 가장 오래 안 쓰인(수정 시각 기준) 사본부터 지운다.
    사본 단위는 책 한 권 — zip 등은 파일 하나, 이미지 폴더 책은 폴더 통째(일부 이미지만 지우면 책이 깨짐).
    지워진 사본의 DB 기록은 남아도 되며, 다음 열람 때 사본이 없으면 다시 받는다."""
    root = view_cache_root()
    entries = []
    total = 0
    if not os.path.isdir(root):
        return 0
    for lib_dir in os.listdir(root):
        lib_path = os.path.join(root, lib_dir)
        if not os.path.isdir(lib_path):
            continue
        for name in os.listdir(lib_path):
            if name.startswith('.rc_'):
                continue  # 받는 중인 임시 파일/폴더
            path = os.path.join(lib_path, name)
            try:
                mtime = os.path.getmtime(path)
                if os.path.isdir(path):
                    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(path) for f in fs)
                else:
                    size = os.path.getsize(path)
            except OSError:
                continue
            entries.append((mtime, size, path))
            total += size
    if total <= max_bytes:
        return 0
    removed = 0
    total_before = total
    for _mtime, size, path in sorted(entries):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            total -= size
            removed += 1
        except OSError:
            pass
        if total <= max_bytes:
            break
    print(f"[GdriveViewCopy] Cache size limit: removed {removed} old copies")
    beta_log('cache.evict', removed=removed, freed_mb=(total_before - total) / 1e6,
             now_mb=total / 1e6, limit_mb=max_bytes / 1e6)
    return removed


def cleanup_stale_view_copies(db_type, older_than_hours=VIEW_COPY_TTL_HOURS):
    """VIEW_COPY_TTL_HOURS(기본 24시간)보다 오래된 'copied' 사본을 로컬에서 지우고
    DB 기록도 삭제한 뒤, 전체 크기 상한을 맞춘다. 다음에 그 책을 열면 다시 받는다.
    스케줄러 인터벌 잡에서 db_type별로 호출된다."""
    stale_rows = GdriveBookCopyRepository.get_stale_copied(db_type, older_than_hours)
    for row in stale_rows:
        local_path = row.get('local_path')
        book_id = row.get('book_id')
        try:
            if local_path and _is_imgdir(local_path):
                shutil.rmtree(os.path.dirname(local_path), ignore_errors=True)
            elif local_path and os.path.isdir(local_path):
                shutil.rmtree(local_path, ignore_errors=True)
            elif local_path and os.path.isfile(local_path):
                os.remove(local_path)
        except OSError as err:
            # 파일이 이미 없어도 DB 기록은 정리한다 — 다음 열람 때 다시 받으면 정상 상태로 복구된다.
            print(f"[GdriveViewCopy] Failed to delete a local file during TTL cleanup (ignored, book_id={book_id}): {err}")

        GdriveBookCopyRepository.delete_by_book_id(db_type, book_id)

    if stale_rows:
        print(f"[GdriveViewCopy] TTL cleanup done ({db_type}): {len(stale_rows)} deleted (older than {older_than_hours} hours)")
        beta_log('cache.ttl_cleanup', db=db_type, removed=len(stale_rows), older_than_h=older_than_hours)
    _enforce_cache_size_limit()
