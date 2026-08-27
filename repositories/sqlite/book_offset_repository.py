# -*- coding: utf-8 -*-
"""
book_offset_repository.py – ZIP 파일 압축 해제 고속화 오프셋 정보(book_offsets) 전담 데이터 액세스 레이어
"""
import database
# utils/lru_cache.py는 project 의존성이 없는 leaf 모듈이라 api.cache를 거치지 않고도
# 순환참조 없이 여기서 바로 LRUCache를 재사용할 수 있다.
from utils.lru_cache import LRUCache

_offset_cache = LRUCache(capacity=5000)


class BookOffsetRepository:
    @staticmethod
    def get_book_offset(db_type, book_id, page_idx):
        """특정 도서 및 페이지 인덱스에 해당하는 ZIP 압축 파일 헤더 오프셋 데이터 조회 (LRU 캐시 적용)"""
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
            WHERE book_id = ? AND page_idx = ?
            """,
            (book_id, page_idx),
        )
        row = cursor.fetchone()
        conn.close()

        res = dict(row) if row else 'NOT_FOUND'
        _offset_cache.put(cache_key, res)
        return dict(row) if row else None
