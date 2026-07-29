---
title: "뷰어 컨텍스트 오버레이 2장 보기 중앙 여백 실시간 토글 기능 추가"
date: 2026-07-29
category: improvement
tags: [viewer, 2page, center_gap, overlay, i18n, UI]
impact: medium
status: completed
---

# 개선 내역: 뷰어 컨텍스트 오버레이 2장 보기 중앙 여백 실시간 토글 기능 추가

## 개요
2장 보기 모드로 도서/만화를 감상할 때 환경설정 패널에 진입하지 않고도, 중앙 클릭 시 나타나는 오버레이 메뉴의 **`[📖 보기]`(Layout) 탭**에서 즉시 `[중앙 여백 보이기 / 감추기]` 상태를 토글할 수 있는 기능 버튼을 추가하였습니다.

## 주요 변경 사항

### 1. 오버레이 메뉴 HTML 구조 추가 (`templates/components/media_viewer.html`)
- `[📖 보기]` 탭 내 1장/2장 보기 전환 버튼 옆에 `[중앙 여백]` 토글 버튼 (`#btn-comic-center-gap`) 추가

### 2. 다국어 번역 키 등록 (`static/i18n/ko.json`, `static/i18n/en.json`)
- `viewer.center_gap_show`: 중앙 여백 / Center Gap
- `viewer.center_gap_hide`: 중앙 여백 감춤 / No Center Gap

### 3. 실시간 토글 및 동기화 로직 구현 (`static/js/viewer.js`, `static/js/viewer/navigation.js`)
- `window.toggleComicCenterGap()`: `remove_2page_center_gap` 로컬스토리지 설정값('0': 여백 있음, '1': 여백 없음) 토글 및 현재 뷰어(만화, PDF, TXT, EPUB) 즉시 새로고침
- `window.syncComicCenterGapButton()`: 오버레이 메뉴 열림 시 저장된 스토리지 값에 맞춰 버튼의 활성화(`active`) 스타일 및 텍스트 자동 동기화
- 환경설정 탭의 `2장 보기 중앙 여백 제거` 체크박스와도 즉시 연동되도록 반영

## 효과 및 검증
- 책의 형태나 스프레드 이미지의 특성에 따라 여백 유무를 오버레이 메뉴에서 즉시 조작할 수 있어 독서 경험이 대폭 향상되었습니다.
- 변경된 설정값은 브라우저 `localStorage`에 자동 저장되므로 뷰어를 닫기 전까지는 물론, 이어서 보기 시에도 지속 유지됩니다.
