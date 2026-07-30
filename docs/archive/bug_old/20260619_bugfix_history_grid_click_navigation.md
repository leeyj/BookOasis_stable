---
title: "최근 읽은 도서 그리드 클릭 시 시리즈 연동 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-19
tags: [bugfix, history, navigation]
---

# 🐛 최근 읽은 도서 그리드 클릭 시 시리즈 연동 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 사이드바 '최근 읽은 도서' 메뉴를 누른 뒤 조회되는 카드 목록에서, '이어보기' 재생 아이콘 주변(카드 본체)을 클릭했을 때 시리즈 상세 화면이 아닌 곧바로 뷰어가 기동되는 현상.

## 2. 원인 분석 (Root Cause Analysis)
- `static/js/ui.js` 내 `renderHistoryGrid` 함수 구성 시, 카드 본체를 클릭하는 이벤트인 `onPrimaryClick`과 재생 아이콘을 클릭하는 `onActionClick`이 모두 `openReader`를 실행하도록 바인딩되어 있었음.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: `static/js/ui.js`
- `renderHistoryGrid` 내부의 `onPrimaryClick` 핸들러가 대시보드 구조와 동일하게 `openBookDetail` 함수를 호출하도록 변경함.
  ```javascript
  onPrimaryClick: (e) => openBookDetail(e, item.series_name || item.title)
  ```

## 4. 결과 검증 (Verification Results)
- 수정 후 '최근 읽은 도서' 그리드 뷰에서 재생 버튼 주변을 클릭 시 정상적으로 시리즈의 단행본 상세 페이지로 연결되며, 재생 버튼을 정확히 클릭 시에만 독서 뷰어가 켜짐을 확인함.
