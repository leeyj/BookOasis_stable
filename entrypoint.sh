#!/bin/bash
set -e

# PUID와 PGID 환경변수 확인 (기본값: root=0)
PUID=${PUID:-0}
PGID=${PGID:-0}

# PUID가 0이 아니면 커스텀 유저를 생성하여 권한을 매핑
if [ "$PUID" -ne 0 ]; then
    echo "Running with PUID: $PUID and PGID: $PGID"
    
    # media_group 이름의 그룹이 존재하지 않으면 PGID로 생성
    if ! getent group media_group >/dev/null; then
        groupadd -g "$PGID" media_group
    fi
    
    # media_user 이름의 유저가 존재하지 않으면 PUID로 생성
    if ! getent passwd media_user >/dev/null; then
        useradd -u "$PUID" -g "$PGID" -m -s /bin/bash media_user
    fi

    # 데이터 저장용 폴더들의 소유권을 media_user로 변경
    chown -R media_user:media_group /app/db /app/covers /app/cache /app/plugins 2>/dev/null || true
    
    # gosu를 사용하여 권한을 강등한 후 명령어 실행
    echo "Starting application as media_user..."
    exec gosu media_user "$@"
else
    # PUID가 0이거나 설정되지 않은 경우 기본적으로 root로 실행
    echo "Running as root..."
    exec "$@"
fi
