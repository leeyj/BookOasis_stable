# -*- coding: utf-8 -*-
import os
from repositories import BookRepository, AudiobookRepository, VideoRepository
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
        """특정 도서의 즐겨찾기 상태 변경 (사용자별)
        오디오북/영상은 book_id 자리에 audiobook_id/video_id가 그대로 전달되며(단일 진행 개체),
        해당 엔티티 테이블의 is_favorite 컬럼을 직접 갱신한다."""
        if db_type == 'audiobook':
            return AudiobookRepository.update_favorite(book_id, is_favorite)
        if db_type == 'video':
            return VideoRepository.update_favorite(book_id, is_favorite)
        return BookRepository.update_favorite(db_type, book_id, is_favorite, user_id)

    @staticmethod
    def update_cover_align(db_type, book_id, align):
        """도서 1권의 커버 썸네일 정렬(왼쪽/중앙/오른쪽) 변경 — 이중 페이지 스캔본 등
        표지가 한쪽으로 치우친 개별 권을 위한 book 단위 설정. 오디오북/영상은 대상 아님."""
        if db_type in ('audiobook', 'video'):
            return False
        return BookRepository.update_cover_align(db_type, book_id, align)

    @staticmethod
    def update_series_favorite(db_type, series_name, is_favorite, user_id):
        """특정 시리즈 전체 도서의 즐겨찾기 상태 변경 (사용자별)
        오디오북/영상은 "시리즈"가 곧 단일 엔티티이므로 제목으로 해당 행을 찾아 한 번에 갱신한다."""
        if db_type == 'audiobook':
            row = AudiobookRepository.get_audiobook_by_series_or_folder_name(series_name)
            return AudiobookRepository.update_favorite(row['id'], is_favorite) if row else False
        if db_type == 'video':
            row = VideoRepository.get_video_by_title_or_folder_name(series_name)
            return VideoRepository.update_favorite(row['id'], is_favorite) if row else False
        return BookRepository.update_series_favorite(db_type, series_name, is_favorite, user_id)

    @staticmethod
    def update_author_favorite(db_type, author_key, is_favorite, user_id):
        """작가별 모음 카드의 즐겨찾기 - 정규화된 작가 키(author_key)에 매칭되는
        해당 작가의 모든 작품을 일괄 즐겨찾기 등록/해제한다.
        영상 강좌는 author 필드가 항상 비어 있어(작가별 카드 자체가 생성되지 않음) 대상에서 제외."""
        from repositories.series_search_query import normalize_author_key

        if db_type == 'video':
            return False

        if db_type == 'audiobook':
            rows = AudiobookRepository.get_all_authors_with_ids()
            matched_ids = [r['id'] for r in rows if normalize_author_key(r['author']) == author_key]
            return AudiobookRepository.update_favorites_bulk(matched_ids, is_favorite)

        rows = BookRepository.get_all_authors_with_ids(db_type)
        matched_ids = [r['id'] for r in rows if normalize_author_key(r['author']) == author_key]
        return BookRepository.update_favorites_bulk(db_type, matched_ids, is_favorite, user_id)
