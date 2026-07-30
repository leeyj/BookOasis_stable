---
title: "일반 설정 탭 내 레거시 알라딘 TTBKey 입력 필드 제거 및 DB 정리"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [cleanup, database, settings, frontend]
---

# 🧹 일반 설정 탭 내 레거시 알라딘 TTBKey 입력 필드 제거 및 DB 정리

## 1. 개선 내역
- **동기**: 기존 시스템의 일반 설정 화면에 중복 노출되던 '알라딘 OpenAPI TTBKey' 입력 폼 필드를 완전 제거하고, 관련 DB 설정 레코드를 정리함으로써 데이터 정합성 유지 및 UI 중복성 해소.

## 2. 영향도
- **영향 범위**: 관리자용 일반 환경설정 화면 및 DB settings 테이블
- **우선순위**: 하 (중복 제거 및 리팩토링)

## 3. 수정 및 소거 사항
- **수정 소스 파일**:
  1. `templates/components/tab_media_library.html` (입력 폼 UI 삭제)
  2. `static/js/settings_tab.js` (입력/저장 관련 클라이언트 제어부 제거)
  3. `tools/clean_legacy_aladin_setting.py` (일회성 DB ALADIN 레코드 삭제 유틸)

- **조치 내용**:
  - `tab_media_library.html`에서 기존 196~203라인에 위치하던 알라딘 API 키 관련 HTML `div` 그룹을 소거했습니다.
  - `settings_tab.js`의 `loadGeneralSettings()` 및 `submitGeneralSettings()`에서 `ALADIN` 키값을 다루는 변수 정의와 API 호출 비동기 배열 프로미스를 완벽히 걷어냈습니다.
  - 원격 DB의 `settings` 테이블에서 `key = 'ALADIN'`인 로우를 즉시 제거하고 반영하는 일회성 파이썬 스크립트 `tools/clean_legacy_aladin_setting.py`를 제작해 원격 서버에서 작동시켰습니다.

## 4. 해결 사항 및 검증 결과
- 수정 사항을 원격지에 배포 후 SSH 상에서 `python3 tools/clean_legacy_aladin_setting.py`를 실행하여 `general.db` 및 `adult.db` 두 곳의 레거시 설정 데이터를 모두 소거했습니다.
- 브라우저로 `환경설정 -> 일반 설정` 진입 시 '알라딘 OpenAPI TTBKey' 필드가 성공적으로 보이지 않으며, 다른 일반 환경설정 저장도 정상 작동함을 최종 검증하였습니다.
