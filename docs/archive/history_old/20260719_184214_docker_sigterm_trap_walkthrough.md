---
title: Walkthrough - docker_sigterm_trap
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# 도커 환경 컨테이너 종료 시 DB 손상 방지를 위한 entrypoint.sh 시널 트랩 개선 결과 (Walkthrough)

도커 컨테이너 중지/재시작 시 백그라운드로 작동하는 스캐너 워커 프로세스가 강제 종료되는 결함을 해결하기 위해, `entrypoint.sh` 수준에서 시그널 트랩 전파 구조를 설계하고 배포 완료하였습니다.

## 변경 사항 (Changes Made)

### [Docker Environment]

#### [MODIFY] [entrypoint.sh](file:///c:/project/media_server/entrypoint.sh)
- `cleanup()` 트랩 함수 추가:
  - 컨테이너가 `SIGTERM` 또는 `SIGINT`를 받으면 Gunicorn 및 백그라운드의 스캐너 워커 프로세스(`tools/scanner_worker.py`)에 `kill -15`를 통해 종료 신호를 전파하도록 설정.
  - 두 하위 프로세스가 모두 정상 종료될 때까지 최대 15초간 대기하는 자발적 종료 폴링 루프 추가.
- 실행 구조 변경:
  - `exec "$@"` 대신 백그라운드로 띄우고 `wait "$WEB_PID"`를 통해 entrypoint 셸 상에서 상시 대기하여 시그널을 받을 수 있도록 구조 개편.

---

## 검증 결과 (Verification Results)

### 배포 테스트 및 기동 확인 완료
- `deploy.py`를 통해 수정된 `entrypoint.sh` 파일을 원격지에 안전하게 배포 완료하였습니다.
- 원격 서버 무중단 재구동 기동이 정상적으로 수행되어 헬스 체크를 안전하게 통과하였습니다.
