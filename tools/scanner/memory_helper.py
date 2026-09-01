# -*- coding: utf-8 -*-
import os
import sys
import time

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database

_SETTING_CACHE_TTL_SEC = 300.0
_setting_cache = {}


def get_setting_float(key, default_value, db_type='general'):
    cache_key = f"{db_type}:{key}"
    cached = _setting_cache.get(cache_key)
    now = time.monotonic()
    if cached and (now - cached['ts'] <= _SETTING_CACHE_TTL_SEC):
        return cached['value']

    try:
        from repositories.settings_repository import SettingsRepository
        val = SettingsRepository.get_value(key)
        if val is not None and str(val).strip():
            value = float(val)
            _setting_cache[cache_key] = {'value': value, 'ts': now}
            return value
    except Exception:
        # DB 경합/disk I/O error 발생 시 기존 캐시값이 존재하면 캐시 만올 연장 후 반환 (노이즈 로그 차단)
        if cached:
            _setting_cache[cache_key]['ts'] = now
            return cached['value']

    _setting_cache[cache_key] = {'value': default_value, 'ts': now}
    return default_value


def check_memory_exceeded(db_type='general'):
    """Detect memory threshold exceeded (reflect DB settings)"""
    available_mb = None
    try:
        import psutil
        mem = psutil.virtual_memory()
        available_mb = mem.available / (1024.0 * 1024.0)
    except Exception as e:
        print(f"[Scanner-Memory] Failed to read system memory: {e}")

    # 2. Process independent physical memory occupation check (RSS)
    rss_mb = None
    try:
        import psutil
        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / (1024.0 * 1024.0)
    except Exception as e:
        print(f"[Scanner-Memory] Failed to read process memory: {e}")

    sys_limit = get_setting_float('SYSTEM_MEM_LIMIT', 1536.0, db_type=db_type)
    rss_limit = get_setting_float('PROCESS_RSS_LIMIT', 2048.0, db_type=db_type)

    system_leak = (available_mb is not None and available_mb < sys_limit)
    process_leak = (rss_mb is not None and rss_mb > rss_limit)

    if system_leak or process_leak:
        reason = []
        if system_leak:
            reason.append(f"System Available RAM insufficient ({available_mb:.1f} MB < threshold {sys_limit:.1f} MB)")
        if process_leak:
            reason.append(f"Process RSS memory exceeded ({rss_mb:.1f} MB > threshold {rss_limit:.1f} MB)")
        print(f"[Scanner-Memory] ⚠️ Memory threshold detected: {', '.join(reason)}")
        return True

    return False
