---
title: "스캔 대기열 신규 등록 시 Pending 고착 및 유령 Running 태스크로 인한 선점거부 결함 조치"
category: "bugfix"
date: 2026-07-24
severity: "critical"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
tags: [scanner_queue, pending_stale, ghost_task, single_worker_lock, bugfix]
---

# 🐛 버그 수정 내역: 스캔 대기열 신규 등록 시 Pending 고착 및 유령 Running 태스크 선점거부 결함 조치

## 증상

새 카테고리를 등록하거나 스캔을 추가할 때, 스캔 대기열(Queue)에 `pending` (대기 중) 상태로 등록된 후 스캐너 워커 프로세스가 이를 `running`으로 전환하지 못하고 대기열에서 멈추어(Stuck) 스캔이 시작되지 않는 현상.

이때 로그에 `Task 'library_scan_..._64' is already in state 'pending'. Rejecting duplicate.` 메시지가 반복 출력됨.

---

## 원인 분석

1. **`cleanup_stale_tasks()`의 NULL PID 유령 태스크 누락 버그**:
   - 과거에 수동/비정상 기동되었거나, PID 기록 없이 DB `scanner_tasks`에 `status = 'running'` 또는 `status = 'exit_pending'` 상태로 남아있는 유령(Ghost) 레코드가 존재했음.
   - `cleanup_stale_tasks()`에서 `pid = row['worker_pid']`가 `None` 또는 빈값(`if not pid: continue`)인 경우 정화를 스킵하도록 구현되어 있어, DB 상에 `status = 'running'` 유령 레코드가 영원히 상주하게 됨.

2. **Single-Worker Lock (`try_acquire_task`) 의 신규 작업 선점 거부**:
   - 신규 스캔 태스크가 인큐된 후 워커가 `try_acquire_task()`를 실행할 때:
     `SELECT id FROM scanner_tasks WHERE status = 'running' AND id != ?`
     쿼리로 이미 실행 중인 타 작업이 있는지 점검함.
   - 이때 DB에 남아있던 유령 `running` 레코드를 발견하고 `already_running = True`로 판단하여, 신규 대기 태스크의 선점을 **영원히 거부(Return False)**함.
   - 이로 인해 신규 태스크가 `pending` 상태에서 시작(running)되지 못하고 대기열에 영구 고착되었음.

---

## 수정 사항

### [repositories/sqlite/scanner_queue_repository.py](file:///c:/project/media_server/repositories/sqlite/scanner_queue_repository.py)

1. **`cleanup_stale_tasks()` 유령 레코드 강제 정화 보완**:
   - `worker_pid` 정보가 없거나(`None`) OS 상에서 실체가 소멸된 `running` / `exit_pending` 유령 태스크도 무조건 `pending` 상태로 즉시 복구(Reset)하고 `worker_pid = NULL`로 완전 정화.

2. **`try_acquire_task()` OS 2중 검사 적용**:
   - `status = 'running'`인 타 작업이 감지되더라도, 해당 레코드의 `worker_pid`가 실제 OS에 살아서 동작하고 있는지 `psutil` / `os.kill` 2중 생존 검사를 수행.
   - 실체가 소멸된 유령 태스크인 경우 즉시 `pending`으로 리셋하고 새 대기 태스크가 정상 선점할 수 있도록 보완.

---

## 해결 결과

- DB 상에 남아있던 PID 누락 유령 `running` 레코드가 완전히 정화됨.
- 신규 카테고리 등록 및 스캔 요청 시 태스크가 대기열 고착 없이 워커 프로세스에 의해 즉시 `running`으로 전환되어 정상 스캔 구동 완료.
