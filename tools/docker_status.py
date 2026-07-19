# -*- coding: utf-8 -*-
import os
import sys
import sqlite3

# 프로젝트 루트 디렉토리를 sys.path에 추가하여 상위 모듈 임포트 가능하도록 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PID_FILE = os.path.join(PROJECT_ROOT, "media_server.pid")
WORKER_PID_FILE = os.path.join(PROJECT_ROOT, "media_server_worker.pid")
DB_DIR = os.path.join(PROJECT_ROOT, "db")

def check_process_alive_by_pid(pid):
    """os.kill(pid, 0)을 사용하여 프로세스가 실제로 살아있는지 판별합니다."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_pid_from_file(file_path):
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    except Exception:
        pass
    return None

def find_processes_by_cmdline(pattern):
    """
    /proc 파일시스템을 직접 분석하여 cmdline에 pattern이 들어있는 PID 목록을 반환합니다.
    (ps 유틸리티가 없을 때를 대비한 독립형 구현)
    """
    pids = []
    if not os.path.exists("/proc"):
        return pids
        
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                cmd_path = os.path.join("/proc", name, "cmdline")
                if os.path.exists(cmd_path):
                    with open(cmd_path, "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore").replace("\x00", " ")
                        if pattern in cmdline:
                            pids.append(int(name))
            except Exception:
                pass
    return pids

def check_db_integrity(db_path):
    if not os.path.exists(db_path):
        return "⚠️ 파일 없음 (미생성)"
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()[0]
        conn.close()
        if res == "ok":
            return "✅ 무결성 정상 (OK)"
        else:
            return f"❌ 손상됨 (오류: {res})"
    except Exception as e:
        return f"❌ 접속 실패 ({e})"

def main():
    print("=" * 60)
    print(" [BookOasis] 도커 컨테이너 내부 서비스 및 DB 상태 실시간 리포트")
    print("=" * 60)

    # 1. 미디어 웹 서버 점검
    web_pid = get_pid_from_file(PID_FILE)
    web_alive = False
    
    if web_pid and check_process_alive_by_pid(web_pid):
        web_alive = True
    else:
        # PID 파일 기준 실패 시, /proccmdline 스캔 Fallback
        fallback_pids = find_processes_by_cmdline("gunicorn")
        if fallback_pids:
            web_pid = fallback_pids[0]
            web_alive = True

    print("\n🖥️  [서비스 프로세스 상태]")
    if web_alive:
        print(f"  - 미디어 웹 서버 (Gunicorn) : 🟢 실행 중 (PID: {web_pid})")
    else:
        print("  - 미디어 웹 서버 (Gunicorn) : 🔴 정지 상태")

    # 2. 스캐너 워커 서버 점검
    worker_pid = get_pid_from_file(WORKER_PID_FILE)
    worker_alive = False
    
    if worker_pid and check_process_alive_by_pid(worker_pid):
        worker_alive = True
    else:
        fallback_worker_pids = find_processes_by_cmdline("tools/scanner_worker.py")
        if fallback_worker_pids:
            worker_pid = fallback_worker_pids[0]
            worker_alive = True

    if worker_alive:
        print(f"  - 백그라운드 스캐너 워커   : 🟢 실행 중 (PID: {worker_pid})")
    else:
        print("  - 백그라운드 스캐너 워커   : 🔴 정지 상태")

    # 3. 데이터베이스 무결성(PRAGMA integrity_check) 점검
    print("\n💾  [데이터베이스 정합성 상태]")
    
    db_general = os.path.join(DB_DIR, "media_general.db")
    db_adult = os.path.join(DB_DIR, "media_adult.db")
    
    print(f"  - 일반 DB (media_general.db) : {check_db_integrity(db_general)}")
    print(f"  - 성인 DB (media_adult.db)   : {check_db_integrity(db_adult)}")

    print("\n" + "=" * 60)
    print(" 컨테이너 헬스 체크가 완료되었습니다.")
    print("=" * 60)

if __name__ == "__main__":
    main()
