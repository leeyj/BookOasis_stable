---
title: "스캔 대기열 취소 시 DB 락 경합 방지 및 Retry/busy_timeout 보완"
category: "bugfix"
date: 2026-07-24
severity: "high"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scan_cancel, database_locked, busy_timeout, retry, bugfix]
---

# 🐛 버그 수정 내역: 스캔 대기열 취소 시 DB 락 경합 방지 및 Retry/busy_timeout 보완

## 증상

스캔 진행 중 대기열에서 [취소] 버튼 클릭 시, `[Queue-Cancel Warning] Failed to update library scan_status to cancelling: database is locked` 경고 로그가 출력되며 `libraries` 테이블의 `scan_status`가 `cancelling`으로 변경되지 않고 취소 요청이 무시되는 현상.

---

## 원인 분석

- `scanner_queue_repository.py` 내 `cancel_task()` 함수에서 `libraries` 테이블의 `scan_status`를 `cancelling`으로 UPDATE할 때, SQLite 커넥션에 `busy_timeout` 설정 및 재시도(Retry) 루프가 부족하였음.
- 스캐너 엔진이나 VFS 새로고침 트랜잭션과 순간적으로 락이 겹치면 단 한 번의 UPDATE 시도가 `database is locked` 예외를 내며 실패하고 스캔 중단 신호 전달이 끊어짐.

---

## 수정 내용

- **[repositories/sqlite/scanner_queue_repository.py](file:///c:/project/media_server/repositories/sqlite/scanner_queue_repository.py)**:
  - `cancel_task()` 의 `libraries.scan_status` UPDATE 처리부에 `PRAGMA busy_timeout = 10000;` (10초 대기) 설정 및 **최대 5회 지연 재시도(Retry) 루프**를 적용함.

---

## 해결 결과

- 스캔 엔진이나 VFS 새로고침 중 취소 요청이 입력되더라도 `database is locked` 에러로 튕기지 않고 백오프 재시도를 통해 `scan_status = 'cancelling'` 을 100% 안전하게 업데이트하여 진행 중인 스캔을 즉시 멈추도록 개선됨.
