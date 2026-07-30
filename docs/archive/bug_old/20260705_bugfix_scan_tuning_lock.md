---
title: "[버그수정] 스캔 완료 후 비동기 DB 최적화 튜닝 시 스캔 큐 락 경합 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-05
tags: [scheduler, scanner, sqlite, lock, vacuum, bugfix]
---

# 🐛 스캔 완료 후 비동기 DB 최적화 튜닝 시 스캔 큐 락 경합 조치

카테고리 스캔 완료 직후 별도의 백그라운드 스레드로 구동되는 데이터베이스 최적화(VACUUM/REINDEX 등) 작업이 실행되는 도중에 스캔 큐에 예약된 다음 스캔 작업이 동시에 기동되면서 발생하는 `sqlite3.OperationalError: database is locked` 문제를 해결하기 위해 대기 가드를 보완하였습니다.

---

## 1. 버그 내역 및 현상
* **문제 상황**: 스케줄러 스캔 혹은 다중 카테고리 스캔 진행 중 스캔 기동 로그가 찍히고 수 초 만에 아래와 같은 에러와 함께 기동 실패함.
  ```text
  스캔 실패 - DB=general, LibraryID=15, 소요시간=87.73초, 에러=database is locked
  ```
* **원인**:
  - `tools/scanner/core.py` 등 스캔 로직의 완료 시점에서 `database.optimize_database()` 함수를 비동기 스레드(`threading.Thread`)로 즉시 분기 실행합니다.
  - 이 최적화 로직은 내부적으로 `VACUUM`을 동반하는데, SQLite의 `VACUUM`은 데이터베이스 파일 전체에 독점 락(Exclusive Lock)을 겁니다.
  - 그러나 스캔 예약 큐(`ScannerQueue`)는 이전 카테고리 스캔 태스크가 리턴되자마자 튜닝 완료 여부와 관계없이 대기열에 쌓여 있던 다음 카테고리 스캔 태스크를 큐에서 꺼내어 `run_scan_job`을 기동합니다.
  - 다음 스캔 작업이 테이블의 `scan_status`를 `scanning`으로 업데이트하는 쿼리 등을 실행하려 할 때, 아직 `VACUUM`에 의해 독점 락이 묶여 있어 락 획득 타임아웃에 걸려 실패하게 됩니다.

---

## 2. 해결 방안 및 수정 사항
1. **스캔 시작 시 튜닝 중 상태 감지 가드 추가 ([scheduler_service.py](file:///C:/project/media_server/services/scheduler_service.py))**:
   - `run_scan_job()` 래퍼 헬퍼 함수 시작부에 데이터베이스의 물리적 튜닝 여부(`is_db_tuning(db_type)`)를 판단하는 동적 대기 가드 루프를 배치하였습니다.
   - 현재 최적화(VACUUM 등) 작업이 활성화된 상태라면 스캔을 시작하지 않고 `scan_history.log`에 `⚠️ 데이터베이스 최적화(튜닝) 작업이 진행 중입니다. 완료 시까지 일시 대기합니다.` 경고 메시지를 기록하며 3초 간격으로 폴링 대기합니다.
   - 이전 작업의 튜닝 스레드가 완료되어 락이 완전 해제되면 대기하고 있던 다음 스캔 작업이 비로소 안전하게 진입하여 오류 없이 바통을 이어받습니다. (최대 120초 대기 후 안전을 위해 타임아웃 예외 리턴 조치)

---

## 3. 영향도 및 결과
* 다수의 카테고리 스캔 작업을 예약 큐에 동시에 적재하여도 각 작업의 꼬리에 붙는 무거운 물리 VACUUM 정리가 안전하게 끝날 때까지 다음 스캔이 순차 대기 조율되므로, 스캔 도중 교착(Deadlock)에 빠져 `database is locked`가 무더기로 발생하던 에러가 완벽히 치료되었습니다.
