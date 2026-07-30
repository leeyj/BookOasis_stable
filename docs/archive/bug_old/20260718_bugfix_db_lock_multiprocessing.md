---
title: "스캐너 구동 시 SQLite DB Lock 및 웹 타임아웃 장애 조치 (multiprocessing 적용)"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, db, sqlite, lock, multiprocessing, performance]
---

# 🐛 스캐너 구동 시 SQLite DB Lock 및 웹 타임아웃 장애 조치

## 1. 버그 및 성능 이슈 내역
- **현상:** 도서 스캔 작업(백그라운드)이 진행되는 동안 웹 서비스의 화면 로딩 속도가 극도로 지연되거나, Cloudflare 타임아웃(524) 또는 Gunicorn 502/504 에러가 빈번하게 발생함.
- **원인:**
  1. 기존 단일 워커 구조에서는 Flask 웹 요청을 처리하는 동일한 파이썬 프로세스 내에 백그라운드 스케줄러와 스캐너 워커가 데몬 스레드(`threading.Thread`)로 동작함.
  2. 스캔 스레드가 무거운 압축 파일 I/O 및 대량의 도서 정보 INSERT/UPDATE를 수행할 때 파이썬의 GIL(Global Interpreter Lock) 경쟁으로 인해 웹 요청 스레드의 CPU 점유가 극도로 방해받음.
  3. SQLite 데이터베이스가 독점적 쓰기(Write) 트랜잭션을 진행하는 동안 웹 서비스의 읽기/쓰기 커넥션 획득 대기가 길어지고, 결국 락 대기 시간초과(`Database is locked`) 및 요청 타임아웃으로 전파됨.

## 2. 영향도
- **시스템 안정성:** 스캔 부하가 높은 시점에 전체 시스템 응답 불가 현상 유발.
- **사용자 경험:** 라이브러리 스캔 시 독서 뷰어 진입 및 대시보드 조회가 완전히 멈추어 사용자 경험이 심각하게 저해됨.

## 3. 수정 사항 (수정 소스 파일 목록)
1. **[database.py](file:///c:/project/media_server/database.py)**
   - 백그라운드 작업과 웹 프로세스의 메모리 격리에 대응하기 위해 SQLite에 작업 큐 테이블인 `scanner_tasks` 정의 추가.
   - 서버 부팅 시 비정상 종료 등으로 고착된 `running` 상태의 작업들을 일괄 `failed`로 정리하는 리셋 방어 코드 추가.
2. **[services/scanner_queue.py](file:///c:/project/media_server/services/scanner_queue.py)**
   - 메모리 `queue.Queue` 기반의 큐 관리를 완전히 SQLite `scanner_tasks` 테이블 조회/수정(DB-backed Queue) 방식으로 전환.
   - 웹 프로세스로부터 중복 `enqueue` 차단 및 작업 취소(`clear_queue`, `cancel_pending_task`) 로직 구현.
   - 격리된 자식 프로세스에서 실행될 `run_scanner_worker_loop()` 구현. 여러 프로세스 경합 시 Race Condition을 막는 원자적 UPDATE(`cursor.rowcount == 1` 체크) 작업 선점 기법 적용.
   - 하위 호환성을 위해 `add_task` 메서드 래퍼 유지.
3. **[services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)**
   - 스캔의 세부 단계(`stage` 정보인 `vfs_refresh`, `book_scan`)를 메모리가 아닌 DB 큐 테이블에 즉시 업데이트하는 `_update_task_stage` 헬퍼 함수 적용.
4. **[core.py](file:///c:/project/media_server/core.py)**
   - Flask 기동 시 `multiprocessing.Process`를 스폰하여 스캐너 워커 프로세스를 완전히 독립된 OS 프로세스로 분리.
   - Windows의 `spawn` 기법 기동 시 자식 프로세스가 메인 모듈을 재임포트하면서 Flask 서버와 스케줄러를 중복 실행하는 무한 부트스트랩 에러 방지를 위해, `start()` 전후로 환경변수 `BOOKOASIS_IS_WORKER`를 동적으로 제어 및 임포트 가드 적용.
   - `atexit` 및 Graceful Shutdown 시그널 수신 시 자식 워커 프로세스를 완전히 종료(`terminate` 및 `join`)하도록 클린업 처리 보강.

## 4. 해결 사항 및 E2E 검증 결과
- **프로세스 완전 격리:** 스캐너 워커가 독립된 PID를 부여받아 웹 프로세스와 CPU 및 GIL을 완전히 격리하여 경쟁을 원천 제거함.
- **동시성 대폭 개선:** 대용량 스캔 중에도 `/health` 엔드포인트 및 웹 요청들이 딜레이 없이 즉각 응답(200 OK)하는 것을 E2E 테스트로 검증 완료.
- **컨테이너 무결성 보존:** 단일 도커 컨테이너 정책을 고수한 채로 내부 파이썬 프로세스 격리를 달성하여 배포 복잡도 증가가 전혀 없음.
