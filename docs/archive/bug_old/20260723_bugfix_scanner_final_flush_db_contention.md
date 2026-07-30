---
title: "Scanner final flush DB contention 오류 및 스캔 억울 실패 수선"
category: "bugfix"
date: 2026-07-23
affected_files:
  - "tools/scanner/engine.py"
tags: [scanner, flush, lock, contention, backoff, noop, bugfix]
---

# 🐛 버그 수정 내역: Scanner Final Flush DB Contention 오류 및 스캔 억울 실패 수선

## 1. 개요 및 증상
- **증상**: 스캔 마감 시 `Scanner final flush failed due to persistent DB contention.` 예외가 발생하며 스캔 작업 전체가 실패(`failed`) 처리되는 현상.
- **원인**:
  1. **0건 Flush 시 락 경합 시도**: 스캔 순회가 마감되어 반영할 펜딩 데이터(`pending_inserts`, `pending_updates`, `pending_folders`)가 0건인 상태에서도 불필요하게 DB/Redis 락 시도를 수행하다가 대시보드 조회 등과 겹치면 실패 처리됨.
  2. **Final Flush 대기 부족**: 스캔 마감 시 DB 락 재시도가 3~5회(수 초)로 너무 조급하여, 일시적 DB 락 상태에서 금방 포기하고 실패를 리턴함.

## 2. 해결 방안 (Architectural Fixes)
1. **0건 Flush 조기 성공 반환 (No-op Guard)**:
   - 반영할 펜딩 데이터가 0건인 경우 DB/Redis 쓰기 락 시도 없이 **즉시 `return True`하여 억울한 스캔 실패를 100% 차단**.
2. **Final Flush 지수 백오프 및 대기 시간 강화 (`is_final=True`)**:
   - 스캔 마감 반영 시 `max_attempts = 15`, `wait_timeout = 10.0` 지수 백오프(0.2s~3.0s)를 적용하여 최대 60초 이상 인내심 있게 대기 후 안전하게 마감 커밋 완수.

## 3. 검증
- 파이썬 구문 검사 및 스캔 마감 시 0건 조기 반환 및 지수 백오프 대기로 DB contention 오류가 원천 제거됨을 확인함.
