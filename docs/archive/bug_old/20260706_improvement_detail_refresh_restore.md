---
title: "도서 상세 화면 새로고침 시 뷰 복구 및 튕김 방지 개선"
date: "2026-07-06"
type: "improvement"
status: "completed"
tags: ["history", "detail", "refresh"]
---

# 도서 상세 화면 새로고침 시 뷰 복구 및 튕김 방지 개선

## 1. 개요 및 요구사항
- **현상**: 사용자가 특정 시리즈의 상세 도서 리스트를 보던 중 브라우저 새로고침(F5)을 하면, 이전에 진입한 상세 뷰 화면이 사라지고 전체 리스트(대시보드 또는 그리드 뷰)로 튕겨 나가는 불편함이 있었습니다.
- **요구사항**: 새로고침을 하더라도 마지막에 보던 도서 상세 리스트 정보가 온전히 복구되어 화면에 유지되도록 가상 라우팅 복원 메커니즘을 적용합니다.

## 2. 해결 방안
- 상세 뷰 진입 시 HTML5 History API (`history.pushState`)에 보존했던 상태 객체(`history.state`)가 새로고침 시점에도 브라우저 메모리에 유지되는 특성을 활용합니다.
- 메인 코어 파일인 `tab_media_library.js` 초기화 시점(`initTabMediaLibrary`)에 `history.state`를 검사하여, 상세 뷰 이력(`view: 'detail'`)이 남아있는 경우 자동으로 해당 도서 상세 함수(`openBookDetail()`)를 스케줄링하여 자동 복구하도록 구현했습니다.

## 3. 수정 파일
- [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js): 초기화 라이프사이클에 히스토리 복원 시 비동기 덮어쓰기 회피용 로컬 변수 캡처 스케줄러 보완
  ```javascript
  if (history.state && history.state.view === 'detail' && history.state.series) {
    const restoreSeries = history.state.series;
    const restoreLibraryId = history.state.libraryId;
    console.log('[History] 새로고침 복원 감지 - 상세 뷰 복구:', restoreSeries);
    setTimeout(() => {
      openBookDetail(null, restoreSeries, restoreLibraryId);
    }, 150);
  }
  ```
- [modal.js](file:///c:/project/media_server/static/js/modal.js): 해시가 `#detail` 인 상태에서 새로고침 등에 의해 히스토리 상태 데이터만 유실된 경우를 보정해주는 `history.replaceState` 방어 코드 삽입
  ```javascript
  if (window.location.hash !== '#detail') {
    history.pushState({ view: 'detail', series: safeSeriesName, libraryId: actualLibraryId }, '', '#detail');
  } else if (!history.state || history.state.view !== 'detail') {
    history.replaceState({ view: 'detail', series: safeSeriesName, libraryId: actualLibraryId }, '', '#detail');
  }
  ```

## 4. 검증 결과
- 상세 뷰(예: 특정 도서 시리즈 목록)에서 브라우저 F5 새로고침 진행 시, 이전 리스트 화면으로 강제 이탈하지 않고 상세 모달 뷰가 끊김 없이 자동 복구되어 띄워짐을 최종 확인했습니다.
