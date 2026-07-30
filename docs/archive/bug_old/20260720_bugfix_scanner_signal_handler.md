---
id: "20260720_bugfix_scanner_signal_handler"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [scanner, worker, lazy-scanner, signal, SIGTERM, SIGINT, rollback, commit, protection]
---

# 20260720 — 스캐너 종료 시그널(SIGTERM/SIGINT) 감지 및 우아한 자진 종료 핸들러 장착 완료

## 버그 내역

### 현상
- 도커 컨테이너 중지(`docker stop`) 또는 Gunicorn/워커 재기동 명령 수행 시, 스캐너가 대용량 파일을 복원하거나 활발한 인덱싱 트랜잭션을 맺고 있는 도중 강제 킬(`SIGKILL`)이 유입되면 DB 트랜잭션이 비정상 파괴되거나 SQLite WAL 로그 버퍼 불일치로 인한 DB 파일 손상(`malformed`)이 발생할 위험이 상존함.

### 근본 원인
- 백그라운드 프로세스인 메인 스캐너 워커(`scanner_worker.py`) 및 서브 프로세스인 레이지 스캐너(`lazy_scanner.py`)가 운영체제의 종료 신호(`SIGTERM`, `SIGINT`)를 명시적으로 포착(Catch)하여 하던 작업을 영리하게 매듭짓는 시그널 핸들러 제어 로직이 결여되어 있었음.

## 영향도
- 도커 자동 업데이트 도구(Watchtower 등)를 사용하는 일반 사용자 환경에서 스캔 중 불시에 빌드가 중단되어 컨테이너가 찢겨나갈 시, 데이터베이스 무결성 유실을 초래하여 서비스 기동 불가 상태를 야기할 수 있음.

## 수정 사항

### 신규 파일

#### `utils/signal_helper.py`
- `SIGTERM` 및 `SIGINT` 시그널 수신 시 메인 스캐너(`tools.scanner.engine.stop_requested`) 및 레이지 스캐너(`tools.lazy_scanner.stop_requested`)의 전역 종료 플래그를 원자적으로 참(`True`)으로 전환해 주는 시그널 감지/등록 공통 모듈 신규 구현.

### 수정 파일 목록

#### `tools/scanner/engine.py`
- 모듈 전역 변수 `stop_requested = False` 정의.
- 라이브러리 스캔 폴더 루프(`as_completed(futures)`) 본문에 `stop_requested` 상시 검출 벽 장착. 감지 즉시 루프를 강제 탈출(`break`)하여 현재까지 수집된 인덱싱 데이터만 `flush_pending_data()`로 트랜잭션을 안전하게 닫고 정지하도록 변경.

#### `tools/lazy_scanner.py`
- 모듈 전역 변수 `stop_requested = False` 정의.
- 도서 개별 스캔 루프 초입에 시그널 가드 배치. 감지 시 진행 중인 작업을 홀딩하고 커넥션을 온전히 `close()`한 뒤 `sys.exit(0)` 정상 종료 코드 반환 처리.
- 모듈 시작 시점에 `register_shutdown_handlers()` 등록.

#### `tools/scanner_worker.py`
- 워커 브로커 큐 기동 진입부(`__main__`)에 `register_shutdown_handlers()` 등록.

## 해결 사항
- 스캐너 기동 도중 중단 요청 신호가 주입되어도 안전하게 트랜잭션을 마감하고 커넥션을 정상 종결한 후 정지하는 시그널 라이프사이클을 완비하여, 무작위 컨테이너 드롭 상황에서도 DB 파손 리스크를 0%에 수렴하도록 보장하였습니다.
