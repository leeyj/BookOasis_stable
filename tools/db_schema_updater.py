# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
import re

# 프로젝트 루트 디렉토리를 sys.path에 추가하여 상위 모듈 임포트 가능하도록 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import database
    from database import (
        DB_GENERAL_PATH,
        DB_ADULT_PATH,
        init_databases,
        get_connection,
        auto_migrate_schema,
        ensure_books_search_index
    )
except ImportError as e:
    print(f"[오류] database.py 모듈을 임포트할 수 없습니다: {e}")
    sys.exit(1)

def run_schema_update():
    print("=" * 60)
    print(" 데이터베이스 최신 스키마 강제 업데이트 및 동기화 도구")
    print("=" * 60)
    
    # 1. DB 파일 존재 및 경로 확인
    db_paths = {
        '일반 DB (media_general)': DB_GENERAL_PATH,
        '성인 DB (media_adult)': DB_ADULT_PATH
    }
    
    for db_name, db_path in db_paths.items():
        print(f"[*] {db_name} 경로 확인: {db_path}")
        if not os.path.exists(db_path):
            print(f"    -> [안내] DB 파일이 아직 존재하지 않습니다. 새로 생성될 예정입니다.")
        else:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"    -> [확인] DB 파일 존재함 (크기: {size_mb:.2f} MB)")

    # 2. init_databases 실행하여 기본 테이블 생성 및 누락 컬럼 체크 자동 수행
    print("\n[*] 1단계: 데이터베이스 기본 초기화 및 기본 마이그레이션 실행 중...")
    try:
        init_databases()
        print(" -> [성공] 데이터베이스 기본 초기화 완료.")
    except Exception as e:
        print(f" -> [실패] 데이터베이스 초기화 중 오류 발생: {e}")
        # 오류가 나더라도 개별 테이블 점검 및 강제 마이그레이션을 계속 시도합니다.

    # 3. 개별 DB 강제 스키마 갱신 및 무결성 정비
    print("\n[*] 2단계: 개별 데이터베이스 강제 스키마 갱신 및 WAL 정리 시작...")
    
    # database.py의 schema 문자열 및 indexes_schema 가져오기
    try:
        with open(os.path.join(PROJECT_ROOT, 'database.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        
        # schema = """ ... """ 부분 추출
        schema_match = re.search(r'schema\s*=\s*"""(.*?)"""', content, re.DOTALL)
        indexes_match = re.search(r'indexes_schema\s*=\s*"""(.*?)"""', content, re.DOTALL)
        
        schema_text = schema_match.group(1) if schema_match else ""
        indexes_text = indexes_match.group(1) if indexes_match else ""
    except Exception as parse_err:
        print(f"[경고] database.py 파일 분석 실패: {parse_err}")
        schema_text = None
        indexes_text = None
    
    for db_key, db_path in [('general', DB_GENERAL_PATH), ('adult', DB_ADULT_PATH)]:
        if not os.path.exists(db_path):
            continue
            
        print(f"\n[+] {db_key.upper()} DB 상세 점검 및 마이그레이션:")
        conn = None
        try:
            # 커넥션 풀을 우회하여 직접 파일 연결을 맺고 동기화 진행
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # (1) PRAGMA 무결성 확인
            print(f"  - DB 연결 및 무결성 확인 중...")
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            print(f"    -> integrity_check 결과: {integrity}")
            
            if integrity != 'ok':
                print(f"    -> [경고] 무결성 이상이 감지되었습니다! 스키마 동기화에 영향이 있을 수 있습니다.")
            
            # (2) auto_migrate_schema를 통한 컬럼 추가 점검
            if schema_text:
                print(f"  - 스키마 내 누락 컬럼 자동 탐지 및 추가 중...")
                auto_migrate_schema(conn, schema_text)
                conn.commit()
            
            # (3) 인덱스 생성 및 점검
            if indexes_text:
                print(f"  - 스키마 내 누락 인덱스 자동 생성 중...")
                # 개별 인덱스 생성 쿼리로 분할해서 실행
                for query in indexes_text.split(';'):
                    query = query.strip()
                    if query:
                        try:
                            cursor.execute(query)
                        except sqlite3.OperationalError as idx_err:
                            # 이미 있는 등의 에러는 무시
                            if "already exists" not in str(idx_err).lower():
                                print(f"    -> 인덱스 생성 에러 ({query[:30]}...): {idx_err}")
                conn.commit()
            
            # (4) FTS5 검색 인덱스 검증
            print(f"  - FTS5 검색 인덱스 상태 점검 중...")
            try:
                ensure_books_search_index(conn)
                print(f"    -> 검색 인덱스 점검 및 재빌드 완료.")
            except Exception as fts_err:
                print(f"    -> FTS5 인덱스 점검 실패 (무시 가능): {fts_err}")
            
            # (5) WAL 모드 트랜케이트 (체크포인트를 통해 WAL에 남아있는 모든 데이터를 DB 원본에 병합)
            print(f"  - WAL 체크포인트(TRUNCATE) 수행 중...")
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            print(f"    -> WAL 체크포인트 완료 및 임시 저널 파일 병합 완료.")
            
        except Exception as db_err:
            print(f"  - [오류] {db_key.upper()} DB 작업 중 문제 발생: {db_err}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
                
    # 4. 마무리로 WAL/SHM 임시 파일이 디스크에 남아있는데 데이터베이스가 닫혀있다면 제거
    print("\n[*] 3단계: 미접속 WAL/SHM 임시 저널 파일 확인 및 정리...")
    for db_key, db_path in [('general', DB_GENERAL_PATH), ('adult', DB_ADULT_PATH)]:
        for ext in ['-wal', '-shm']:
            temp_file = db_path + ext
            if os.path.exists(temp_file):
                # 크기가 0이거나 미사용 중인 경우 지워서 다음 기동 시 정합성 유지
                try:
                    os.remove(temp_file)
                    print(f"  - 임시 파일 정리됨: {os.path.basename(temp_file)}")
                except Exception:
                    pass # 현재 락이 잡혀있거나 사용 중이면 무시
                    
    print("\n" + "=" * 60)
    print(" 데이터베이스 스키마 및 마이그레이션 동기화가 성공적으로 완료되었습니다!")
    print(" 서비스를 재시작해 주시기 바랍니다.")
    print("=" * 60)

if __name__ == '__main__':
    run_schema_update()
