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
        print(f"[Scanner-Memory] 설정 읽기 실패 ({key}): {e}")
    return default_value

def check_memory_exceeded():
    """메모리 임계점 초과 여부 감지 (DB 설정 반영)"""
    available_mb = None
    try:
        import psutil
        mem = psutil.virtual_memory()
        available_mb = mem.available / (1024.0 * 1024.0)
    except Exception as e:
        print(f"[Scanner-Memory] 시스템 메모리 읽기 실패: {e}")

    # 2. 프로세스 단독 물리 메모리 점유 체크 (RSS)
    rss_mb = None
    try:
        import psutil
        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / (1024.0 * 1024.0)
    except Exception as e:
        print(f"[Scanner-Memory] 프로세스 메모리 읽기 실패: {e}")

    sys_limit = get_setting_float('SYSTEM_MEM_LIMIT', 1536.0)
    rss_limit = get_setting_float('PROCESS_RSS_LIMIT', 2048.0)

    system_leak = (available_mb is not None and available_mb < sys_limit)
    process_leak = (rss_mb is not None and rss_mb > rss_limit)

    if system_leak or process_leak:
        reason = []
        if system_leak:
            reason.append(f"System Available RAM 부족 ({available_mb:.1f} MB < 임계치 {sys_limit:.1f} MB)")
        if process_leak:
            reason.append(f"Process RSS 메모리 초과 ({rss_mb:.1f} MB > 임계치 {rss_limit:.1f} MB)")
        print(f"[Scanner-Memory] ⚠️ 메모리 임계치 감지: {', '.join(reason)}")
        return True

    return False
