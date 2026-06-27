# -*- coding: utf-8 -*-
import os

def detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached):
    """사라진 경로와 신규 발견 경로 간 Basename 비교를 통해 도서 이동(Rename)을 자동 감지하고 보존 처리"""
    deleted_paths = set(db_books.keys()) - found_file_paths
    new_paths = found_file_paths - set(db_books.keys())

    if deleted_paths and new_paths:
        del_basename_map = {}
        for dp in deleted_paths:
            basename = os.path.basename(dp)
            del_basename_map[basename] = (dp, db_books[dp])

        for np in list(new_paths):
            basename = os.path.basename(np)
            if basename in del_basename_map:
                old_path, book_id = del_basename_map[basename]
                cursor.execute("UPDATE books SET file_path = ? WHERE id = ?", (np, book_id))
                print(f"[Scanner-Move] 🚚 도서 이동 감지 완료: '{old_path}' -> '{np}' (기존 ID {book_id} 및 독서 기록 유지)")
                
                # 메모리 상의 캐시 정보 갱신
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
                
    return deleted_paths

def handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
    """더 이상 탐색되지 않는 도서를 DB 및 사용자 히스토리에서 트랜잭션 안전하게 삭제"""
    if not deleted_paths:
        return True
        
    # 0개 비상 브레이크 안전장치
    if not found_file_paths and len(db_books) > 0:
        print(f"[Scanner] ⚠️ 치명적 경고: 다중 경로 {target_paths}에서 읽어들인 파일이 0개입니다. 마운트가 해제되었거나 경로 문제가 의심되므로 파일 삭제 로직을 취소합니다.")
        return False

    for dp in deleted_paths:
        if dp in db_books:
            book_id = db_books[dp]
            cursor.execute("DELETE FROM user_progress WHERE book_id = ?", (book_id,))
            cursor.execute("DELETE FROM user_reading_log WHERE book_id = ?", (book_id,))
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
            print(f"[Scanner] 파일 삭제 감지되어 DB에서 제거: {dp}")
            
    return True
