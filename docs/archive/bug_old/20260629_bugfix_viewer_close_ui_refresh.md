---
title: "뷰어 종료 시 화면 이력 및 진척도 정보 실시간 자동 리렌더링 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, viewer, ui, rendering, synchronization]
---

# 🧠 [Bugfix] 뷰어 종료 시 화면 이력 및 진척도 정보 실시간 자동 리렌더링 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 책 완독 후 모달 뷰어를 닫거나 [뒤로 가기] 등으로 뷰어 화면을 나가는 상황
- **장애 현상**: 뷰어를 이탈했음에도 완독한 도서가 메인 화면이나 보관함의 '최근 읽은 도서' 이력에서 여전히 미완독 상태로 보이거나 지워지지 않고, 브라우저 새로고침(F5)을 수동으로 눌러야만 비로소 정상 갱신되어 사라지는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 사용자가 독서 진행도를 수동 혹은 자동으로 남겼음에도 대시보드 화면상 상태가 갱신되지 않고 그대로 동결되어, 진척도의 실시간 반영 체감이 훼손되는 UX 결함을 낳았습니다.

---

## 3. 원인 파악 (Root Cause)
- [viewer.js](file:///c:/project/media_server/static/js/viewer.js) 내 `closeMediaViewer()` 실행 시, 진척도 전송 API인 `/api/media/progress`를 호출(Flush)하긴 하지만, 전송이 끝난 시점 또는 뷰어가 파괴된 시점에 대시보드(`loadDashboardData`)나 상세 화면(`openBookDetail`)을 다시 가져와 렌더링해주는 화면 갱신 트리거가 전무했기 때문입니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [viewer_progress.js](file:///c:/project/media_server/static/js/viewer_progress.js#L83-L109)
- `flushProgress` 함수가 fetch 요청의 `Promise`를 최종 반환하도록 구조를 개선하여, 데이터베이스에 쓰기가 완료된 정합 시점을 프론트엔드가 콜백으로 잡을 수 있게 보완했습니다.

### [MODIFY] [viewer.js](file:///c:/project/media_server/static/js/viewer.js#L130-L159)
- `closeMediaViewer` 내부에서 진척도 동기화가 완전히 끝나는 Promise 성공 분기점(`then`)을 포착해 즉시 뷰어 상태 갱신 함수를 연동하였습니다.
- 활성 탭 상태(`state.currentLibraryId === 'home'` 또는 `'history'`)에 맞춰 메인 화면 조회를 실시간 재실행합니다.
- 아울러, 도서 상세 정보 보기 영역(`.book-detail-view`)이 활성화되어 노출 중인 경우, 내부 요소를 기민하게 파싱하여 `openBookDetail`을 재차 쿼리 호출함으로써 단행본 진척바와 완독 배지가 수동 새로고침 없이 즉각 리프레시되도록 개선을 확보했습니다.

---

## 5. 최종 검증 (Verification)
- 도서 완독 후 뷰어 모달 창을 닫자마자, 백그라운드로 API 전송 및 완료 콜백 처리가 순식간에 흘러 대시보드 내 완독 도서 이력이 실시간으로 목록에서 즉시 소거되는 E2E 연동 결과를 직접 확인했습니다.
- 상세 도서 권수 목록 내에서도 읽기를 끝내고 복귀했을 때 완독 배지 및 진행률 게이지가 실시간 연쇄 업데이트됨을 최종 검증 완료하였습니다.
