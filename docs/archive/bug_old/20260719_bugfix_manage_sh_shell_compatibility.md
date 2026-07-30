---
title: "POSIX sh 셸 호환성 부재로 인한 manage.sh 실행 실패 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-07-19
tags: [shell, manage, docker, posix, bugfix]
---

# 🐛 POSIX sh 셸 호환성 부재로 인한 manage.sh 실행 실패 버그 조치

## 1. 버그 내역
- 도커 환경에서 사용자가 `docker exec -it bookoasis sh ./manage.sh` 처럼 명시적으로 `sh` (POSIX 표준 셸) 인터프리터 지정을 사용해 실행하는 경우, bash 전용 환경변수인 `${BASH_SOURCE[0]}`가 비어 있게 됨.
- 이로 인해 `APP_DIR` 탐색 구문에서 구 디렉토리 절대 경로를 찾지 못하고 `cd ""` 처리되어 디렉토리 이동에 실패하고 스크립트 실행이 중단되는 문제 발생.

## 2. 영향도
- 도커 컨테이너 내에서 사용자가 서비스 상태 조회(`manage.sh status`)나 수동 조작을 위해 `exec sh ./manage.sh` 기동 시 동작하지 않음.

## 3. 수정 사항
- 대상 파일: [manage.sh](file:///c:/project/media_server/manage.sh#L4-L6)
- 수정 내용:
  - `${BASH_SOURCE[0]}`가 존재하지 않거나 빈 값일 경우, POSIX 셸 파라미터 기본값인 `$0`을 Fallback으로 채택해 스크립트 자기 자신 파일명을 안전하게 참조하고 정상적으로 `APP_DIR` 경로를 파싱해 내도록 대안 구현 완료.

## 4. 해결 사항
- 도커 내부의 `sh` 또는 `ash`, `bash` 기동 여부와 상관없이 모든 셸 환경에서 `manage.sh`가 항상 완벽한 절대 경로를 잡아 정상 작동하도록 수정 및 조치 완료하였습니다.
