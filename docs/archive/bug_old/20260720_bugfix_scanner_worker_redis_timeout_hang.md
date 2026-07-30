---
id: "20260720_bugfix_scanner_worker_redis_timeout_hang"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [redis, worker, timeout, socket, hang]
---

# 20260720 — Redis 소켓 타임아웃 불일치로 인한 스캐너 워커 프리징 버그 수정

## 버그 내역

### 현상
- 스캐너 스케줄러가 백그라운드 큐(`scanner_tasks` 테이블)에 작업을 정상 등록하더라도, 스캐너 워커 프로세스가 대기 중인 작업을 가져가지 않고 정지(Hung) 상태에 빠짐.
- 서비스를 재시작할 때만 워커가 밀려있던 큐 항목들을 비로소 순차 소비하기 시작하며, 사용자 관점에서는 기동 시에 스캔이 다시 중복 등록되어 도는 것처럼 보임.

### 근본 원인
- `services/scanner_queue.py`의 `run_scanner_worker_loop`에서 새로운 작업을 감지하기 위해 Redis `brpop` 블로킹 팝 대기(timeout=3초)를 수행함.
- 그러나 `utils/redis_helper.py`의 Redis `ConnectionPool` 초기화 시 클라이언트 소켓 읽기 제한(`socket_timeout`)이 `2.0초`로 짧게 걸려있었음.
- 클라이언트 소켓 타임아웃이 서버 블로킹 팝 대기 시간보다 짧기 때문에 3초 대기 중 무조건 `TimeoutError` 예외가 연속으로 발생.
- 예외 누적으로 인해 결국 Redis 연결 풀의 핸들이 꼬이고 소켓 I/O 대기 상태에 고착(Hung)되어 스캐너 워커 루프 전체가 멈추게 됨.

## 영향도
- 주기적 스케줄 스캔이 등록된 후 워커 프리징으로 인해 처리되지 않고 큐에 무한히 누적되어 방치됨.
- 다음 서비스 재시작 시점에만 누적 큐가 비정상적으로 밀려 실행됨.

## 수정 사항

### 수정 파일 목록

#### `utils/redis_helper.py`
- `get_redis_client` 내 `redis.ConnectionPool.from_url` 초기화 시 `socket_timeout` 설정을 기존 `2.0`초에서 `15.0`초로 상향 조정.
- 이로써 `brpop` 블로킹 대기(3초) 시 소켓 읽기 타임아웃 예외가 원천적으로 차단됨.

## 해결 사항
- Redis 연결의 무한 고착(Hang)을 방지하고 `brpop` 블로킹 수신이 안정적으로 이루어져, 스캐너 워커가 새벽 및 주간에 새로 인큐되는 작업을 정상적으로 즉시 수행함.
