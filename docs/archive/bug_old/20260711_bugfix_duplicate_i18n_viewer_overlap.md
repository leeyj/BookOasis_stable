---
bug_id: "20260711_bugfix_duplicate_i18n_viewer_overlap"
title: "i18n 번역 리소스 내 중복 viewer 객체 선언에 따른 다국어 렌더링 파괴 버그 수정"
date: "2026-07-11"
severity: "HIGH"
status: "RESOLVED"
affected_files:
  - "static/i18n/ko.json"
  - "static/i18n/en.json"
---

# 버그 수정 보고서: 중복 viewer 키 중복 정의 복구

## 1. 버그 내역 (Bug Description)
*   **현상**: 뷰어 내 퀵 여백 상세 설정을 추가하면서 `ko.json` 및 `en.json` 파일의 최하단에 `"viewer": { ... }` 객체를 신규로 추가함.
*   **원인**: 그러나 이미 기존 번역 파일의 중간(라인 295 부근)에 방대한 양의 `"viewer"` 번역 블록이 정의되어 있는 상태였음. 이로 인해 JSON 최하단에 중복 정의된 빈약한 `"viewer"` 객체가 기존 객체를 완전히 덮어씌우거나(Overwrite) JSON 문법 오류를 야기하여, 전체 뷰어의 텍스트 라벨들이 번역되지 않고 `viewer.from_beginning` 등 키값 그대로 노출되는 화면 깨짐 현상이 유발됨.

## 2. 영향도 (Impact Analysis)
*   독서 뷰어 진입 시 하단 오버레이 조작 버튼 및 안내 문구들이 모두 원문 키값으로 노출되어, 다국어 렌더링이 완전히 파괴되고 조작 편의성을 떨어뜨리는 높은 심각도의 버그임.

## 3. 수정 사항 (Code Changes)
*   [ko.json](file:///c:/project/media_server/static/i18n/ko.json)
    *   최하단에 중복 선언된 `viewer` 객체 및 `filter` 객체 뒤의 잘못된 콤마(`,`)를 소거하여 JSON 구문 정밀성 복구.
    *   라인 295에 존재하는 본래의 `"viewer": {` 객체 블록 내부에 신규 다국어 키 4개(`spacing_settings`, `spacing_settings_short`, `padding_vertical`, `padding_horizontal`)를 계층적으로 병합 주입.
*   [en.json](file:///c:/project/media_server/static/i18n/en.json)
    *   한국어 팩과 동일하게 최하단 중복 블록 및 후행 콤마 소거 처리.
    *   라인 295의 기존 `"viewer"` 오브젝트 내에 영어 퀵 여백 키들을 주입 및 통합 완료.

## 4. 해결 사항 (Resolution)
*   JSON 중복 선언 해소를 통한 문법적 유효성 확보 및 기존 번역 데이터의 완전 복원. 뷰어 화면 진입 시 하단 바의 다국어 텍스트가 다시 유려하게 렌더링됨.
