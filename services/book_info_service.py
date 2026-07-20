# -*- coding: utf-8 -*-
import os
from repositories.book_repository import BookRepository
from utils.cache_helper import get_zip_file_hybrid
from services.stream_service import get_imgdir_files

class BookInfoService:
    @staticmethod
    def get_viewer_info(db_type, book_id):
        row = BookRepository.get_book_cover_image(db_type, book_id)
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
        row = BookRepository.get_book_pages_and_path(db_type, book_id)
        if not row:
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
                BookRepository.update_book_pages(db_type, book_id, total_pages)

        return total_pages
