#!/bin/bash

# --- BookOasis 미디어 서버 관리 스크립트 ---
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$APP_DIR/media_server.pid"
WORKER_PID_FILE="$APP_DIR/media_server_worker.pid"
LOG_FILE="$APP_DIR/logs/media_server_startup.log"
WORKER_LOG_FILE="$APP_DIR/logs/media_server_worker_startup.log"

cd "$APP_DIR" || exit 1

wait_for_app_ready() {
    local health_url="http://127.0.0.1:5930/health"
    local attempt=0

    echo "[*] 미디어 서버 준비 상태 확인 중..."
    while [ "$attempt" -lt 60 ]; do
        if command -v curl >/dev/null 2>&1; then
            if curl -fsS "$health_url" >/dev/null 2>&1; then
                echo "[+] 미디어 서버 health 확인 완료."
                return 0
            fi
        else
            if python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen('http://127.0.0.1:5930/health', timeout=1)
PY
            then
                echo "[+] 미디어 서버 health 확인 완료."
                return 0
            fi
        fi

        attempt=$((attempt + 1))
        sleep 1
    done

    echo "[!] 미디어 서버 health 확인 시간 초과. 워커는 계속 기동합니다."
    return 1
}

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "[*] 이미 미디어 서버가 실행 중입니다. (PID: $PID)"
        else
            echo "[!] 오래된 PID 파일이 있어 삭제합니다."
            rm "$PID_FILE"
        fi
    fi

    echo "[*] 미디어 서버 구동을 시작합니다..."
    mkdir -p "$APP_DIR/db"
    mkdir -p "$APP_DIR/covers"
    mkdir -p "$APP_DIR/cache"
    mkdir -p "$APP_DIR/logs"
    
    # Gunicorn을 통해 5930 포트로 백그라운드 기동 (주기적 워커 재시작 적용 및 타임아웃 방지)
    nohup env PYTHONUNBUFFERED=1 BOOKOASIS_ENABLE_EMBEDDED_WORKER=false python3 -m gunicorn -w 1 --threads 12 --max-requests 500 --max-requests-jitter 50 --timeout 300 -b 0.0.0.0:5930 core:app > "$LOG_FILE" 2>&1 &
    
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"
    
    sleep 2
    if ps -p "$NEW_PID" > /dev/null 2>&1; then
        echo "[+] 미디어 서버 구동 성공! (PID: $NEW_PID)"
    else
        echo "[!] 미디어 서버 구동 실패. $LOG_FILE 로그를 확인해 주세요."
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
    fi

    wait_for_app_ready

    # ── 독자적인 백그라운드 스캐너 워커 프로세스 기동 ──
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if ps -p "$W_PID" > /dev/null 2>&1; then
            echo "[*] 이미 스캐너 워커가 실행 중입니다. (PID: $W_PID)"
            return 0
        else
            rm "$WORKER_PID_FILE"
        fi
    fi

    echo "[*] 스캐너 워커 구동을 시작합니다..."
    nohup env PYTHONUNBUFFERED=1 python3 tools/scanner_worker.py > "$WORKER_LOG_FILE" 2>&1 &
    W_NEW_PID=$!
    echo "$W_NEW_PID" > "$WORKER_PID_FILE"
    
    sleep 2
    if ps -p "$W_NEW_PID" > /dev/null 2>&1; then
        echo "[+] 스캐너 워커 구동 성공! (PID: $W_NEW_PID)"
    else
        echo "[!] 스캐너 워커 구동 실패. $WORKER_LOG_FILE 로그를 확인해 주세요."
        [ -f "$WORKER_PID_FILE" ] && rm "$WORKER_PID_FILE"
    fi
}

stop() {
    echo "[*] 미디어 서버 프로세스를 모두 검출하여 정리합니다..."
    
    # 1. PID 파일 기준 종료
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "[*] PID 파일 기준 미디어 서버 종료 시도 (PID: $PID)"
            kill -15 "$PID"
            sleep 1
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID"
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # 2. 잔존 gunicorn core:app 프로세스 소탕
    PIDS=$(pgrep -f "gunicorn.*core:app")
    if [ -n "$PIDS" ]; then
        echo "[*] 남아있는 미디어 Gunicorn 프로세스 정리 대상: $PIDS"
        for P in $PIDS; do
            if ps -p "$P" > /dev/null 2>&1; then
                kill -15 "$P"
            fi
        done
        sleep 1
        for P in $PIDS; do
            if ps -p "$P" > /dev/null 2>&1; then
                kill -9 "$P"
            fi
        done
        echo "[+] 남아있던 프로세스 정리 완료."
    fi

    # 3. 스캐너 워커 프로세스 정리
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if ps -p "$W_PID" > /dev/null 2>&1; then
            echo "[*] PID 파일 기준 스캐너 워커 종료 시도 (PID: $W_PID)"
            kill -15 "$W_PID"
            sleep 1
            if ps -p "$W_PID" > /dev/null 2>&1; then
                kill -9 "$W_PID"
            fi
        fi
        rm -f "$WORKER_PID_FILE"
    fi

    # 잔존 워커 루프 프로세스 소탕
    W_PIDS=$(pgrep -f "tools/scanner_worker.py")
    if [ -n "$W_PIDS" ]; then
        echo "[*] 남아있는 스캐너 워커 프로세스 정리 대상: $W_PIDS"
        for WP in $W_PIDS; do
            if ps -p "$WP" > /dev/null 2>&1; then
                kill -9 "$WP"
            fi
        done
    fi
}

status() {
    echo "=== [미디어 서버 서비스 상태] ==="
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "[+] 미디어 서버: 실행 중 (PID: $PID)"
            PORT_INFO=$(netstat -tlpn 2>/dev/null | grep "$PID")
            [ -n "$PORT_INFO" ] && echo "    포트 정보: $PORT_INFO"
        else
            echo "[-] 미디어 서버: 정지 상태 (오래된 PID 파일 존재)"
        fi
    else
        PID=$(pgrep -f "gunicorn.*core:app")
        if [ -n "$PID" ]; then
            echo "[+] 미디어 서버: 실행 중 (PID: $PID, PID 파일 없음)"
        else
            echo "[-] 미디어 서버: 정지 상태"
        fi
    fi

    echo "=== [스캐너 워커 서비스 상태] ==="
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if ps -p "$W_PID" > /dev/null 2>&1; then
            echo "[+] 스캐너 워커: 실행 중 (PID: $W_PID)"
        else
            echo "[-] 스캐너 워커: 정지 상태 (오래된 PID 파일 존재)"
        fi
    else
        W_PID=$(pgrep -f "tools/scanner_worker.py")
        if [ -n "$W_PID" ]; then
            echo "[+] 스캐너 워커: 실행 중 (PID: $W_PID, PID 파일 없음)"
        else
            echo "[-] 스캐너 워커: 정지 상태"
        fi
    fi
}

restart() {
    stop
    sleep 1
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        restart
        ;;
    *)
        echo "사용법: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
