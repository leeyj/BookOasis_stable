---
title: EPUB/TXT 뷰어 여백(Padding) 조절 미반영 및 maxWidth 고정 결함 수선
date: 2026-07-24
tags: [viewer-padding, epub, txt, realtime-update, maxwidth-clamping, bugfix]
---

# 🐛 EPUB/TXT 뷰어 여백(Padding) 조절 미반영 및 maxWidth 고정 결함 수선

## 1. 개요 및 영향도
- **이슈 항목**: 뷰어 퀵 여백 패널 및 설정 탭에서 상단/하단/좌측/우측 여백 슬라이더를 변경하더라도 뷰어 본문에 실시간 여백이 반영되지 않거나, 좌우 여백(`padLeft`, `padRight`) 변경이 시각적으로 미적용되는 현상.
- **영향 범위**: EPUB, TXT 소설 뷰어 페이지 모드 및 스크롤 모드 전체.

---

## 2. 근본 원인 분석 (Root Cause)
1. **실시간 조절 슬라이더 리렌더링 오프(Off)**:
   - `viewer_padding.js` 의 `applyViewerPaddingRealtime` 함수가 슬라이더 조절 시 `localStorage` 값만 갱신하고 `commitViewerPadding()` 실시간 리렌더링을 호출하지 않아, 조절창을 닫기 전까지 화면 여백이 변하지 않음.
2. **PC/태블릿 등 고해상도 화면에서의 `maxWidth` 강제 고정**:
   - `txt_settings_apply.js` 에서 단면 보기 시 `scrollWrapper` 의 `maxWidth` 가 `800px` 로 제한되어 있어, 화면 폭이 넓은 디바이스에서 좌우 여백(`padLeft`, `padRight`) 슬라이더를 조절하더라도 `margin: auto` 에 의해 본문이 800px 박스 중앙에 고정되면서 시각적 여백 변경이 차단됨.

---

## 3. 수선 내역 (Fix Details)

### A. 실시간 슬라이더 조절 디바운스 즉시 반영 (`static/js/viewer/viewer_padding.js`)
- `applyViewerPaddingRealtime` 함수 실행 시 50ms 디바운스로 `commitViewerPadding()` 을 자동 호출하여, 슬라이더를 움직이는 동안 뷰어 본문의 여백이 라이브로 늘어나고 줄어들도록 개선.

### B. `scrollWrapper` 패딩 인라인 대입 (`static/js/viewer/txt_settings_apply.js`)
- `scrollWrapper` 에 `paddingLeft` 및 `paddingRight` 스타일을 직접 대입하고 `box-sizing: border-box` 를 명시하여, 고해상도 PC/태블릿 및 모바일 어떤 기기에서든 좌우 여백 변경이 100% 즉각 반영되도록 수선.

---

## 4. 검증 결과
- 설정 탭 및 뷰어 퀵 조절창에서 상단/하단/좌측/우측 여백 변경 시 실시간으로 뷰어 여백이 즉각 조절됨을 확인.
