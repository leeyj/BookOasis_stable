# -*- coding: utf-8 -*-
import os
import sqlite3
import argparse

# Path configuration
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_SERVER_DIR = os.path.dirname(TOOLS_DIR)
DB_DIR = os.path.join(MEDIA_SERVER_DIR, 'db')
COVERS_DIR = os.path.join(MEDIA_SERVER_DIR, 'covers')

DB_PATHS = {
    'general': os.path.join(DB_DIR, 'media_general.db'),
    'adult': os.path.join(DB_DIR, 'media_adult.db')
}

def clean_unused_covers(delete_mode=False):
    print("=== [BookOasis] 미사용 구형 커버 이미지 정리 유틸리티 기동 ===")
    if not delete_mode:
        print("[NOTICE] 현재 모드는 '--dry-run' (시뮬레이션) 입니다. 실제 삭제는 진행되지 않습니다.")
        print("[NOTICE] 물리적 파일 삭제를 적용하려면 '--delete' 옵션을 추가하여 실행하세요.")
    
    # 1. DB에서 active 참조 중인 표지 이미지 파일명 수집
    active_covers = set()
    for db_name, db_path in DB_PATHS.items():
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT cover_image FROM books WHERE cover_image IS NOT NULL AND cover_image != ''")
            rows = cursor.fetchall()
            for r in rows:
                active_covers.add(r['cover_image'])
            conn.close()
            print(f"[+] '{db_name}' DB 로드 완료. 활성 커버 레코드 수: {len(rows)}개")
        except Exception as e:
            print(f"[!] '{db_name}' DB 쿼리 중 오류 발생: {e}")

    if not active_covers:
        print("[!] DB에서 활성화된 표지 레코드를 발견하지 못했습니다. 안전을 위해 물리 파일 정리를 종료합니다.")
        return

    # 2. covers 디렉토리 내 실제 파일 스캔 및 비교
    if not os.path.exists(COVERS_DIR):
        print(f"[!] 커버 폴더가 존재하지 않습니다: {COVERS_DIR}")
        return

    all_physical_files = os.listdir(COVERS_DIR)
    unused_files = []
    total_saved_size = 0

    for filename in all_physical_files:
        filepath = os.path.join(COVERS_DIR, filename)
        # 디렉토리 제외 및 순수 파일 대상 판별
        if not os.path.isfile(filepath):
            continue
        
        # 기본 디폴트 커버 이미지는 소거 대상에서 보존
        if filename == 'default_cover.jpg':
            continue

        # DB에서 쓰이지 않는 미사용 파일 수집
        if filename not in active_covers:
            try:
                fsize = os.path.getsize(filepath)
                unused_files.append((filename, filepath, fsize))
                total_saved_size += fsize
            except Exception:
                pass

    print(f"[*] 분석 완료: 물리 파일 총 {len(all_physical_files)}개 중 미사용 파일 {len(unused_files)}개 검출")
    
    if not unused_files:
        print("[+] 정리할 미사용 표지 파일이 없습니다. 디스크가 무결한 상태입니다.")
        return

    # 3. 결과 출력 및 삭제 실행 분기
    print("\n--- [미사용 대상 파일 목록 (상위 최대 50개 출력)] ---")
    for idx, (fname, fpath, fsize) in enumerate(unused_files[:50]):
        size_kb = fsize / 1024.0
        print(f"  [{idx+1}] {fname} ({size_kb:.2f} KB)")
    if len(unused_files) > 50:
        print(f"  ...외 {len(unused_files) - 50}개 파일 추가 존재 ...")
    
    total_saved_mb = total_saved_size / (1024.0 * 1024.0)
    print(f"\n[!] 예상 확보 가능 디스크 공간: {total_saved_mb:.2f} MB")

    if delete_mode:
        print("\n[*] 경고: 실제 파일 제거 작업을 시작합니다...")
        success_count = 0
        fail_count = 0
        for fname, fpath, fsize in unused_files:
            try:
                os.remove(fpath)
                success_count += 1
            except Exception as ex:
                fail_count += 1
                print(f"[!] 파일 제거 실패 '{fname}': {ex}")
        print(f"[+] 정리 완료! 성공: {success_count}개 파일 삭제됨, 실패: {fail_count}개")
        print(f"[+] 최종 확보 공간: {total_saved_mb:.2f} MB")
    else:
        print("\n[+] 시뮬레이션 완료. 실제 파일 삭제가 필요할 경우 아래 명령어 형태로 실행하십시오:")
        print("    python tools/clean_unused_covers.py --delete")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="BookOasis Unused Cover Cleanup Tool")
    parser.add_argument('--delete', action='store_true', help="실제 미사용 정적 커버 파일들을 일괄 삭제합니다.")
    args = parser.parse_args()
    
    clean_unused_covers(delete_mode=args.delete)
