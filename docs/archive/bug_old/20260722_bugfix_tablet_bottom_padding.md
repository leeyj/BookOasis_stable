---
title: "태블릿 및 모바일 브라우저 하단 영역 잘림 및 여백 부족 개선"
date: "2026-07-22"
bug_id: "20260722_tablet_bottom_padding_fix"
affected_files:
  - "templates/components/views/library_dashboard.html"
  - "static/css/style.css"
  - "static/css/mobile.css"
impact: "태블릿 및 모바일 기기 브라우저 뷰포트에서 도서 보관함 대시보드 스크롤 시 하단 카피라이트 및 카드 영역 잘림 현상 조치"
resolved: true
---

# 태블릿 및 모바일 브라우저 하단 영역 잘림 및 여백 부족 개선

## 1. 버그 개요
- 아이패드 및 안드로이드 태블릿 브라우저(1200px 이하 뷰포트 등)에서 메인 화면(도서 보관함 대시보드)을 스크롤할 때, 하단 영역(카피라이트 문구 및 하단 책 카드 리스트)의 여백 부족으로 하단이 답답하게 눌려 보이거나 일부분이 잘려서 보이는 현상이 발생함.

## 2. 원인 분석
- `style.css` 내 데스크톱 및 태블릿 공통 메인 컨테이너 `.library-main-content` 요소에 하단 패딩(`padding-bottom`) 속성이 지정되어 있지 않았음.
- `mobile.css`의 `1200px` 이하 미디어 쿼리 구간에서 설정된 `padding-bottom: calc(2rem ...)` 값이 태블릿의 가로/세로 뷰포트 스크롤 끝 지점에서 하단 콘텐츠 가시성을 확보하기에 부족하였음.
- 대시보드 서브 템플릿(`library_dashboard.html`) 하단 카피라이트 컨테이너에 `margin-top: -0.4rem` 음수 마진이 부여되어 하단 스크롤 공간을 침범함.

## 3. 수정 사항
- `templates/components/views/library_dashboard.html` (line 31):
  - 카피라이트 래퍼 <div>의 음수 마진을 `margin-top: 0.5rem; padding-bottom: 1rem;`으로 변경하여 대시보드 최하단에 여유 공간 제공.
- `static/css/style.css` (line 209):
  - `.library-main-content` 기본 클래스에 `padding-bottom: calc(2.5rem + env(safe-area-inset-bottom, 0px));` 속성 추가.
  - 시스템 티커가 있을 시 패딩을 `64px`로 상향.
- `static/css/mobile.css` (line 153):
  - 태블릿 및 모바일 뷰포트 구간에서 `.library-main-content` 하단 패딩을 `calc(3rem + env(safe-area-inset-bottom, 0px))`로 상향 조정하여 하단 스크롤 끝 시점 가시성 확보.

## 4. 검증 결과
- 태블릿 및 모바일 해상도 화면에서 스크롤을 최하단으로 내렸을 때 하단 카피라이트 문구와 카드 섹션이 잘림 없이 넉넉한 패딩 공간과 함께 정상 노출됨을 확인.
