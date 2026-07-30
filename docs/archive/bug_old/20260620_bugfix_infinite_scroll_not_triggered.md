---
title: "도서 목록 무한 스크롤 감지 미동작 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, infinite-scroll, scroll-height]
---

# 🐛 도서 목록 무한 스크롤 감지 미동작 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 목록(라이브러리 그리드) 우측 영역에서 마우스를 끝까지 스크롤해도 하단에 추가 도서 목록(다음 페이지)이 자동으로 추가 로드되지 않고 멈추는 오류 발생.

## 2. 원인 분석 (Root Cause Analysis)
- 기존의 무한 스크롤 이벤트 감지 수식에서 `document.documentElement` 의 `scrollTop` 및 `scrollHeight` 만을 추출하여 사용함.
- 일부 브라우저 환경(Chrome, Safari 및 모바일 뷰)이나 특정 HTML DTD 선언 레이아웃에 의해 `document.documentElement.scrollTop` 값이 항상 `0`으로 판단되거나, 실질적인 높이 정보가 `document.body` 또는 `window` 객체에 누적되어 조건문(`scrollTop + clientHeight >= scrollHeight - 150`)을 통과하지 못하는 크로스 브라우저 호환성 버그가 원인임.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- `scrollTop`, `scrollHeight`, `clientHeight`를 계산할 때 브라우저 파편화를 극복할 수 있도록 통합 호환성 수식으로 대체함.
  - `scrollTop`: `window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop`
  - `scrollHeight`: `document.documentElement.scrollHeight || document.body.scrollHeight`
  - `clientHeight`: `document.documentElement.clientHeight || window.innerHeight`
- 다음 추가 도서 로딩 임계점을 기존 150px에서 200px로 확대 적용하여 연속 스크롤 로드 체감을 부드럽게 개선함.
- 환경설정(`settings`) 페이지가 노출되어 목록 스크롤 대상이 없을 시에는 무한 스크롤이 트리거되지 않도록 방어 필터 조건을 명시적으로 탑재함.

## 4. 결과 검증 (Verification Results)
- 코드를 로컬에 적용하고 홈 서버 원격지에 동기화 배포 및 재시동함.
- 브라우저를 통해 다량의 책이 수납된 카테고리에 진입하여 마우스 휠 스크롤 작동 시, 하단에 로딩바가 일시 노출되며 다음 페이지 도서가 정상적으로 연쇄 렌더링됨을 확인함.
