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
    gosu \
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy Source Code and Entrypoint
COPY . .
RUN chmod +x /app/entrypoint.sh /app/manage.sh

# 7. Create volumes and directories
RUN mkdir -p db covers cache plugins

# 8. Expose Application Port
EXPOSE 5930

# 9. Graceful Shutdown 시그널 지정 (Docker stop 시 SIGTERM 전달 보장)
STOPSIGNAL SIGTERM

# 10. Volume Configuration for persistence
VOLUME ["/app/db", "/app/covers", "/app/cache"]

# 11. Startup Command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--workers", "1", "--threads", "12", "--bind", "0.0.0.0:5930", "--timeout", "300", "--graceful-timeout", "15", "core:app"]
