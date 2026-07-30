---
title: "스캐너 워커 Redis brpop 유휴 고착 및 DB 큐 미감지 버그 수정"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "utils/redis_helper.py"
  - "services/scanner_queue.py"
tags: [scanner, worker, redis, brpop, idle-hang, socket-timeout]
---

# 스캐너 워커 Redis brpop 유휴 고착 및 DB 큐 미감지 버그 수정

## 1. 버그 개요
- 백그라운드 스캐너 워커(`scanner_worker.py`)가 장시간(예: 야간 유휴 시간) 가동된 후, 신규 스캔 작업이 DB 대기열(`scanner_tasks`)에 `pending`으로 정상 적재됨에도 불구하고 워커가 이를 픽업하지 못하고 "대기 중" 상태에 멈춰있는 현상.
- 스캐너 워커 프로세스(PID)는 정상 살아있는 것으로 표시되나 실제 큐 감지 기능이 마비되는 결함.

## 2. 원인 분석
- `utils/redis_helper.py`의 `redis_brpop` 블로킹 호출 시 장시간 네트워크/소켓 유휴로 인해 커넥션이 끊기거나 타임아웃 예외가 발생할 경우, 기존 싱글톤 클라이언트 레퍼런스(`_client`)가 재초기화되지 않아 무한 에러 또는 소켓 먹통(Hang) 상태에 빠짐.
- `services/scanner_queue.py` 워커 루프에서 `redis_brpop` 예외 발생 시 디버깅 로그 없이 `pass`로 무시되어 문제 파악이 어려웠음.

## 3. 수정 사항
1. **`utils/redis_helper.py` (`redis_brpop`)**:
   - `redis_brpop` 예외 발생 시 `global _client` 레퍼런스를 `None`으로 즉각 초기화하여 다음 루프 호출 시 `get_redis_client()`를 통해 Redis 소켓 재연결이 자동으로 이루어지도록 자동 복구 메커니즘 연동.
2. **`services/scanner_queue.py` (`run_scanner_worker_loop`)**:
   - `redis_brpop` 예외 발생 시 방어 로그(`Redis brpop polling error...`)를 남기고, 즉시 SQLite DB direct fallback 기능(`ScannerQueueRepository.get_next_pending_task()`)이 상시 작동하도록 이중 가드 강화.

## 4. 검증 결과
- Redis 커넥션 장애 또는 유휴 소켓 절단 시에도 `_client` 자동 리셋 및 DB 폴링 Fallback을 통해 `pending` 스캔 작업이 즉각 이어서 실행됨을 확인함.
