# -*- coding: utf-8 -*-
"""
book_offset_repository.py – MariaDB 전용 ZIP 파일 압축 해제 고속화 오프셋 정보(book_offsets) 데이터 액세스 레이어
"""
import database
from utils.lru_cache import LRUCache

_offset_cache = LRUCache(capacity=5000)

class BookOffsetRepository:
    @staticmethod
    def get_book_offset(db_type, book_id, page_idx):
        cache_key = f"{db_type}:{book_id}:{page_idx}"
        cached = _offset_cache.get(cache_key)
        if cached is not None:
            return cached if cached != 'NOT_FOUND' else None

        conn = database.get_connection(db_type)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT filename, local_header_offset, compress_size, file_size, compress_type, data_offset
            FROM book_offsets
            WHERE book_id = %s AND page_idx = %s
            """,
            (book_id, page_idx),
        )
        row = cursor.fetchone()
        conn.close()

        res = dict(row) if row else 'NOT_FOUND'
        _offset_cache.put(cache_key, res)
        return dict(row) if row else None
