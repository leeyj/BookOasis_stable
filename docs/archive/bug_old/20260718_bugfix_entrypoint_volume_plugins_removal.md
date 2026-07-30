---
title: "도커 진입 스크립트(entrypoint.sh) 내 plugins 디렉토리 검증 및 소유권 변경 소거"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, docker, entrypoint, volume, plugins]
---

# 🐛 도커 진입 스크립트(entrypoint.sh) 내 plugins 디렉토리 검증 및 소유권 변경 소거

## 1. 버그 및 이슈 정의
- **배경:** 이미지 무결성 보장을 위해 `Dockerfile` 및 도커 컴포즈 명세에서 `/app/plugins` 볼륨 마운트를 안전하게 제외하였음.
- **현상:** 그러나 기동 엔트리포인트 스크립트인 `entrypoint.sh` 내에 여전히 `/app/plugins`가 디렉토리 검증(`DATA_DIRS`) 및 소유권 변경(`chown -R`) 대상으로 남아있어, PUID/PGID 유저 권한 매핑 실행 시 매번 비장치 폴더인 플러그인 소스 내부를 순회하며 속도 지연 및 불필요한 파일 접근 권한 마찰 가능성을 유발함.

## 2. 해결 방안
- `entrypoint.sh` 내의 디렉토리 검사 목록과 권한 조율 대상 목록에서 `/app/plugins`를 영구 제거하여 볼륨 마운트 제외 정책과 최종 통합을 완료함.

## 3. 수정 사항 (수정 소스 파일 목록)
- **[entrypoint.sh](file:///c:/project/media_server/entrypoint.sh)**
  - 13라인의 `DATA_DIRS` 변수 정의에서 `/app/plugins` 경로 제외.
  - 74라인의 `chown -R` 명령 수행 대상 폴더 목록에서 `/app/plugins` 제외.

## 4. 해결 사항 및 E2E 검증 결과
- **설정 일관성 정비 완료:** 도커 및 컴포즈 전반에 이어 컨테이너 최종 진입점의 쉘 스크립트까지 플러그인 유실 유발 여지가 완전히 정화되어, 컨테이너 부팅 속도가 한층 개선되고 호스트와의 권한 마찰 가능성이 제거되었음을 코드 상으로 최종 검증함.
