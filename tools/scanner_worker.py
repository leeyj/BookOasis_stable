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
    run_scanner_worker_loop()
