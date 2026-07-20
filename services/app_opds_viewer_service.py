# -*- coding: utf-8 -*-
"""Service layer for App OPDS viewer compatibility endpoints."""

import mimetypes
import os

import database
from services.stream_service import StreamService


def get_stream_page(db_type: str, book_id: int, page_idx: int, user_id: int = 1, role=None):
    file_path, file_format = StreamService.get_book_file_info(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return {'status': 'book_not_found'}

    result = StreamService.extract_page(file_path, page_idx, db_type=db_type, book_id=book_id)
    if result is None:
        return {'status': 'extract_failed'}

    img_data, mime_type = result

    try:
        total_pages = StreamService.get_total_pages_for_book(
            db_type,
            book_id,
            file_path=file_path,
            file_format=file_format,
        )
        if total_pages > 0:
            StreamService.record_progress(db_type, book_id, page_idx, total_pages, user_id=user_id)
    except Exception as e:
        print(f"[App-OPDS Progress Recorder] Fail: {e}")

    return {'status': 'ok', 'img_data': img_data, 'mime_type': mime_type}


def get_txt_content(db_type: str, book_id, user_id: int = 1, role=None):
    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return {'status': 'book_not_found'}

    content, error = StreamService.get_txt_content(file_path)
    if error:
        if error == 'File not found':
            return {'status': 'file_not_found'}
        return {'status': 'error', 'error': error}

    return {'status': 'ok', 'content': content}


def get_pdf_source(db_type: str, book_id, user_id: int = 1, role=None):
    file_path = StreamService.get_file_path(db_type, book_id, user_id=user_id, role=role)
    if not file_path:
        return {'status': 'book_not_found'}
    if not os.path.exists(file_path):
        return {'status': 'file_not_found'}

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext == '.epub':
        mime = 'application/epub+zip'
    elif ext == '.pdf':
        mime = 'application/pdf'
    elif ext == '.txt':
        mime = 'text/plain'
    else:
        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or 'application/octet-stream'

    return {'status': 'ok', 'file_path': file_path, 'mime': mime}


def get_progress_state(db_type: str, book_id, user_id: int = 1):
    state = StreamService.get_progress_state(db_type, book_id, user_id=user_id)
    if not state:
        return {'status': 'book_not_found'}
    return {'status': 'ok', 'state': state}


def save_progress(db_type: str, book_id, page_idx, total_pages, epub_session=None, user_id: int = 1):
    if total_pages is None:
        total_pages = 1
    StreamService.record_progress(
        db_type,
        book_id,
        page_idx,
        total_pages,
        user_id=user_id,
        epub_session=epub_session,
    )


def mark_unread(db_type: str, book_id, user_id: int = 1):
    from repositories.reading_progress_repository import ReadingProgressRepository
    ReadingProgressRepository.delete_user_progress_by_book(db_type, book_id, user_id)


def preload_next_book(db_type: str, book_id, user_id: int = 1):
    from services.book_service import BookService
    from utils.cache_helper import start_background_copy

    next_book = BookService.get_next_book(db_type, book_id, user_id=user_id)
    if not next_book or not next_book.get('file_path'):
        return {'status': 'no_next'}

    next_file_path = next_book['file_path']
    if os.path.exists(next_file_path):
        start_background_copy(next_file_path)
        print(f"[App-OPDS Viewer-Preload] Preloading next book successfully: {next_book['title']}")
        return {'status': 'ok', 'preloaded_book_id': next_book['id']}

    return {'status': 'next_not_exist'}
