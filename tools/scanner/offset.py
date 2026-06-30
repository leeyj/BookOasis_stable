# -*- coding: utf-8 -*-
import os
import zipfile
from utils.sort_helper import natural_sort_key

def collect_zip_offsets(cursor, book_id, file_path):
    """Analyze image entries of ZIP file and collect byte offset metadata (reuse active cursor)"""
    if not os.path.exists(file_path):
        return

    img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    try:
        cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))
        
        with zipfile.ZipFile(file_path, 'r') as zf:
            infolist = zf.infolist()
            img_infos = [info for info in infolist if info.filename.lower().endswith(img_ext)]
            img_infos.sort(key=lambda x: natural_sort_key(x.filename))
            
            bulk_data = []
            for page_idx, info in enumerate(img_infos):
                bulk_data.append((
                    book_id,
                    page_idx,
                    info.filename,
                    info.header_offset,
                    info.compress_size,
                    info.file_size,
                    info.compress_type
                ))
            
            if bulk_data:
                cursor.executemany("""
                    INSERT INTO book_offsets 
                    (book_id, page_idx, filename, local_header_offset, compress_size, file_size, compress_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, bulk_data)
                
                cursor.execute("""
                    UPDATE books SET 
                        total_pages = ?, 
                        has_offsets = 1 
                    WHERE id = ?
                """, (len(bulk_data), book_id))
                
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset index complete (total {len(bulk_data)} pages)")
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset index failed: {e}")

def collect_zip_offsets_data(file_path):
    """Analyze image entries of ZIP file and collect byte offset metadata (pure memory parsing)"""
    if not os.path.exists(file_path):
        return []

    img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            infolist = zf.infolist()
            img_infos = [info for info in infolist if info.filename.lower().endswith(img_ext)]
            img_infos.sort(key=lambda x: natural_sort_key(x.filename))
            
            bulk_data = []
            for page_idx, info in enumerate(img_infos):
                bulk_data.append((
                    page_idx,
                    info.filename,
                    info.header_offset,
                    info.compress_size,
                    info.file_size,
                    info.compress_type
                ))
            return bulk_data
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset parsing failed: {e}")
        return []
