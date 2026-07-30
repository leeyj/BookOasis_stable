---
title: "스캔 시 is_deleted=1 도서 is_deleted=0 원복 미흡 및 목록 미노출 버그 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "tools/scanner/engine.py"
  - "tools/scanner/db_writer.py"
tags: [scan, is_deleted, restoration, db_writer, bugfix]
---

# 🐛 버그 수정 내역: 스캔 시 is_deleted=1 도서 is_deleted=0 원복 미흡 및 목록 미노출 버그 수선

## 1. 개요 및 증상
- **증상**: 스캐너 로그에는 파일 스캔 성공으로 기록되나, 카테고리 화면에서는 "등록된 책이 없습니다" (0건)으로 노출되는 현상.
- **원인**: 과거 삭제/휴지통 이력으로 인해 DB(`books` 테이블)에 `is_deleted = 1` 상태로 존재하던 도서 파일이 실물 경로에 존재하여 재스캔되더라도, `bulk_update_books` 쿼리에 `is_deleted = 0` (정상 복원) 및 `library_id` 갱신 세팅이 누락되어 화면 필터(`COALESCE(is_deleted, 0) = 0`)에 의해 차단되었던 현상.

## 2. 해결 방안 (Architectural Fixes)
1. **스캔 UPDATE 쿼리 시 `is_deleted = 0` 및 `library_id` 강제 원복 (`db_writer.py`)**:
   - `bulk_update_books` UPDATE 쿼리에 `is_deleted = 0` 및 `library_id = ?` 구문을 추가하여 실물 파일이 존재하여 스캔될 경우 삭제 상태 도서가 즉시 정상 복원되어 화면 목록에 100% 표출되도록 수선.

```sql
UPDATE books SET 
    is_deleted   = 0,
    library_id   = COALESCE(?, library_id),
    series_name  = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE series_name END,
...
```

## 3. 검증 결과
- 정적 검증 및 `is_deleted = 1` 도서 재스캔 시 `is_deleted = 0` 원복이 정상 적용됨을 확인함.
