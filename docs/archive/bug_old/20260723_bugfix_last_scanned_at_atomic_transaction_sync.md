---
title: "스캔 완료 시 last_scanned_at 단일 트랜잭션 원자적 통합 및 UI 실시간 동기화"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "tools/scanner/engine.py"
  - "services/scheduler_service.py"
  - "static/js/scheduler.js"
tags: [scanner, transaction, atomic, last_scanned_at, bugfix]
---

# 🐛 버그 수정 내역: last_scanned_at 단일 트랜잭션 원자적 통합 및 UI 실시간 동기화

## 1. 개요 및 증상
- **증상**: 카테고리 스캔/크론 스캔 완료 후에도 카테고리 목록의 마지막 스캔 시각(`last_scanned_at`)이 갱신되지 않거나 이전 시각으로 계속 유지되는 현상.
- **원인**:
  1. **트랜잭션 분리 (Non-Atomic Transaction)**: `tools/scanner/engine.py`에서 도서 데이터 추가/갱신 커밋 완료 후 커넥션을 닫은 뒤, 바깥의 `scheduler_service.py`에서 별도의 커넥션으로 `libraries.last_scanned_at` 갱신을 뒤늦게 시도하다가 커넥션/락 엇갈림이 발생함.
  2. **UI 상태 미갱신**: 스캔 완수 후 웹 UI에서 카테고리 목록 시각을 새로고침 없이 즉시 업데이트하는 이벤트 리프레시 연동이 누락됨.

## 2. 해결 방안 (Architectural Fixes)
1. **단일 트랜잭션 원자적(Atomic) 통합 (`tools/scanner/engine.py`)**:
   - `scan_library()` 엔진 마감 트랜잭션(`scan-end-cleanup`) 시점에 `scanner_progress` 삭제와 함께 **`libraries` 테이블의 `scan_status = 'ready'` 및 `last_scanned_at = CURRENT_TIMESTAMP` 갱신을 단일 DB 트랜잭션으로 커밋**하여 100% 누락 방지.
2. **프론트엔드 실시간 UI 리프레시 (`static/js/scheduler.js`)**:
   - 스캔 완료 소켓/알림 이벤트 수신 시 `tab_media_library` 카테고리 데이터 재조회를 호출하여 화면의 `last_scanned_at`을 실시간 갱신.

## 3. 검증
- 구문 검사 및 스캔 완료 후 단일 트랜잭션으로 `last_scanned_at`이 100% 원자적 커밋됨을 검증.
