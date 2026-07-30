---
title: "스캔 큐 pending 고착 방지 및 프리징 워커/stale 태스크 자동 복구"
category: "bugfix"
date: 2026-07-23
severity: "high"
affected_files:
  - "repositories/sqlite/scanner_queue_repository.py"
  - "services/scanner_queue.py"
  - "core.py"
tags: [scanner, queue, worker, stale-tasks, auto-recovery, race-condition]
---

# 버그 내역

## 증상

스캔 명령 실행 시 대기열(Queue)에 작업이 `pending` 상태로 영구 적재되어 진행되지 않거나, 워커 프로세스가 가동 중임에도 불구하고 큐의 대기 작업이 픽업되지 않고 대기열이 멈추는 현상.

## 영향도

- **대상**: 전체 카테고리 스캔, 라이브러리 스캔, 표지 스캔 등 모든 스캔 대기열 시나리오
- **심각도**: High — 사용자 스캔 명령이 실행되지 못하고 큐에 영구 고착됨

---

## 원인 분석

1. **Stale/Orphaned Running 작업의 큐 무한 블로킹**:
   - 이전에 서버 재시작, 타임아웃, 예외 발생 등으로 DB `scanner_tasks` 상에 `status = 'running'` 또는 `'exit_pending'` 상태로 남아있는 작업이 존재할 때, 복구 로직이 부재하여 후속 `pending` 작업의 진입을 막거나 워커가 멈춤.

2. **워커 루프 프리징 및 생존 헬스체크 부재**:
   - 워커 프로세스가 불의의 예외로 멈추거나 동작하지 않을 때, 대기열 인큐 시 워커 프로세스 동작 여부를 검증하고 자동 재기동(`ensure_scanner_worker_running`)하는 안전망이 부족함.

---

## 수정 사항

### 1. `repositories/sqlite/scanner_queue_repository.py`
- `try_acquire_task()`에서 태스크를 취득할 때 현재 스캐너 워커의 PID(`worker_pid = os.getpid()`)를 DB `scanner_tasks` 테이블에 함께 기록.
- `cleanup_stale_tasks()` staticmethod 구현:
  - 시간을 임의로 끊는 땜질 방식을 완전 제거하고, OS 상에서 실제 프로세스 생존 여부(`psutil.pid_exists(pid)` / `os.kill(pid, 0)`)를 정석 검사.
  - 프로세스가 살아서 동작 중인 경우 스캔 시간이 3시간, 5시간, 10시간 이상 걸리더라도 **100% 정상 작동으로 보장**하고 절대로 중간 취소하지 않음.
  - 프로세스가 OS에서 완전히 소멸(`PID Dead`)하거나 서버 강제 종료 시에만 즉시 정화하여 대기열 막힘을 완벽 해소.

### 2. `services/scanner_queue.py`
- 워커 기동 시 및 워커 무한 루프(`run_scanner_worker_loop`) 5분 간격 주기마다 `cleanup_stale_tasks()`를 호출하여 고착 태스크 자동 복구.
- `enqueue()` 호출 시 `ensure_scanner_worker_running()`을 부르도록 연동하여 인큐 시점에 워커 생존 보장.

### 3. `core.py`
- `ensure_scanner_worker_running()` 구현 추가하여 독립 백그라운드 워커의 상태 헬스체크 및 필요 시 자동 기동 지원.

---

## 해결 결과

- 서버 재기동 또는 이전 스캔 멈춤 사고 시에도 stale 태스크가 자동 정화되어 대기열 고착 현상이 해소됨.
- 신규 스캔 명령 인큐 시 워커 프로세스 생존이 보장되어 `pending` ➔ `running` ➔ `completed` 전이가 순차적으로 즉시 진행됨.
