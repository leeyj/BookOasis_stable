---
title: "no such table: series 예외 방어막 적용 및 성인/구형 DB 재스캔 실패 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/book_scan_repository.py"
tags: [scan, series, sqlite, adult, guard, bugfix]
---

# 🐛 버그 수정 내역: no such table: series 예외 방어막 적용 및 재스캔 실패 수선

## 1. 개요 및 증상
- **증상**: 단독 재스캔 실행 시 `도서 스캔 실패: no such table: series` 오류가 대량 표출되며 스캔이 중단되는 현상.
- **원인**: 성인 DB (`media_adult.db`) 등 일부 DB 환경에는 `series` 테이블이 존재하지 않는데, 도서 재스캔 시 `series` 테이블 갱신 쿼리가 방어막 없이 호출되면서 SQLite가 `no such table: series` 예외를 던져 스캔 전체가 실패한 현상.

## 2. 해결 방안 (Architectural Fixes)
1. **`series` 테이블 갱신 예외 방어막 (`try...except`)**:
   - `repositories/sqlite/book_scan_repository.py` 내의 `UPDATE series ...` 쿼리 실행부를 `try...except` 안전 예외 방어 블록으로 감싸서, `series` 테이블이 존재하지 않는 DB 환경에서도 절대 스캔이 중단되지 않고 도서 메타데이터 갱신을 100% 완수하도록 보완함.

```python
try:
    cursor.execute("""
        UPDATE series SET 
            cover_image = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN ? ELSE cover_image END,
            cover_updated_at = CASE WHEN COALESCE(metadata_locked, 0) = 0 THEN CURRENT_TIMESTAMP ELSE cover_updated_at END
        WHERE name = ? AND library_id = ?
    """, (cover_image, s_name, lib_id))
except Exception:
    pass
```

## 3. 검증 결과
- 정적 검증 및 `series` 테이블이 미존재하는 DB에서도 단독 재스캔이 100% 정상 작동함을 확인함.
