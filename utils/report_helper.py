# -*- coding: utf-8 -*-
import os
import json
import glob
from datetime import datetime

# cache/reports 디렉터리 경로 결정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, 'cache', 'reports')

def get_reports_dir():
    """리포트 저장 폴더 생성 및 반환"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR

def save_scan_report(library_id, error_list):
    """
    스캔 결과 감지된 오류 목록을 {library_id}_{timestamp}.json 파일로 저장합니다.
    이후 해당 library_id 기준 리포트 수가 10개를 초과할 시 가장 오래된 파일을 순환 소거합니다.
    """
    if not error_list:
        print(f"[ReportHelper] 카테고리 {library_id} 에러 내역이 없어 리포트 저장을 생략합니다.")
        return None

    reports_dir = get_reports_dir()
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{library_id}_{timestamp}.json"
    file_path = os.path.join(reports_dir, filename)

    report_data = {
        'library_id': library_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'errors_count': len(error_list),
        'errors': error_list
    }

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=4)
        print(f"[ReportHelper] 📄 스캔 에러 리포트 저장 성공: {file_path}")
    except Exception as e:
        print(f"[ReportHelper ERROR] 리포트 파일 저장 실패: {e}")
        return None

    # 카테고리(library_id)별 링 버퍼 순환 소거 실행 (최대 10개 유지)
    try:
        pattern = os.path.join(reports_dir, f"{library_id}_*.json")
        existing_files = glob.glob(pattern)
        
        # 파일 이름(타임스탬프 포함) 기준으로 정렬하여 가장 오래된 것부터 추출
        existing_files.sort(key=os.path.basename)
        
        if len(existing_files) > 10:
            excess = len(existing_files) - 10
            for i in range(excess):
                old_file = existing_files[i]
                try:
                    os.remove(old_file)
                    print(f"[ReportHelper] ♻️ 순환 소거 정책에 따라 구형 리포트 물리 삭제: {old_file}")
                except Exception as del_err:
                    print(f"[ReportHelper ERROR] 구형 리포트 제거 실패: {del_err}")
    except Exception as e:
        print(f"[ReportHelper ERROR] 리포트 순환 정리 도중 에러: {e}")

    return filename

def delete_all_reports(library_id):
    """카테고리 삭제 시, 해당 library_id로 시작하는 모든 리포트 파일을 일괄 제거합니다."""
    reports_dir = get_reports_dir()
    pattern = os.path.join(reports_dir, f"{library_id}_*.json")
    try:
        files = glob.glob(pattern)
        removed_count = 0
        for f in files:
            try:
                os.remove(f)
                removed_count += 1
            except Exception as e:
                print(f"[ReportHelper ERROR] 리포트 파일 개별 제거 실패 ({f}): {e}")
        if removed_count > 0:
            print(f"[ReportHelper] 🗑️ 카테고리 {library_id} 삭제에 따라 연계 리포트 {removed_count}개 일괄 삭제 완료.")
        return True
    except Exception as e:
        print(f"[ReportHelper ERROR] 카테고리 {library_id} 연계 리포트 파일 조회 실패: {e}")
        return False
