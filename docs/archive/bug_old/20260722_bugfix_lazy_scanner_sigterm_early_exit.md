---
title: "서버 재기동/종료 시그널(SIGTERM) 수신 시 스캔 큐 오조기 마감 버그 수정"
category: "bugfix"
date: 2026-07-22
severity: "high"
affected_files:
  - "tools/lazy_scanner.py"
tags: [lazy_scanner, sigterm, exit_code, auto-resume]
---

# 서버 재기동/종료 시그널(SIGTERM) 수신 시 스캔 큐 오조기 마감 버그 수정

## 1. 버그 개요
- 대량 스캔(예: 1448건) 진행 도중 서버 배포/재기동으로 인해 `SIGTERM` 시그널(시그널 15)이 수신되면, 아직 스캔 대상이 많이 남아있음에도 불구하고(예: 717번째 처리 중) `Exit Code 0` (스캔 완료)을 리턴하는 결함.
- 상위 워커(`scanner_queue.py`)가 스캔이 전량 완료된 것으로 오판하여 태스크를 DB에서 `completed` 상태로 최종 마감해 버림.
- 이로 인해 서버 재기동 후 대기열에서 잔여 스캔 작업이 사라져 사용자가 다시 수동으로 스캔을 눌러야만 하였음.

## 2. 원인 분석
- `tools/lazy_scanner.py` 내부의 `stop_requested` 수신 처리부(Line 288 및 553)에서 시그널 수신 시 Exit Code를 구분하지 않고 항상 `sys.exit(0)`으로 마감하도록 구현되어 있었음.

## 3. 수정 사항
- `tools/lazy_scanner.py`:
  - `stop_requested` (SIGTERM/SIGINT) 수신 시 `Exit Code 0` 대신 **`Exit Code 10` (서브-배치 재기동/재개 요청 코드)**을 리턴하도록 패치.
  - 상위 워커가 수신 시 `exit_pending` 상태를 유지하고 서버 재기동 후 residual pending 항목을 자동으로 픽업하여 연쇄 재개하도록 보장.

## 4. 검증 결과
- 스캔 도중 종료 시그널 수신 시 "더 이상 스캔할 대상이 없습니다 (Exit Code 0)" 대신 "서버 재기동/종료 시그널 감지로 안전 중단 (Exit Code 10)"을 리턴하여 스캔 태스크가 자동 재개 대기 상태로 안전하게 보존됨을 확인함.
