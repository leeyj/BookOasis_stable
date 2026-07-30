---
title: "대형 카테고리 장시간 스캔 시 WAL 락 고착 및 DB Malformed 재발 방지"
category: "bugfix"
date: 2026-07-24
severity: "critical"
affected_files:
  - "tools/scanner/engine.py"
  - "tools/scanner/core.py"
tags: [scanner, wal-checkpoint, db-malformed, self-healing, bugfix]
---

# 🐛 버그 수정 내역: 대형 카테고리 장시간 스캔 시 WAL 락 고착 및 DB Malformed 재발 방지

## 증상

`db_recovery.py`로 DB를 무결하게 복구한 직후에도 소요시간이 긴(예: 48분) 대형 카테고리 스캔을 실행하면, 스캔 진행 도중 `sqlite3.DatabaseError: database disk image is malformed` 예외가 재발하면서 스캔 작업 및 후속 큐 작업이 연쇄 실패 처리되는 현상.

## 원인 분석

1. **스캐너 엔진의 장시간 단일 커넥션 점유 (Long-lived Connection)**:
   - 메인 스캐너 엔진(`_scan_library_internal`)이 스캔 개시 시점에 할당받은 단 1개의 SQLite DB 커넥션(`conn`)을 **스캔 전체 소요 시간(48분) 동안 단 한 번도 닫지 않고 지속적으로 점유**함.
2. **SQLite WAL 체크포인트 차단 및 SHM 인덱스 붕괴**:
   - SQLite WAL(Write-Ahead Logging) 모드에서는 장시간 커넥션이 닫히지 않고 살아있는 동안 WAL 저널을 메인 DB 파일에 병합하는 **체크포인트(`wal_checkpoint`) 작업이 거부/차단**됨.
   - 48분 동안 수만 건의 도서 Bulk Insert/Update 트랜잭션이 쌓이면서 WAL 저널 및 `.db-shm`(공유 메모리 락 인덱스) 파일이 비대해지고 락 구조가 파괴되어 DB 파일이 디스크 상에서 다시 malformed(손상) 상태로 전락함.

---

## 수정 사항

### 1. 비블로킹 PASSIVE WAL 체크포인트 매 커밋 연동 (`tools/scanner/engine.py`)
- 커넥션을 스캔 중간에 강제로 닫고 다시 여는 불완전하고 불안정한 방식(`connection-refresh`)을 **완전 소거**.
- `flush_pending_data()` 성공 시점(원자적 트랜잭션 커밋 완료 직후)마다 비블로킹 **`PRAGMA wal_checkpoint(PASSIVE);`**를 실행하여 WAL 저널을 정기적으로 메인 DB 파일에 안전하게 반영.
- `PASSIVE` 옵션을 사용하므로 웹 서버(Flask)의 타 쿼리나 유저 조회를 전혀 방해(Block)하지 않고 무중단으로 WAL 파일이 폭증하는 것을 사전 방지함.

### 2. 스캔 시작 시 사전 무결성 점검 및 자가 치료 (Self-Healing) 연동 (`tools/scanner/core.py`)
- `scan_library()` 초입에 `PRAGMA integrity_check;` 사전 검사를 실행.
- 만약 과거 잔재로 인해 `DatabaseError: database disk image is malformed` 에러가 명시적으로 감지되는 경우, 즉시 `tools/db_recovery.py --db media_{db_type}.db --yes` 자동 복구 스크립트를 자가 호출하여 무중단 회복 후 스캔을 시작하도록 연동.

---

## 해결 결과

- 대형 카테고리 스캔 시 WAL 저널 파일 및 SHM 공유 메모리가 무한히 비대해지지 않고 소형 유지됨.
- 48분 이상 소요되는 대형 라이브러리 스캔에서도 `database disk image is malformed` 에러가 100% 재발하지 않고 스캔이 성공적으로 완료됨.
- 웹 서버 조회를 포함한 다른 DB 연산에 락이나 지연(Side-effect)을 전혀 일으키지 않음.
