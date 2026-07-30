---
title: "APScheduler 타임존 구성 오류 및 Lazy 스캐너 미동작 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-21
tags: [scheduler, timezone, bugfix]
---

# APScheduler 타임존 구성 오류 및 Lazy 스캐너 미동작 수정

## 1. 버그 개요
- **장애 현상**: 사용자 설정상 타임존이 `Asia/Seoul`로 정상 등록되어 있음에도 불구하고, 백그라운드 스케줄러(APScheduler)가 UTC 기준으로 스케줄을 처리하여 05:00 KST에 예약된 `Lazy cover scanner`가 오동작/미동작함.
- **발생 원인**: `scheduler.start()`가 실행된 이후에 `scheduler.configure(timezone=...)`가 호출되어 `SchedulerAlreadyRunningError: Cannot reconfigure the scheduler once it has been started` 예외가 발생함. 이로 인해 스케줄러가 기본값인 UTC로 강제 환원되어 동작함.

## 2. 영향도
- 스케줄러를 기반으로 동작하는 모든 백그라운드 작업(도서 자동 스캔, Lazy cover 스캔, FTS 색인 등)이 KST(한국 표준시) 기준이 아닌 UTC 기준으로 9시간씩 지연되어 실행됨.

## 3. 수정 사항
- **수정 소스 파일**: [scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)
- **수정 내용**:
  1. `start_scheduler()` 메소드 내에서 스케줄러가 구동(`start()`)되기 **전에** `reload_all_jobs()`를 호출하여 `configure()` 처리가 안전하게 선행되도록 조정.
  2. 스케줄러가 이미 `running` 상태인 런타임 중에 타임존 변경이 발생할 경우, `configure()` 대신 `scheduler._timezone = target_tz` 및 `scheduler.timezone = target_tz`를 통해 안전하게 동적으로 타임존을 주입할 수 있도록 예외 분기 처리.

## 4. 해결 확인
- 수정 후 스케줄러 초기화 시 `[Scheduler ERROR] Failed to configure scheduler timezone (Asia/Seoul): Scheduler is already running` 예외 로그가 사라졌으며, 정상적으로 `[Scheduler] Timezone configured successfully to: Asia/Seoul` 로그가 출력됨을 확인함.
