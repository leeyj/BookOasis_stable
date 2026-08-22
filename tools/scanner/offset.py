# -*- coding: utf-8 -*-
import os
import zipfile
from utils.sort_helper import natural_sort_key

IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')


def _offsets_from_zipfile(zf):
    """열려 있는 zipfile.ZipFile(로컬 파일이든 메모리 버퍼든)에서 이미지 항목의
    오프셋 메타데이터를 (page_idx, filename, header_offset, compress_size, file_size, compress_type)
    튜플 리스트로 뽑아낸다. 로컬 스캔과 gdrive 원격(Range 기반) 스캔이 이 로직을 공유한다."""
    img_infos = [info for info in zf.infolist() if info.filename.lower().endswith(IMG_EXT)]
    img_infos.sort(key=lambda x: natural_sort_key(x.filename))
    return [
        (page_idx, info.filename, info.header_offset, info.compress_size, info.file_size, info.compress_type)
        for page_idx, info in enumerate(img_infos)
    ]


def collect_zip_offsets(cursor, book_id, file_path):
    """Analyze image entries of ZIP file and collect byte offset metadata (reuse active cursor)"""
    if not os.path.exists(file_path):
        return

    try:
        cursor.execute("DELETE FROM book_offsets WHERE book_id = ?", (book_id,))

        with zipfile.ZipFile(file_path, 'r') as zf:
            bulk_data = [
                (book_id, page_idx, filename, header_offset, compress_size, file_size, compress_type)
                for page_idx, filename, header_offset, compress_size, file_size, compress_type in _offsets_from_zipfile(zf)
            ]

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

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            return _offsets_from_zipfile(zf)
    except Exception as e:
        print(f"[Scanner-Offset] '{os.path.basename(file_path)}' offset parsing failed: {e}")
        return []
