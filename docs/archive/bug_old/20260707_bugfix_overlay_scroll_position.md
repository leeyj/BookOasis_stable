---
id: bugfix-20260707-overlay-scroll-position
date: 2026-07-07
type: bugfix
severity: high
status: fixed
affected_files:
  - static/css/tab_media_library_viewer.css
---

# 버그: 스크롤 모드에서 컨텍스트 메뉴(오버레이)가 현재 뷰포트 밖에 표시되는 문제

## 버그 내역

- **발생 조건**: zip / epub / txt / pdf 뷰어에서 **스크롤 모드(scroll-mode)** 활성 상태
- **발생 환경**: 모바일 뷰 (iOS Safari, Android 브라우저 등)
- **증상**: 화면 중앙 영역 클릭 시 컨텍스트 메뉴(오버레이)가 현재 스크롤 위치 기준이 아닌
  전체 문서 최상단 기준으로 렌더링되어, 화면에 보이지 않음

## 원인 분석

### DOM 구조

```
#media-viewer-modal  (position: fixed)
  └─ .viewer-body    (position: relative)
       └─ #comic-overlay-menu  (position: absolute ← 문제)
```

### 정상 상태 (page 모드)

`.viewer-body`가 `position: relative`이므로 `#comic-overlay-menu`(position: absolute)의
기준점(containing block)이 `.viewer-body`가 됨 → 오버레이가 뷰어 내부에 정확히 배치됨.

### 스크롤 모드 시 문제 발생 경로

`syncHotspotPointerEvents()` 함수가 스크롤 모드 시 `.viewer-modal`에
`scroll-mode-active` 클래스를 추가함.

mobile.css 해당 규칙:
```css
.viewer-modal.scroll-mode-active {
    overflow-y: auto !important;
}
.viewer-modal.scroll-mode-active .viewer-body {
    overflow: visible !important;
    height: auto !important;   /* ← 핵심 원인 */
}
```

`height: auto`가 되면 `.viewer-body`의 실제 높이가 스크롤 가능한 전체 문서 높이만큼
늘어나고, `position: absolute`인 `#comic-overlay-menu`의 `top: 0`이
**문서 최상단(스크롤 오프셋 0)**을 가리키게 됨.

사용자가 스크롤을 내린 상태에서 오버레이를 열면, 오버레이는 화면 밖(위쪽)에 존재하여
보이지 않는 현상 발생.

## 영향도

- **대상 포맷**: zip, cbz, epub, txt, pdf (스크롤 모드가 적용되는 모든 포맷)
- **대상 환경**: 모바일 (scroll-mode-active 클래스가 적용되는 뷰포트)
- **영향 범위**: 스크롤 모드에서 오버레이 메뉴 자체가 보이지 않아 설정/완독처리 등
  모든 오버레이 기능 사용 불가

## 수정 사항

### 수정 파일: `static/css/tab_media_library_viewer.css`

```css
/* 수정 전 */
.comic-overlay-menu {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

/* 수정 후 */
.comic-overlay-menu {
    position: fixed;   /* absolute → fixed: 스크롤과 무관하게 뷰포트 기준 고정 */
    top: 0;
    left: 0;
    width: 100vw;      /* 뷰포트 단위로 명시 */
    height: 100vh;
}
```

## 해결 사항

`position: fixed`는 항상 뷰포트(브라우저 화면)를 기준으로 배치되므로,
`viewer-body`의 높이나 overflow 상태에 전혀 영향을 받지 않음.
스크롤 위치와 무관하게 현재 화면 기준 top:0 에 정확히 오버레이가 표시됨.
