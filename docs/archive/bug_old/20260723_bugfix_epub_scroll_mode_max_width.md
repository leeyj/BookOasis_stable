---
title: "EPUB/TXT 스크롤 보기 모드 본문 좌우 폭 과다 확장 현상 수정"
category: "bugfix"
date: 2026-07-23
severity: "low"
affected_files:
  - "static/js/viewer/txt_settings_apply.js"
  - "static/js/viewer/viewer_padding.js"
  - "static/css/tab_media_library_viewer.css"
tags: [epub, viewer, scroll-mode, max-width, UI]
---

# 버그 내역

## 증상

EPUB 및 TXT 뷰어에서 보기 모드를 '스크롤(Scroll)' 모드로 변경 시, 본문 텍스트 레이아웃의 `max-width` 제한이 제거되어 모니터 화면 전체 가로폭(100%)으로 한 줄에 수백 자가 펼쳐지면서 가독성이 심각하게 하락하던 현상.

## 근본 원인 분석

- `txt_settings_apply.js` 및 `viewer_padding.js`에서 스크롤 모드(`scrollMode === 'scroll'`) 설정 시 `scrollWrapper.style.maxWidth` 값을 빈 값(`''`) 또는 `100%`로 지정함.
- 이에 따라 이미지 요소는 600px 중앙 정렬되고 텍스트는 화면 100%로 퍼지는 레이아웃 불일치가 발생함.

---

## 수정 사항

1. **`static/js/viewer/txt_settings_apply.js`**:
   - 스크롤 모드 시 `scrollWrapper`의 `maxWidth`를 표준 독서 너비인 **`850px`**로 고정하고 `margin: 0 auto`로 중앙 정렬 적용.
2. **`static/js/viewer/viewer_padding.js`**:
   - 여백 조절판 적용 시에도 세로 스크롤 모드일 경우 `wrapper.style.maxWidth = '850px'` 및 중앙 정렬 유지.
3. **`static/css/tab_media_library_viewer.css`**:
   - `#txt-scroll-wrapper:not(.scroll-mode-page)` 스타일 규칙에 `max-width: 850px; margin-left: auto; margin-right: auto;` 기본 CSS 추가.

---

## 해결 결과

- 대형 뷰포트나 와이드 모니터 환경에서도 EPUB/TXT 스크롤 보기 시 본문 텍스트가 850px 가로폭 이내로 예쁘게 중앙에 정돈되어 가독성이 대폭 향상됨.
