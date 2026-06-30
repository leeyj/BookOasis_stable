# -*- coding: utf-8 -*-
"""
cache.py – 미디어 서버 공용 캐시 모듈
  - SizedLRUCache: 바이트 크기 기반 LRU 캐시 (이미지 RAM 캐시용)
  - LRUCache     : 개수 기반 LRU 캐시 (ZIP 객체 / namelist 캐시용)
"""
import threading
from collections import OrderedDict

# ─── 캐시 설정 상수 ───────────────────────────────────────────
IMAGE_CACHE_MAX_BYTES = 8 * 1024 * 1024 * 1024   # 8 GB
PREFETCH_AHEAD        = 4                          # 미리 추출할 페이지 수
ZIP_CACHE_CAPACITY    = 5                          # 열어둘 ZIP 파일 최대 수

# 로컬 디스크 캐시 설정 (구글 드라이브 마운트 레이턴시 극복용)
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISK_CACHE_DIR = os.path.join(BASE_DIR, 'cache')
DISK_CACHE_MAX_BYTES = 5 * 1024 * 1024 * 1024    # 5 GB (최대 캐시 용량)
DISK_CACHE_MAX_FILES = 10                         # 열어둘 로컬 디스크 파일 최대 수
os.makedirs(DISK_CACHE_DIR, exist_ok=True)



class SizedLRUCache:
    """
    바이트 크기 기반 LRU 캐시.
    총 메모리 사용량(bytes)으로 상한을 제어하며,
    초과 시 가장 오래된 항목부터 자동 퇴출(evict)합니다.
    스레드 안전합니다.
    """
    def __init__(self, max_bytes: int):
        self.max_bytes     = max_bytes
        self.cache         = OrderedDict()   # key -> (value, size_bytes)
        self.current_bytes = 0
        self.lock          = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key][0]

    def put(self, key, value, size_bytes: int):
        with self.lock:
            if key in self.cache:
                self.current_bytes -= self.cache[key][1]
                self.cache.move_to_end(key)
            self.cache[key] = (value, size_bytes)
            self.current_bytes += size_bytes
            # 상한 초과 시 오래된 항목 퇴출
            while self.current_bytes > self.max_bytes and self.cache:
                _, (_, evicted_size) = self.cache.popitem(last=False)
                self.current_bytes -= evicted_size

    def stats(self) -> dict:
        with self.lock:
            return {
                'items'  : len(self.cache),
                'used_mb': round(self.current_bytes / 1024 / 1024, 1),
                'max_gb' : round(self.max_bytes / 1024 / 1024 / 1024, 1),
            }


class LRUCache:
    """
    개수 기반 LRU 캐시 (ZIP 파일 객체 / namelist 용).
    스레드 안전합니다.
    """
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


# ─── 공용 캐시 인스턴스 (모듈 싱글턴) ────────────────────────
zip_cache      = LRUCache(capacity=ZIP_CACHE_CAPACITY)       # ZipFile 객체
namelist_cache = LRUCache(capacity=ZIP_CACHE_CAPACITY)       # 정렬된 이미지 목록
image_cache    = SizedLRUCache(max_bytes=IMAGE_CACHE_MAX_BYTES)  # 이미지 bytes


class DiskCacheManager:
    """로컬 디스크 캐시 파일들의 LRU 정리와 메타 관리를 스레드 안전하게 처리"""
    def __init__(self, cache_dir, max_bytes, max_files):
        self.cache_dir = cache_dir
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.lock = threading.Lock()

    def get_local_path(self, original_path):
        import hashlib
        # 원본 파일 경로 해시값으로 고유 파일명 생성
        path_hash = hashlib.md5(original_path.encode('utf-8')).hexdigest()
        _, ext = os.path.splitext(original_path)
        return os.path.join(self.cache_dir, f"{path_hash}{ext}")

    def update_access(self, local_path):
        """접근 시간을 업데이트하여 LRU 순서를 보장"""
        with self.lock:
            if os.path.exists(local_path):
                os.utime(local_path, None)

    def clean_up_if_needed(self):
        """캐시 용량 혹은 개수 초과 시 오래된(mtime 기준) 파일부터 삭제"""
        with self.lock:
            if not os.path.exists(self.cache_dir):
                return

            files = []
            for name in os.listdir(self.cache_dir):
                # 복사 완료를 뜻하는 .done 파일 및 현재 복사 중인 .tmp 임시 파일은 제외하고 실제 zip 파일만 검사
                if name.endswith('.done') or name.endswith('.tmp'):
                    continue
                fpath = os.path.join(self.cache_dir, name)
                if os.path.isfile(fpath):
                    files.append((fpath, os.path.getmtime(fpath), os.path.getsize(fpath)))

            # 가장 오래된(mtime이 작은) 순서대로 정렬
            files.sort(key=lambda x: x[1])

            total_size = sum(x[2] for x in files)
            total_count = len(files)

            while (total_size > self.max_bytes or total_count > self.max_files) and files:
                oldest_file, _, fsize = files.pop(0)
                try:
                    os.remove(oldest_file)
                    # 동반된 .done 지시 파일이 있다면 함께 지움
                    done_file = oldest_file + '.done'
                    if os.path.exists(done_file):
                        os.remove(done_file)
                    total_size -= fsize
                    total_count -= 1
                    print(f"[DiskCache] LRU eviction completed: {os.path.basename(oldest_file)}")
                except Exception as e:
                    print(f"[DiskCache] LRU eviction error: {e}")

disk_cache_manager = DiskCacheManager(DISK_CACHE_DIR, DISK_CACHE_MAX_BYTES, DISK_CACHE_MAX_FILES)

