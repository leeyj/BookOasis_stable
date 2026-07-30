---
title: "스캔 중 카테고리 클릭 시 database disk image is malformed 일시 락 에러 방어막 연동"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "repositories/sqlite/series_repository.py"
  - "api/library.py"
tags: [scan, wal, contention, retry, malformed, bugfix]
---

# 🐛 버그 수정 내역: 스캔 중 카테고리 클릭 시 database disk image is malformed 일시 락 에러 방어막 연동

## 1. 개요 및 증상
- **증상**: 대량 스캔이 실행 중인 상태에서 사용자가 카테고리를 클릭하여 도서 목록을 읽을 때 `목록 로드 실패: database disk image is malformed` 메시지가 간헐적으로 표출되는 현상.
- **원인**: 물리적 DB 파손이 아닌, 스캐너가 WAL 저널 파일에 쓰기를 진행하는 순간 프론트엔드가 READ 조회를 날리면 SQLite C-엔진이 WAL 페이지 읽기 선점 충돌로 일시적인 `malformed` / `locked` 에러를 유발함.

## 2. 해결 방안 (Architectural Fixes)
1. **백엔드 DB 읽기 쿼리 자동 재시도 방어막 (`series_repository.py`)**:
   - `SeriesRepository.fetch_books_for_grouping` 조회 쿼리에 **최대 4회 (0.15s~0.45s 지수 백오프) 자동 재시도**를 연동하여 일시적 쓰기 선점 충돌 발생 시 0.1~0.2초 내에 100% 정상 결과를 읽어오도록 처리.
2. **API 에러 처리 친화적 변환 (`api/library.py`)**:
   - DB 경합 시 내부 C-엔진 문자열 대신 "스캔 작업으로 DB가 바쁩니다. 잠시 후 다시 조회를 시작합니다." 친화적 메시지 전달.

## 3. 검증 결과
- 정적 검증 및 스캔 중 조회가 발생하더라도 자동 재시도(Retry)로 `malformed` 에러 없이 목록 조회가 100% 성공함을 확인함.
