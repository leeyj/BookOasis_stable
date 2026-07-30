---
title: "스캔 큐 실행 중 작업이 대기 중(pending)으로 오표시되는 버그 수정"
category: "bugfix"
date: 2026-07-22
severity: "medium"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scanner, queue, status, ui, pending, running]
---

# 버그 내역

## 증상

백그라운드 스캐너 워커 프로세스가 라이브러리 스캔을 정상적으로 수행 중(로그상 메타데이터 파싱 및 스캔 진행 중)임에도 불구하고, 웹 Dashboard 및 대기열 관리 UI (`/api/media/system/queue`)의 상태 목록에서 실행 중 작업이 '대기 중(pending)' 아이콘 및 라벨로만 표기되는 현상.

## 근본 원인

1. `repositories/sqlite/scanner_queue_repository.py` 내 `fetch_queue_status()`의 DB 쿼리가 `status = 'running'`만 한정 조회하여, 워커 재기동 대기(`exit_pending`) 중이거나 상태 동기화 딜레이 시 `running_task`를 `None`으로 판정함.
2. `running` 작업의 레코드 ID가 `pending` 목록 쿼리에서 제외되지 않아, 실행 중인 태스크가 `pending` 목록으로도 동시에 반환되는 Race Condition 발생.

## 수정 사항

### `repositories/sqlite/scanner_queue_repository.py`
- `fetch_queue_status()` 쿼리 업데이트:
  - `status IN ('running', 'exit_pending')` 조건으로 확장하고 `CASE WHEN status = 'running' THEN 1 ELSE 2 END` 순으로 실행 중 작업을 정확히 캡처.
  - 감지된 실행 중 작업의 `id`를 `pending` 목록 조회 쿼리에서 `id != ?` 조건으로 제외하여 중복 및 대기 중 오표기 방지.

## 해결 결과

- 스캔 실행 시 대기열 UI 첫 번째 목록에 **파란색/보라색 '진행 중'** 스피너 뱃지와 세부 단계(VFS 갱신 / 도서 스캔 중)가 정확히 실시간 노출됩니다.
