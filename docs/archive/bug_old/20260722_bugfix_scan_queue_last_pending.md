---
title: "스캔 큐 3개 적재 시 마지막 작업 pending 고착 버그 수정"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "services/scanner_queue.py"
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scanner, queue, pending, race-condition]
---

# 버그 내역

## 증상

스캔 작업을 3개 큐에 쌓으면 마지막 스캔이 실행되지 않고 `pending` 상태로 영구 대기하며, 수동으로 취소해야만 해당 상태에서 벗어날 수 있는 현상.

## 영향도

- **대상**: 라이브러리 스캔 또는 전체 스캔(`scan-all`) 시 3개 이상 큐를 적재하는 모든 시나리오
- **심각도**: High — 마지막 스캔 작업이 영구 대기 상태로 남아 자동 진행이 불가능함
- **사용자 경험**: 수동 취소 조치 필요, 데이터 미동기화 위험

---

## 원인 분석

### Bug 1: `get_task_by_key()` — 비결정적 fetchone() (근본 원인)

**파일**: `repositories/sqlite/scanner_queue_repository.py`

scanner_tasks 테이블에는 동일 task_key로 여러 레코드가 존재할 수 있음.
(동일 라이브러리가 반복 스캔될 때마다 completed, failed, pending 등의 행이 누적)

ORDER BY 없이 fetchone()을 호출하면 어떤 행이 반환될지 비결정적이다.
과거의 pending 또는 running 상태 행이 반환될 경우, 후속 enqueue() 로직에서 중복 판정으로 거부된다.

### Bug 2: `enqueue()` — update_task_to_pending() 실패 시 silent 종료

**파일**: `services/scanner_queue.py`

update_task_to_pending()의 UPDATE WHERE 조건은 AND status NOT IN ('pending', 'running')이다.
조회 시점과 업데이트 시점 사이에 해당 행의 상태가 바뀐 경우 rowcount = 0으로 실패한다.
이때 False를 반환하고 조용히 종료하면 DB에 해당 작업의 row가 생성되지 않아
워커가 영영 처리할 수 없게 된다.

---

## 수정 사항

### 수정 1: `get_task_by_key()` — ORDER BY id DESC LIMIT 1 추가

**파일**: `repositories/sqlite/scanner_queue_repository.py`

동일 task_key의 가장 최신 행을 반환하여 과거 completed/failed 행이 오염시키는 비결정성 제거.

### 수정 2: `enqueue()` — INSERT fallback 로직 추가

**파일**: `services/scanner_queue.py`

update_task_to_pending()이 race condition으로 실패하더라도 새 row를 INSERT하여
워커가 반드시 처리할 수 있도록 보장.
INSERT마저 실패하는 경우(실제 중복 pending/running)에만 중복 거부 처리.

---

## 해결 결과

- 3개 이상 스캔 큐 적재 시 모든 작업이 순차적으로 정상 처리됨
- pending 고착 현상 해소
- Race condition 발생 시에도 명확한 로그로 추적 가능
