# -*- coding: utf-8 -*-
"""
book_offset_repository.py – ZIP 파일 압축 해제 고속화 오프셋 정보(book_offsets) 전담 데이터 액세스 레이어
"""
import threading
from collections import OrderedDict
import database

# ─── 로컬 LRU 캐시 (api.cache 임포트 시 순환 의존성 방지를 위해 인라인 정의) ───
class _LRUCache:
    """개수 기반 LRU 캐시 – 스레드 안전"""
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.cache    = OrderedDict()
        self.lock     = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

_offset_cache = _LRUCache(capacity=5000)


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
            SELECT filename, local_header_offset, compress_size, file_size, compress_type
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
