---
title: "EPUB 연속 스크롤 모드 시 이중 스크롤바 노출 오류 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "scroll", "scrollbar"]
---

# EPUB 연속 스크롤 모드 시 이중 스크롤바 노출 오류 수정

## 1. 개요 및 증상
- **현상**: EPUB 리더에서 '스크롤 보기' 모드로 감상 시, 화면 우측 가장자리에 서로 다른 스크롤바 2개가 나란히 이중으로 노출되는 레이아웃 불일치 현상이 발생했습니다.

## 2. 원인 분석
- **부모 Body 스크롤과 EPUB 컨테이너 스크롤의 동시 활성화**:
  - 만화 및 텍스트 뷰어에서 세로 스크롤 시 브라우저 터치 락을 풀기 위해 `document.body.style.overflow = 'auto'` 처리를 수행하고 있었습니다.
  - 그러나 EPUB 스크롤 모드 개편에 따라 `#epub-viewer-container` 가 독점적으로 세로 스크롤(`overflow-y: auto`)을 담당하게 되면서, `body` 에도 스크롤바가 생기고 `container` 에도 스크롤바가 각각 독립 생성되어 이중 스크롤바가 생겼습니다.

## 3. 해결 방안
- [viewer.js](file:///c:/project/media_server/static/js/viewer.js): `syncHotspotPointerEvents` 내 바디 스크롤 제어문을 조율했습니다.
  - EPUB 포맷(`isEpub`)일 때는, 모드 여하를 불문하고 `viewerModal`에서 `scroll-mode-active` 클래스를 소거하고, 바깥 창인 **`document.body.style.overflow = 'hidden'`을 강제**하여 바깥쪽 스크롤바 생성을 원천 억제했습니다.
  - 이를 통해 뷰어 바깥 영역은 완벽하게 고정되며, 실제 EPUB 본문 스크롤러인 `#epub-viewer-container` 의 스크롤바 1개만 화면 우측에 정갈하게 유지되도록 고쳤습니다.

## 4. E2E 검증 결과
- EPUB 스크롤 보기 시 이중 스크롤바가 완전히 소거되고, 브라우저 스크롤 흔들림 없이 오직 EPUB 리더 본문의 싱글 스크롤바만 깔끔하게 동작하는 것을 최종 확인했습니다.
