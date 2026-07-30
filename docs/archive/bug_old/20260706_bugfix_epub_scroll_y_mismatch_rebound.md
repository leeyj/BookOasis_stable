---
title: "EPUB 연속 스크롤 모드 시 역스크롤 튕김 및 표지 바운딩 오류 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "scroll", "rebound", "layout"]
---

# EPUB 연속 스크롤 모드 시 역스크롤 튕김 및 표지 바운딩 오류 수정

## 1. 개요 및 증상
- **현상**: EPUB 리더에서 '스크롤 보기' 모드를 선택한 후 휠을 아래로 내릴 때는 정상 작동하나, 위로 다시 올려 읽기 위해 **역스크롤(올라가는 스크롤)을 할 때 화면이 아래로 튕겨서 되돌아가거나(Jittering), 첫 번째 표지 부근에 근접하면 두 번째 페이지 경계선으로 강제 스냅되어 튕겨버리는 연산 장애**가 확인되었습니다.

## 2. 원인 분석
- **챕터 Prepend 시 스크롤탑 보정 오차**:
  - epubJS 연속 스크롤(`scrolled-doc`)은 뷰포트 내부에 보일 챕터 `Iframe`들을 세로로 동적 덧붙임 렌더링합니다.
  - 아래로 내릴 때는 자연스럽게 뒤로 덧붙지만, 위로 스크롤하여 올라갈 때는 **앞쪽 챕터 Iframe을 컨테이너 위쪽(Prepend)에 동적 삽입**하게 됩니다.
  - 이 삽입 순간에 늘어난 높이만큼 **부모 스크롤바의 `scrollTop` 위치 보정(가산)**이 정확히 수행되지 않으면 화면이 갑자기 엉뚱한 이전 지점으로 튀게 됩니다.
- **컨테이너 스크롤 락 및 높이 제한 모순**:
  - 기존 코드에서는 `renderOptions` 설정 시 스크롤 모드임에도 `height: '100%'`로 강제했고, 렌더 타겟인 `.epub-area` 에도 `height: 100%` 및 `overflow-y: auto`를 얹었습니다.
  - 이로 인해 epubJS 엔진 내부의 가상 돔 높이 연산자와 실제 브라우저 돔 스크롤바 간에 높이 감지 균열이 발생해 위쪽 prepend 시 보정 연산이 정상 작동하지 못했습니다.

## 3. 해결 방안
- [viewer_epub.js](file:///c:/project/media_server/static/js/viewer_epub.js):
  - `initEpubViewer` 및 `changeEpubScrollMode` 에서 스크롤 모드(`scrolled-doc`) 렌더링 시 **`renderOptions.height = 'auto'`** 로 변경하여 콘텐츠 길이에 따라 렌더 타겟이 무한 확장되게 놔두고, epubJS가 스크롤 관찰을 컨테이너에 올바르게 위임하도록 교정했습니다.
  - `applyEpubSettings()` 에서 **`#epub-viewer-container` 가 부모 돔으로서 세로 스크롤(`overflow-y: auto !important`)을 직접 담당**하도록 동적으로 overflow 스타일을 전환했습니다. (페이지 보기 모드 시에는 100% 뷰포트에 한정하기 위해 `overflow-y: hidden` 처리합니다.)
  - 또한 테마 인젝션 시 과하게 들어가던 `!important` 폰트 규격을 소거하여 Iframe 내부 콘텐츠 높이 반환 오차를 완치했습니다.
- [tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css):
  - `.epub-area` 영역의 `height: 100%` 및 `overflow-y: auto` 강제를 걷어내고, 자연스럽게 늘어날 수 있도록 **`height: auto; overflow: visible;`** 로 복구했습니다.

## 4. E2E 검증 결과
- EPUB 도서 진입 후 스크롤 모드 상태에서:
  - 마우스 휠을 아래로 내리다 위로 연속 역스크롤해 올려도 튐이나 튕김 현상 없이 한 줄 한 줄 정밀하게 위로 텍스트가 거꾸로 잘 보존되며 흘러갑니다.
  - 맨 첫 장(표지) 끝 라인까지 안전하고 매끄럽게 안착 및 유지가 완료되는 정상 스크롤 작동성을 최종 확인했습니다.
