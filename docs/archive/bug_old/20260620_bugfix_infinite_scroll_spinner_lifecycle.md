---
title: "무한 스크롤 스피너 라이프사이클 조건 제어 및 LIMIT 30개 상향 조정"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [infinite-scroll, spinner, page-limit]
---

# 🧠 무한 스크롤 스피너 라이프사이클 조건 제어 및 LIMIT 30개 상향 조정

## 1. 개요 및 버그 내용
- **현상**:
  - 도서 라이브러리 목록 무한 스크롤 중, 도서가 더 로드될 데이터가 있음에도 불구하고 비동기 로드 함수 `finally` 절에서 조건 없이 스피너의 `display = 'none'`을 처리하여 `IntersectionObserver` 관찰 대상이 소거되는 문제 발생.
  - 책 목록을 초기 스크롤 및 로드하는 LIMIT 설정이 20개로 고정되어 있어 30개로 상향할 필요가 있음.
- **영향 범위**: 도서 목록 라이브러리 무한 스크롤 그리드 렌더러

## 2. 원인 분석
- `tab_media_library.js` 내 `loadBooksList`가 호출되고 나서 통신이 완료되면 `finally` 블록에서 다음 페이지 존재 여부(`state.hasMore`)와 무관하게 `spinner.style.display = 'none'`으로 강제 은폐함. 이로 인해 최하단의 감시 요소가 소멸되어 더 이상 스크롤 이벤트가 관찰되지 않음.
- `state.js` 내 `LIMIT` 변수가 `20` 또는 이전 세션 값으로 유지되고 있었음.

## 3. 조치 내용
1. **[tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)**:
   - `loadBooksList` 함수의 `finally` 절을 아래와 같이 수정하여 `state.hasMore`가 참일 경우 스피너가 지속 노출되도록 개선.
   ```javascript
   finally {
     state.isLoading = false;
     if (spinner) {
       spinner.style.display = state.hasMore ? 'block' : 'none';
     }
   }
   ```
2. **[state.js](file:///c:/project/media_server/static/js/state.js)**:
   - `LIMIT` 값을 `30`으로 세팅/유지하여 서버 통신 시 한 번에 30개씩 요청하도록 보장.

## 4. 결과 및 검증
- `deploy.py` 배포 완료 후 E2E 테스트를 진행하여 초기 30개의 도서가 정상 노출되고, 스크롤바가 하단 영역을 감지할 때 추가 30개 목록이 지속 로드되는 것을 확인.
