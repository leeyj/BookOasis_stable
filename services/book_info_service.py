# -*- coding: utf-8 -*-
import os
import database
from utils.cache_helper import get_zip_file_hybrid
from services.stream_service import get_imgdir_files

class BookInfoService:
    @staticmethod
    def get_viewer_info(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT id, cover_image FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        total_pages = BookInfoService.get_total_pages(db_type, book_id)
        if total_pages is None:
            return None

        return {
            'total_pages': total_pages,
            'cover_image': row['cover_image']
        }

    @staticmethod
    def get_total_pages(db_type, book_id):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("SELECT total_pages, file_path, file_format FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        total_pages = row['total_pages'] or 0
        file_format = (row['file_format'] or '').lower()
        file_path = row['file_path']

        imgdir_exists = file_format == 'imgdir' and file_path and os.path.isdir(os.path.dirname(file_path))
        if total_pages == 0 and file_path and (os.path.exists(file_path) or imgdir_exists):
            if file_format in ('zip', 'cbz'):
                zf = get_zip_file_hybrid(file_path)
                if zf:
                    try:
                        img_ext = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                        total_pages = len([n for n in zf.namelist() if n.lower().endswith(img_ext)])
                    except Exception:
                        total_pages = 0
                    # `get_zip_file_hybrid` returns a cached ZipFile object.
                    # Closing it here can invalidate the shared cache and break later stream extraction.

            elif file_format == 'imgdir':
                try:
                    total_pages = len(get_imgdir_files(os.path.dirname(file_path)))
                except Exception:
                    total_pages = 0

            elif file_format == 'pdf':
                try:
                    import fitz
                    doc = fitz.open(file_path)
                    total_pages = doc.page_count
                    doc.close()
                except Exception:
                    total_pages = 0

            if total_pages > 0:
                conn2 = database.get_connection(db_type)
                conn2.execute("UPDATE books SET total_pages = ? WHERE id = ?", (total_pages, book_id))
                conn2.commit()
                conn2.close()

        conn.close()
        return total_pages
