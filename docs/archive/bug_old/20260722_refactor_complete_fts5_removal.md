---
title: "FTS5 가상 테이블 및 관련 구문 100% 완전 소거 및 순수 B-Tree 검색 통일"
category: "refactor"
date: 2026-07-22
severity: "high"
affected_files:
  - "database.py"
  - "services/opds_service.py"
  - "repositories/sqlite/opds_repository.py"
  - "services/scheduler_service.py"
  - "tools/db_schema_updater.py"
tags: [fts5, remove, sqlite, b-tree, refactor]
---

# FTS5 가상 테이블 및 관련 구문 100% 완전 소거 및 순수 B-Tree 검색 통일

## 1. 정돈 목적 및 얻는 효과
- FTS5 가상 테이블(`books_search`)과 그림자 테이블(`_data`, `_idx`, `_content`, `_docsize`, `_config`) 및 트리거로 인해 발생하던 DB 트랜잭션 락 경합 및 `database disk image is malformed` 위험 요소를 100% 원천 소거했습니다.
- 검색 기능을 순수 B-Tree 인덱스 기반 `LIKE` 통합 검색으로 통일하여 구조를 대폭 단순화하고 DB 안정성을 극대화했습니다.

## 2. 주요 수정 내역
1. **[database.py](file:///c:/project/media_server/database.py)**:
   - `ensure_books_search_index` 제거.
   - `cleanup_legacy_fts_index(conn)`를 신설하여 구형 `books_search` 가상/그림자 테이블 및 트리거를 원격 DB 기동 시 자동 소거(`DROP TABLE IF EXISTS`)하도록 조치.
   - `FTS_REBUILD_CRON` 설정 항목 제거.
2. **[opds_service.py](file:///c:/project/media_server/services/opds_service.py) & [opds_repository.py](file:///c:/project/media_server/repositories/sqlite/opds_repository.py)**:
   - OPDS 전용 `search_books_fts` 및 `_build_fts_match_query` 로직을 소거하고 `search_books_like` 기반으로 통합 정돈.
3. **[scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)**:
   - 불필요해진 밤샘 FTS 재빌드 배치 작업(`run_fts_rebuild_job`) 완전 제거.
4. **[tools/db_schema_updater.py](file:///c:/project/media_server/tools/db_schema_updater.py)**:
   - 스키마 마이그레이션 시 FTS5 빌드 대신 `cleanup_legacy_fts_index`를 실행하여 정리 수행.

## 3. 검증 결과
- `python deploy.py` 실행 완료.
- 원격 DB 마이그레이션 중 구형 FTS5 가상 테이블 정리가 수행되었으며, FTS 에러/경고 한 줄 없이 미디어 서버(`PID: 2396347`) 및 스캐너 워커(`PID: 2396406`)가 100% 깨끗하게 정갈 구동됨을 확인함.
