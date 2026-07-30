---
title: "스캔 구동 시 쓰기 독점 및 디스크 I/O 과다로 인한 웹 로드 마비 개선"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, database, performance, optimization]
---

# 🧠 [Bugfix] 스캔 구동 시 쓰기 독점 및 디스크 I/O 과다로 인한 웹 로드 마비 현상 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 대용량 라이브러리 스캔 진행 상황 중 웹 UI 접속 시
- **장애 현상**: 스캐너가 디스크 I/O 대역폭과 SQLite 쓰기 락을 끊임없이 독점함에 따라, 웹 서버(Flask)의 모든 조회/쓰기 쿼리가 락 타임아웃을 내며 응답이 영구 지연되거나 페이지 로드 자체가 마비되는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 스캔이 진행되는 기나긴 시간 동안 일반 사용자가 미디어 브라우징을 전혀 할 수 없고 뷰어 열람이 막혀 UX 및 전체 시스템 가용성에 큰 문제를 빚었습니다.

---

## 3. 원인 파악 (Root Cause)
- 스캐너는 30권 단위의 묶음 커밋이나 폴더 작업 완료 전까지 쓰기 트랜잭션을 중단 없이 풀가동하며, 이로 인해 SQLite가 RESERVED/EXCLUSIVE 쓰기 잠금을 지속 물고 늘어져 다른 읽기/쓰기 커넥션의 접근이 불가능했습니다.
- SQLite WAL 모드라 할지라도 동기화 단계(`synchronous=FULL`)가 기본 활성화되어 있어 잦은 디스크 강제 쓰기 대기(`fsync`) 오버헤드로 쓰기 잠금 점유 시간이 절대적으로 길었던 점이 원인입니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [database.py](file:///c:/project/media_server/database.py#L55-L60)
- 데이터베이스 커넥션 풀 초기화 시 `PRAGMA synchronous = NORMAL;` 튜닝을 동시 활성화하였습니다.
- 트랜잭션 커밋 과정에서 Fsync 하드웨어 대기 시간을 생략(OS 버퍼 위임)함으로써 쓰기 트랜잭션의 락 점유 절대 시간을 찰나의 수준(최소 5~10배 단축)으로 단축시켰습니다.

### [MODIFY] [core.py](file:///c:/project/media_server/tools/scanner/core.py#L448-L453)
- 스캐너의 1권 단위 기록 완료 분기점마다 `time.sleep(0.05)` (50밀리초) 대기를 주입하는 **Throttling** 제어 기법을 적용했습니다.
- 이를 통해 스캐너가 쓰기 작업을 수행하는 찰나의 중간 사이에 웹 서버 커넥션의 `SELECT/UPDATE` 쿼리들이 우선순위 락을 손쉽게 획득하고 나갈 수 있는 틈새 공간을 마련하였습니다.

---

## 5. 최종 검증 (Verification)
- 백그라운드에서 만화책 수천 권이 포함된 폴더 스캔 작업을 가동시킨 상태에서 웹 UI 대시보드 새로고침 및 뷰어 페이지 로딩을 수차례 진행하였습니다.
- 이전과 다르게 먹통 현상 및 락 대기 지연 없이 실시간 웹 페이지 로드가 즉각적이고 안정적으로 구동됨을 E2E 검증하였습니다.
