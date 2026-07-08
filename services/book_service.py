# -*- coding: utf-8 -*-
import os
import database
from utils.sort_helper import natural_sort_key
from utils.cover_helper import get_cover_image_with_t

class BookService:
    @staticmethod
    def get_next_book(db_type, book_id, user_id=1):
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        
        # 1. 대상 책의 series_name, library_id, file_path 조회
        cursor.execute("SELECT series_name, library_id, file_path FROM books WHERE id = ? AND COALESCE(is_deleted, 0) = 0", (book_id,))
        current_book = cursor.fetchone()
        if not current_book:
            conn.close()
            return None

        series_name = current_book['series_name']
        library_id = current_book['library_id']
        current_file_path = current_book['file_path']

        # 2. 같은 시리즈 내의 책 전체 조회 (진척도 결합)
        cursor.execute("""
            SELECT b.id, b.title, b.file_format, b.total_pages, b.cover_image, b.cover_updated_at, b.file_path, p.pages_read
            FROM books b
            LEFT JOIN user_progress p ON b.id = p.book_id AND p.user_id = ?
            WHERE COALESCE(b.is_deleted, 0) = 0 AND b.series_name = ? AND b.library_id = ?
        """, (user_id, series_name, library_id))
        rows = cursor.fetchall()
        conn.close()

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
    def update_favorite(db_type, book_id, is_favorite):
        """특정 도서의 즐겨찾기 상태 변경"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET is_favorite = ? WHERE id = ?", (is_favorite, book_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def update_series_favorite(db_type, series_name, is_favorite):
        """특정 시리즈 전체 도서의 즐겨찾기 상태 변경"""
        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET is_favorite = ? WHERE series_name = ?", (is_favorite, series_name))
        conn.commit()
        conn.close()
        return True
