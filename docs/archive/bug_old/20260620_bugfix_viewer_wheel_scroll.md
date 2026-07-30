---
title: "미디어 뷰어 휠 스크롤 미동작 및 무한 페이지 넘김 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, viewer, wheel-scroll]
---

# 🐛 미디어 뷰어 휠 스크롤 미동작 및 무한 페이지 넘김 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 독서 중 뷰어 화면에서 마우스 휠 스크롤을 굴렸을 때 스크롤이 전혀 동작하지 않는 문제 발생.
- 휠을 굴렸을 때 페이지가 순식간에 끝까지 넘어가버리는 휠 폭주(무한 페이지 넘김) 현상.

## 2. 원인 분석 (Root Cause Analysis)
- 뷰어 최상단에 마우스를 클릭해 페이지를 넘길 수 있도록 설정한 공통 투명 핫스팟 레이어(`common-viewer-hotspot`)가 배치되어 있어, 마우스 휠 이벤트를 캡처하여 하위의 실 스크롤 컨테이너로 전달하지 않고 가로막고 있었음.
- 페이지 모드('page')일 때 마우스 휠 감도에 따른 쓰로틀링(Throttling) 필터가 부재하여, 한 번의 휠 작동에도 수많은 휠 이벤트가 동시 다발적으로 트리거되어 여러 페이지가 고속으로 전환됨.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [viewer.js](file:///c:/project/media_server/static/js/viewer.js)
- `initWheelListener` 이벤트를 신설하여 핫스팟 레이어(`common-viewer-hotspot`)가 가로채는 휠 입력을 수신하도록 함.
- **세로 스크롤/웹툰 모드**: 활성화된 포맷(TXT, PDF, Comic fit-width)의 실질적인 내부 스크롤 컨테이너(`txt-scroll-wrapper` 등)를 찾아 `scrollBy` 메소드로 직접 휠 델타 값을 수신받아 부드럽게 스크롤을 연동하도록 함. EPUB scrolled 모드의 경우 렌더링된 iframe 내부로 `scrollBy` 신호를 바이패스 처리함.
- **가로 페이지 모드**: 휠 방향(deltaY)에 따라 다음/이전 페이지를 호출하되, `wheelLock` 플래그 및 `setTimeout`을 통해 600ms 동안 중복 처리를 완전 제어하는 쓰로틀링 필터를 적용함.

## 4. 결과 검증 (Verification Results)
- 만화 뷰어 '높이맞춤'에서 마우스 휠을 굴릴 때 600ms 간격을 두고 부드럽게 한 페이지씩 넘어가는 것을 확인.
- 텍스트(TXT) 리더 및 만화 뷰어 '너비맞춤(웹툰)' 모드에서 휠 스크롤이 끊김 없이 부드럽게 세로 스크롤을 작동시킴을 확인함.
