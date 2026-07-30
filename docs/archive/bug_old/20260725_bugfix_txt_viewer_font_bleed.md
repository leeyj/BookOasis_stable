---
title: "TXT/EPUB 뷰어 폰트 변경 시 페이지 모드 오른쪽 글자 삐져나옴(Bleed) 결함 조치"
category: "bugfix"
date: 2026-07-25
severity: "medium"
affected_files:
  - "static/js/viewer/txt_settings_apply.js"
  - "static/js/viewer_settings.js"
  - "static/css/tab_media_library_viewer.css"
tags: [txt_viewer, epub_viewer, multi_column, font_bleed, layout_reflow, bugfix]
---

# 🐛 버그 수정 내역: TXT/EPUB 뷰어 폰트 변경 시 페이지 모드 오른쪽 글자 삐져나옴 결함 조치

## 증상

TXT/EPUB 뷰어의 페이지 넘김 모드(`scrollMode === 'page'`)에서 폰트(바탕체, 고딕체, Pretendard, 커스텀 폰트 등)를 변경하거나 특정 폰트로 렌더링될 때, 화면 오른쪽 끝에 다음 페이지(오른쪽 컬럼)의 첫 몇 글자가 삐져나오거나 잘려서 비치는 현상 발생.

---

## 원인 분석

1. **CSS Multi-Column 계산 및 Subpixel Rounding 오차**:
   - `txt_settings_apply.js`에서 1장 및 2장 보기 다단 폭(`columnWidth`)을 px 단위 고정값으로 지정하고 `columnWidth`와 `columnCount`를 동시에 적용했습니다.
   - `Math.floor()` 계산 오차 및 subpixel rounding 오차로 인해 `scrollWrapper.clientWidth`와 `contentArea` 컬럼 폭의 합 사이에 정밀도 차이(유휴 공간)가 생기면서 우측 경계 뒤쪽의 2번째 컬럼 글자 첫부분이 화면 끝에 표시되었습니다.

2. **비동기 폰트 로드 및 Reflow 후 레이아웃 스냅 미재정렬**:
   - 폰트 변경 시 글꼴의 자간, 폭, 높이 등 Font Metrics가 달라지거나 커스텀 폰트가 비동기로 다운로드 완료되었을 때 뷰어 다단 레이아웃 재계산 및 `snapTxtPageScrollLeft()` 정렬이 다시 실행되지 않아 이전 레이아웃 위치에 정지해 있었습니다.

3. **다단 콘텐츠 오버플로우 방지 CSS 부재**:
   - `.scroll-mode-page .txt-content` 및 `.txt-chunk` 스타일에 `break-inside: avoid` 및 정확한 width 지정이 미흡하였습니다.

---

## 수정 사항

1. **`static/js/viewer/txt_settings_apply.js`**:
   - 1장 보기(`pageStep === '1'`) 시 `columnWidth = '100%'`로 설정하여 컨테이너 폭에 밀착.
   - 2장 보기(`pageStep === '2'`) 시 `columnWidth = calc((100% - ${pageGap}px) / 2)`로 설정하여 정밀 다단 분할.
   - `document.fonts.ready` 완료 시점에 `snapTxtPageScrollLeft()` 정렬 추가.

2. **`static/js/viewer_settings.js`**:
   - `loadAndApplyCustomFont`에서 비동기 폰트 로드가 완료된 직후 스냅 재정렬을 수행하도록 처리.

3. **`static/css/tab_media_library_viewer.css`**:
   - `#txt-scroll-wrapper.scroll-mode-page .txt-content`에 `width: 100%` 보완 및 `.txt-chunk`에 `break-inside: avoid` 스타일 추가.

---

## 해결 사항

- 폰트 종류, 폰트 크기, 패딩 변경 시에도 TXT/EPUB 뷰어 페이지 모드에서 오른쪽 글자 삐져나옴 및 비침 현상이 완벽히 해결됨.
- 비동기 커스텀 폰트 다운로드 완료 시에도 텍스트가 정확한 뷰포트 위치로 정렬됨.
