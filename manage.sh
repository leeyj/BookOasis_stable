#!/bin/bash

# --- BookOasis 미디어 서버 관리 스크립트 ---
SCRIPT_PATH=""
if [ -n "$BASH_VERSION" ]; then
    eval 'SCRIPT_PATH="${BASH_SOURCE[0]}"'
fi
[ -z "$SCRIPT_PATH" ] && SCRIPT_PATH="$0"
APP_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PID_FILE="$APP_DIR/media_server.pid"
WORKER_PID_FILE="$APP_DIR/media_server_worker.pid"
LOG_FILE="$APP_DIR/logs/media_server_startup.log"
WORKER_LOG_FILE="$APP_DIR/logs/media_server_worker_startup.log"

FORCE_RESTART="false"
for arg in "$@"; do
    if [ "$arg" = "--force" ]; then
        FORCE_RESTART="true"
    fi
done

check_pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

find_pids_by_pattern() {
    local pattern="$1"
    if command -v ps >/dev/null 2>&1; then
        ps ax | grep "$pattern" | grep -v grep | awk '{print $1}'
    elif [ -d "/proc" ]; then
        # ps 명령어가 없는 경우 /proc/[PID]/cmdline 직접 파싱 Fallback
        for name in /proc/[0-9]*; do
            if [ -d "$name" ]; then
                local pid
                pid=$(basename "$name")
                if [ -f "$name/cmdline" ]; then
                    # cmdline 파일은 널(\x00) 바이트로 나뉘어 있으므로 grep -a(바이너리) 검사 적용
                    if grep -q -a "$pattern" "$name/cmdline" 2>/dev/null; then
                        echo "$pid"
                    fi
                fi
            fi
        done
    fi
}

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
            return 0
        else
            echo "[!] 오래된 PID 파일이 있어 삭제합니다."
            rm "$PID_FILE"
        fi
    fi

    # ── [기동 전 DB 무결성 및 스키마 검사 가드] ──
    echo "[*] 기동 전 데이터베이스 무결성(PRAGMA integrity_check) 검사 중..."
    local db_ok=true
    for db_name in "media_general.db" "media_adult.db"; do
        local db_file="$APP_DIR/db/$db_name"
        if [ -f "$db_file" ]; then
            if command -v sqlite3 >/dev/null 2>&1; then
                local res
                res=$(sqlite3 "$db_file" "PRAGMA integrity_check;" 2>&1)
                if [ "$res" != "ok" ]; then
                    echo "[!] 경고: 데이터베이스 파일이 손상되었습니다: $db_name (오류: $res)"
                    db_ok=false
                fi
            fi
        fi
    done

    if [ "$db_ok" = false ]; then
        echo "[!] 손상된 DB가 발견되어 자동 복구(db_recovery.py)를 가동합니다..."
        if python3 tools/db_recovery.py --yes; then
            echo "[+] 데이터베이스 자동 복구가 성공적으로 완료되었습니다."
        else
            echo "[❌ 치명적 오류] 데이터베이스 자동 복구에 실패했습니다. 안전을 위해 서비스를 구동하지 않습니다."
            return 1
        fi
    else
        echo "[+] 데이터베이스 무결성 정상 확인."
    fi

    # ── [최신 스키마 강제 동기화 의무화] ──
    echo "[*] 데이터베이스 최신 스키마 자동 동기화(db_schema_updater.py) 실행 중..."
    if python3 tools/db_schema_updater.py; then
        echo "[+] 최신 스키마 동기화 완료."
    else
        echo "[경고] 스키마 동기화 진행 중 오류가 발생했으나 기동을 계속합니다."
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
    if check_pid_alive "$NEW_PID"; then
        echo "[+] 미디어 서버 구동 성공! (PID: $NEW_PID)"
    else
        echo "[!] 미디어 서버 구동 실패. $LOG_FILE 로그를 확인해 주세요."
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
        return 1
    fi

    wait_for_app_ready

    # ── 독자적인 백그라운드 스캐너 워커 프로세스 기동 ──
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if check_pid_alive "$W_PID"; then
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
    if check_pid_alive "$W_NEW_PID"; then
        echo "[+] 스캐너 워커 구동 성공! (PID: $W_NEW_PID)"
    else
        echo "[!] 스캐너 워커 구동 실패. $WORKER_LOG_FILE 로그를 확인해 주세요."
        [ -f "$WORKER_PID_FILE" ] && rm "$WORKER_PID_FILE"
    fi
}

stop() {
    # 스캔 상태 체크 가드
    if [ -f "db/media_general.db" ] && command -v sqlite3 >/dev/null 2>&1; then
        SCANNING_COUNT=$(sqlite3 -init /dev/null -cmd ".timeout 2000" db/media_general.db "SELECT COUNT(*) FROM libraries WHERE scan_status = 'scanning';" 2>/dev/null || echo 0)
        RUNNING_TASKS=$(sqlite3 -init /dev/null -cmd ".timeout 2000" db/media_general.db "SELECT COUNT(*) FROM scanner_tasks WHERE status = 'running';" 2>/dev/null || echo 0)
        TOTAL_SCANNING=$((SCANNING_COUNT + RUNNING_TASKS))
        
        if [ "$TOTAL_SCANNING" -gt 0 ]; then
            echo "[!] 경고: 현재 라이브러리 스캔 작업이 진행 중입니다. (진행 중인 스캔: $SCANNING_COUNT, 실행 중인 태스크: $RUNNING_TASKS)"
            echo "[!] 이 상태에서 강제 종료 시 데이터베이스 손상(malformed) 위험이 매우 큽니다."
            
            if [ "$FORCE_RESTART" = "true" ]; then
                echo "[*] --force 옵션이 감지되어 종료를 강행합니다."
            else
                if [ -t 0 ]; then
                    read -p "정말 종료하시겠습니까? (y/N): " CONFIRM
                    if [[ ! "$CONFIRM" =~ ^[yY](es)?$ ]]; then
                        echo "[-] 중단되었습니다."
                        exit 1
                    fi
                else
                    echo "[❌ 오류] 비대화형 환경에서 스캔 중 종료 시도가 차단되었습니다. 스캔 완료 후 시도하시거나 --force 옵션을 사용해 주세요."
                    exit 1
                fi
            fi
        fi
    fi

    echo "[*] 미디어 서버 프로세스를 모두 검출하여 정리합니다..."
    
    # 1. PID 파일 기준 종료
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if check_pid_alive "$PID"; then
            echo "[*] PID 파일 기준 미디어 서버 종료 시도 (PID: $PID)"
            kill -15 "$PID"
            
            # Graceful Shutdown 대기 (최대 30초)
            for i in {1..30}; do
                if ! check_pid_alive "$PID"; then
                    break
                fi
                sleep 1
            done
            
            if check_pid_alive "$PID"; then
                if [ "$FORCE_RESTART" = "true" ]; then
                    echo "[!] 미디어 서버가 SIGTERM(15)에 응답하지 않아 강제 종료(SIGKILL)합니다."
                    kill -9 "$PID"
                else
                    echo "[!] 미디어 서버가 SIGTERM(15)에 응답하지 않았습니다. 강제 종료는 수행하지 않고 종료를 중단합니다."
                    return 1
                fi
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # 2. 잔존 gunicorn core:app 프로세스 소탕
    PIDS=$(find_pids_by_pattern "gunicorn.*core:app")
    if [ -n "$PIDS" ]; then
        echo "[*] 남아있는 미디어 Gunicorn 프로세스 정리 대상: $PIDS"
        for P in $PIDS; do
            if check_pid_alive "$P"; then
                kill -15 "$P"
            fi
        done
        
        # 잔존 프로세스들에 대해서도 최대 10초 대기
        for i in {1..10}; do
            STILL_ALIVE=false
            for P in $PIDS; do
                if check_pid_alive "$P"; then
                    STILL_ALIVE=true
                fi
            done
            if [ "$STILL_ALIVE" = false ]; then
                break
            fi
            sleep 1
        done
        
        for P in $PIDS; do
            if check_pid_alive "$P"; then
                if [ "$FORCE_RESTART" = "true" ]; then
                    kill -9 "$P"
                else
                    echo "[!] 남아있는 미디어 Gunicorn 프로세스는 강제 종료하지 않습니다."
                    return 1
                fi
            fi
        done
        echo "[+] 남아있던 프로세스 정리 완료."
    fi

    # 3. 스캐너 워커 프로세스 정리
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if check_pid_alive "$W_PID"; then
            echo "[*] PID 파일 기준 스캐너 워커 종료 시도 (PID: $W_PID)"
            kill -15 "$W_PID"
            
            # 스캐너 워커의 안전한 트랜잭션 마무리를 위해 최대 30초 대기
            for i in {1..30}; do
                if ! check_pid_alive "$W_PID"; then
                    break
                fi
                sleep 1
            done
            
            if check_pid_alive "$W_PID"; then
                if [ "$FORCE_RESTART" = "true" ]; then
                    echo "[!] 스캐너 워커가 SIGTERM(15)에 응답하지 않아 강제 종료(SIGKILL)합니다."
                    kill -9 "$W_PID"
                else
                    echo "[!] 스캐너 워커가 SIGTERM(15)에 응답하지 않았습니다. 강제 종료는 수행하지 않고 종료를 중단합니다."
                    return 1
                fi
            fi
        fi
        rm -f "$WORKER_PID_FILE"
    fi

    # 잔존 워커 루프 프로세스 소탕
    W_PIDS=$(find_pids_by_pattern "tools/scanner_worker.py")
    if [ -n "$W_PIDS" ]; then
        echo "[*] 남아있는 스캐너 워커 프로세스 정리 대상: $W_PIDS"
        for WP in $W_PIDS; do
            if check_pid_alive "$WP"; then
                kill -15 "$WP"
            fi
        done
        
        for i in {1..30}; do
            W_STILL_ALIVE=false
            for WP in $W_PIDS; do
                if check_pid_alive "$WP"; then
                    W_STILL_ALIVE=true
                fi
            done
            if [ "$W_STILL_ALIVE" = false ]; then
                break
            fi
            sleep 1
        done
        
        for WP in $W_PIDS; do
            if check_pid_alive "$WP"; then
                if [ "$FORCE_RESTART" = "true" ]; then
                    kill -9 "$WP"
                else
                    echo "[!] 남아있는 스캐너 워커 프로세스는 강제 종료하지 않습니다."
                    return 1
                fi
            fi
        done
    fi

    # 4. 잔존 독립 레이지 스캐너 프로세스 소탕
    LAZY_PIDS=$(find_pids_by_pattern "tools/lazy_scanner.py")
    if [ -n "$LAZY_PIDS" ]; then
        echo "[*] 백그라운드 레이지 스캐너 프로세스 정리 대상: $LAZY_PIDS"
        for LP in $LAZY_PIDS; do
            if check_pid_alive "$LP"; then
                kill -15 "$LP"
            fi
        done
        
        for i in {1..30}; do
            L_STILL_ALIVE=false
            for LP in $LAZY_PIDS; do
                if check_pid_alive "$LP"; then
                    L_STILL_ALIVE=true
                fi
            done
            if [ "$L_STILL_ALIVE" = false ]; then
                break
            fi
            sleep 1
        done
        
        for LP in $LAZY_PIDS; do
            if check_pid_alive "$LP"; then
                if [ "$FORCE_RESTART" = "true" ]; then
                    echo "[!] 레이지 스캐너 강제 종료 (PID: $LP)"
                    kill -9 "$LP"
                else
                    echo "[!] 남아있는 레이지 스캐너 프로세스는 강제 종료하지 않습니다."
                    return 1
                fi
            fi
        done
    fi
}

status() {
    echo "=== [미디어 서버 서비스 상태] ==="
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if check_pid_alive "$PID"; then
            echo "[+] 미디어 서버: 실행 중 (PID: $PID)"
            PORT_INFO=$(netstat -tlpn 2>/dev/null | grep "$PID")
            [ -n "$PORT_INFO" ] && echo "    포트 정보: $PORT_INFO"
        else
            echo "[-] 미디어 서버: 정지 상태 (오래된 PID 파일 존재)"
        fi
    else
        PID=$(find_pids_by_pattern "gunicorn.*core:app" | head -n 1)
        if [ -n "$PID" ]; then
            echo "[+] 미디어 서버: 실행 중 (PID: $PID, PID 파일 없음)"
        else
            echo "[-] 미디어 서버: 정지 상태"
        fi
    fi

    echo "=== [스캐너 워커 서비스 상태] ==="
    if [ -f "$WORKER_PID_FILE" ]; then
        W_PID=$(cat "$WORKER_PID_FILE")
        if check_pid_alive "$W_PID"; then
            echo "[+] 스캐너 워커: 실행 중 (PID: $W_PID)"
        else
            echo "[-] 스캐너 워커: 정지 상태 (오래된 PID 파일 존재)"
        fi
    else
        W_PID=$(find_pids_by_pattern "tools/scanner_worker.py" | head -n 1)
        if [ -n "$W_PID" ]; then
            echo "[+] 스캐너 워커: 실행 중 (PID: $W_PID, PID 파일 없음)"
        else
            echo "[-] 스캐너 워커: 정지 상태"
        fi
    fi
}

restart() {
    stop "$@"
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
