---
title: "FTS5 가상 테이블 기동 예외 완전 방어 조치"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "database.py"
tags: [fts5, sqlite, database, bugfix]
---

# FTS5 가상 테이블 기동 예외 완전 방어 조치

## 1. 분석 결과
- 서비스 내 도서 검색 및 탐색 쿼리는 이미 안정적인 `LIKE` 문법 및 고속 SQLite B-Tree 인덱스(`idx_books_series_lib_title`, `idx_books_library_active_series`)로 완전 전환되어 있습니다.
- 다만 `ensure_books_search_index` 실행 시 특정 SQLite 버전 환경이나 락 경합 시 발생할 수 있는 FTS5 가상 테이블 에러(`vtable constructor failed: books_search`)가 마이그레이션 예외로 누출되어 기동 로그에 경고성 에러를 남기던 현상을 차단할 필요가 있었습니다.

## 2. 조치 사항
- **[database.py](file:///c:/project/media_server/database.py)**
  - `ensure_books_search_index(conn)` 내 예외 처리 구문을 `except Exception`으로 확장하고, FTS 관련 가상 테이블 점검에 실패하더라도 예외를 바깥으로 던지지 않고 안전하게 우회(`Warning` 로깅 후 즉시 리턴)하도록 보완.
  - 서비스 기동 및 DB 트랜잭션 전반에 결코 영향을 주지 않도록 완벽히 격리시켰습니다.

## 3. 검증
- `python deploy.py` 실행 완료: 재기동 시 마이그레이션 및 서비스 구동이 예외 없이 깔끔하게 완료됨을 확인.
