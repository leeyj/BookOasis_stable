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
    def get_card_summary(db_type, book_id=None, series_name=None, library_id=None):
        """그리드 카드 '...' 정보 팝업용: 시리즈면 도서 수/전체 용량 합산, 단일 도서면 그 파일의 경로/용량만 반환"""
        series_name = str(series_name or '').strip()
        if series_name:
            row = BookRepository.get_card_summary_by_series(db_type, series_name, library_id)
            if not row or not row.get('book_count'):
                return None
            return {
                'title': series_name,
                'physical_path': os.path.dirname(row.get('sample_path') or ''),
                'book_count': int(row.get('book_count') or 0),
                'total_size': int(row.get('total_size') or 0),
            }

        if not book_id:
            return None
        row = BookRepository.get_card_summary_by_book_id(db_type, book_id)
        if not row:
            return None
        return {
            'title': row.get('title') or '',
            'physical_path': row.get('file_path') or '',
            'book_count': 1,
            'total_size': int(row.get('file_size') or 0),
        }

    @staticmethod
    def get_reader_info(db_type, book_id, user_id=None):
        """킷오스크 모드 등에서 openReader()를 book_id만으로 즉시 호출하기 위한 메타 조회"""
        row = BookRepository.get_book_reader_info(db_type, book_id, user_id=user_id)
        if not row:
            return None

        total_pages = row['total_pages'] or 0
        if total_pages == 0:
            total_pages = BookInfoService.get_total_pages(db_type, book_id) or 0

        return {
            'id': row['id'],
            'title': row['title'],
            'file_format': row['file_format'],
            'total_pages': total_pages,
            'pages_read': row['pages_read'] or 0
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
                    import pypdfium2 as pdfium
                    pdf = pdfium.PdfDocument(file_path)
                    total_pages = len(pdf)
                    pdf.close()
                except Exception:
                    total_pages = 0

            if total_pages > 0:
                BookRepository.update_book_pages(db_type, book_id, total_pages)

        return total_pages
