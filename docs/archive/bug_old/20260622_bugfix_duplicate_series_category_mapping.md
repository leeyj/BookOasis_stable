---
title: "동일 시리즈명 클릭 시 타 카테고리 도서 매핑 버그 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-22
tags: [frontend, backend, api, detail, library_id]
---

# 🐛 동일 시리즈명 클릭 시 타 카테고리 도서 매핑 버그 조치 (Bugfix Report)

## 1. 버그 내역 및 현상
- **현상**: 새로 추가된 도서인 "행복이 가득한 집" (잡지 카테고리, Library ID: 15) 시리즈 카드를 대시보드 또는 신규 추가 도서 뷰에서 클릭했을 때, 동일한 시리즈명을 가진 다른 카테고리인 "만화(완결A)" (Library ID: 2)의 상세 페이지로 즉시 이동하는 버그 발생.
- **원인**:
  1. 프론트엔드의 도서 카드 렌더러에서 상세 뷰를 열 때 (`openBookDetail`) 도서의 실제 `library_id`를 넘기지 않고 `series_name` 문자열만 넘겨주어 전역 라이브러리 상태를 참조함.
  2. 대시보드 상태에서는 `state.currentLibraryId`가 `'home'` 또는 `'history'`와 같은 시스템 식별값이었으므로, 백엔드의 `BookDetailService.get_media_detail`에서 카테고리 격리 쿼리(`use_lib_filter`)를 탈 수 없었음.
  3. 백엔드에서 `library_id` 없이 `series_name` 조건만으로 DB를 쿼리하여 DB에 더 일찍 스캔 등록되었던 만화 카테고리의 책 정보가 상세화면 목록으로 잘못 반환됨.

## 2. 영향도 및 범위
- **영향 범위**: 대시보드 홈 화면, 최근 읽은 도서 그리드, 상세 보기 팝업 갱신, 알라딘 메타데이터 및 카테고리 간 메타 복사 연동 부분.
- **영향도**: 카테고리에 중복 시리즈명이 있는 잡지, 코믹, 소설 등이 혼용될 때 도서 카드의 상세 진입이 완전히 엉뚱한 페이지로 왜곡되어 전반적인 데이터 접근을 불가능하게 함.

## 3. 수정 및 해결 사항
- **백엔드 서비스 로직 수정**:
  - `BookDetailService.get_media_detail` 함수에서 `library_id` 인자가 시스템 예약어(`home`, `history` 등)이거나 비어있는 경우, 해당 `series_name`에 부합하는 도서 레코드로부터 실제 물리적인 `library_id`를 조회(Resolve)해오도록 쿼리를 보완.
- **프론트엔드 라우트 및 호출 인자 정비**:
  - `openBookDetail` 함수에 `libraryId` 매개변수를 추가하고, `fetchMediaDetail` 및 히스토리 pushState 상태 관리에 카테고리 ID를 연동.
  - `ui.js` 내의 대시보드, 히스토리 그리드 렌더러 등 모든 카드 클릭 이벤트 핸들러에서 `item.library_id` 인자를 함께 넘겨주도록 변경.
  - 메타데이터 적용 후 부분 새로고침(`metadata_search.js`) 및 브라우저 뒤로가기 복원(`tab_media_library.js` popstate) 시에도 해당 `libraryId` 상태가 유지되도록 보완.

## 4. 조치 소스 파일 목록
- [book_detail_service.py](file:///c:/project/media_server/services/book_detail_service.py)
- [modal.js](file:///c:/project/media_server/static/js/modal.js)
- [ui.js](file:///c:/project/media_server/static/js/ui.js)
- [book_list.js](file:///c:/project/media_server/static/js/book_list.js)
- [metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js)
- [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
