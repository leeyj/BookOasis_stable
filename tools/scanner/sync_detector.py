# -*- coding: utf-8 -*-
import os
import datetime

def _is_mariadb_mode():
    engine = os.environ.get('DB_ENGINE', os.environ.get('DBMS', 'sqlite')).lower()
    return engine in ('mariadb', 'mysql')

def _normalize_path(path):
    if not path:
        return ""
    # 윈도우/리눅스 경로 구분자 차이를 통일하기 위해 백슬래시를 슬래시로 변환 및 양끝 공백 제거
    return path.replace('\\', '/').strip()

def _is_imgdir_virtual_path(path):
    return bool(path and path.lower().endswith('__folder__.imgdir'))

def detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached):
    """Auto-detect book movement (Rename) through Basename comparison between disappeared path and newly discovered path and preserve"""
    # 윈도우/리눅스 경로 구분자 불일치 예방을 위한 경로 정규화 매핑 적용
    norm_db_books = { _normalize_path(k): v for k, v in db_books.items() }
    norm_found_file_paths = { _normalize_path(p) for p in found_file_paths }

    deleted_paths = set(norm_db_books.keys()) - norm_found_file_paths
    new_paths = norm_found_file_paths - set(norm_db_books.keys())

    # IMGDIR virtual records intentionally skip basename-based move matching.
    deleted_imgdir_paths = {p for p in deleted_paths if _is_imgdir_virtual_path(p)}
    new_imgdir_paths = {p for p in new_paths if _is_imgdir_virtual_path(p)}
    deleted_paths = deleted_paths - deleted_imgdir_paths
    new_paths = new_paths - new_imgdir_paths

    ph = '%s' if _is_mariadb_mode() else '?'
    if deleted_paths and new_paths:
        del_basename_map = {}
        for dp in deleted_paths:
            basename = os.path.basename(dp)
            del_basename_map[basename] = (dp, norm_db_books[dp])

        for np in list(new_paths):
            basename = os.path.basename(np)
            if basename in del_basename_map:
                old_path, book_id = del_basename_map[basename]
                # DB 저장 시에도 정규화된(슬래시 형태의) 경로를 사용하여 OS 이식성 보장
                cursor.execute(f"UPDATE books SET file_path = {ph} WHERE id = {ph}", (np, book_id))
                print(f"[Scanner-Move] 🚚 Book movement detection complete: '{old_path}' -> '{np}' (Existing ID {book_id} and reading history maintained)")
                
                # Update cache info in memory
                db_books[np] = book_id
                if old_path in db_meta_full:
                    db_meta_full.add(np)
                    db_meta_full.remove(old_path)
                if old_path in db_offsets_cached:
                    db_offsets_cached.add(np)
                    db_offsets_cached.remove(old_path)
                
                deleted_paths.remove(old_path)
                new_paths.remove(np)
                del_basename_map.pop(basename)

    return deleted_paths | deleted_imgdir_paths

def handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
    """Transaction-safely soft delete books no longer found, and restore previously soft deleted books if found again"""
    norm_db_books = { _normalize_path(k): v for k, v in db_books.items() }
    norm_found_file_paths = { _normalize_path(p) for p in found_file_paths }
    ph = '%s' if _is_mariadb_mode() else '?'

    # 0. 복구 처리 (기존에 is_deleted=1 상태였으나 물리적으로 다시 발견된 책 복구)
    if norm_found_file_paths:
        restore_paths = [p for p in found_file_paths if _normalize_path(p) in norm_db_books]
        if restore_paths:
            for i in range(0, len(restore_paths), 900):
                chunk = restore_paths[i:i+900]
                placeholders = ','.join([ph] * len(chunk))
                cursor.execute(f"""
                    UPDATE books 
                    SET is_deleted = 0, deleted_at = NULL 
                    WHERE file_path IN ({placeholders}) AND is_deleted = 1
                """, tuple(chunk) if _is_mariadb_mode() else chunk)

    if not deleted_paths:
        return True
        
    # 0 files emergency brake safety device
    if not found_file_paths and len(db_books) > 0:
        print(f"[Scanner] ⚠️ Fatal Warning: 0 files read from multiple paths {target_paths}. Mount unmounted or path issue suspected, aborting file deletion logic.")
        return False

    # 1. 소프트 딜리트 처리
    for dp in deleted_paths:
        norm_dp = _normalize_path(dp)
        if norm_dp in norm_db_books:
            book_id = norm_db_books[norm_dp]
            cursor.execute(f"""
                UPDATE books 
                SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP 
                WHERE id = {ph}
            """, (book_id,))
            print(f"[Scanner] File disappearance detected, set to trash: {dp}")
            
    # 2. [대안 2 적용] 7일 이상 경과한 소프트 딜리트 도서들을 영구 하드 딜리트 (자동 비우기)
    try:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"""
            SELECT id, cover_image, file_path FROM books
            WHERE COALESCE(is_deleted, 0) = 1
              AND deleted_at <= {ph}
        """, (cutoff,))
        old_deleted_rows = cursor.fetchall()

        # 이 비우기는 스캔 범위/라이브러리와 무관하게 DB 전체에 적용된다. 그 사이 파일이 다시
        # 나타났는데(다른 부분 스캔이 막 처리 중일 수도 있음) 여기서 row를 지워버리면, 그 스캔의
        # UPDATE가 0 rows로 끝나 도서가 DB에서 통째로 사라진다. 실제 파일이 있으면 지우지 않고 복구한다.
        reappeared_ids = [
            r['id'] for r in old_deleted_rows
            if r['file_path'] and not r['file_path'].startswith(('gdrive:', 'gdrive://'))
            and os.path.exists(r['file_path'])
        ]
        if reappeared_ids:
            placeholders = ','.join([ph] * len(reappeared_ids))
            cursor.execute(f"""
                UPDATE books SET is_deleted = 0, deleted_at = NULL WHERE id IN ({placeholders})
            """, tuple(reappeared_ids) if _is_mariadb_mode() else reappeared_ids)
            print(f"[Scanner-Cleanup] Skipped purge of {len(reappeared_ids)} trashed books whose files exist again (restored).")
            old_deleted_rows = [r for r in old_deleted_rows if r['id'] not in set(reappeared_ids)]

        if old_deleted_rows:
            old_ids = [r['id'] for r in old_deleted_rows]
            placeholders = ','.join([ph] * len(old_ids))
            params = tuple(old_ids) if _is_mariadb_mode() else old_ids
            
            # 연관 데이터 삭제 - repositories/trash_repository_shared.py의 수동 "휴지통 비우기"와
            # 반드시 같은 목록을 유지할 것(스키마에 FK/CASCADE가 없어 두 삭제 경로가 각자
            # 목록을 들고 있다 - 예전엔 이 자동 경로에 user_favorites/book_annotations/
            # epub_bookmarks/collection_items가 빠져 있어서, 파일이 7일 이상 사라졌다가
            # 다시 나타나 새 id로 재등록될 때 옛 id를 참조하던 즐겨찾기/하이라이트/북마크/
            # 컬렉션 항목이 영구 고아 레코드로 남았다).
            cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM user_favorites WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM book_annotations WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM epub_bookmarks WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM collection_items WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM tts_progress WHERE book_id IN ({placeholders})", params)
            cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders})", params)
            
            # 커버 이미지 물리 파일 소거
            from services.cover_storage_service import get_covers_dir
            covers_dir = get_covers_dir()
            for r in old_deleted_rows:
                cover_img = r['cover_image']
                if cover_img:
                    for root, dirs, files in os.walk(covers_dir):
                        if cover_img in files:
                            try:
                                os.remove(os.path.join(root, cover_img))
                                print(f"[Scanner-Cleanup] Physically deleted old cover: {cover_img}")
                            except Exception as ex:
                                print(f"[Scanner-Cleanup WARNING] Failed to delete old cover file: {ex}")
            
            print(f"[Scanner-Cleanup] Successfully auto-cleaned {len(old_ids)} books that were soft-deleted more than 7 days ago.")
    except Exception as cleanup_err:
        print(f"[Scanner-Cleanup ERROR] Failed to auto empty old trash: {cleanup_err}")

    return True
