# -*- coding: utf-8 -*-
import os
from repositories.book_repository import BookRepository
from utils.sort_helper import natural_sort_key
from utils.cover_helper import get_cover_image_with_t

class BookService:
    @staticmethod
    def get_next_book(db_type, book_id, user_id=1):
        # 1. 대상 책의 series_name, library_id, file_path 조회
        current_book = BookRepository.get_book_basic_info(db_type, book_id)
        if not current_book:
            return None

        series_name = current_book['series_name']
        library_id = current_book['library_id']
        current_file_path = current_book['file_path']

        # 2. 같은 시리즈 내의 책 전체 조회 (진척도 결합)
        rows = BookRepository.get_books_by_series(db_type, series_name, library_id, user_id)

        # 3. 책 목록 정제 및 정렬
        books_list = []
        for r in rows:
            clean_title = r['title']
            file_format = (r['file_format'] or '').lower()
            if file_format == 'imgdir' and r['file_path']:
                clean_title = os.path.basename(os.path.dirname(r['file_path'])) or clean_title
            elif r['file_path']:
                filename_with_ext = os.path.basename(r['file_path'])
                clean_title, _ = os.path.splitext(filename_with_ext)
            books_list.append({
                'id': r['id'],
                'title': clean_title,
                'file_format': r['file_format'],
                'total_pages': r['total_pages'],
                'cover_image': get_cover_image_with_t(r['cover_image'], r['cover_updated_at']),
                'file_path': r['file_path'] or '',
                'pages_read': r['pages_read'] or 0
            })

        # 부모 디렉토리 격리 필터 적용
        if books_list and current_file_path:
            target_dir = os.path.dirname(current_file_path)
            books_list = [bk for bk in books_list if bk['file_path'] and os.path.dirname(bk['file_path']) == target_dir]

        books_list.sort(key=lambda x: natural_sort_key(x['title']))

        # 4. 다음 책 탐색
        next_book = None
        for idx, bk in enumerate(books_list):
            if str(bk['id']) == str(book_id):
                if idx + 1 < len(books_list):
                    next_book = books_list[idx + 1]
                break

        return next_book

    @staticmethod
    def update_favorite(db_type, book_id, is_favorite, user_id):
        """특정 도서의 즐겨찾기 상태 변경 (사용자별)"""
        return BookRepository.update_favorite(db_type, book_id, is_favorite, user_id)

    @staticmethod
    def update_series_favorite(db_type, series_name, is_favorite, user_id):
        """특정 시리즈 전체 도서의 즐겨찾기 상태 변경 (사용자별)"""
        return BookRepository.update_series_favorite(db_type, series_name, is_favorite, user_id)
