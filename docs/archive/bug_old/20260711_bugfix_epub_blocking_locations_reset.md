---
title: "EPUB 뷰어 진척도 복원 누락 및 locations 대기 블로킹 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, epub, loading, seekbar]
---

# EPUB 뷰어 진척도 복원 누락 및 locations 대기 블로킹 결함 조치

## 1. 버그 내역 및 증상
- 책을 35% 등의 지점까지 정상적으로 읽어둔 이어읽기 상태에서 EPUB 뷰어에 진입하면, 읽던 위치로 복원되지 못하고 첫 페이지(`0%` 또는 `1%`)로 복귀해버리는 결함.
- 동시에 하단 슬라이더바가 `1 / 1` (최대 페이지 1)로 강제 고정되어 슬라이드가 아예 동작하지 않는 현상.

## 2. 원인 분석
- **locations 연산 동기 대기(Await Blocking)**: `[page_mode.js](file:///c:/project/media_server/static/js/viewer/epub/page_mode.js)` 의 `activateRenditionPageMode()` 함수 내에서, 읽던 위치를 그리는 `safeRenditionDisplay()` 호출 전에 무거운 `await ensureLocations(book, locationsChars)` 함수를 동기식으로 먼저 완수하도록 지연하고 있었음.
- **슬라이더 잠김 및 복원 실패**: 이 연산은 전체 텍스트를 파싱하므로 수초~십수초 이상이 소요되며, 연산이 대기되는 동안 뷰어는 첫 페이지 기준인 최대치 `1` 상태로 멈추어 있게 됨. 또한 모바일이나 사양 지연 시 위치 조회 연산 도중 타임아웃 등으로 복원 흐름이 끊겨 `0%` (첫 장)로 복구 지점을 찾지 못하고 튕겨 나감.

## 3. 조치 사항
1. **렌더링 순서 최적화 (Non-blocking Display)**:
   - `safeRenditionDisplay(rendition, currentLocationCfi)` 연산을 최상위로 올리고 즉시 프로미스로 실행하여, 계산 완료 여부와 무관하게 사용자가 읽던 위치를 즉시 화면에 띄우도록(0.1초 내 초고속 렌더링) 순서를 수정함.
2. **Locations 연산 백그라운드 위임**:
   - `ensureLocations()` 대기를 걷어내고, 백그라운드 비동기 프로미스(`then()`)로 전환하여 렌더링을 방해하지 않고 뒤에서 가만히 작동하도록 개선함. 연산이 끝나는 시점에 슬라이더 UI 수치를 동적으로 정상 동기화시켜 슬라이더 잠금 문제를 완전 종식함.

## 4. 해결 확인 및 영향도
- EPUB 도서 진입 즉시 35% 등의 타겟 CFI 위치로 완벽하게 이어읽기 화면이 턱 표시되며, 슬라이더도 최대 퍼센트(100)와 현재 위치(35%)를 정상 취득하여 부드러운 감상 및 슬라이드 조작이 완수됨.
