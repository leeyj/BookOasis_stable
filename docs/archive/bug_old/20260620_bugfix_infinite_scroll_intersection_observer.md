---
title: "IntersectionObserver API 기반 모던 무한 스크롤 구조 전환"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, infinite-scroll, intersection-observer]
---

# 🐛 IntersectionObserver API 기반 모던 무한 스크롤 구조 전환 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 목록 스크롤 감지 시, 비동기 호출 시차 및 렌더링 갱신 주기 틈새로 스크롤 이벤트가 무작위 중복 실행되어 순식간에 마지막 페이지까지 API를 호출해버리는 무한 스크롤 루프 현상(중복 호출 폭주) 발생.

## 2. 원인 분석 (Root Cause Analysis)
- 기존의 스크롤바 높이 연산 방식(`scrollTop + clientHeight >= scrollHeight - 200`)은 마우스 휠 작동 시의 고주파 스크롤 이벤트를 걸러내지 못함.
- 비동기 API 통신 응답 대기 시점과 그리드 DOM 렌더링(Reflow) 시점 사이에 발생하는 미세한 시차에 휠이 움직이면 락이 무력화되어 연쇄 트리거되는 웹 브라우저 이벤트 루프 특유의 타이밍 문제가 근본 원인임.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- 기존의 고전적인 `window.addEventListener('scroll')` 높이 계산 리스너를 완전히 폐기함.
- 최신 브라우저 표준인 **`IntersectionObserver` API** 기반 무한 스크롤 제어로 전환함.
  - 최하단 로딩 스피너(`infinite-scroll-spinner`)를 감시 대상(Target)으로 등록하고, 스피너가 뷰포트 바닥 200px 지점 이내로 교차 진입할 때만 안전하게 비동기 `loadBooksList(true)`를 단 1회씩 정적으로 트리거하도록 개편함.
  - 뷰 전환 시(`selectCategory`) 및 첫 구동 시(`DOMContentLoaded`) 각각 관찰 옵저버를 신선하게 연결/해제하여 메모리 누수와 오동작을 완벽 차단함.

## 4. 결과 검증 (Verification Results)
- 소스 코드 적용 후 원격 홈 서버에 배포하고 서비스를 재구동함.
- 휠 스크롤을 끝까지 내려도 중복 다중 호출이나 무한 루프 폭주 없이, 스피너가 교차하는 정밀 시점에만 1페이지씩 도서 목록이 부드럽고 차분하게 페이징 누적되는 것을 검증 완료함.
