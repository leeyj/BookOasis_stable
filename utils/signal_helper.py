# -*- coding: utf-8 -*-
import signal
import sys

def register_shutdown_handlers():
    """
    SIGTERM 및 SIGINT 시그널 핸들러를 등록하여
    스캐너 엔진과 레이지 스캐너가 즉각 전역 종료 플래그를 감지하도록 연동합니다.
    """
    def handle_signal(signum, frame):
        print(f"\n[Shutdown-Signal-Guard] 종료 시그널({signum}) 수신. 우아한 종료 프로세스를 기동합니다...")
        
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
