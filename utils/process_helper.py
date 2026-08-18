# -*- coding: utf-8 -*-
"""
process_helper.py - OS 프로세스 생존 여부를 PID 재사용(reuse) 오탐 없이 검증하기 위한 공용 헬퍼.
"""


def is_scanner_worker_pid_alive(pid):
    """
    주어진 PID가 실제로 살아있는 scanner_worker.py 프로세스인지 확인합니다.

    단순 PID 존재 여부(os.kill(pid, 0) / psutil.pid_exists)만으로는, 워커 프로세스가
    죽은 뒤 OS가 같은 PID를 완전히 무관한 다른 프로세스에 재사용(PID reuse)했을 때
    "살아있다"고 오판할 수 있다. 이 경우 scanner_tasks 행이 영원히 running/exit_pending
    상태로 고착되어(cleanup_stale_tasks가 정화하지 못하고, try_acquire_task도 새 워커의
    선점을 계속 거부함) 재시작 후에도 스캔이 재개되지 않는 것처럼 보이는 문제로 이어진다.
    cmdline까지 함께 검사해 진짜 scanner_worker.py 프로세스인지 확인한다.
    """
    if not pid:
        return False
    try:
        import psutil
        try:
            proc = psutil.Process(pid)
            cmdline = proc.cmdline()
            return any('scanner_worker.py' in str(arg) for arg in cmdline)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    except ImportError:
        # psutil 미설치 환경: cmdline 검증이 불가하므로 기존 방식(PID 존재 여부)으로 폴백.
        import os
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError, ValueError):
            return False
