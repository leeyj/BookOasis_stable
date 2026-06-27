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
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy Source Code
COPY . .

# 7. Create volumes and directories
RUN mkdir -p db covers cache plugins

# 8. Expose Application Port
EXPOSE 5930

# 9. Volume Configuration for persistence
VOLUME ["/app/db", "/app/covers", "/app/cache", "/app/plugins"]

# 10. Startup Command
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5930", "--timeout", "120", "api:app"]
