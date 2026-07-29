---
title: "뷰어 컨텍스트 메뉴 [보기] 탭 모바일 전용 전체화면 전환 버튼 추가"
date: 2026-07-29
category: improvement
tags: [viewer, mobile, fullscreen, context_menu, ui_ux]
impact: medium
status: completed
---

# 개선 내역: 뷰어 컨텍스트 메뉴 [보기] 탭 모바일 전용 전체화면 전환 버튼 추가

## 개요
모바일 기기(안드로이드, iOS) 사용자들의 시청 및 독서 편의성을 극대화하기 위해, 뷰어 중앙 클릭 시 노출되는 컨텍스트 오버레이 메뉴의 **`[📖 보기]` 탭에 모바일 전용 전체화면 전환 버튼(`btn-overlay-fullscreen-mobile`)**을 신설하였습니다.

## 주요 변경 사항

### 1. 뷰어 오버레이 UI 마크업 추가 (`templates/components/media_viewer.html`)
- `[📖 보기]` 탭 (`#overlay-tab-layout`) 내에 모바일 전용 전체화면 토글 버튼 추가:
  - 아이콘 `#overlay-mobile-fullscreen-icon`
  - 라벨 `#overlay-mobile-fullscreen-label` (i18n: `viewer.fullscreen` / `viewer.exit_fullscreen`)

### 2. 모바일 기기 감지 및 상태 실시간 동기화 (`static/js/viewer/fullscreen_controller.js`, `static/js/viewer/navigation.js`)
- **`isMobileDevice()` 판별 로직 구현**: Android/iOS UserAgent 및 터치 포인트(`maxTouchPoints`), 뷰포트 너비(1024px 이하)를 종합 체크하여 모바일 단말일 경우에만 해당 버튼을 노출(`display: inline-flex`).
- **`syncViewerFullscreenState()` 토글 연동**:
  - 전체화면 진입 시: `fa-compress` 아이콘 + `[전체화면 해제]` 텍스트 전환
  - 전체화면 해제 시: `fa-expand` 아이콘 + `[전체화면]` 텍스트 전환

### 3. 다국어(i18n) 번역 키 추가 (`static/i18n/ko.json`, `static/i18n/en.json`)
- `viewer.fullscreen`: "전체화면" / "Fullscreen"
- `viewer.exit_fullscreen`: "전체화면 해제" / "Exit Fullscreen"

## 변경 소스 파일
- `templates/components/media_viewer.html`
- `static/js/viewer/fullscreen_controller.js`
- `static/js/viewer/navigation.js`
- `static/i18n/ko.json`
- `static/i18n/en.json`
