---
title: "무한 스크롤 prefetch 임계 마진 최적화 및 120개 한도 상향"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [scroll-performance, infinite-scroll, IntersectionObserver, prefetch]
---

# 🧠 무한 스크롤 prefetch 임계 마진 최적화 및 120개 한도 상향

## 1. 개요 및 버그 내용
- **현상**: 마우스 휠 스크롤이 빠를 때, 기존의 무한 스크롤 감지 마진(`200px`)이 너무 좁아 다음 리스트 데이터를 받아오는 동안 스크롤이 끊기거나 스피너 대기 화면을 거쳐야만 하는 딜레이 현상 발생. 
- **LIMIT 상향 요건**: 데이터 페이지네이션 단위를 기존 60개에서 120개로 확대하였으나, 리스트 한 페이지가 차지하는 물리적 높이가 늘어남에 따라 스크롤바가 최하단에 다다라야만 로드가 감지되는 대기 문제 재발.

## 2. 원인 분석
- `IntersectionObserver`의 `rootMargin` 감지 마진이 데이터 노출 한계치(`LIMIT`)에 걸맞지 않게 너무 작게 잡혀 있어 백그라운드 사전 로드(Prefetch)가 스크롤 속도보다 한 템포 늦게 트리거되었음.

## 3. 조치 내용
1. **페이지 로드 한계치 상향 ([`state.js`](file:///c:/project/media_server/static/js/state.js))**:
   - `LIMIT` 값을 `60`에서 `120`으로 수정하여 렌더링 성능과 로드 효율을 확인하기 위한 탐색 노출 대역 확대.
2. **IntersectionObserver 사전 감지 마진 극대화 ([`infinite_scroll.js`](file:///c:/project/media_server/static/js/infinite_scroll.js))**:
   - `rootMargin`을 기존 `'0px 0px 200px 0px'`에서 `'0px 0px 2000px 0px'`로 대폭 확장하여, 사용자가 실제 마지막 카드에 근접하기 훨씬 전에 다음 페이지 비동기 로딩을 사전 트리거하도록 설계.

## 4. 결과 및 검증
- 120개 도서가 노출되어도 리플로우 차단 설계(`DocumentFragment`)가 되어 있어 속도 저하 현상 없음.
- 최하단 약 2~3 화면 높이가 남았을 때 사전에 다음 120개 리스트를 백그라운드에서 당겨오므로, 스피너 휠 차단/대기 없이 물 흐르듯 무한히 스크롤링되는 안정된 탐색 UX 확보.
