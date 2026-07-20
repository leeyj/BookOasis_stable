# -*- coding: utf-8 -*-
"""
db_tuning_service.py – 데이터베이스 물리 파일 조각 모음, 최적화 및 인덱스 정밀 튜닝 서비스 레이어
"""
import os
import sqlite3

# DB 파일 경로 참조를 위한 의존성 가져오기
import database

# DB 튜닝 진행 중 전역 상태 딕셔너리
_tuning_status = {
    'general': False,
    'adult': False
}

def is_db_tuning(db_type='general'):
    """현재 데이터베이스가 튜닝(VACUUM 등) 작업 중인지 반환"""
    return _tuning_status.get(db_type, False)

def optimize_database(db_type='general'):
    """
    데이터베이스 최적화를 수행합니다:
    1. ANALYZE를 실행해 질의 최적화 통계 갱신
    2. REINDEX를 실행해 인덱스 트리 재정렬
    3. 별도 커넥션 세션으로 VACUUM을 구동하여 삭제된 빈 물리 공간 파편화 회수
    """
    global _tuning_status
    if _tuning_status.get(db_type, False):
        print(f"[optimize_database] {db_type} database optimization is already in progress.")
        return False, "이미 최적화 작업이 진행 중입니다."
        
    _tuning_status[db_type] = True
    print(f"[*] [{db_type}] Starting database optimization engine...")
    
    try:
        from repositories.db_tuning_repository import DbTuningRepository
        DbTuningRepository.run_sqlite_optimize(db_type)
        
        print(f"[+] [{db_type}] Database defragmentation and optimization tuning successful!")
        return True, "최적화 완료"
    except Exception as e:
        print(f"[!] [{db_type}] Error during database optimization: {e}")
        return False, str(e)
    finally:
        _tuning_status[db_type] = False
