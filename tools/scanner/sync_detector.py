# -*- coding: utf-8 -*-
import os

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
                cursor.execute("UPDATE books SET file_path = ? WHERE id = ?", (np, book_id))
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

    # 0. 복구 처리 (기존에 is_deleted=1 상태였으나 물리적으로 다시 발견된 책 복구)
    if norm_found_file_paths:
        restore_paths = [p for p in found_file_paths if _normalize_path(p) in norm_db_books]
        if restore_paths:
            for i in range(0, len(restore_paths), 900):
                chunk = restore_paths[i:i+900]
                placeholders = ','.join(['?'] * len(chunk))
                cursor.execute(f"""
                    UPDATE books 
                    SET is_deleted = 0, deleted_at = NULL 
                    WHERE file_path IN ({placeholders}) AND is_deleted = 1
                """, chunk)

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
            cursor.execute("""
                UPDATE books 
                SET is_deleted = 1, deleted_at = datetime('now', 'localtime') 
                WHERE id = ?
            """, (book_id,))
            print(f"[Scanner] File disappearance detected, set to trash: {dp}")
            
    # 2. [대안 2 적용] 7일 이상 경과한 소프트 딜리트 도서들을 영구 하드 딜리트 (자동 비우기)
    try:
        cursor.execute("""
            SELECT id, cover_image FROM books
            WHERE COALESCE(is_deleted, 0) = 1
              AND deleted_at <= datetime('now', '-7 days', 'localtime')
        """)
        old_deleted_rows = cursor.fetchall()
        if old_deleted_rows:
            old_ids = [r['id'] for r in old_deleted_rows]
            placeholders = ','.join(['?'] * len(old_ids))
            
            # 연관 데이터 삭제
            cursor.execute(f"DELETE FROM user_progress WHERE book_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM user_reading_log WHERE book_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM book_offsets WHERE book_id IN ({placeholders})", old_ids)
            cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders})", old_ids)
            
            # 커버 이미지 물리 파일 소거
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            covers_dir = os.path.join(base_dir, 'covers')
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
