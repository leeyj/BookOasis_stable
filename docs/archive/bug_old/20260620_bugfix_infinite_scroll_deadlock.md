---
title: "무한 스크롤 락 상충으로 인한 데드락 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, infinite-scroll, deadlock]
---

# 🐛 무한 스크롤 락 상충으로 인한 데드락 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 목록 스크롤 시 무한 스크롤이 단 1회도 작동하지 않으며, `isLoading` 상태가 계속 `true`인 상태로 잠겨 있는 먹통 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- `tab_media_library.js`의 스크롤 리스너 내부에서 중복 트리거 방지를 위해 동기식으로 `state.isLoading = true;`를 수동으로 지정함.
- 그러나 그 직후 실행되는 `loadBooksList(true)` 함수 초입에 `if (state.isLoading) return;` 이라는 락 검사 코드가 배치되어 있음.
- 이로 인해 이미 락이 걸린 것으로 인지하여 `loadBooksList` 내부 로직이 즉시 `return` 처리되어 로딩 작업과 `finally` 블록의 락 해제(`isLoading = false;`)가 절대 도달하지 않는 데드락이 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
- 스크롤 리스너 내부의 수동 락 코드 `state.isLoading = true;`를 완전 제거함.
- `loadBooksList`를 호출하면 함수 시작점 내부에서 동기적으로 안전하게 `state.isLoading = true`를 세팅하고 제어하므로 이중 락 문제를 해결함. 임시로 주입했던 디버그 로깅 코드 또한 깔끔하게 거두었습니다.

## 4. 결과 검증 (Verification Results)
- 소스 코드 적용 후 원격 홈 서버에 배포하고 서비스를 재구동함.
- F12 개발자 도구의 콘솔 창에서 락 걸림 없이 스크롤 마진 조건 충족 시마다 비동기로 도서 데이터가 하단에 원활하게 페이징 누적되는 것을 최종 확인 완료함.
