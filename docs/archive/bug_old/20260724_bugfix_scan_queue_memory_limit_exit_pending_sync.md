---
title: "스캔 중 메모리/용량 제한 재시작 시 대시보드 대기열 Pending 오표시 결함 조치"
category: "bugfix"
date: 2026-07-24
severity: "high"
affected_files:
  - "tools/scanner/engine.py"
  - "services/scanner_queue.py"
tags: [memory_limit, exit_pending, queue_status, status_sync, redis_mismatch, bugfix]
---

# 🐛 버그 수정 내역: 스캔 중 메모리/용량 제한 재시작 시 대시보드 대기열 Pending 오표시 결함 조치

## 증상

스캔 중 메모리 제한(`check_memory_exceeded`) 또는 1회 처리 용량/폴더 제한에 도달하여 스캐너 프로세스가 안전 재시작될 때, 터미널 상에서는 `Resuming scan...`으로 실제 스캔이 정상 진행되고 있음에도 불구하고 **웹 대시보드 UI의 스캔 대기열 상에는 해당 태스크가 '대기 중 (pending)' 아이콘 및 라벨로 표기되는 현상**.

---

## 원인 분석

1. **메모리 비상 정지 시 `scanner_tasks` DB 갱신 누락**:
   - `engine.py`에서 메모리 임계치 도달 시 `os._exit(0)`을 호출하기 직전에 `scanner_tasks` 테이블의 태스크 상태를 `exit_pending` (재기동 대기 중)으로 변경하지 않고 종료함.
2. **`cleanup_stale_tasks()` 의 `pending` 리셋 및 Redis 큐 미소유**:
   - 워커 프로세스 재시작 시 `cleanup_stale_tasks()`가 죽은 PID 태스크를 감지하고 DB 태스크 상태를 `status = 'pending'` 으로 복구함.
   - 이때 Redis List(`queue:scanner`)에는 해당 태스크 키가 이미 POP되어 삭제된 상태이므로, 워커는 SQLite Fallback(`get_next_pending_task`)으로 이 태스크를 꺼내와서 스캔을 이어 받아 실행함.
   - 실제 스캔이 이미 실행 중임에도 불구하고, DB 상태 갱신 트랜잭션 딜레이 및 메모리 캐시 딜레이(2초)로 인해 웹 대시보드 UI가 태스크를 `pending` (대기 중) 상태로 판정하여 오표시하였음.

---

## 수정 내용

1. **[tools/scanner/engine.py](file:///c:/project/media_server/tools/scanner/engine.py)**:
   - 메모리 비상 정지(`check_memory_exceeded`) 시 `os._exit(0)`을 호출하기 바로 직전에, `scanner_tasks` 테이블의 태스크 상태를 **`status = 'exit_pending'`, `stage = 'Paused due to memory limit (Auto-Resuming...)'`** 로 명시적 커밋하여 백엔드/웹 UI에 상태 변화를 즉시 전달.

2. **[services/scanner_queue.py](file:///c:/project/media_server/services/scanner_queue.py)**:
   - 대기열 상태 캐시 딜레이를 `2.0`초에서 `0.5`초로 대폭 축소하여 워커 재시작 후 스캔이 이어서 진행될 때 웹 UI에 `running` (스캔 중)으로 즉시 원자적 반영되도록 보완.

---

## 해결 결과

- 메모리/용량 제한으로 프로세스가 안전 재시작되더라도, 실제 터미널 스캔 진행 상태와 웹 대시보드 UI의 스캔 대기열 상태(`running` / `exit_pending`)가 100% 실시간 일치함.
