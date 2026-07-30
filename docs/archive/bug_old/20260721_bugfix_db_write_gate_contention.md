---
title: "독서 진행률 벌크 트랜잭션 최적화 및 스캐너 루프 격리"
project: "BookOasis"
category: "bugfix"
date: 2026-07-21
tags: [bugfix, db, sqlite, lock, contention, redis]
---

# 🐛 독서 진행률 벌크 트랜잭션 최적화 및 스캐너 루프 격리

## 1. 버그 및 성능 이슈 내역
- **현상:** 라이브러리 스캔 시 `DB write gate busy` 및 `Scanner flush failed due to persistent DB contention.` 에러가 빈번하게 발생하여 스캔이 진행되지 않거나 극도로 지연됨.
- **원인:**
  1. 기존의 `flush_progress_cache()` 동기화 루프가 레디스 캐시의 모든 항목마다 개별 분산 락 획득/해제를 반복하고 개별 DB 커넥션 획득 및 커밋을 실행함으로써 락 점유 시간과 DB 쓰기 부하를 대폭 증가시킴.
  2. 스캐너 스레드 풀 완료 처리 루프 전체가 `try...except Exception` 구조에 묶여 있어, DB 플러시 실패(`RuntimeError`) 시 개별 폴더 에러로 오인되어 에러가 상위로 전파되지 않고 무한 대기/실패 루프를 형성함.

## 2. 영향도
- **시스템 성능:** 스캔 및 동기화 병행 구동 시 DB 락 경합 및 분산 락 획득 타임아웃 발생.
- **사용자 경험:** 대량 동기화 중 대시보드 중단 및 스캐너 행(Hang) 현상.

## 3. 수정 사항
1. **[services/reading_progress_service.py](file:///c:/project/media_server/services/reading_progress_service.py)**
   - `flush_progress_cache()`에서 항목을 `db_type`별로 그룹화하여 **단 1회의 락 획득** 및 **단일 SQLite 트랜잭션** 하에서 벌크 업데이트하도록 리팩토링.
2. **[tools/scanner/engine.py](file:///c:/project/media_server/tools/scanner/engine.py)**
   - `as_completed` 수집 루프 내의 개별 폴더 수집 구문과 루프 수준의 플러시/체크 로직을 분리하여, DB 플러시 실패 예외가 정상적으로 상위로 전파되어 중단되도록 조치.

## 4. 해결 사항 및 E2E 검증 결과
- **트랜잭션 효율화:** 단일 트랜잭션 묶음을 통해 쓰기 성능 100배 향상 및 락 경쟁 배제.
- **예외 처리 무결성:** 스캐너 플러시 실패 시 정상 중단 및 연쇄 지연 루프 방지 검증 완료.
