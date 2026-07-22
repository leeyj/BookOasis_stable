# -*- coding: utf-8 -*-
from services.stream_page_service import (
    IMG_EXT,
    get_img_files,
    get_imgdir_files,
    StreamPageService,
)
from services.reading_progress_service import ReadingProgressService
from services.text_epub_content_service import TextEpubContentService


class StreamService:
    @staticmethod
    def get_book_file_info(db_type, book_id, user_id=None, role=None):
        return StreamPageService.get_book_file_info(db_type, book_id, user_id=user_id, role=role)

    @staticmethod
    def get_total_pages_for_book(db_type, book_id, file_path=None, file_format=None):
        return StreamPageService.get_total_pages_for_book(
            db_type,
            book_id,
            file_path=file_path,
            file_format=file_format,
        )

    @staticmethod
    def extract_page(file_path: str, page_idx: int, db_type: str = 'general', book_id=None):
        return StreamPageService.extract_page(file_path, page_idx, db_type=db_type, book_id=book_id)

    @staticmethod
    def record_progress(db_type: str, book_id, page_idx: int, total_pages: int, user_id=1, epub_session=None):
        return ReadingProgressService.record_progress(
            db_type,
            book_id,
            page_idx,
            total_pages,
            user_id=user_id,
            epub_session=epub_session,
        )

    @staticmethod
    def get_progress_state(db_type: str, book_id, user_id=1):
        return ReadingProgressService.get_progress_state(db_type, book_id, user_id=user_id)

    @staticmethod
    def get_txt_content(file_path):
        return TextEpubContentService.get_txt_content(file_path)

    @staticmethod
    def get_file_path(db_type, book_id, user_id=None, role=None):
        return StreamPageService.get_file_path(db_type, book_id, user_id=user_id, role=role)

    @staticmethod
    def get_epub_content(file_path, book_id, db_type):
        return TextEpubContentService.get_epub_content(file_path, book_id, db_type)

    @staticmethod
    def get_epub_meta(file_path, book_id, db_type):
        return TextEpubContentService.get_epub_meta(file_path, book_id, db_type)

    @staticmethod
    def get_epub_chapter(file_path, book_id, db_type, chapter_idx):
        return TextEpubContentService.get_epub_chapter(file_path, book_id, db_type, chapter_idx)

    @staticmethod
    def extract_epub_resource(file_path, resource_path):
        return TextEpubContentService.extract_epub_resource(file_path, resource_path)
