---
title: "태블릿/모바일 뷰포트에서 media-library-container 하단 잘림 및 여백 부족 조치"
category: "bugfix"
date: 2026-07-22
severity: "low"
affected_files:
  - "static/css/mobile.css"
  - "templates/components/views/library_dashboard.html"
tags: [css, tablet, mobile, padding, viewport]
---

# 태블릿/모바일 뷰포트에서 media-library-container 하단 잘림 및 여백 부족 조치

## 1. 버그 개요
- iPad, Android 태블릿 등 터치 기반 모바일/태블릿 기기의 브라우저 하단 영역(Safe Area 및 스크롤 바텀)에서 `.media-library-container` 및 `.library-main-content` 내부 요소(도서 카드의 하단 메타 텍스트 및 Copyright 문구)가 물리적으로 가려지거나 화면 끝에 딱 붙어 잘리는 현상.

## 2. 수정 사항
- `static/css/mobile.css`:
  - `.media-library-container` 하단 padding을 `calc(4.5rem + env(safe-area-inset-bottom, 0px))`로 여유 있게 확충.
  - `.library-main-content` 및 티커 활성화 상태 하단 padding을 각각 `5rem` 및 `92px`로 확장하여 충분한 스크롤 이동 여백 확보.
- `templates/components/views/library_dashboard.html`:
  - 대시보드 하단 Copyright 영역의 `padding-bottom`을 `3.5rem`으로 증대하여 가려짐을 원천 방지.

## 3. 검증 결과
- 태블릿 뷰포트(1200px 미만) 화면에서 대시보드 및 카테고리 도서 그리드 최하단까지 스크롤 시 카피라이트와 도서 카드 하단 영역이 가려짐 없이 깔끔하게 노출되는 것을 확인함.
