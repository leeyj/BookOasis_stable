---
title: "RAM 환수 후 서브-배치 재기동시 exit_pending 태스크 running 선점 불가 버그 수정"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scanner, queue, exit_pending, running, acquire_task]
---

# RAM 환수 후 서브-배치 재기동시 exit_pending 태스크 running 선점 불가 버그 수정

## 1. 버그 개요
- 1회 처리 용량 한도(`LAZY_SCAN_MAX_BATCH_SIZE_MB`)에 도달하거나 메모리 제한 초과 시 `lazy_scanner` 프로세스가 `Exit Code 10`을 남기며 현재 태스크를 `exit_pending` 상태로 변경함.
- `scanner_queue` 서브-배치 무한 루프에서 다음 연쇄 배치를 기동하려고 하나, `try_acquire_task` 및 `get_next_pending_task`의 DB UPDATE 쿼리가 `status = 'pending'` 조건만 수용하고 `exit_pending` 상태를 픽업 및 `running`으로 전환하지 못하여 스캔 작업이 대기중 상태에 계속 머무는 현상.

## 2. 원인 분석
- `ScannerQueueRepository.try_acquire_task()`의 SQL 조건: `WHERE id = ? AND status = 'pending'`
- `exit_pending` 상태인 태스크를 `running`으로 상태 변경(선점)하려고 시도할 때 `rowcount = 0`이 되어 기동 실패 후 `continue` 루프로 빠짐.

## 3. 수정 사항
- `repositories/sqlite/scanner_queue_repository.py`:
  - `try_acquire_task()`, `get_pending_task_by_key()`, `get_next_pending_task()` 쿼리의 대상 상태 조건에 `exit_pending`을 추가하여 `status IN ('pending', 'exit_pending')`로 보완.
  - 연쇄 서브-배치 기동 시 `exit_pending` 태스크가 선순위로 즉시 `running`으로 선점되어 연속 스캔되도록 보장.

## 4. 검증 결과
- 1회 용량 한도 도달 후 프로세스가 재시작하면 대기열 UI 상태가 멈추지 않고 즉각 `exit_pending` → `running(진행 중)`으로 전환되어 연속 스캔이 정상 작동함을 확인함.
