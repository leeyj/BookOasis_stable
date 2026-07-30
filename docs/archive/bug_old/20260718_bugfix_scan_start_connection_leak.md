---
title: "스캔 시동 DB 최신 경로 조회 예외에 따른 커넥션 누수 장애 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, db, sqlite, connection-leak, lock, scan]
---

# 🐛 스캔 시동 DB 최신 경로 조회 예외에 따른 커넥션 누수 장애 조치

## 1. 버그 및 성능 이슈 내역
- **현상:** 도서 스캔을 시동하여 대기열에서 꺼내 실행할 때 스캐너 백그라운드 프로세스가 DB 락(`database is locked`) 상태에 걸려 큐 작업 수행을 멈추고 먹통이 되는 장애 발생.
- **원인:**
  1. 최근 추가된 `run_scan_job` 내의 DB 실시간 최신 경로 쿼리부에서 `conn_path.close()`가 `try` 블록 최하단 성공 지점에만 존재함.
  2. `library_id` 바인딩 시 타입 불일치 등으로 쿼리 도중 한 번이라도 예외가 터지면 `conn_path.close()` 호출이 누락되어 **커넥션 누수(Leak)**가 지속 발생함.
  3. 누수된 커넥션들로 인해 SQLite 파일의 쓰기 락이 잠겨 자식 프로세스의 작업 조회가 아예 중단됨.

## 2. 영향도
- **스캔 불능:** 스캔 명령을 내려도 대기열에 쌓일 뿐, 자식 프로세스가 DB 락 경합으로 인해 작업을 영구히 시작하지 못하는 마비 상태 초래.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)**
  - `run_scan_job` 함수 내부의 실시간 경로 조회 로직을 `try ... finally` 구조로 전면 보강하여, 어떠한 예외 상황이 발생하더라도 `conn_path.close()`가 확실히 실행되도록 수정.
  - `library_id` 바인딩 파라미터를 `int(library_id)`로 캐스팅하여 데이터베이스의 엄격한 형식 불일치 문제를 예방.

## 4. 해결 사항 및 E2E 검증 결과
- **스캔 정상 구동 및 락 방지:** 최신 경로 조회 시 자원 누수를 원천 차단하여, 스캔 트리거 시 즉시 대기열에서 작업을 선점하고 스캔 진행률(status=scanning) 상태로 진입하는 것을 원격 E2E 검증 완료.
