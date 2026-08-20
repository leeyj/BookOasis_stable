# -*- coding: utf-8 -*-
"""
process_helper.py - OS 프로세스 생존 여부를 PID 재사용(reuse) 오탐 없이 검증하기 위한 공용 헬퍼.
"""
import os

# 이 설치본의 루트 디렉터리 (utils/의 상위). 같은 호스트에 네이티브 설치본과
# 별개의 Docker 컨테이너(예: ad-hoc 테스트용)가 동시에 떠 있는 경우, cmdline에
# 'scanner_worker.py'가 포함된 프로세스가 host PID namespace에 여러 개 보일 수 있다.
# PID가 재사용되면 그 중 "우리 것이 아닌" scanner_worker.py 프로세스를 우리 워커로
# 오인할 수 있으므로, cwd까지 함께 대조해 진짜 이 설치본의 워커인지 확인한다.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_scanner_worker_pid_alive(pid):
    """
    주어진 PID가 실제로 살아있는, 그리고 '이 설치본'의 scanner_worker.py 프로세스인지 확인합니다.

    단순 PID 존재 여부(os.kill(pid, 0) / psutil.pid_exists)만으로는, 워커 프로세스가
    죽은 뒤 OS가 같은 PID를 완전히 무관한 다른 프로세스에 재사용(PID reuse)했을 때
    "살아있다"고 오판할 수 있다. 이 경우 scanner_tasks 행이 영원히 running/exit_pending
    상태로 고착되어(cleanup_stale_tasks가 정화하지 못하고, try_acquire_task도 새 워커의
    선점을 계속 거부함) 재시작 후에도 스캔이 재개되지 않는 것처럼 보이는 문제로 이어진다.
    cmdline까지 함께 검사해 진짜 scanner_worker.py 프로세스인지 확인하고, 나아가 같은
    호스트의 다른 설치본(예: ad-hoc 테스트 Docker 컨테이너)이 재사용된 PID에 우연히
    scanner_worker.py를 띄우고 있는 경우까지 걸러내기 위해 cwd도 이 설치본 경로와 대조한다.
    """
    if not pid:
        return False
    try:
        import psutil
        try:
            proc = psutil.Process(pid)
            cmdline = proc.cmdline()
            if not any('scanner_worker.py' in str(arg) for arg in cmdline):
                return False

            try:
                proc_cwd = proc.cwd()
            except (psutil.AccessDenied, OSError):
                # cwd를 알 수 없는 환경(권한 제한 등)에서는 cmdline 일치만으로 판단(기존 동작 유지)
                return True

            if os.path.normcase(os.path.normpath(proc_cwd)) != os.path.normcase(os.path.normpath(_APP_DIR)):
                print(
                    f"[ProcessHelper WARNING] PID {pid}에 scanner_worker.py 프로세스가 있지만 "
                    f"작업 디렉터리가 이 설치본과 다릅니다 (found='{proc_cwd}', expected='{_APP_DIR}'). "
                    f"PID 재사용으로 다른 설치본(예: 테스트 Docker 컨테이너)의 워커를 우리 워커로 오인할 뻔했습니다 - 다른 프로세스로 간주합니다."
                )
                return False

            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    except ImportError:
        # psutil 미설치 환경: cmdline 검증이 불가하므로 기존 방식(PID 존재 여부)으로 폴백.
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError, ValueError):
            return False
