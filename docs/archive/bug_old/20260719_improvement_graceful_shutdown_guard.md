---
title: "스캔 중 재시작 방지 가드 및 Graceful Shutdown 대기 개선"
project: "BookOasis"
category: "improvement"
date: 2026-07-19
tags: [deployment, graceful-shutdown, safety-guard, bugfix]
---

# 🚀 스캔 중 재시작 방지 가드 및 Graceful Shutdown 대기 개선

## 1. 개선 배경 및 목적
- 라이브러리 스캔 작업(대량의 DB 쓰기 발생) 도중 소스 배포(`deploy.py`)가 진행되면 기존 `manage.sh`가 `SIGTERM` 후 단 1초만 대기하고 곧바로 `SIGKILL`(`kill -9`)로 프로세스를 강제 종료했습니다.
- 이로 인해 활성화되어 있던 SQLite 트랜잭션이 비정상 중단되고 WAL 저널 동기화가 무너져 데이터베이스 손상(`database disk image is malformed`)이 유발되던 치명적인 현상을 근본적으로 차단하기 위함입니다.

## 2. 주요 개선 사항
- **[manage.sh](file:///c:/project/media_server/manage.sh) stop/restart 개선**:
  - `SIGTERM`(`kill -15`) 시그널 전달 후 프로세스가 안정적으로 메모리를 해제하고 DB 커넥션을 닫을 때까지 최대 15초(15회 폴링) 동안 자발적 종료를 대기하도록 개선.
  - SQLite CLI 쿼리를 사용해 일반 DB의 스캔 상태(`libraries.scan_status = 'scanning'` 및 `scanner_tasks.status = 'running'`)를 체크하고, 스캔이 진행 중일 때 비대화형 쉘에서는 기동을 중단하고 경고를 출력하도록 방어 조건(가드) 추가. (수동 강행 시 `--force` 매개변수 필요)
- **[deploy.py](file:///c:/project/media_server/deploy.py) 배포 사전 검증 가드 추가**:
  - 소스 업로드 전 SSH 커넥션을 통해 원격 DB의 스캔 활성화 여부를 선제 체크.
  - 스캔 중인 경우 배포를 즉시 시작하지 않고 사용자에게 경고한 후 확인 입력(y/N)을 받도록 가드 로직을 삽입하여 오배포로 인한 DB 깨짐 현상을 차단.

## 3. 검증 결과
- 수정 완료 후 `deploy.py`를 통해 홈 서버 배포 및 무중단 재구동 헬스 체크 정상 통과를 확인하였습니다.
- 스캔 중 재시작 및 배포 차단 조건이 안정적으로 정착되었습니다.
