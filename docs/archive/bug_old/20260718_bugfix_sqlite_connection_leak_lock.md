---
title: "스캔 대기열 등록 시 SQLite UNIQUE 충돌에 의한 커넥션 누수 및 database is locked 장애 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, db, sqlite, lock, connection-leak, multiprocessing]
---

# 🐛 스캔 대기열 등록 시 SQLite UNIQUE 충돌에 의한 커넥션 누수 및 database is locked 장애 조치

## 1. 버그 및 성능 이슈 내역
- **현상:** 웹 UI에서 카테고리를 일괄 스캔하거나 다량의 스캔 요청을 빠르게 인입시킬 때, `database is locked` 또는 `UNIQUE constraint failed` 에러가 연쇄적으로 발생하며 스캔 대기열 등록이 차단되고 큐 워커가 동작하지 않음.
- **원인:**
  1. `services/scanner_queue.py` 내의 `enqueue` 등 DB 연동 로직에서 데이터베이스 커넥션(`conn`)을 획득한 뒤, 성공 흐름 하단에서만 `conn.close()`를 실행함.
  2. 일괄 스캔 등으로 중복 작업이 발생하여 SQLite 제약 조건 위반(`UNIQUE constraint failed`) 에러가 나거나 예외가 발생할 경우, 코드의 `except` 분기로 탈출하면서 **`conn.close()` 호출이 누락되어 커넥션이 닫히지 않고 풀에서 상실(Connection Leak)됨.**
  3. 누수된 커넥션들이 SQLite 파일의 쓰기 락을 해제하지 않고 물고 있어, 이후 발생하는 모든 DB 쿼리들이 `database is locked` 타임아웃 오류를 일으킴.
  4. 추가로 서버 재기동 시 `database.py`에서 `running` 상태의 작업만 실패로 정리하고, 대기(`pending`) 중인 유령 레코드들은 그대로 둔 채 기동되어 중복 인큐 거절 현상을 지속시켰음.

## 2. 영향도
- **대기열 기능 마비:** 일괄 스캔 트리거가 2~3개 카테고리만 등록된 채 연쇄 락 오류로 중단됨.
- **워커 정지:** 백그라운드 프로세스가 DB 락으로 인해 새로운 큐 작업을 조회하지 못함.

## 3. 수정 사항 (수정 소스 파일 목록)
1. **[services/scanner_queue.py](file:///c:/project/media_server/services/scanner_queue.py)**
   - `enqueue`, `get_queue_status`, `clear_queue`, `cancel_pending_task`, `run_scanner_worker_loop` 등 모든 DB CRUD 메서드를 대상으로 자원 관리를 `try ... finally` 블록으로 래핑하여 에러가 발생하더라도 `conn.close()` 호출을 100% 보장함.
   - `enqueue` 시 INSERT 구문을 `INSERT OR IGNORE`로 전환하여 고유키 제약조건 예외가 터지지 않고 안전하게 우회하도록 개선.
2. **[database.py](file:///c:/project/media_server/database.py)**
   - 740라인 근처 서버 재기동 시의 고착(Stuck) 데이터 클린업 쿼리를 보완하여 `running`뿐만 아니라 `pending` 상태의 고착 작업도 일괄 실패(`failed`) 처리하도록 수정.

## 4. 해결 사항 및 E2E 검증 결과
- **커넥션 누수 원천 차단:** 예외 상황에서도 `finally` 블록을 타며 커넥션이 안전하게 풀로 반환되어 락 누적 현상이 완전히 해소됨.
- **일괄 스캔 정상 작동:** 다수의 카테고리 동시 일괄 스캔을 실행해도 누락이나 락 지연 없이 모든 카테고리가 큐 대기열에 순차적으로 안정 안착하는 것을 원격 E2E 테스트로 검증 완료.
