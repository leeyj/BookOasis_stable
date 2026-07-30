---
title: "manage.sh status 실행 시 pgrep 명령어 유실 오류 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [shell, docker, process]
---

# 🧠 manage.sh status 실행 시 pgrep 명령어 유실 오류 조치

## 1. 버그 내역
* **현상**: 일부 경량 도서 컨테이너 내부(debian-slim, alpine 등 `procps` 패키지가 미설치된 이미지)에서 `./manage.sh status` 실행 시 `pgrep: command not found` 오류가 출력되며 프로세스 판독에 실패함.
* **원인**: `manage.sh` 내부에서 잔존 프로세스 정제 및 상태 조회를 수행할 때 `pgrep` 유틸리티를 직접 사용함.

## 2. 영향도
* **영향 범위**: 도커 내 프로세스 수동 모니터링 관리 도구 (`manage.sh`), Gunicorn 웹 서버 및 스캐너 워커 프로세스 상태 조회 기능.

## 3. 조치 및 해결 사항
* **대체 방식 적용**: 외부 패키지 의존성이 있는 `pgrep` 명령어를 모든 POSIX 기반 리눅스 및 최소형 도커 이미지에 기본 내장된 `ps`, `grep`, `awk` 조합으로 대체하여 크로스플랫폼 호환성을 확보함.
* **수정 내역**:
  * `pgrep -f "gunicorn.*core:app"` -> `ps ax | grep "gunicorn.*core:app" | grep -v grep | awk '{print $1}'`
  * `pgrep -f "tools/scanner_worker.py"` -> `ps ax | grep "tools/scanner_worker.py" | grep -v grep | awk '{print $1}'`
  * [manage.sh](file:///c:/project/media_server/manage.sh) 수정 완료.
