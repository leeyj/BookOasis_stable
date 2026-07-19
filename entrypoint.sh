#!/bin/bash
set -e

# PUID와 PGID 환경변수 확인 (기본값: root=0)
PUID=${PUID:-0}
PGID=${PGID:-0}

# ─────────────────────────────────────────────────────────
# [공통] 데이터 디렉토리 권한 및 쓰기 가능 여부 사전 검증
# NAS(Synology, QNAP 등) 환경에서 bind mount 시
# 디렉토리가 read-only로 마운트되는 경우를 사전에 감지합니다.
# ─────────────────────────────────────────────────────────
DATA_DIRS="/app/db /app/covers /app/cache /app/logs"

# ── Graceful Shutdown을 위한 시그널 트랩 ──
WEB_PID=0

cleanup() {
    echo "[Entrypoint] SIGTERM/SIGINT received. Shutting down gracefully..."
    
    # 1. Gunicorn 웹 서버 종료
    if [ "$WEB_PID" -ne 0 ]; then
        echo "[Entrypoint] Stopping Gunicorn web server (PID: $WEB_PID)..."
        kill -15 "$WEB_PID" 2>/dev/null || true
    fi
    
    # 2. 스캐너 워커 프로세스 검출 및 종료
    W_PIDS=$(pgrep -f "tools/scanner_worker.py")
    if [ -n "$W_PIDS" ]; then
        echo "[Entrypoint] Stopping Scanner Workers (PIDs: $W_PIDS)..."
        for WP in $W_PIDS; do
            kill -15 "$WP" 2>/dev/null || true
        done
    fi
    
    # 3. 최대 15초 동안 프로세스 자발적 종료 대기
    for i in {1..15}; do
        ALIVE=false
        if [ "$WEB_PID" -ne 0 ] && ps -p "$WEB_PID" >/dev/null 2>&1; then
            ALIVE=true
        fi
        W_PIDS_CHECK=$(pgrep -f "tools/scanner_worker.py")
        if [ -n "$W_PIDS_CHECK" ]; then
            ALIVE=true
        fi
        
        if [ "$ALIVE" = false ]; then
            break
        fi
        sleep 1
    done
    
    # 4. 15초 이후에도 살아있는 프로세스는 강제 종료 (SIGKILL)
    if [ "$WEB_PID" -ne 0 ] && ps -p "$WEB_PID" >/dev/null 2>&1; then
        echo "[Entrypoint] Gunicorn failed to exit. Force killing..."
        kill -9 "$WEB_PID" 2>/dev/null || true
    fi
    W_PIDS_KILL=$(pgrep -f "tools/scanner_worker.py")
    if [ -n "$W_PIDS_KILL" ]; then
        echo "[Entrypoint] Scanner workers failed to exit. Force killing..."
        for WP in $W_PIDS_KILL; do
            kill -9 "$WP" 2>/dev/null || true
        done
    fi
    
    echo "[Entrypoint] Graceful shutdown completed."
    exit 0
}

trap cleanup SIGTERM SIGINT

wait_for_web_health() {
    local health_url="http://127.0.0.1:5930/health"
    local attempts=0
    local max_attempts=120

    while [ "$attempts" -lt "$max_attempts" ]; do
        if command -v curl >/dev/null 2>&1; then
            if curl -fsS "$health_url" >/dev/null 2>&1; then
                return 0
            fi
        else
            if python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen('http://127.0.0.1:5930/health', timeout=1)
PY
            then
                return 0
            fi
        fi

        attempts=$((attempts + 1))
        sleep 1
    done

    return 1
}

start_worker_after_health() {
    local run_as_user="$1"

    (
        if wait_for_web_health; then
            echo "[Entrypoint] Web health detected. Starting scanner worker..."
        else
            echo "[Entrypoint] Web health timeout. Starting scanner worker anyway..."
        fi

        if [ -n "$run_as_user" ]; then
            gosu "$run_as_user" python3 tools/scanner_worker.py > /app/logs/media_server_worker.log 2>&1
        else
            python3 tools/scanner_worker.py > /app/logs/media_server_worker.log 2>&1
        fi
    ) &
}

echo "[Entrypoint] 데이터 디렉토리 권한 확인 중..."
for dir in $DATA_DIRS; do
    # 디렉토리가 없으면 생성 시도
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir" 2>/dev/null || {
            echo "[Entrypoint] ⚠️  디렉토리 생성 실패: $dir (권한을 확인하세요)"
            continue
        }
    fi
    # 쓰기 권한 보장 (호스트에서 read-only로 마운트된 경우 대비)
    chmod 755 "$dir" 2>/dev/null || true
done

# DB 디렉토리 실제 쓰기 가능 여부 테스트
if ! touch /app/db/.write_test 2>/dev/null; then
    echo ""
    echo "=========================================================="
    echo " [Entrypoint] ❌ 치명적 오류: /app/db 디렉토리에 쓰기 권한이 없습니다."
    echo ""
    echo " 호스트에서 아래 명령을 실행한 후 컨테이너를 재시작하세요:"
    echo ""
    echo "   chmod -R 755 <host_db_path>"
    echo "   chmod 664 <host_db_path>/*.db 2>/dev/null || true"
    echo ""
    echo " Synology NAS 예시:"
    echo "   chmod -R 755 /volume1/docker/BookOasis/db"
    echo ""
    echo " 또는 docker-compose.yml에 PUID/PGID를 설정하세요:"
    echo "   environment:"
    echo "     - PUID=1000"
    echo "     - PGID=1000"
    echo "=========================================================="
    echo ""
    exit 1
fi
rm -f /app/db/.write_test

# DB 파일 권한 보장 (파일이 있는 경우만)
chmod 664 /app/db/*.db 2>/dev/null || true
chmod 664 /app/db/*.db-wal 2>/dev/null || true
chmod 664 /app/db/*.db-shm 2>/dev/null || true

echo "[Entrypoint] ✅ 데이터 디렉토리 쓰기 권한 확인 완료"

# PUID가 0이 아니면 커스텀 유저를 생성하여 권한을 매핑
if [ "$PUID" -ne 0 ]; then
    echo "[Entrypoint] Running with PUID: $PUID and PGID: $PGID"
    
    # media_group 이름의 그룹이 존재하지 않으면 PGID로 생성
    if ! getent group media_group >/dev/null; then
        groupadd -g "$PGID" media_group
    fi
    
    # media_user 이름의 유저가 존재하지 않으면 PUID로 생성
    if ! getent passwd media_user >/dev/null; then
        useradd -u "$PUID" -g "$PGID" -m -s /bin/bash media_user
    fi

    # 데이터 저장용 폴더들의 소유권을 media_user로 변경
    chown -R media_user:media_group /app/db /app/covers /app/cache /app/logs 2>/dev/null || true
    
    # ── 도커 내부 스캐너 워커 프로세스 지연 기동 (웹 health 이후) ──
    echo "[Entrypoint] Worker launch scheduled (after web health) as media_user..."
    start_worker_after_health "media_user"
    
    # gosu를 사용하여 권한을 강등한 후 명령어 실행 (백그라운드)
    echo "[Entrypoint] Starting application as media_user..."
    gosu media_user "$@" &
    WEB_PID=$!
else
    # PUID가 0이거나 설정되지 않은 경우 기본적으로 root로 실행
    echo "[Entrypoint] Running as root..."
    
    # ── 도커 내부 스캐너 워커 프로세스 지연 기동 (웹 health 이후) ──
    echo "[Entrypoint] Worker launch scheduled (after web health) as root..."
    start_worker_after_health ""
    
    # 백그라운드 구동
    "$@" &
    WEB_PID=$!
fi

# 시그널을 받을 수 있도록 wait 명령으로 대기
wait "$WEB_PID"

