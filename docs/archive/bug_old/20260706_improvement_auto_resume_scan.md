---
title: "스캐너 비정상 종료 시 자동 이어하기(Auto-Resume) 기능 구현"
project: "BookOasis"
category: "improvement"
date: 2026-07-06
tags: [improvement, scanner, scheduler, database, recovery]
---

# 🚀 스캐너 비정상 종료 시 자동 이어하기(Auto-Resume) 기능 조치 보고서

## 1. 개선 내역 (Improvement Report)
- **현상**: Rclone VFS I/O 또는 DB 경합 등으로 스캔 도중 Gunicorn 워커 프로세스가 타임아웃 종료되었을 때, 기존에는 기동 시점에 스캔 상태가 `'ready'`로 초기화만 되고 자동으로 재기동되지 않아, 다음 크론 스케줄이 오기 전까지는 스캔이 멈춰 있는 한계가 있었습니다.
- **개선 내용**: 
  1. 기동 시점에 강제 종료의 흔적인 `'scanning'` 상태의 라이브러리를 `'interrupted'`(중단됨) 상태로 명시 변경합니다.
  2. 스케줄러 서비스(`SchedulerService`)가 기동되는 즉시 데이터베이스를 스캔하여 `'interrupted'` 상태의 라이브러리가 존재할 경우, 이를 감지하고 자동으로 스캔 대기열(ScannerQueue)에 인큐하여 재작동시킵니다.
  3. 이미 엔진에 내장되어 있던 체크포인트(`scanner_progress`) 기능과 맞물려, 중단되었던 디렉토리 시점부터 지능적으로 스캔을 이어 수행합니다.

## 2. 영향도 (Impact Assessment)
- **영향 범위**: 스케줄러 서비스 및 초기 DB 셋업 라이프사이클
- **효과**: 불의의 프로세스 폭사, 타임아웃, 시스템 강제 재부팅 시에도 유저가 수동 개입할 필요 없이 서버 기동 즉시 스캔이 안정적으로 재개됩니다.

## 3. 수정 사항 및 해결 사항 (Resolutions)
- **수정 소스 파일**: 
  1. [database.py](file:///c:/project/media_server/database.py)
     - `init_databases()` 시 Stuck 상태 초기화 쿼리를 `'ready'` 대신 `'interrupted'`로 업데이트하도록 변경.
  2. [scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)
     - `start_scheduler()` 단계에서 `auto_resume_interrupted_jobs()` 헬퍼를 추가하여 `'interrupted'` 상태 카테고리를 자동 감지하고 인큐 처리.

---
*최종 작성일: 2026-07-06*
