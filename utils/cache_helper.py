# -*- coding: utf-8 -*-
import os
import zipfile
import threading
from api.cache import zip_cache, disk_cache_manager

# 동일 파일에 대한 중복 로딩 방지 락
_file_load_locks = {}
_file_load_locks_mutex = threading.Lock()

def get_file_load_lock(file_path):
    with _file_load_locks_mutex:
        if file_path not in _file_load_locks:
            _file_load_locks[file_path] = threading.Lock()
        return _file_load_locks[file_path]

# ZipFile 읽기 스레드 안전성 보장용 락
_zip_read_locks = {}
_zip_read_locks_mutex = threading.Lock()

def get_zip_read_lock(file_path):
    with _zip_read_locks_mutex:
        if file_path not in _zip_read_locks:
            _zip_read_locks[file_path] = threading.Lock()
        return _zip_read_locks[file_path]

# 백그라운드 복사 진행 상태 관리
_background_copies = {}
_background_copies_lock = threading.Lock()

def start_background_copy(original_path):
    """구글 드라이브 마운트 경로의 ZIP 파일을 백그라운드에서 로컬 디스크 캐시로 조용히 복사"""
    local_path = disk_cache_manager.get_local_path(original_path)
    done_file = local_path + '.done'

    if os.path.exists(local_path) and os.path.exists(done_file):
        disk_cache_manager.update_access(local_path)
        return

    with _background_copies_lock:
        if original_path in _background_copies:
            return
        _background_copies[original_path] = True

    def _copy_thread():
        try:
            disk_cache_manager.clean_up_if_needed()
            temp_path = local_path + '.tmp'
            print(f"[DiskCacheHelper] Background copy started: {os.path.basename(original_path)} -> {os.path.basename(local_path)}")
            
            with open(original_path, 'rb') as src, open(temp_path, 'wb') as dst:
                while True:
                    chunk = src.read(1024 * 1024) # 1MB
                    if not chunk:
                        break
                    dst.write(chunk)
            
            if os.path.exists(local_path):
                os.remove(local_path)
            os.rename(temp_path, local_path)
            
            with open(done_file, 'w') as f:
                f.write('done')
                
            disk_cache_manager.update_access(local_path)
            print(f"[DiskCacheHelper] Background copy completed: {os.path.basename(original_path)}")
        except Exception as e:
            print(f"[DiskCacheHelper] Background copy failed ({os.path.basename(original_path)}): {e}")
            if os.path.exists(local_path + '.tmp'):
                try: os.remove(local_path + '.tmp')
                except: pass
        finally:
            with _background_copies_lock:
                _background_copies.pop(original_path, None)

    t = threading.Thread(target=_copy_thread, daemon=True)
    t.start()

def get_zip_file_hybrid(file_path):
    """
    하이브리드 ZIP 캐시 획득 헬퍼
    """
    local_path = disk_cache_manager.get_local_path(file_path)
    done_file = local_path + '.done'
    
    is_cached = os.path.exists(local_path) and os.path.exists(done_file)
    target_path = local_path if is_cached else file_path

    zf = zip_cache.get(target_path)
    if zf is not None:
        if is_cached:
            disk_cache_manager.update_access(local_path)
        return zf

    if not os.path.exists(target_path):
        return None

    with get_file_load_lock(target_path):
        zf = zip_cache.get(target_path)
        if zf is not None:
            return zf

        try:
            if is_cached:
                ram_zf = zipfile.ZipFile(target_path, 'r')
                disk_cache_manager.update_access(local_path)
                print(f"[DiskCacheHelper] Local cache hit: {os.path.basename(file_path)}")
            else:
                start_background_copy(file_path)
                ram_zf = zipfile.ZipFile(target_path, 'r')
                print(f"[DiskCacheHelper] Google Drive remote Seek mode activated: {os.path.basename(file_path)}")
                
            zip_cache.put(target_path, ram_zf)
            return ram_zf
        except Exception as e:
            print(f"[DiskCacheHelper] Failed to create ZIP object: {e}")
            return None
