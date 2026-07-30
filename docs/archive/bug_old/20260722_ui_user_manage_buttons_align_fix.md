---
title: "사용자 관리 탭 우측 관리 버튼 UI 레이아웃 고정 및 반응형 정돈"
category: "ui"
date: 2026-07-22
severity: "low"
affected_files:
  - "templates/components/settings/users_tab.html"
  - "static/js/settings/users.js"
  - "templates/components/settings/general_tab.html"
tags: [ui, layout, users, buttons, align]
---

# 사용자 관리 탭 우측 관리 버튼 UI 레이아웃 고정 및 반응형 정돈

## 1. 수정 목적
- 해상도 변경 시 **[사용자 수동 등록 및 관리]** 테이블에서 `[비번 변경]`, `[초기 비밀번호 재설정]`, `[삭제]` 버튼의 글자 수 차이 및 퍼센티지 컬럼 폭 지정으로 인해 버튼 위치가 어색하게 줄바꿈되거나 정렬이 깨지는 현상을 해결했습니다.

## 2. 주요 수정 사항
- **[templates/components/settings/users_tab.html](file:///c:/project/media_server/templates/components/settings/users_tab.html)**
  - 테이블 헤더 컬럼 너비를 퍼센트(%) 대신 `ID: 60px`, `Role: 120px`, `기본 비번 여부: 160px`, `관리: 220px (우측 정렬)`로 명확하게 고정하여 테이블이 해상도에 맞춰 일정하게 줄어들도록 개선.
- **[static/js/settings/users.js](file:///c:/project/media_server/static/js/settings/users.js)**
  - 우측 관리 셀의 버튼 컨테이너를 `display: inline-flex; justify-content: flex-end; gap: 0.5rem;`으로 통합.
  - 버튼 규격(`height: 32px; white-space: nowrap;`)을 100% 동일하게 통일하고 문구를 '초기 비번 재설정'으로 깔끔히 정돈하여 줄바꿈 방지.
- **[templates/components/settings/general_tab.html](file:///c:/project/media_server/templates/components/settings/general_tab.html)**
  - 크론 및 단축키 인풋 항목에 `flex-wrap: wrap` 및 `min-width: 200px`를 추가하여 좁은 화면에서도 우수한 가독성을 유지.

## 3. 검증 결과
- 해상도가 줄어들더라도 우측 관리 버튼들이 깨짐 없이 가지런히 우측 정렬 상태를 유지함을 확인.
