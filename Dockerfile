# 1. Base Image
FROM python:3.10-slim

# 2. Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5930

# 3. Working Directory
WORKDIR /app

# 4. Install System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    gosu \
    && rm -rf /var/lib/apt/lists/*

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
RUN mkdir -p db covers cache plugins

# 8. Expose Application Port
EXPOSE 5930

# 9. Graceful Shutdown 시그널 지정 (Docker stop 시 SIGTERM 전달 보장)
STOPSIGNAL SIGTERM

# 10. Volume Configuration for persistence
VOLUME ["/app/db", "/app/covers", "/app/cache", "/app/plugins"]

# 11. Startup Command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--workers", "1", "--threads", "12", "--bind", "0.0.0.0:5930", "--timeout", "300", "--graceful-timeout", "15", "core:app"]
