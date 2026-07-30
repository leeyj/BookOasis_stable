---
title: "무한 스크롤 장애 진단을 위한 디버그 로깅 적용"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [debug, infinite-scroll, logging]
---

# 🐛 무한 스크롤 장애 진단을 위한 디버그 로깅 적용 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 목록 무한 스크롤(하단 스크롤 시 추가 도서 로드)이 특정 환경에서 동작하지 않아 원인 식별을 위해 디버그 코드를 추가 적용함.

## 2. 원인 분석 (Root Cause Analysis)
- 눈으로 스크롤 좌표값 및 락 플래그 상태를 추적하기 위해 임시 디버깅용 `console.log` 출력을 추가하여 문제 지점을 브라우저 콘솔에서 직접 파악할 수 있도록 조치함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- `window.addEventListener('scroll')` 내부에서 `scrollTop`, `clientHeight`, `scrollHeight` 및 `state.isLoading`, `state.hasMore` 상태 변수를 한 줄의 로그로 실시간 출력하도록 로깅을 보완함.

## 4. 결과 검증 (Verification Results)
- F12 개발자 도구의 콘솔 창을 열고 스크롤할 시, `[InfiniteScroll-Debug]` 프리픽스를 가진 실시간 디버그 로그가 실시간 출력되는지 확인 예정.
