---
title: Walkthrough - metadata_rerender_id_loss
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

메타데이터 일괄 적용 완료 후 상세 페이지 화면이 새로고침 없이 즉각 정상적으로 리렌더링되지 않고 0권으로 꼬이던 최종 문제를 조치하였습니다.

## 🛠️ 수정 사항

### 1. 리렌더링 시 라이브러리 ID 결정 로직의 history.state 배제 및 실재 데이터 기반 교체 ([metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js))
- 메타데이터 적용이 완료된 직후, 화면을 갱신하기 위해 `openBookDetail`을 호출할 때 넘겨주던 `activeLibId` 변수가 `history.state.libraryId` 참조 실패 시 문자열 `"undefined"` 등으로 오염되어 데이터 조회 실패(0권)를 낳던 심각한 구조적 문제를 해결했습니다.
- 불확실한 `history.state`를 배제하고, 직접 조회하여 신뢰성이 보장되는 `targetBook.library_id` 변수를 `activeLibId` 결정 규칙 1순위로 승격시켰습니다.

---

## 🧪 E2E 최종 검증 결과
- **메타 적용 완료 후 원활한 리렌더링 검증**: "나 혼자 탑에서 농사" 상세 페이지에서 알라딘 메타데이터 검색 매칭 후 "적용"을 눌렀을 때, `openBookDetail` 함수에 정수형 라이브러리 ID(`4`)가 완벽히 주입되어 백엔드 API 요청이 오류 없이 호출되는 것을 확인했습니다.
- **실시간 화면 동기화**: 적용 즉시 로딩 스피너 작동 후 설명과 썸네일 표지(WebP), 그리고 단행본 목록 `1권`이 꼬임 없이 실시간으로 리페인팅(Repainting)되는 것을 최종 검증했습니다.
