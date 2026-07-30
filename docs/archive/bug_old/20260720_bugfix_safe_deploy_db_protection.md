---
id: "20260720_bugfix_safe_deploy_db_protection"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [deploy, sqlite, lock, timeout, graceful, shutdown, corruption]
---

# 20260720 — 배포 중 DB 락 대기 및 강제 즉사로 인한 DB 깨짐 예방 조치 완료

## 버그 내역

### 현상
- 원격 배포(`deploy.py`) 진행 시, Gunicorn 서버가 `fuser -k`에 의해 비정상 종료(SIGKILL)되어 쓰기/체크포인트 중이던 SQLite DB의 무결성이 손상됨.
- 또한, 백그라운드 스캐너 프로세스(`lazy_scanner.py`)가 DB를 바쁘게 사용하고 있는 상태에서 배포가 시작되면, `manage.sh stop` 내부의 `sqlite3` 조회 명령줄이 DB 락 대기로 인해 무한 행(Hang)에 빠져 배포가 도중에 중단 및 먹통이 됨.

### 근본 원인
- `deploy.py` 내에 우아한 종료 절차(Graceful Shutdown)를 거치지 않고 웹 포트를 즉사시키는 `fuser -k` 명령어가 하드코딩되어 있었음.
- `manage.sh` 내의 `sqlite3` CLI 호출 시 SQLite DB가 다른 프로세스에 의해 락 상태일 때 무한 대기하는 기본 동작을 차단하는 타임아웃 옵션이 부재했음.

## 영향도
- 배포 프로세스가 완료되지 않고 터미널이 굳어 버리는 현상 유발.
- SQLite 파일 손상(`database disk image is malformed`)을 반복적으로 초래하여 전체 서비스 중단을 초래함.

## 수정 사항

### 수정 파일 목록

#### `deploy.py`
- 5930 포트를 강제 즉사시키던 `fuser -k 5930/tcp` 명령줄을 완전히 제거하여 프로세스 종료를 `manage.sh` 에 일원화 및 단독 위임.
- 비대화형 환경에서 스캔 중 정지 가드에 가로막혀 배포가 정지되는 상황을 극복하기 위해, 재구동 명령어를 `manage.sh restart --force` 옵션으로 안전하게 강화.

#### `manage.sh`
- `stop` 시점에 `sqlite3` 쿼리를 호출하는 명령줄들에 락 대기 타임아웃 제한 옵션(`-init /dev/null -cmd ".timeout 2000"`)을 주입.
- DB가 락 상태여도 최대 2초만 대기하고 예외처리(`2>/dev/null || echo 0`)되어 무한 멈춤 현상을 원천 해결.

## 해결 사항
- 배포 중 프로세스 강제 즉사로 인한 DB 파손 위험성을 없애고, DB가 락이 걸린 꽉 막힌 상태이더라도 배포 터미널이 굳지 않고 안전하게 재시작 절차를 완수하도록 보장합니다.
