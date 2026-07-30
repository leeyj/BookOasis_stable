---
title: "미디어 서버 권한 격리 강화 및 OPDS DB Basic Auth 보안 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [security, backend, auth]
---

# 🛡️ 미디어 서버 권한 격리 강화 및 OPDS DB Basic Auth 보안 조치

## 1. 취약점 및 개선 대상
- **현상**:
  - 일반 OPDS 경로(`/opds` 이하 및 도서 다운로드)에 어떠한 인증 장치도 마련되어 있지 않아 주소만 알면 누구나 카탈로그를 조회하고 원본 도서 파일을 무단으로 통째 다운로드해 갈 수 있었음.
  - 성인 OPDS의 경우 하드코딩된 임시 토큰(`SECRET_ADULT_TOKEN`)에 의존하고 있어 보안성이 극도로 취약했음.
  - 어드민 전용 API(`admin.py` 하위 라우트 전체)에 개별 권한 체크가 없어, 로그인된 일반 사용자(`user` role)가 라이브러리 삭제, 추가, 서버 설정 수정을 임의로 호출할 수 있었음.
  - `stream.py` 및 `library.py` 내의 성인 도서관 데이터 접근 시 일반 사용자와 어드민 사용자의 권한 필터가 작동하지 않았음.

## 2. 영향도
- **영향 범위**: 도서 원본 파일 직접 유출 취약점 및 비인가 어드민 API 조작 위험.
- **영향 등급**: **High** (보안 필수 영역으로 외부 공개 망에 연결 시 데이터 탈취 및 시스템 손상 가능성 상존)

## 3. 조치 및 해결 사항
- **수정 소스 파일**:
  - [auth.py](file:///c:/project/media_server/api/auth.py)
  - [admin.py](file:///c:/project/media_server/api/admin.py)
  - [stream.py](file:///c:/project/media_server/api/stream.py)
  - [library.py](file:///c:/project/media_server/api/library.py)
  - [opds.py](file:///c:/project/media_server/api/opds.py)
- **조치 사항**:
  - **어드민 권한 완벽 분리**: `@admin_required` 데코레이터를 신설하여 `admin.py`와 `library.py` 내의 모든 환경설정 및 관리 기능들에 대해 `role == 'admin'` 권한을 의무적으로 검증.
  - **성인 라이브러리 완벽 격리**: `check_adult_permission` 헬퍼를 추가하여 `db_type == 'adult'`인 모든 데이터 조회 및 이미지 스트리밍, PDF/TXT 원본 다운로드 요청 시 세션의 `role`이 `'admin'` 인지 대조하여 비인가 요청 시 `403 Forbidden` 처리.
  - **OPDS DB Basic Auth 통합 구현**:
    - 하드코딩 토큰 방식 폐기.
    - `/opds` 및 `/opds-adult` 전역 경로에 대해 HTTP Basic Auth 헤더를 파싱하고 DB 내 사용자 패스워드 해시를 실시간 검증하도록 구현.
    - 성인 OPDS 경로 접근 시 검증된 사용자의 `role`이 `'admin'` 인지 유효성 추가 보장.
    - 비인가 접근 시 브라우저 및 클라이언트 앱에 `401 Unauthorized`를 전달하여 표준 인증 창 팝업을 유도.
