---
title: Docker 사용자용 MariaDB 마이그레이션 가이드
project: BookOasis
category: guide
date: 2026-08-06
---

# 🐳 Docker 사용자용 MariaDB 마이그레이션 가이드

BookOasis는 최신 버전으로 업데이트 시 **데이터베이스 및 스키마가 존재하지 않으면 자동으로 MariaDB 데이터베이스(`media_general`, `media_adult`, `media_audiobook`) 및 스키마를 자동 생성**합니다.

이후 도커 컨테이너 내부의 마이그레이션 도구(`python tools/migrator_sqlite_to_mariadb.py`)를 1회 실행하여 기존 SQLite 데이터를 MariaDB로 동기화할 수 있습니다.

---

## 시나리오 1. 이미 사용 중인 기존 MariaDB가 있는 경우 (외부/호스트 DB)

이미 Synology NAS, 외부 MariaDB 컨테이너, 또는 호스트 MariaDB 서버를 운영 중인 사용자를 위한 절차입니다.

### 1단계: `docker-compose.override.yml` 작성
기존 `docker-compose.yml`을 수정하지 않고 `docker-compose.override.yml` 파일을 생성하여 접속 정보를 지정합니다.

```yaml
version: "3.8"

services:
  bookoasis:
    environment:
      - DB_ENGINE=mariadb
      - MARIADB_HOST=host.docker.internal    # Linux 호스트 또는 외부 MariaDB IP/도메인 지정
      - MARIADB_PORT=3306
      - MARIADB_USER=your_db_user            # 기존 MariaDB 사용자 계정
      - MARIADB_PASSWORD=your_db_password    # 기존 MariaDB 비밀번호
      - MARIADB_DATABASE_PREFIX=media_       # DB 이름 접두사 (미지정 시 media_)
    extra_hosts:
      - "host.docker.internal:host-gateway" # 호스트 OS의 MariaDB 접속용 설정
```
> ※ 동일한 Docker 네트워크 상에 기존 MariaDB 컨테이너가 있다면 `MARIADB_HOST`에 컨테이너 이름을 적고 `networks` 설정을 추가하시면 됩니다.

### 2단계: 최신 이미지 빌드 및 재기동
```bash
docker-compose down
docker-compose pull   # 또는 docker-compose build
docker-compose up -d
```
*※ 컨테이너가 가동되면서 MariaDB에 `media_general`, `media_adult`, `media_audiobook` 데이터베이스 및 스키마가 자동 생성됩니다.*

### 3단계: 기존 SQLite 데이터를 MariaDB로 1-Click 이전
도커 컨테이너 내부로 접속하거나 `docker exec` 명령어로 마이그레이션 명령을 실행합니다.

```bash
docker exec -it bookoasis python tools/migrator_sqlite_to_mariadb.py
```
> **진행 결과**: `libraries`, `books`, `user_progress`, `audiobooks`, `audiobook_progress` 등 기존의 모든 데이터가 MariaDB로 고속 대량 이관됩니다.

---

## 시나리오 2. MariaDB까지 컨테이너로 신규 구축하여 이관하는 경우

기존에는 SQLite만 사용하다가, Docker Compose로 MariaDB 컨테이너를 한꺼번에 새로 띄워서 데이터를 이관하는 경우입니다.

### 1단계: `docker-compose.override.yml` 작성
MariaDB 전용 환경 구성을 오버라이드 파일에 정의하여 띄웁니다.

```yaml
version: "3.8"

services:
  bookoasis:
    environment:
      - DB_ENGINE=mariadb
      - MARIADB_HOST=mariadb
      - MARIADB_PORT=3306
      - MARIADB_USER=bookoasis
      - MARIADB_PASSWORD=bookoasis_pass
      - MARIADB_DATABASE_PREFIX=media_
    depends_on:
      redis:
        condition: service_started
      mariadb:
        condition: service_healthy

  mariadb:
    image: mariadb:10.11
    container_name: bookoasis_mariadb
    restart: unless-stopped
    environment:
      - MARIADB_ROOT_PASSWORD=root_pass
      - MARIADB_USER=bookoasis
      - MARIADB_PASSWORD=bookoasis_pass
      - MARIADB_DATABASE=media_general
    volumes:
      - ./mariadb_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 5
```

### 2단계: MariaDB 포함 전체 컨테이너 구동
```bash
docker-compose down
docker-compose up -d
```
*※ `mariadb` 컨테이너가 건강 상태(Healthy)에 도달하면 `bookoasis` 컨테이너가 구동되며 필요한 DB 3개를 자동 생성합니다.*

### 3단계: 기존 SQLite 데이터를 MariaDB로 1-Click 이전
```bash
docker exec -it bookoasis python tools/migrator_sqlite_to_mariadb.py
```

---

## 🔒 4단계: 이전 완료 후 무결성 검증 및 백업 (공통)

1. **웹 브라우저 접속**: BookOasis 웹UI 접속 후 기존 라이브러리 목록, 도서, 읽기/듣기 진행도가 정상 표출되는지 확인합니다.
2. **기존 SQLite 백업**: 마이그레이션이 완전히 성공한 후 기존 `./db/*.db` 파일은 백업 용도로 보관하시면 됩니다. (원할 경우 `.env`나 override 파일에서 `DB_ENGINE=sqlite`로 변경하면 언제든 기존 SQLite 모드로 복구 가능합니다.)
