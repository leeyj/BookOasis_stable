---
title: "서버 재기동 시 스캔 고착 및 취소 상태에 따른 재스캔 락 방어 로직 보강"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, startup, scan-lock, resume, database]
---

# 🐛 서버 재기동 시 스캔 고착 및 취소 상태에 따른 재스캔 락 방어 로직 보강

## 1. 버그 및 이슈 정의
- **현상:** 서버가 비정상 또는 정상 재기동할 때, 카테고리의 `scan_status`가 `cancelling`(취소 중) 상태로 남아있거나 큐의 실행 상태가 꼬여있을 경우, 사용자가 다음 스캔 명령을 내려도 상태 가드에 걸려 작동하지 않는 현상 유발.
- **기존 로직의 한계:** 
  - 이전에는 스캔 자동 재개(Auto-Resume) 기능 작동을 위해 단순히 `scanning`을 `interrupted`로만 치환하였음.
  - 하지만 `cancelling` 상태 및 큐(`scanner_tasks`)의 `running` 유령 태스크들이 큐를 무한 블로킹하고 있어 복합적인 락 문제를 해결하지 못함.

## 2. 해결 방안 (정교한 기동 복원 정책 구현)
1. **`cancelling` 카테고리 복구:** 사용자가 명시적으로 중단을 눌렀던 카테고리는 복구할 필요가 없으므로 기동 시 즉시 **`'ready'`**로 복원시켜 재스캔을 보장함.
2. **`scanning` 카테고리 복구:** 스캔 도중 끊겼던 카테고리는 기존의 유용한 **"자동 복원(Auto-Resume)"** 기법을 유지하도록 **`'interrupted'`** 상태로 전환시킴.
3. **작업 큐 (`scanner_tasks`) 정화:** 
   - 실체가 없는 **`'running'` (실행 중)** 상태의 태스크만 **`'failed'`**로 닫아줌.
   - **`'pending'` (대기 중)** 상태의 작업은 강제 실패시키지 않고 보존하여, 재기동 후 자식 워커가 순차적으로 안전하게 처리하도록 하여 대기열의 연속성을 보장함.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[database.py](file:///c:/project/media_server/database.py)**
  - `init_databases()` 내의 고착 스캔 상태 초기화 쿼리를 정교화하여 3단계로 분리(cancelling -> ready, scanning -> interrupted, running -> failed) 작성함.

## 4. 해결 사항 및 E2E 검증 결과
- **안정성 입증:** 서버 재기동 후 꼬였던 `cancelling` 및 대기열이 안전하게 정화되면서도, 이전 중단 작업에 대한 `Auto-Resume`이 정상 작동하고 대기열의 `pending` 태스크도 이어서 스캔되는 것을 로그를 통해 최종 확인 완료.
