"""스캔 이력 로그(logs/scan_history.log) 기록 공용 헬퍼.

scheduler_service.py(라이브러리 스캔)와 cover_scan_service.py(표지 전용 스캔)에
거의 동일한 로그 파일 경로 계산 + 타임스탬프 접두 로직이 각각 따로 있던 것을 통합했다.
"""
import os
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
_LOG_FILE_PATH = os.path.join(_LOG_DIR, 'scan_history.log')


def write_scan_log(message):
    """logs/scan_history.log에 '[YYYY-MM-DD HH:MM:SS] message' 형태로 한 줄 추가 기록한다."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_FILE_PATH, 'a', encoding='utf-8') as f_log:
            f_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as ex_log:
        print(f"[ScanLogger ERROR] Failed to write log file: {ex_log}")
