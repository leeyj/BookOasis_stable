---
title: "EPUB 스크롤 보기 상태에서 다음 책 이동 시 화면 락 오류 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "epub", "scroll"]
---

# EPUB 스크롤 보기 상태에서 다음 책 이동 시 화면 락 오류 수정

## 1. 개요 및 증상
- **현상**: EPUB 책을 '스크롤 보기(scroll mode)'로 설정하여 마지막 페이지까지 도달해 다음 책(다음 화 이어서 보기)으로 자동/수동 전환되면, 다음 책이 렌더링된 이후 스크롤이 불가능해지거나 화면이 터치/동작하지 않고 락이 걸리는 현상이 발생했습니다.
- **특이점**: 가로 '페이지 보기' 상태에서는 정상 작동하며, 오직 세로 '스크롤 보기' 모드에서만 발생했습니다.

## 2. 원인 분석
- 뷰어 코어 조율기인 `viewer.js` 내의 **`syncHotspotPointerEvents()`** 함수에서, 터치 스크롤 동작 허용을 판단하는 `isScrollActive` 조건문에 EPUB 포맷(`isEpub`) 여부가 누락되어 있었습니다.
  ```javascript
  // 기존 코드
  const isScrollActive = scrollMode === 'scroll' && (isComic || isTxt);
  ```
- 이로 인해 EPUB 스크롤 보기 상태가 되었음에도 `isScrollActive`가 `false`로 남아:
  1. `media-viewer-modal`의 스크롤 활성화 클래스(`scroll-mode-active`)가 바인딩되지 못하고, 브라우저 바디 스크롤 차단(`overflow: hidden`)이 풀리지 않았습니다.
  2. 최상단 터치 핫스팟 레이어(`common-viewer-hotspot`)가 모바일 해상도에서도 사라지지 않고 전체 화면을 덮은 상태로 모든 터치와 스크롤 이벤트를 갈취하여 차단하고 있었습니다.

## 3. 수정 사항
- [viewer.js](file:///c:/project/media_server/static/js/viewer.js): `syncHotspotPointerEvents` 내의 포맷 검사 조건에 `isEpub` 변수를 신설 및 추가 맵핑하여 스크롤 모드 판정 기준을 정상화했습니다.
  ```javascript
  const isEpub = (fmt === 'epub');
  const isScrollActive = scrollMode === 'scroll' && (isComic || isTxt || isEpub);
  ```

## 4. E2E 검증 및 완료 여부
- 모바일 해상도 브라우저 환경에서 EPUB 도서를 '스크롤' 모드로 감상하다가 마지막에 다다라 다음 에피소드로 전환되었을 때, 핫스팟 터치 레이어가 의도대로 비활성화되어 순정 터치 스크롤과 스와이프 동작이 방해 없이 정상적으로 매끄럽게 수행됨을 검증했습니다.
