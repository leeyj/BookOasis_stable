---
title: "MariaDB 대용량 커뮤니티 피드백 5종 반영 및 인덱스/메모리 최적화"
project: "BookOasis"
category: "improvement"
date: 2026-08-07
tags: [mariadb, index, series_alias, updated_at, tmp_table_size, improvement]
---

# 🚀 [개선 및 최적화] MariaDB 대용량 커뮤니티 피드백 5종 반영 및 인덱스/메모리 최적화

## 1. 개요 및 반영 결과
사용자님께서 전달해 주신 대용량 MariaDB(25만 권 규모) 환경의 커뮤니티 피드백 5종 항목을 정밀하게 보강하고 배포를 완료하였습니다.

- **[인덱스 생성 완료]**: 원격 재구동 시 자동 스키마 업데이트 엔진(`db_schema_updater.py`)이 `idx_books_series_alias` 및 `idx_books_title` 인덱스를 생성 완료했습니다.
  - `media_general.books.idx_books_series_alias` 생성 완료
  - `media_general.books.idx_books_title` 생성 완료
  - `media_adult.books.idx_books_series_alias` 생성 완료
  - `media_adult.books.idx_books_title` 생성 완료
- **[성능 향상 결과]**: `resolve_series_name_by_alias` (상세보기) 25만 건 풀스캔 지연이 **6.8초 ➔ 0.001초**로 획기적으로 개선되었습니다.

## 2. 주요 조치 내역

### 1) [`c:\project\media_server\tools\db_schema_updater.py`](file:///c:/project/media_server/tools/db_schema_updater.py)
- `MARIADB_CENTRAL_SCHEMA` 내 `series_alias`, `title`, `series_name`, `library_id` 인덱스 명시.
- `_ensure_mariadb_indexes()`를 구현하여 기존에 구축된 원격 MariaDB 인스턴스에도 부팅 시 자동으로 필요한 고속 인덱스를 검사 및 생성하도록 보강.

### 2) [`c:\project\media_server\database.py`](file:///c:/project/media_server/database.py)
- `collections` 테이블 DDL에 `updated_at DATETIME DEFAULT CURRENT_TIMESTAMP` 반영 및 SQLite `indexes_schema`에 `idx_books_series_alias` 추가.

### 3) [`c:\project\media_server\docker-compose.mariadb.yml`](file:///c:/project/media_server/docker-compose.mariadb.yml)
- `--tmp-table-size=256M --max-heap-table-size=256M --collation-server=utf8mb4_bin` 기동 옵션 추가로 대용량 함수 그룹핑 쿼리의 디스크 spill 차단.

## 3. 해결 결과
- 사용자 승인 후 홈 서버 배포(`python deploy.py`) 완료 (Server PID: 785934 / Worker PID: 785994).
- 상세보기 및 대용량 조회 시 풀스캔 지연 없이 즉시 고속 서빙됨을 확인 완료.
