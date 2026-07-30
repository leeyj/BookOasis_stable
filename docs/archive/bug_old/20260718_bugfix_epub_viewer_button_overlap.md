---
title: "EPUB 뷰어 전체화면 닫기 단추와 목차(TOC) 열기 단추의 모바일 겹침 오작동 버그 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, mobile, layout, safe-area, css, view]
---

# 🐛 EPUB 뷰어 전체화면 닫기 단추와 목차(TOC) 열기 단추의 모바일 겹침 오작동 버그 수정

## 1. 버그 정의 및 원인
- **현상:** 모바일 크롬 등 상단 시스템 노치(Notch)가 존재하는 모바일 디바이스에서 EPUB 뷰어 전체화면을 켤 시, 닫기 버튼과 목차 버튼이 완전히 수직 중첩되어 목차 기능을 누르지 못하고 닫기 기능만 수행되는 장애가 보고됨.
- **원인 (코드 결함 규명):**
  - 닫기 버튼(`.floating-close-btn`)은 기기 노치 여백을 감안하도록 `top: calc(40px + env(safe-area-inset-top, 0px))` 상대 수식을 탑재함.
  - 목차 버튼(`epub-toc-btn`)은 상수 값인 `top: 90px`로 인라인 하드코딩됨.
  - 이로 인해 모바일 노치 여백 크기(`safe-area-inset-top` = 45px~50px)가 적용되면 닫기 버튼 높이가 `85px~90px`로 밀려 내려오게 되어 `90px`에 있던 목차 버튼을 완벽히 덮어버림.

## 2. 해결 방안
- 목차 버튼 또한 기기 노치 여백 가변 값을 정상 가산하도록 수식을 변경하고, 닫기 버튼과 수직 수치 간격 `60px`을 완벽하게 확보할 수 있도록 리팩토링함.
- 수식: `top: calc(100px + env(safe-area-inset-top, 0px))` 및 `right: calc(20px + env(safe-area-inset-right, 0px))`

## 3. 수정 사항 (수정 소스 파일 목록)
- **[static/js/viewer/txt_toc.js](file:///c:/project/media_server/static/js/viewer/txt_toc.js)**
  - 221라인 `btn.id = 'epub-toc-btn'` 생성 구문 내 `style.cssText` 인라인 탑/라이트 배치 정의를 calc()와 env()를 조합한 동적 배치 수식으로 갱신함.

## 4. 해결 사항 및 E2E 검증 결과
- **겹침 오동작 완치:** 원격 NAS 서버 배포 후 모바일 뷰포트 시뮬레이션 테스트 결과, 닫기 버튼과 목차 버튼이 상호 간의 안전 거리를 유지하며 개별 조작이 명확하고 편안하게 이루어지는 것을 정밀 확인 및 조치 완료.
