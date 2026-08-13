# -*- coding: utf-8 -*-
"""
lru_cache.py – 개수 기반 LRU 캐시(스레드 안전). 프로젝트 의존성이 전혀 없는 leaf 모듈이라
api/cache.py와 repositories/{mariadb,sqlite}/book_offset_repository.py 양쪽에서 순환참조 없이 공용으로 쓴다.
"""
import threading
from collections import OrderedDict


class LRUCache:
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
