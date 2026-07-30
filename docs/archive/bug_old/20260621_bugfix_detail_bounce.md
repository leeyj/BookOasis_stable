---
title: "Bugfix - 도서 메타데이터 적용 후 상세화면에서 이탈하여 목록으로 튕기는 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bugfix, modal, javascript]
---

# 버그 트러블슈팅: 도서 메타데이터 적용 후 상세화면 이탈(리스트 튕김) 조치 (metadata_search.js)

## 1. 버그 내역 및 현상
- **현상**: 도서 상세 보기 화면(`detail-view`) 진입 상태에서 특정 단행본(권수) 카드를 우클릭하여 메타데이터 검색 모달창을 띄우고 메타데이터를 적용하면, 검색 모달창이 닫히면서 원래 보던 상세 화면에 머무르지 못하고 메인 카테고리 도서 목록(그리드 뷰)으로 강제 전환되는 현상이 발생했습니다.
- **원인**: 
  1. `selectMetadataBook` 함수 내에서 개별 도서 적용(`isSeriesMode === false`) 후, 무조건 카테고리 전체 목록을 다시 불러오는 `window.selectCategory(state.currentLibraryId)`를 호출하도록 코딩되어 있었습니다. 이 함수가 실행되면서 강제로 화면 상태가 그리드(목록) 뷰로 원복되었습니다.
  2. 또한 `isSeriesMode === true` 분기에서 `openBookDetail` 함수를 호출할 때 임포트되지 않은 함수 명칭을 글로벌 스코프 가드 없이 호출하여 `ReferenceError`를 뿜을 위험이 있었습니다.

## 2. 영향도
- **영향 범위**: 프론트엔드 모듈화 화면(`static/js/metadata_search.js`).
- **영향 수준**: 중 (Medium) - 메타데이터를 개별로 입힐 때마다 상세 창이 닫히고 도서 목록으로 강제 튕겨나가게 됨으로써 연속적인 메타데이터 매핑 및 편집 작업 시 극심한 UX 피로감을 유발합니다.

## 3. 조치 및 수정사항
- **수정 소스 파일**: [metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js)
- **수정 내용**:
  1. **상세 화면 상태 탐지 및 분기 처리**:
     - `isSeriesMode === false`인 경우, `history.state`를 조회하여 현재 사용자가 상세 보기 화면에 있는지 확인합니다(`history.state.view === 'detail'`).
     - 상세 보기 상태라면 `history.state.series`에 보관된 시리즈 명칭을 추출하여 `window.openBookDetail(null, activeSeries)`을 호출함으로써 상세화면 제자리에서 부분 새로고침을 실행합니다.
     - 상세 화면이 아닐 경우(그리드 목록에서 우클릭하여 수색을 돌린 경우)에만 기존처럼 `window.selectCategory(...)`를 수행하여 리스트를 리프레시합니다.
  2. **글로벌 스코프 참조 안정화**:
     - `isSeriesMode === true`의 끝자락에서 `openBookDetail`을 호출할 때도 명시적으로 글로벌 바인딩된 `window.openBookDetail`을 호출하여 ESM 모듈 컴파일 단계나 Strict Mode 환경에서의 `ReferenceError` 발생을 차단했습니다.

## 4. 해결 확인 및 E2E 검증
- 수정된 코드가 정상 동작하는 것을 원격 홈 서버(`192.168.0.20:5930`) 무중단 프로세스 재기동 배포 후 실제 UI 화면에서 수동 E2E 테스트를 통해 교차 검증을 수행했습니다.
- 상세 보기 창에서 단행본을 우클릭하여 메타정보를 덮어씌운 경우 목록으로 이탈하지 않고 상세 보기 내 썸네일과 메타데이터 텍스트만 실시간으로 즉시 갱신되는 것을 완벽하게 확인했습니다.
