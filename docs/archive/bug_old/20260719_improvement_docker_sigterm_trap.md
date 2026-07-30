---
title: "도커 컨테이너 종료 시 스캐너 워커 SIGTERM 전파 누락 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-19
tags: [docker, entrypoint, graceful-shutdown, sigterm, bugfix]
---

# 🐛 도커 컨테이너 종료 시 스캐너 워커 SIGTERM 전파 누락 오류 조치

## 1. 버그 내역
- 도커 환경에서 컨테이너 정지/재시작(`docker stop`, `docker-compose down`)을 시도할 때, 도커 데몬이 컨테이너의 `PID 1`로 동작하는 메인 프로세스(Gunicorn)에만 `SIGTERM`을 전송함.
- 백그라운드에서 동작 중이던 실제 도서 스캐너 워커 프로세스(`scanner_worker.py`)는 `SIGTERM`을 포워딩받지 못하고 작동하다가, 도커의 기본 대기 시간(10초) 경과 후 `SIGKILL`(`kill -9`)로 일시 끔살당해 활성화된 SQLite 트랜잭션 도중 파일 정합성이 파괴되어 DB Malformed(손상) 상태에 빠지게 됨.

## 2. 영향도
- 도커 컨테이너 중지 시 라이브러리 스캔 진행률이나 작업이 한창이던 데이터베이스 전체가 깨짐 (Malformed DB).

## 3. 수정 사항
- 대상 파일: [entrypoint.sh](file:///c:/project/media_server/entrypoint.sh)
- 수정 내용:
  - `entrypoint.sh`에 `SIGTERM` 및 `SIGINT` 시그널을 가로채는 `cleanup()` 트랩 핸들러를 정의.
  - 신호 수신 시, 컨테이너 내의 `Gunicorn` 프로세스(WEB_PID) 및 백그라운드의 스캐너 워커 프로세스(`scanner_worker.py` 관련 PIDs)에 명시적으로 `kill -15` (SIGTERM) 신호를 전파.
  - 두 서브 프로세스가 자발적으로 DB 커넥션을 release하고 WAL 저널을 메인 파일에 병합하여 Graceful하게 종료할 때까지 최대 15초간 대기하는 루프를 탑재.
  - 하단의 실행 구문을 `exec "$@"` 대신 백그라운드로 띄우고 `wait` 명령어로 신호가 들어올 때까지 entrypoint 셸 상에서 상시 대기하도록 재구성.

## 4. 해결 사항
- 도커 컨테이너 라이프사이클에 맞춰 완벽한 Graceful Shutdown 신호 전파 메커니즘을 내장함으로써, 도커 환경에서 스캔 중 컨테이너를 중지하더라도 데이터베이스가 절대 깨지지 않도록 원천 복구 및 보장을 완료했습니다.
- 원격 배포 및 무중단 재구동 헬스 체크 정상 통과를 완료하였습니다.
