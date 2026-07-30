---
title: "메타데이터 적용 프로세스 중 targetBook 변수 스코프 에러(ReferenceError) 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [metadata, scope_error, reference_error, bugfix]
---

# 🐛 메타데이터 적용 프로세스 중 targetBook 변수 스코프 에러(ReferenceError) 수정

## 1. 버그/개선 내역
- **현상**: 상세 화면 메타데이터 검색 매치 적용(일괄 적용) 시 브라우저 콘솔에서 `ReferenceError: targetBook is not defined`가 발생하며 정보 덮어쓰기 기능이 중단되고 화면 렌더링에 실패함.
- **원인**:
  - `metadata_search.js` 내 `selectMetadataBook` 함수에서 `targetBook` 변수가 `if (detailRes.success)` 블록 안에서 `const`로 선언됨.
  - 하지만 모달 닫기 후 리렌더링을 지시하는 `window.openBookDetail` 함수 호출부(`activeLibId` 지정 구문 포함)는 해당 블록 외부 하단에 위치하고 있어, 외부 블록에서 접근할 수 없는 `targetBook`을 참조하게 되어 참조 오류(ReferenceError)가 발생함.

## 2. 영향 범위
- 메타데이터 적용 및 리렌더링 통제 스크립트 (`static/js/metadata_search.js`)

## 3. 수정 사항
- **JS 스크립트 수정** (`static/js/metadata_search.js`):
  - `targetBook` 변수 선언부를 `detailRes.success` 조건문 밖(상위 블록)으로 호이스팅하여 `let targetBook = null;`로 먼저 정의함.
  - 비동기 응답 성공 시 해당 변수에 데이터를 매핑하고, 하위 실행 블록 종료 후에도 변수의 스코프가 보장되어 안전하게 `targetBook.library_id`를 참조할 수 있도록 조치함.

## 4. 해결 사항
- 변수 스코프 에러가 소거되어 메타데이터 일괄 적용 프로세스(API 호출부터 모달 닫기 및 화면 리페인팅까지)가 도중에 중단되지 않고 단번에 부드럽게 완료됨.
