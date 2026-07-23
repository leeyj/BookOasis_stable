# -*- coding: utf-8 -*-
import os
import signal
import sys
import threading
import time


def _arm_forced_exit_after_grace(grace_seconds=25):
    def _watchdog():
        time.sleep(max(1, int(grace_seconds)))
        print(f"[Shutdown-Signal-Guard] Grace period expired after {grace_seconds}s. Forcing process exit.")
        os._exit(143)

    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()

def register_shutdown_handlers():
    """
    SIGTERM 및 SIGINT 시그널 핸들러를 등록하여
    스캐너 엔진과 레이지 스캐너가 즉각 전역 종료 플래그를 감지하도록 연동합니다.
    """
    def handle_signal(signum, frame):
        print(f"\n[Shutdown-Signal-Guard] 종료 시그널({signum}) 수신. 우아한 종료 프로세스를 기동합니다...")
        _arm_forced_exit_after_grace(25)

        # 0. 스크립트 직접 실행(__main__) 경로의 전역 플래그도 함께 갱신
        # 예) python tools/lazy_scanner.py 로 실행 시 stop_requested는 __main__에 존재
        try:
            main_mod = sys.modules.get('__main__')
            if main_mod is not None and hasattr(main_mod, 'stop_requested'):
                setattr(main_mod, 'stop_requested', True)
        except Exception:
            pass
        
        # 1. 메인 스캐너 엔진 플래그 설정
        try:
            import tools.scanner.engine
            tools.scanner.engine.stop_requested = True
        except ImportError:
            pass

        # 2. 레이지 스캐너 엔진 플래그 설정
        try:
            import tools.lazy_scanner
            tools.lazy_scanner.stop_requested = True
        except ImportError:
            pass

        # 3. 큐 프로세스에 가동 중인 활성 자식 서브프로세스 정리
        try:
            import services.scanner_queue
            services.scanner_queue.stop_requested = True
            if services.scanner_queue.active_subprocess:
                print(f"[Shutdown-Signal-Guard] 실행 중인 자식 서브프로세스 감지. 종료 신호 전파 (PID: {services.scanner_queue.active_subprocess.pid})")
                services.scanner_queue.active_subprocess.terminate()
        except Exception as sub_err:
            pass

    try:
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
        print("[Shutdown-Signal-Guard] SIGTERM / SIGINT 종료 핸들러가 성공적으로 등록되었습니다.")
    except Exception as e:
        print(f"[Shutdown-Signal-Guard ERROR] 핸들러 등록 실패 (비메인 스레드 가능성): {e}")
