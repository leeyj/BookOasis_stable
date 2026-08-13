# -*- coding: utf-8 -*-
"""
trash_repository.py – 휴지통(is_deleted=1) 도서 복구 및 물리적 일괄 삭제 데이터 액세스 레이어.
SQL 로직은 repositories/trash_repository_shared.py 공용 모듈에 있으며, 이 클래스는
sqlite 플레이스홀더('?')만 지정하는 얇은 래퍼다.
"""
from repositories.trash_repository_shared import (
    check_cover_reference_count,
    fetch_book_covers,
    get_all_deleted_book_ids,
    get_deleted_book_ids_by_library,
    get_deleted_books,
    hard_delete_books_transaction,
    restore_books,
)

_PLACEHOLDER = '?'


class TrashRepository:
    @staticmethod
    def get_deleted_books(db_type):
        return get_deleted_books(db_type)

    @staticmethod
    def restore_books(db_type, book_ids):
        return restore_books(db_type, book_ids, _PLACEHOLDER)

    @staticmethod
    def get_deleted_book_ids_by_library(db_type, library_id):
        return get_deleted_book_ids_by_library(db_type, library_id, _PLACEHOLDER)

    @staticmethod
    def get_all_deleted_book_ids(db_type):
        return get_all_deleted_book_ids(db_type)

    @staticmethod
    def fetch_book_covers(db_type, book_ids):
        return fetch_book_covers(db_type, book_ids, _PLACEHOLDER)

    @staticmethod
    def check_cover_reference_count(db_type, cover_image):
        return check_cover_reference_count(db_type, cover_image, _PLACEHOLDER)

    @staticmethod
    def hard_delete_books_transaction(db_type, book_ids, target_covers):
        return hard_delete_books_transaction(db_type, book_ids, target_covers, _PLACEHOLDER)
