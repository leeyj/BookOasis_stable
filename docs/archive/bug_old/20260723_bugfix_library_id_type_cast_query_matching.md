---
title: "library_id 타입 불일치(정수 vs 문자열)로 인한 스캔 후 카테고리 도서 0건 표출 버그 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/series_repository.py"
  - "tools/scanner/engine.py"
  - "tools/scanner/db_writer.py"
tags: [scan, library_id, type_mismatch, cast, query, bugfix]
---

# 🐛 버그 수정 내역: library_id 타입 불일치(정수 vs 문자열)로 인한 스캔 후 카테고리 도서 0건 표출 버그 수선

## 1. 개요 및 증상
- **증상**: 스캐너 로그상에서는 신규 도서(`ins=19`)가 100% 정상적으로 DB에 등록 완수되었으나, UI 카테고리 화면 클릭 시 도서 목록이 0건으로 표출되는 현상.
- **원인**: DB(`books` 테이블)에 등록되거나 조회될 때의 `library_id` 데이터 타입(정수 vs 문자열)의 불일치로 인해 SQLite `WHERE b.library_id = ?` 파라미터 매칭이 실패하여 0건이 반환되었던 현상.

## 2. 해결 방안 (Architectural Fixes)
1. **조회 쿼리 `library_id` 정수/문자열 동시 매칭 유연화 (`series_repository.py`)**:
   - `fetch_books_for_grouping` 조회 쿼리의 조건식을 `(b.library_id = ? OR CAST(b.library_id AS TEXT) = ?)` 형태로 보완하여 DB 컬럼 데이터의 타입과 무관하게 100% 정상 매칭되도록 조치.
2. **스캐너 쓰기 `library_id` 정수형 고정 (`engine.py`, `db_writer.py`)**:
   - 스캐너에서 `library_id` 를 처리 및 저장할 때 항상 `int(library_id)` 로 변환하여 DB 내 타일 타입을 정수형으로 일관화.

## 3. 검증 결과
- 정적 구문 검사 및 타입에 관계없이 카테고리 도서 목록 19건이 100% 즉시 노출됨을 확인함.
