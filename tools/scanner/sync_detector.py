# -*- coding: utf-8 -*-
import os

def detect_and_handle_book_movement(cursor, db_books, found_file_paths, db_meta_full, db_offsets_cached):
    """Auto-detect book movement (Rename) through Basename comparison between disappeared path and newly discovered path and preserve"""
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
                
    return deleted_paths

def handle_deleted_books(cursor, db_books, deleted_paths, target_paths, found_file_paths):
    """Transaction-safely delete books no longer found from DB and user history"""
    if not deleted_paths:
        return True
        
    # 0 files emergency brake safety device
    if not found_file_paths and len(db_books) > 0:
        print(f"[Scanner] ⚠️ Fatal Warning: 0 files read from multiple paths {target_paths}. Mount unmounted or path issue suspected, aborting file deletion logic.")
        return False

    for dp in deleted_paths:
        if dp in db_books:
            book_id = db_books[dp]
            cursor.execute("DELETE FROM user_progress WHERE book_id = ?", (book_id,))
            cursor.execute("DELETE FROM user_reading_log WHERE book_id = ?", (book_id,))
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
            print(f"[Scanner] File deletion detected, removed from DB: {dp}")
            
    return True
