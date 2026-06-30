# -*- coding: utf-8 -*-
import os
import sys

MEDIA_SERVER_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if MEDIA_SERVER_DIR not in sys.path:
    sys.path.append(MEDIA_SERVER_DIR)

import database

def get_setting_float(key, default_value):
    try:
        conn = database.get_connection('general')
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row['value']:
            return float(row['value'])
    except Exception as e:
        print(f"[Scanner-Memory] Failed to read setting ({key}): {e}")
    return default_value

def check_memory_exceeded():
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

    sys_limit = get_setting_float('SYSTEM_MEM_LIMIT', 1536.0)
    rss_limit = get_setting_float('PROCESS_RSS_LIMIT', 2048.0)

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
