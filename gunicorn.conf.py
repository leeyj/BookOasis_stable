# gunicorn.conf.py – gunicorn이 실행 위치(앱 폴더)에서 자동으로 읽는 설정 파일.
# manage.sh(cd 후 실행) / systemd(WorkingDirectory) / Docker(WORKDIR /app) 모두 앱 폴더에서 띄우므로 따로 -c를 줄 필요 없다.
# 실행 옵션(워커 수, --max-requests 등)은 지금처럼 각 실행 명령에 두고, 여기엔 훅만 둔다.
import atexit
import os
import sys
import threading

# 정리 작업(진행도 flush, 스케줄러 중지, DB 풀 종료) 자체가 멈춰도 이 시간 뒤엔 무조건 끝낸다
WORKER_EXIT_CLEANUP_TIMEOUT = 20


def worker_exit(server, worker):
    """작업 프로세스가 끝날 때 정리 작업만 하고 바로 종료한다.

    워커가 1개라 기존 워커가 완전히 끝나야 새 워커가 뜬다. 그런데 파이썬은 종료 시 gthread 요청 스레드가
    모두 끝나길 기다리므로, rclone(Google Drive) 마운트 읽기에서 멈춘 요청이 하나라도 있으면 --max-requests
    재활용 때 프로세스가 끝나지 못하고 --timeout(300초) 강제 종료까지 서버가 응답하지 않았다
    (2026-10-01 홈 서버 5분 중단, 로그엔 "cannot schedule new futures after shutdown"이 2초마다 반복).
    정상 종료 때 돌던 atexit 정리를 여기서 직접 돌린 뒤 os._exit로 멈춘 스레드를 기다리지 않고 끝낸다.
    """
    # 이미 죽은 워커를 정리할 때 마스터 프로세스에서도 이 훅이 불린다(arbiter.kill_worker) - 마스터는 건드리지 않는다
    if os.getpid() != worker.pid:
        return
    # 앱 로드/부팅 실패는 원래 종료 코드로 끝나야 마스터가 재시작을 멈춘다 - 정상 흐름에 맡긴다
    if not getattr(worker, 'booted', False):
        return

    watchdog = threading.Timer(WORKER_EXIT_CLEANUP_TIMEOUT, lambda: os._exit(0))
    watchdog.daemon = True
    watchdog.start()

    try:
        atexit._run_exitfuncs()
    except Exception as e:
        print(f"[Gunicorn] worker_exit 정리 중 오류 (무시): {e}", file=sys.stderr)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(0)
