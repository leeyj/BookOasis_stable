---
title: "pyyaml 의존성 누락 및 Docker 실행 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [bugfix, dependency, docker, entrypoint]
---

# 🐛 pyyaml 의존성 누락 및 Docker 실행 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 사용자가 BookOasis 서버 실행 및 Docker 컨테이너 실행 시 다음 두 가지 오류를 보고함.
  1. `pyyaml` 라이브러리가 없어 실행이 차단되는 문제.
  2. Docker 컨테이너 실행 시 `core.py` 대신 `api.py`를 엔트리포인트(`api:app`)로 지정하여 실행 실패하는 문제.

## 2. 원인 분석 (Root Cause Analysis)
- `pyyaml` 패키지가 프로젝트 내부 메타데이터 수동 처리 및 스케줄링 설정 등에서 로드되어 사용되나, `requirements.txt`에 누락되어 의존성이 주입되지 못함.
- 프로젝트 개편 시 실제 Flask 애플리케이션 생성 및 초기화 로직은 `core.py`로 이관되었으며, 기존 `api.py`는 주역할을 이관한 빈 안내 래퍼 파일로 변경됨. 그러나 `Dockerfile`의 `CMD` 기동 옵션이 여전히 구버전 형태인 `api:app`으로 설정되어 있어, Gunicorn이 `app` 인스턴스를 찾지 못하고 크래시가 났음.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**:
  - [requirements.txt](file:///c:/project/media_server/requirements.txt): `PyYAML==6.0.1` 패키지를 추가하여 필요한 패키지가 컨테이너 및 런타임에 설치되도록 조치했습니다.
  - [Dockerfile](file:///c:/project/media_server/Dockerfile): Gunicorn 기동 엔트리포인트를 기존 `api:app`에서 실제 실행 진입점인 `core:app`으로 수정했습니다.

## 4. 결과 검증 (Verification Results)
- `requirements.txt` 내 `PyYAML` 추가 후 로컬 환경 패키지 설치 완료.
- `Dockerfile` 빌드 후 기동 엔트리포인트 오류가 없음을 확인.
