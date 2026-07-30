---
title: "도커 배포 환경 내 plugins.metadata 모듈 유실로 인한 ModuleNotFoundError 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, docker, volume, plugin, deployment]
---

# 🐛 도커 배포 환경 내 plugins.metadata 모듈 유실로 인한 ModuleNotFoundError 조치

## 1. 버그 내역 및 원인 분석
- **현상:** 도서 빌드 후 배포된 Docker 이미지 기반 컨테이너 구동 시 `ModuleNotFoundError: No module named 'plugins.metadata'` 에러를 발생시키며 앱 서버가 다운됨.
- **원인:**
  1. `Dockerfile` 내에 `VOLUME ["/app/db", "/app/covers", "/app/cache", "/app/plugins"]` 지정을 통해 `/app/plugins`를 익명 볼륨으로 선언함.
  2. 도커의 볼륨 관리 정책상 컨테이너가 기동되면서 해당 경로에 외부 볼륨이 바인딩되거나 마운트될 때, 이미지 빌드 타임에 복사되었던 `/app/plugins` 내부의 정적 디렉토리 및 파일(기본 번들 메타데이터 플러그인 소스코드)이 빈 볼륨에 의해 덮어씌워지거나 가려지는(masking) 결함이 유발됨.
  3. 이로 인해 파이썬 엔진이 기본 의존 모듈인 `plugins.metadata.base` 등을 로드하지 못하고 비정상 종료됨.

## 2. 영향도
- **배포 불능:** 도커 환경을 사용하는Synology NAS, Docker-compose 운영 환경에서 미디어 서버가 전혀 구동되지 않는 치명적 에러 유발.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[Dockerfile](file:///c:/project/media_server/Dockerfile)**
  - 37라인의 볼륨 선언에서 `/app/plugins`를 영구 제외시킴.
  - 이를 통해 플러그인 폴더는 컨테이너 이미지 레이어에 상주하여 파일의 안정성과 무결성이 보장되며, 사용자가 외부 볼륨 연결을 원할 경우 `docker-compose.yml` 등 실행 명세에서만 마운트하도록 Best Practice를 준수함.

## 4. 해결 사항 및 E2E 검증 결과
- **플러그인 파일 무결성 보존:** `/app/plugins` 볼륨 지정을 철회함으로써 컨테이너 기동 시 파일 가림 현상이 제거되어 `ModuleNotFoundError` 결함이 완벽히 예방됨.
