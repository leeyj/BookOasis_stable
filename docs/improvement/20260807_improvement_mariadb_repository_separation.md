---
title: "SQLite 및 MariaDB 쿼리/레포지토리 완전 분리 아키텍처 구축"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [mariadb, sqlite, architecture, repository_pattern, native_sql, improvement]
---

# 🚀 [아키텍처 개선] SQLite 및 MariaDB 쿼리/레포지토리 완전 분리 구축

## 1. 개요 및 배경
- **배경**: 기존 미디어 서버는 SQLite용 SQL 쿼리를 실행 시 정규식(`_convert_sql`)으로 MariaDB 방언으로 변환하여 사용했으나, 구문 오변환, 다중 공백/줄바꿈 인식 한계, MariaDB 1064 Syntax Error 및 DB 고유 기능 활용 제약 등 다수의 런타임 결함이 지속 유발됨.
- **목적**: 런타임 SQL 자동 변환 레이어의 위험성을 근본 차단하고 DB 성능과 가독성을 극대화하기 위해 `repositories/mariadb/` 전용 Native SQL 레이어를 구축하고 동적 팩토리 라우터로 이원화.

## 2. 주요 개선 사항 (수정/생성 소스 파일)

### 1) [`c:\project\media_server\repositories\mariadb/`](file:///c:/project/media_server/repositories/mariadb) (신규 패키지 구축)
- MariaDB Native SQL 기반 17개 레포지토리 모듈 완전 구현:
  - `audiobook_repository.py`, `book_offset_repository.py`, `book_repository.py`, `book_scan_repository.py`, `category_repository.py`, `collection_repository.py`, `db_tuning_repository.py`, `metadata_repository.py`, `opds_repository.py`, `plugin_repository.py`, `reading_progress_repository.py`, `scanner_queue_repository.py`, `scheduler_repository.py`, `series_repository.py`, `settings_repository.py`, `trash_repository.py`, `user_repository.py`
  - MariaDB Native 문법 적용: `%s` 파라미터 바인딩, `REPLACE INTO` / `ON DUPLICATE KEY UPDATE` Upsert, `` `key` `` 이스케이프, `DATE_FORMAT()`, `CONCAT()` 적용.

### 2) [`c:\project\media_server\repositories\__init__.py`](file:///c:/project/media_server/repositories/__init__.py)
- `DB_ENGINE` / `DBMS` 설정값(`mariadb` | `sqlite`)에 따라 알맞은 Native 레포지토리 패키지를 동적 로드하도록 동적 라우팅 알고리즘 확장.
- 상위 `services/` 및 `api/`의 기존 임포트 구문(`from repositories.series_repository import SeriesRepository`) 100% 하위 호환 보장.

## 3. 기대 효과
- **결함 원천 차단**: 런타임 SQL 정규식 변환에 따른 1064 Syntax Error 및 이스케이프 오류 결함 100% 제거.
- **쿼리 성능 극대화**: MariaDB Native 최적화 쿼리를 직접 수행하여 대용량 DB 처리 속도 및 인덱스 효율성 대폭 향상.
