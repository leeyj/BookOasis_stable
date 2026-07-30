---
title: "무한 스크롤 마우스 휠 감지 감도 개선 및 임계치 조정"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bugfix, infinite-scroll, intersection-observer, scroll-wheel]
---

# 🐛 무한 스크롤 마우스 휠 감지 감도 개선 및 임계치 조정 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 보관함 목록 뷰에서 마우스 휠을 끝까지 굴려도 무한 스크롤 다음 페이지 불러오기(API 추가 로드)가 자동으로 작동하지 않음.
- 오직 화면 우측의 브라우저 스크롤바를 마우스로 직접 클릭하여 아래로 강하게 끌어내리는(드래그) 경우에만 다음 페이지가 로드되는 불편 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- 기존 `IntersectionObserver`의 옵션 중 `threshold`가 `0.1`로 고정되어 있었음. 이는 로딩 스피너 엘리먼트(`infinite-scroll-spinner`) 면적의 최소 10% 이상이 교차 영역(뷰포트 가상 영역) 안으로 완벽히 인입되어야 감지를 시작하도록 제한함.
- 마우스 휠 스크롤은 마우스 드래그 스크롤에 비해 브라우저의 렌더링 스레드 부하 분산(가속 및 비동기 처리) 동작이 작용하여 레이아웃 업데이트가 지연되는 경향이 있음.
- 또한 `rootMargin`이 `2000px`로 지나치게 거대하여 이미 초기 로드 시 뷰포트보다 너무 깊은 곳에서 연산 처리가 완료된 뒤, 실시간 휠 동작 상태에서는 추가적인 상태 갱신이 누락되거나 무시되는 불일치 현상이 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [infinite_scroll.js](file:///c:/project/media_server/static/js/infinite_scroll.js)
  - `threshold` 값을 `0.1`에서 **`0`**으로 대폭 하향 조정함. 이제 단 1픽셀만 교차 감지 영역(Margin boundary) 내에 들어와도 즉각 교차 이벤트가 발동됩니다.
  - `rootMargin` 값을 `2000px`에서 **`800px`**로 변경하여, 과도한 메모리 연산 낭비 및 브라우저 엔진의 업데이트 최적화 스킵 현상을 막고 안정적으로 휠 유입 지점에 인터셉션되도록 보정함.

## 4. 결과 검증 (Verification Results)
- 소스 코드 수정 후 마우스 휠 롤링 시, 로딩 바운더리 진입 지점(800px 전방)에서 즉각 교차 연산이 트리거되어 `[InfiniteScroll-Observer] Spinner intersected -> Loading next page...` 콘솔 로그가 유실 없이 찍히는 것을 확인.
- 정상적으로 비동기 데이터 로드 및 렌더링이 연속되어 마우스 휠만으로 끊김 없는 라이브러리 스크롤 페이징 확인 완료.
