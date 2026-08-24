# 1. Base Image
FROM python:3.10-slim

# 2. Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5930

# 3. Working Directory
WORKDIR /app

# 4. Install System Dependencies
# intel-media-va-driver(Intel iGPU)/mesa-va-drivers(AMD Radeon)/libva2/vainfo: VAAPI 하드웨어
# 트랜스코딩 런타임 드라이버. ffmpeg 패키지 자체는 VAAPI hwaccel을 컴파일 지원하지만,
# 실제 동작에는 이 드라이버 스택이 별도로 필요하다 (설정 > 일반 > 영상 트랜스코딩의
# "VAAPI 점검" 버튼이 이 패키지 유무 + /dev/dri 패스스루 여부를 확인함). mesa-va-drivers가
# 없으면 libva가 AMD GPU를 자동 감지해도 radeonsi_drv_video.so를 못 찾아
# "vaInitialize failed with error code -1"로 실패한다 (커뮤니티 문의로 확인, 2026-08-17).
# 둘 다 Debian에서 amd64 전용 패키지(iGPU/dGPU 자체가 x86 하드웨어라 arm64에는 없음).
# GHCR 멀티아키텍처 빌드(linux/amd64,linux/arm64)가 arm64에서 apt-get install 시
# "Unable to locate package"로 실패하는 것을 막기 위해 TARGETARCH가 amd64일 때만 설치한다.
# tzdata: python:3.10-slim 베이스에는 /usr/share/zoneinfo가 없어, 이게 없으면 docker-compose의
# TZ 환경변수를 설정해도 조용히 무시되고 컨테이너는 계속 UTC로 동작한다.
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    gosu \
    tzdata \
    curl \
    unzip \
    && if [ "$TARGETARCH" = "amd64" ]; then \
         apt-get install -y --no-install-recommends intel-media-va-driver mesa-va-drivers libva2 vainfo; \
       fi \
    && rm -rf /var/lib/apt/lists/*

# 4-1. rclone(wiserain mod 빌드) 설치 — "Drive에서 복사해오기" 기능 전용. 사용자가 컨테이너
# 안에 직접 설치하던 방식(docker exec)은 root 계정으로 이뤄지는 경우가 많아 앱 실행 계정
# (media_user, PUID 사용 시)과 rclone.conf 위치가 어긋나는 문제가 반복 보고됐다
# (v2.4.3 CHANGELOG 참조). 이미지에 미리 심어두면 이 설치 단계 자체가 사라진다.
# 일반 rclone이 아닌 mod 빌드를 쓰는 이유는 국내 커뮤니티에서 흔히 쓰는 구글 드라이브
# 관련 확장 기능 때문 — 표준 rclone 릴리스와 CLI 호환.
RUN curl -fsSL https://raw.githubusercontent.com/wiserain/rclone/mod/install.sh | bash

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy Source Code and Entrypoint
COPY . .
RUN chmod +x /app/entrypoint.sh /app/manage.sh

# 6-1. plugins/ 는 docker-compose에서 바인드 마운트되는 사용자 데이터 폴더라, 완전히 빈
# 호스트 폴더로 마운트되면 컨테이너 안의 원본(base.py 등 필수 프레임워크 파일)이 가려져
# 버린다. 마운트에 가려지지 않는 별도 경로에 원본을 보관해 두었다가, entrypoint.sh가
# 부팅 시 "없으면 채워넣기"(있으면 절대 덮어쓰지 않음) 방식으로 시드한다.
RUN mkdir -p /app/_plugin_framework_defaults && \
    cp -r /app/plugins/metadata/. /app/_plugin_framework_defaults/

# 7. Create volumes and directories
# rclone: 사용자가 자신의 rclone.conf를 그대로 바인드 마운트할 수 있는 고정 경로.
# utils/rclone_gdrive_copy.py의 설정 경로 우선순위 1순위.
RUN mkdir -p db covers cache plugins rclone

# 8. Expose Application Port
EXPOSE 5930

# 9. Graceful Shutdown 시그널 지정 (Docker stop 시 SIGTERM 전달 보장)
STOPSIGNAL SIGTERM

# 10. Volume Configuration for persistence
VOLUME ["/app/db", "/app/covers", "/app/cache", "/app/plugins"]

# 11. Startup Command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--workers", "1", "--threads", "12", "--bind", "0.0.0.0:5930", "--timeout", "300", "--graceful-timeout", "15", "core:app"]
