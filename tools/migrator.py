import os
import sys
import sqlite3
import shutil
from datetime import datetime

def select_file_via_gui():
    """GUI 파일 선택 창을 띄워 사용자가 DB 파일을 선택할 수 있도록 합니다."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()  # 메인 GUI 창은 숨김
        file_path = filedialog.askopenfilename(
            title="수정할 SQLite DB 파일을 선택하세요",
            filetypes=[("Database Files", "*.db *.sqlite *.sqlite3 *.db3"), ("All Files", "*.*")]
        )
        return file_path
    except Exception as e:
        print(f"GUI 창을 열 수 없습니다. 직접 경로 입력 모드로 전환합니다. (에러: {e})")
        return None

def backup_db(db_path):
    """안전한 작업을 위해 수정 전에 기존 DB 파일의 백업본(.bak)을 생성합니다."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.{timestamp}.bak"
    shutil.copy2(db_path, backup_path)
    print(f"\n[안내] 원본 데이터베이스 백업 완료: {backup_path}")
    return backup_path

def replace_string_in_db(db_path, target_str, replacement_str, conflict_mode="IGNORE"):
    """DB 내의 모든 테이블과 텍스트 필드를 탐색하여 문자열을 치환합니다.
    conflict_mode: UNIQUE 제약조건 충돌 발생 시 처리 모드 ('IGNORE' 또는 'REPLACE')
    """
    if not os.path.exists(db_path):
        print(f"오류: 해당 경로에 파일이 존재하지 않습니다: {db_path}")
        return

    # 1. 백업본 생성
    backup_db(db_path)

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 2. 데이터베이스 내의 모든 테이블 이름 가져오기
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        total_updated_rows = 0
        print("\n치환 작업 시작...")

        for table in tables:
            # SQLite 내부 시스템 테이블은 수정 대상에서 제외
            if table.startswith("sqlite_"):
                continue

            # 3. 테이블 내의 모든 컬럼 정보(이름 및 데이터 타입) 조회
            cursor.execute(f"PRAGMA table_info(`{table}`);")
            columns_info = cursor.fetchall()

            for col_info in columns_info:
                col_name = col_info[1]
                col_type = col_info[2].upper()

                # 텍스트 데이터를 가질 수 있는 컬럼 타입만 필터링 (동적 타입 포함)
                is_text_like = any(t in col_type for t in ["TEXT", "CHAR", "CLOB", "VARCHAR", ""])

                if is_text_like:
                    try:
                        # 4. 해당 컬럼에서 타겟 문자열이 들어있는 행만 업데이트 (중복 충돌 제어 포함)
                        update_query = f"""
                            UPDATE OR {conflict_mode} `{table}`
                            SET `{col_name}` = REPLACE(`{col_name}`, ?, ?)
                            WHERE `{col_name}` LIKE ?
                        """
                        like_pattern = f"%{target_str}%"

                        cursor.execute(update_query, (target_str, replacement_str, like_pattern))

                        # 업데이트된 행 수 확인
                        if cursor.rowcount > 0:
                            print(f"  - [{table}] 테이블의 '{col_name}' 컬럼: {cursor.rowcount}개 행 수정 완료")
                            total_updated_rows += cursor.rowcount

                    except sqlite3.OperationalError:
                        # 뷰(View)나 읽기 전용 컬럼, 혹은 가상 테이블 등은 스킵
                        pass

        # 5. 변경사항 커밋
        conn.commit()
        print(f"\n[성공] 치환 작업이 완료되었습니다! 총 {total_updated_rows}개의 데이터가 변경되었습니다.")

    except Exception as e:
        print(f"\n[오류] 데이터베이스 처리 중 문제가 발생했습니다: {e}")
        if conn:
            conn.rollback()
            print("[롤백] 변경 사항을 모두 취소하고 이전 상태로 되돌렸습니다.")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # 치환 설정값
    TARGET_STR = "/data/comics"
    REPLACEMENT_STR = "/mnt/gds2/GDRIVE/READING"

    db_file = None

    # 1. 인자로 파일 경로를 넘겨받은 경우 (예: python redb.py ./db/media_general.db)
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    else:
        # 2. 인자가 없으면 GUI 파일 탐색기를 띄움
        print("파일 선택 창을 통해 수정할 DB 파일을 선택해 주세요...")
        db_file = select_file_via_gui()

        # 3. GUI를 취소했거나 사용할 수 없을 경우 터미널에서 직접 경로 입력 받기
        if not db_file:
            db_file = input("DB 파일의 절대 경로를 직접 입력하세요: ").strip()
            # 윈도우 탐색기에서 경로 복사 시 양끝에 붙는 따옴표 제거
            db_file = db_file.strip("'\"")

    if db_file and os.path.exists(db_file):
        print(f"\n- 선택된 파일: {db_file}")
        print(f"- 치환 작업: '{TARGET_STR}'  ===>  '{REPLACEMENT_STR}'")

        # UNIQUE 제약 조건 충돌 방안 선택
        print("\n[경고] 이미 변경하려는 경로가 DB에 등록되어 있으면 중복 에러(UNIQUE constraint failed)가 발생할 수 있습니다.")
        print("중복 에러가 발생했을 때 해결 방법을 선택하세요:")
        print("  1. IGNORE  (중복되는 기존 데이터 유지, 변경하려는 항목은 건너뜀 - 안전)")
        print("  2. REPLACE (기존의 중복된 데이터를 지우고, 변경하려는 항목으로 덮어씀)")
        mode_input = input("선택 (1 또는 2, 기본값: 1): ").strip()

        conflict_mode = "REPLACE" if mode_input == "2" else "IGNORE"

        confirm = input(f"\n[{conflict_mode}] 모드로 정말로 이 파일의 내용을 치환하시겠습니까? (y/n): ").strip().lower()
        if confirm == 'y':
            replace_string_in_db(db_file, TARGET_STR, REPLACEMENT_STR, conflict_mode)
        else:
            print("사용자가 취소하여 작업을 중단합니다.")
    else:
        print("\n[경고] 올바른 DB 파일 경로가 지정되지 않았습니다.")