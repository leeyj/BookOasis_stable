---
title: "도커 컴포즈 명세(docker-compose) 파일들의 plugins 볼륨 마운트 해제 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, docker, docker-compose, volume, plugins]
---

# 🐛 도커 컴포즈 명세(docker-compose) 파일들의 plugins 볼륨 마운트 해제 조치

## 1. 버그 및 이슈 정의
- **현상:** 사용자가 `docker-compose up`을 기동하여 컨테이너 환경을 배포하려 할 때, `ModuleNotFoundError: No module named 'plugins.metadata'` 오류가 발생하며 서버 기동 실패.
- **원인:**
  1. `Dockerfile` 볼륨에서 `/app/plugins`를 제거했으나, 배포에 쓰이는 도커 컴포즈 명세서(`docker-compose.yml` 계열)의 `volumes` 리스트에 여전히 `- ./plugins:/app/plugins` 호스트 바인드 마운트가 잔존하고 있었음.
  2. 도커 구동 시 호스트의 빈 `./plugins` 폴더가 컨테이너 내부의 핵심 플러그인 모듈 소스코드 경로를 마스킹하여 유실을 일으킴.

## 2. 해결 방안
- 도커 컴포즈 설정 파일들 전반에서 `- ./plugins:/app/plugins` 바인딩 정의를 일괄 소거하여, 이미지 레이어에 보존된 번들 플러그인 소스코드가 안전하게 동작할 수 있도록 교정함.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[docker-compose.yml](file:///c:/project/media_server/docker-compose.yml)**
  - 18라인의 `plugins` 볼륨 마운트 소거.
- **[docker-compose.ghcr.yml](file:///c:/project/media_server/docker-compose.ghcr.yml)**
  - 15라인의 `plugins` 볼륨 마운트 소거.
- **[docker-compose.override.example.yml](file:///c:/project/media_server/docker-compose.override.example.yml)**
  - 18라인의 `plugins` 볼륨 마운트 소거.

## 4. 해결 사항 및 E2E 검증 결과
- **설정 무결성 보장:** 세 가지 도커 명세 파일 전반에서 `plugins` 볼륨 결함 라인이 완전히 소거되어, 사용자가 어떤 컴포즈 구동 명령을 쓰더라도 모듈 유실 에러가 완벽히 예방됨을 검증함.
