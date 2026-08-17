# 🍃 BookOasis MariaDB 전환 및 마이그레이션 통합 완벽 가이드

이 문서는 BookOasis 미디어 서버를 기본 SQLite 엔진에서 **고성능 대용량 MariaDB 엔터프라이즈 엔진**으로 전환하는 방법과 기존 데이터(도서 정보, 읽은 기록, 즐겨찾기 등)를 손실 없이 이관하는 절차를 아주 쉽고 상세하게 설명합니다.

---

## 🚀 왜 MariaDB로 전환해야 하나요?

1. **대용량 미디어(20만 권 이상) 쿼리 쾌속 최적화**: 시리즈 그룹핑 및 대표 표지 선점 SQL 처리 속도가 1.9초에서 **0.02초(100배 이상)**로 대폭 향상됩니다.
2. **동시 접속 및 동시 스캔 성능 보장**: SQLite의 DB Lock(잠금) 현상 없이 여러 기기에서 동시에 읽고 스캔할 수 있습니다.
3. **완벽한 데이터 보존 마이그레이션 도구 제공**: 기존 사용 중이던 SQLite 데이터베이스를 단 **1초 만에 MariaDB로 자동 이관**해 드립니다.

---

## 🛠️ 준비 사항 (사전 확인)

전환 작업 전 아래 2가지 중 **자신의 상황에 맞는 설치 유형**을 하나 선택하세요:

- **[유형 A] MariaDB가 없는 경우 (권장)**: Docker Compose로 BookOasis와 MariaDB 컨테이너를 한꺼번에 자동 구동.
- **[유형 B] 이미 사용 중인 MariaDB가 있는 경우**: Synology NAS, 헤츠너, 기존 MariaDB 컨테이너에 연결.

---

## 📌 [유형 A] Docker Compose로 MariaDB 자동 함께 기동하기 (가장 쉬운 방법)

새로운 MariaDB 컨테이너를 함께 띄워서 운영하고 싶으신 분들을 위한 **가장 간편한 방법**입니다.

### 1단계: 제공되는 `docker-compose.mariadb.yml` 활용

프로젝트에 포함된 `docker-compose.mariadb.yml` 파일은 BookOasis 서버와 MariaDB 컨테이너, 그리고 4개 미디어 DB(`media_general`, `media_adult`, `media_audiobook`, `media_video`) 및 계정 권한 초기화 스크립트(`init.sql`)를 자동으로 함께 구성해 드립니다.

```bash
# 기존 컨테이너 중지
docker-compose down

# MariaDB 포함 구성으로 기동
docker-compose -f docker-compose.mariadb.yml up -d
```

> 💡 **참고**: 비밀번호 변경을 원하시면 `docker-compose.mariadb.yml` 파일 내의 `MARIADB_PASSWORD` 및 `MYSQL_ROOT_PASSWORD` 값을 원하는 비밀번호로 수정 후 실행하세요.

---

## 📌 [유형 B] 기존 외부 MariaDB (NAS / 호스트 DB)에 연결하기

이미 Synology NAS, 타 미디어 서버, 또는 외부 MariaDB를 운영 중이신 경우입니다.

### 1단계: MariaDB에 데이터베이스 및 권한 생성 (1회 필요)

외부 MariaDB의 phpMyAdmin, DBeaver, 또는 CLI에 접속하여 4개 미디어 DB와 권한을 생성합니다:

```sql
CREATE DATABASE IF NOT EXISTS media_general CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_adult CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_audiobook CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE DATABASE IF NOT EXISTS media_video CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

-- 사용자 생성 및 권한 부여 ('your_password'를 원하는 비밀번호로 변경하세요)
CREATE USER IF NOT EXISTS 'bookoasis'@'%' IDENTIFIED BY 'your_password';
-- 주의: "GRANT ... ON media_%.*" 같은 와일드카드 패턴은 GRANT 문에서 지원되지 않습니다
-- (실제 실행 시 SQL 구문 오류). 아래처럼 현재 4개 DB에 개별로 권한을 부여하세요. 이후
-- BookOasis가 새 미디어 세션을 추가하면(예: 앞으로 media_X가 새로 생기면) 이 GRANT 블록에
-- 한 줄만 추가해서 다시 실행하면 됩니다.
GRANT ALL PRIVILEGES ON media_general.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_adult.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_audiobook.* TO 'bookoasis'@'%';
GRANT ALL PRIVILEGES ON media_video.* TO 'bookoasis'@'%';
FLUSH PRIVILEGES;
```

### 2단계: `docker-compose.override.yml` 작성

기존 `docker-compose.yml`을 직접 수정하지 않고, 같은 폴더에 `docker-compose.override.yml` 파일을 만들어 접속 정보를 입력합니다.

```yaml
version: "3.8"

services:
  bookoasis:
    environment:
      - DB_ENGINE=mariadb
      - MARIADB_HOST=host.docker.internal    # 또는 MariaDB 서버 IP (예: 192.168.0.20)
      - MARIADB_PORT=3306
      - MARIADB_USER=bookoasis
      - MARIADB_PASSWORD=your_password
      - MARIADB_DATABASE_PREFIX=media_
    extra_hosts:
      - "host.docker.internal:host-gateway" # 호스트 OS의 MariaDB 접속용
```

### 3단계: 컨테이너 재기동

```bash
docker-compose down
docker-compose up -d
```

---

## 📦 2. 기존 SQLite 데이터를 MariaDB로 자동 마이그레이션하기

서버가 MariaDB 모드로 부팅되면, 기존 SQLite에 들어있던 **읽던 위치, 완독 상태, 즐겨찾기, 사용자 계정 데이터**를 MariaDB로 100% 자동 이관할 수 있습니다.

### 마이그레이션 실행 명령어 (1초 소요)

BookOasis 컨테이너가 실행 중인 상태에서 터미널에 아래 명령어 1 줄을 입력합니다:

```bash
docker exec -it bookoasis python tools/migrator_sqlite_to_mariadb.py
```

#### 🖥️ 실행 결과 화면 예시:
```text
============================================================
 BookOasis SQLite ➔ MariaDB 데이터 마이그레이터
============================================================
[+] MariaDB 커넥션 연결 성공 (Host=127.0.0.1:3306)
[1/3] Database: media_general 이관 중...
  - [books] 73,234 건 복사 완료
  - [users] 2 건 복사 완료
  - [user_progress] 1,450 건 복사 완료
  - [user_favorites] 84 건 복사 완료
[2/3] Database: media_adult 이관 중...
[3/3] Database: media_audiobook 이관 중...
============================================================
✨ 모든 데이터 마이그레이션이 성공적으로 완료되었습니다!
============================================================
```

---

## ❓ 자주 묻는 질문 및 트러블슈팅 (FAQ)

### Q1. `Access denied for user 'bookoasis'@'%' to database 'media_adult'` 또는 `SELECT command denied ... for table 'media_video'.'videos'` 에러가 발생해요!
- **원인**: MariaDB 공식 도커 이미지는 기본적으로 1개의 DB만 생성하므로 나머지 DB 권한이 빠져있을 수 있습니다. 특히 BookOasis가 버전업하며 새 미디어 세션(예: v2.1.0의 영상 강좌 → `media_video`)을 추가하면, **이미 예전에 MariaDB로 전환해서 쓰고 계시던 분**은 새로 생긴 DB(또는 그 안의 특정 테이블)에 대한 권한이 없어서 이 에러를 만날 수 있습니다. `Access denied ... to database`(에러 1044)와 `SELECT command denied ... for table`(에러 1142)은 같은 근본 원인(권한 부족)의 두 가지 다른 증상일 뿐이며 해결책은 동일합니다. Docker Compose 번들형(유형 A)이라도, `docker-entrypoint-initdb.d/init.sql`은 MariaDB 데이터 볼륨이 **완전히 비어있는 최초 1회**에만 실행되므로 기존 컨테이너를 업데이트만 한 경우엔 자동으로 반영되지 않습니다.
- **해결책**: Docker Compose 번들형(유형 A)이라면 최신 버전의 `docker-compose.mariadb.yml`을 그대로 사용하세요 — `mariadb-grant-repair` 서비스가 `docker-compose up`을 실행할 때마다 자동으로 4개 DB에 대한 GRANT를 재확인/재부여하므로, 앞으로는 새 미디어 세션이 추가돼도 이 작업을 손으로 다시 할 필요가 없습니다. 외부 MariaDB(유형 B)를 쓰신다면 아래 SQL을 1회 실행하세요.
  ```sql
  CREATE DATABASE IF NOT EXISTS media_video CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
  GRANT ALL PRIVILEGES ON media_general.* TO 'bookoasis'@'%';
  GRANT ALL PRIVILEGES ON media_adult.* TO 'bookoasis'@'%';
  GRANT ALL PRIVILEGES ON media_audiobook.* TO 'bookoasis'@'%';
  GRANT ALL PRIVILEGES ON media_video.* TO 'bookoasis'@'%';
  FLUSH PRIVILEGES;
  ```
  (`GRANT ... ON media_%.*` 같은 와일드카드 패턴은 GRANT 문에서 지원되지 않아 SQL 구문 오류가 발생하니 사용하지 마세요.)

### Q2. 기존 SQLite로 되돌리고 싶으면 어떻게 하나요?
- `docker-compose.override.yml`에서 `DB_ENGINE=sqlite`로 변경하거나 해당 파일을 삭제 후 `docker-compose restart` 하시면 즉시 기존 SQLite 데이터베이스로 원복됩니다. 기존 데이터는 전혀 훼손되지 않습니다.

### Q3. 리눅스 파일 시스템에서 파일명 대소문자가 달라도 잘 구분되나요?
- 네! BookOasis는 MariaDB 이관 시 `file_path` 컬럼에 `utf8mb4_bin` (바이너리 정밀 매칭) 콜레이션을 자동 적용하므로 대소문자 및 특수문자가 들어간 파일 경로도 100% 완벽하게 보존됩니다.

---
*최종 업데이트: 2026-08-06 (v1.8.2 기준)*
