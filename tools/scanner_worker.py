# -*- coding: utf-8 -*-
"""
scanner_worker.py – 독립 백그라운드 스캐너 워커 기동 스크립트
"""
import os
import sys

# 현재 파일의 상위 상위 디렉토리를 sys.path에 추가하여 모듈 참조 보장
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.scanner_queue import run_scanner_worker_loop

if __name__ == '__main__':
    # ─── .env 환경 변수 로드 ───
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(BASE_DIR, '.env')
        load_dotenv(env_path)
    except Exception as env_err:
        print(f"[Scanner-Worker] .env 로드 실패: {env_err}")

    # ─── 유령 태스크 및 고착 스캔 상태 부팅 시점 자동 정화 ───
    try:
        from repositories.sqlite.scanner_queue_repository import ScannerQueueRepository
        ScannerQueueRepository.startup_cleanup_ghost_tasks()
    except Exception as clean_err:
        print(f"[Scanner-Worker] 부팅 시점 유령 태스크 정화 실패: {clean_err}")

    run_scanner_worker_loop()
