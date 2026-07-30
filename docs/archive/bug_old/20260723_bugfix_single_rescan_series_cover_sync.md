---
title: "단독 재스캔 시 시리즈(series) 테이블 커버 경로 미동기화 및 새로고침 커버 유실 버그 수정"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/book_scan_repository.py"
  - "services/book_scan_service.py"
tags: [scanner, rescan, series, cover, sync, bugfix]
---

# 🐛 버그 수정 내역: 단독 재스캔 시 series 테이블 커버 미동기화 수선

## 1. 개요 및 증상
- **증상**: 개별 도서(단행본 카드)에서 [재스캔] 실행 직후에는 화면에 새 표지가 정상적으로 노출되지만, 브라우저를 새로고침(F5)하면 이전 커버 URL이 다시 불러와져 옛날 표지로 원복되는 현상.
- **원인**: 단독 재스캔 API 실행 시 `books` (단행본 테이블)의 `cover_image`는 새 표지 경로로 갱신되었으나, 시리즈 목록 및 대시보드가 참조하는 `series` (시리즈 테이블)의 `cover_image` 필드가 동기화되지 않고 이전 파일 경로로 남아있었음.

## 2. 영향 범위 (Impact)
- **영향 받는 모듈**:
  - `repositories/sqlite/book_scan_repository.py`
  - `services/book_scan_service.py`
  - 대시보드 및 시리즈 카드 뷰어 컴포넌트

## 3. 수정 사항 (Fixes)
- `BookScanRepository.update_book_scanned_metadata()` 함수 내에 단독 재스캔으로 도서 표지가 갱신될 시, 해당 도서의 시리즈(`series` 테이블) 대표 `cover_image` 및 `cover_updated_at`을 최신 표지 경로로 함께 갱신하는 트랜잭션 SQL 쿼리 추가.
- `metadata_locked == 0` 조건 하에서 안전하게 수행되도록 보장.

```sql
-- series 테이블 커버 자동 동기화 쿼리
UPDATE series SET 
    cover_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN ? ELSE cover_image END,
    cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN CURRENT_TIMESTAMP ELSE cover_updated_at END
WHERE name = ? AND library_id = ?;
```

## 4. 검증 결과
- 정적 구문 검사 및 단독 재스캔 실행 후 새로고침(F5) 시 최신 커버 유지 확인.
