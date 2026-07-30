---
title: Walkthrough - docker_status_tool
project: BookOasis
category: history
date: 2026-07-19
type: walkthrough
---
# 도커 전용 헬스 체크 도구(tools/docker_status.py) 개발 결과 (Walkthrough)

도커 컨테이너 내에서 외부 프로세스 유틸리티(ps)나 sqlite3 CLI, 셸 문법 에러의 호환성 제약 없이 안전하게 상태를 진단할 수 있도록 파이썬 전용 헬스 툴을 개발하여 적용 완료했습니다.

## 변경 사항 (Changes Made)

### [Tools]

#### [NEW] [docker_status.py](file:///c:/project/media_server/tools/docker_status.py)
- 순수 파이썬 내장 API(`os.kill`) 및 `/proc` 수동 탐색 Fallback을 결합하여 컨테이너 환경의 웹(Gunicorn) 및 스캐너 워커 프로세스의 실제 가동 유무를 감지.
- 내장 `sqlite3` API를 사용하여 `media_general.db` 및 `media_adult.db`의 무결성(PRAGMA integrity_check) 정합성을 판단 후 리포트.

### [Server Controls]
- `manage.sh` 내 기동 셸 환경의 Bad substitution 문법 방지를 위해 eval 가드 적용 보완.

---

## 검증 결과 (Verification Results)

### E2E 테스트 통과
- `deploy.py` 배포를 통해 원격 배포 및 무중단 재구동 성공.
- 도커 사용자가 컨테이너 밖에서 `docker exec -it bookoasis python tools/docker_status.py`를 실행하여 100% 한글 헬스 결과(웹/워커/DB 상태)를 출력받을 수 있음을 E2E 검증하였습니다.
