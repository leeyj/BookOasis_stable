#!/bin/bash
# scanner_worker_supervisor.sh - manage.sh가 띄우는 스캐너 워커 재시작 루프 (Docker entrypoint.sh의 루프와 같은 역할)
#
# 워커(tools/scanner_worker.py)가 죽으면 3초 뒤 다시 띄운다. 예전 manage.sh는 한 번 띄우고 끝이라, 워커가 죽으면
# 웹이 작업 등록 때 gunicorn 자식으로 워커를 대신 띄웠고 그게 전용 워커와 겹쳐 워커가 둘이 되기도 했다.
# 이제 웹은 전용 워커 운영에서 워커를 띄우지 않으므로(core.should_enable_embedded_scanner_worker) 재시작은 여기서 한다.
#
# 환경변수 (manage.sh가 넘긴다)
#   WORKER_PID_FILE   실제 워커 PID를 적는 파일 - manage.sh stop의 '30초 안전 종료 대기'가 워커 자체를 기다리도록
#   WORKER_STOP_FLAG  이 파일이 있으면 다시 띄우지 않고 끝낸다 (manage.sh stop이 맨 먼저 만든다)
#   WORKER_RESTART_DELAY  재시작 대기 초 (기본 3)
set -u
cd "$(dirname "$0")/.." || exit 1
: "${WORKER_PID_FILE:?WORKER_PID_FILE is required}"
: "${WORKER_STOP_FLAG:?WORKER_STOP_FLAG is required}"
WORKER_PYTHON="${WORKER_PYTHON:-python3}"
DELAY="${WORKER_RESTART_DELAY:-3}"

while [ ! -f "$WORKER_STOP_FLAG" ]; do
    "$WORKER_PYTHON" tools/scanner_worker.py &
    child=$!
    echo "$child" > "$WORKER_PID_FILE"
    wait "$child"
    code=$?
    [ -f "$WORKER_STOP_FLAG" ] && break
    echo "[scanner_worker_supervisor] scanner worker exited (code: $code). Restarting in ${DELAY} seconds..."
    sleep "$DELAY"
done
echo "[scanner_worker_supervisor] stop flag found - exiting."
