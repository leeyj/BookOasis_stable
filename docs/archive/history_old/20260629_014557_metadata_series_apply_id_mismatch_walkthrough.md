---
title: Walkthrough - metadata_series_apply_id_mismatch
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# 작업 결과 요약 (Walkthrough)

대시보드 또는 전체 목록에서 진입하여 시리즈 메타데이터 수동 검색 및 적용 시, 설명과 표지 이미지가 화면에 즉시 로드되지 않던 현상을 해결했습니다.

## 🛠️ 수정 사항

### 1. 메타데이터 검색 및 전파 로직 예외 처리 보강 ([metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js))
- 시리즈 상세 화면 내 "메타정보 검색" 실행 시, 현재 라이브러리 상태값(`state.currentLibraryId`)이 물리 라이브러리 정수 ID가 아닌 시스템 식별자(`'home'`)일 때 백엔드 UPDATE 매칭 쿼리가 0건 실행되어 데이터 전파가 무산되던 구조적 원인을 해결했습니다.
- 전파 API(`api.copyMetadata`) 전송을 위한 폼 데이터 조립 시 `target_library_id` 파라미터로 `targetBook.library_id`를 동적으로 추적·추출해 냄으로써, 실제 소속 라이브러리의 고유 정수 ID가 정확히 백엔드로 전달되도록 정비했습니다.

---

## 🧪 E2E 최종 검증 결과
- **대시보드(Home) 내 시리즈 메타 갱신 E2E 테스트**: 대시보드 화면에 노출된 도서를 통해 상세 뷰로 접근하여 "메타정보 검색" 및 "적용"을 실행했을 때, 백엔드 쿼리에 올바른 정수형 라이브러리 ID가 바인딩되면서 `books` 테이블 레코드 갱신이 성공하는 것을 확인했습니다.
- **실시간 UI 갱신 상태 검증**: 적용 후 모달창이 닫히며 즉각적으로 메타 썸네일 표지(WebP) 및 설명 텍스트가 정상 갱신되어, 깨짐 및 빈칸 현상 없이 올바르게 출력되는 것을 최종 검증했습니다.
