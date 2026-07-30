---
title: Walkthrough - graceful_shutdown_guard
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# DB 손상 방지를 위한 Graceful Shutdown 및 스캔 가드 개선 결과 (Walkthrough)

스캔 도중 배포 또는 강제 재시작 시 발생할 수 있는 데이터베이스 깨짐(Database Disk Image is Malformed) 현상을 예방하기 위해, 프로세스 종료 로직 고도화 및 선제 스캔 체크 가드를 반영하였습니다.

## 변경 사항 (Changes Made)

### [Server Controls]

#### [MODIFY] [manage.sh](file:///c:/project/media_server/manage.sh)
- `stop()` 함수 내 프로세스 종료 처리 시 `kill -15`를 보낸 후 최대 15초 동안 프로세스가 자발적으로 모든 DB 커넥션을 닫을 때까지 1초 간격으로 대기하는 Graceful Shutdown 대기 절차 구현.
- `stop()` / `restart()` 진입 시 DB의 스캔 상태를 조회하여, 스캔이 실행 중일 경우 비대화형 셸에서는 안전하게 중단 처리하고 대화형 셸에서는 확인 프롬프트 작동. 강제 실행이 필요할 경우 `--force` 인자 전달 지원.

#### [MODIFY] [deploy.py](file:///c:/project/media_server/deploy.py)
- 원격지에 배포용 소스를 올리기 전 SSH 채널을 통해 원격지의 스캔 상태를 선제 검사. 스캔이 실행 중일 경우 대화형 사용자 동의(y/N)를 요구하여 실수로 스캔 와중에 배포하는 현상을 원천 방어.

---

## 검증 결과 (Verification Results)

### 배포 테스트 및 정상 기동 완료
- `deploy.py`를 실행하여 개선된 로직과 안전 장치가 원격 운영 서버에 무결하게 배포 및 동기화 완료되었음을 확인했습니다.
- 원격 서버의 기동 결과 웹 및 스캐너 워커 프로세스가 안전하게 리부팅 완료되었습니다.
