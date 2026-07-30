---
title: "UNIQUE file_path 충돌 시 UPSERT를 통한 카테고리 자동 이관 및 is_deleted=0 복원 근본 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "tools/scanner/db_writer.py"
tags: [scanner, db_writer, upsert, on_conflict, file_path, bugfix]
---

# 🐛 버그 수정 내역: UNIQUE(file_path) 충돌 시 UPSERT를 통한 카테고리 자동 이관 및 is_deleted=0 복원 근본 수선

## 1. 개요 및 근본 원인
- **증상**: 스캐너 로그상에서는 신규 도서(`ins=19`)가 정상 커밋되었다고 나오나, 해당 카테고리 화면 클릭 시 도서가 0건으로 나오는 현상.
- **근본 원인**: 스캔된 도서 파일들이 과거 다른 카테고리(`library_id = 36`)에서 삭제되어 `is_deleted = 1` 상태로 DB에 고유 파일 경로(`file_path`)가 이미 등록되어 있었음. 스캐너가 신규 카테고리(`library_id = 54`)로 인서트를 시도할 때 `INSERT OR IGNORE` 쿼리가 기존 `file_path` UNIQUE 제약조건 충돌로 인해 신규 인서트를 무시(IGNORE)해버려 `library_id = 54`로 이관되지 못하고 기존 `library_id = 36`, `is_deleted = 1` 상태에 계속 갇혀 있었음.

## 2. 해결 방안 (Architectural Root Cause Fixes)
1. **UPSERT (`ON CONFLICT(file_path) DO UPDATE`) 구문 전격 도입 (`db_writer.py`)**:
   - `bulk_insert_books` 쿼리를 `INSERT INTO books ... ON CONFLICT(file_path) DO UPDATE SET library_id = EXCLUDED.library_id, is_deleted = 0, ...` 구문으로 전환.
   - 구형 카테고리에 삭제 상태로 갇혀있던 도서라도 새로 스캔된 카테고리로 **`library_id`가 자동 변경되고 `is_deleted = 0`으로 완벽히 복원**되어 카테고리 목록 화면에 100% 즉시 표출되도록 원천 수선함.

```sql
INSERT INTO books 
(library_id, title, series_name, author, isbn, file_path, file_format, total_pages, cover_image, publisher, link, score, summary, release_date, genre, tags, file_mtime, file_size, is_deleted) 
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
ON CONFLICT(file_path) DO UPDATE SET
    library_id   = EXCLUDED.library_id,
    is_deleted   = 0,
    title        = EXCLUDED.title,
    series_name  = EXCLUDED.series_name,
    cover_image  = CASE WHEN COALESCE(books.metadata_locked, 0) = 0 THEN COALESCE(NULLIF(EXCLUDED.cover_image, ''), books.cover_image) ELSE books.cover_image END,
    file_mtime   = EXCLUDED.file_mtime,
    file_size    = EXCLUDED.file_size
```

## 3. 검증 결과
- 정적 구문 검증 및 구형 카테고리에 갇힌 도서가 새 카테고리로 자동 이관 및 복원됨을 확인함.
