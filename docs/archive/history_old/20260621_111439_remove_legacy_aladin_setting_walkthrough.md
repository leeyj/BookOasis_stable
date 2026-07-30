---
title: Walkthrough - remove_legacy_aladin_setting
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 레거시 알라딘 OpenAPI 설정 소거 및 DB 정리 워크쓰루

## 변경 사항 및 해결 내용
- **일반 설정 탭 UI/JS 폼 소거**: `templates/components/tab_media_library.html`와 `static/js/settings_tab.js`에서 중복 노출되던 '알라딘 OpenAPI TTBKey' 필드를 삭제하고, 관련 입출력/저장 조작 로직을 모두 걷어냈습니다.
- **일회성 DB 청소 진행**: `tools/clean_legacy_aladin_setting.py` 일회성 스크립트를 작성 및 배포하여, 원격 서버의 `general` 및 `adult` 두 SQLite DB의 `settings` 테이블에서 `key = 'ALADIN'`인 로우를 안전하게 영구 소거하였습니다.

## 검증 결과
- **DB 소거 로그**:
  ```
  [*] 'general' 데이터베이스 구형 ALADIN 설정 소거 프로세스 시작...
  [+] 구형 ALADIN 설정 감지됨 (값: 'ttbleeyj782058001') -> 삭제를 수행합니다.
  [+] 'general' DB에서 ALADIN 키 소거 완료!
  [*] 'adult' 데이터베이스 구형 ALADIN 설정 소거 프로세스 시작...
  [+] 구형 ALADIN 설정 감지됨 (값: 'ttbleeyj782058001') -> 삭제를 수행합니다.
  [+] 'adult' DB에서 ALADIN 키 소거 완료!
  ```
- **UI 교차 검증**: 브라우저를 통해 `환경설정 -> 일반 설정` 진입 시 '알라딘 OpenAPI TTBKey' 입력 폼이 보이지 않는 상태를 확인하였고, 다른 기본 시스템 설정 저장 프로세스도 정상 수행됨을 검증 완료했습니다.
