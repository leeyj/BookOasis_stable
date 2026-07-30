---
title: "모바일 브라우저 뷰어 하단 오버레이 슬라이더 및 정보 가림 버그 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-18
tags: [bugfix, mobile, css, seekbar, safe-area, layout]
---

# 🐛 모바일 브라우저 뷰어 하단 오버레이 슬라이더 및 정보 가림 버그 조치

## 1. 버그 정의 및 원인
- **현상:** 모바일 크롬 및 사파리 등 모바일 기기 브라우저로 뷰어 감상 시, 하단 시스템 제스처 바(Home indicator)나 브라우저 자체 제어 툴바 영역에 오버레이 풋터(`.overlay-footer`)의 시크바 슬라이더 및 페이지 정보 배지가 겹쳐 가려지거나 터치가 어려워지는 버그 발생.
- **원인:**
  - 하단 오버레이 풋터의 패딩이 `padding: 0.7rem 1.2rem 0.8rem;`과 같이 반응형 요소 없이 단순 수치로만 정의되어 있어, 가변 모바일 하단 여백 추가 시 풋터 내부의 정보가 화면 밖이나 조작바 밑으로 밀려 은폐됨.

## 2. 해결 방안
- 오버레이 풋터의 하단 패딩에 모바일 가변 여백 환경변수인 **`env(safe-area-inset-bottom, 0px)`**를 합산하도록 수정하여 모바일 크롬 등의 하단 조작계 영역을 확실하게 방어함.
- 수식: `padding: 0.7rem 1.2rem calc(0.8rem + env(safe-area-inset-bottom, 0px))`

## 3. 수정 사항 (수정 소스 파일 목록)
- **[static/css/tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css)**
  - 649라인 `.overlay-footer` 클래스 정의 내 `padding` 값을 safe-area bottom 연산이 가산된 형태로 리팩토링함.

## 4. 해결 사항 및 E2E 검증 결과
- **하단 정보 노출 정상화:** 원격 NAS 서버 배포 후 모바일 기기 브라우저(크롬 등) 실 기기 검증 결과, 하단 제스처 바나 브라우저 바의 간섭 없이 페이지 시크바 및 정보 배지가 최하단 위쪽으로 안전하게 안착하여 매우 쾌적하고 명확하게 노출되는 것을 최종 확인 및 완치 완료.
