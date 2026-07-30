---
title: "모달 닫기 시 전역 변수 초기화로 인한 시리즈 갱신 오류 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [metadata, close_modal, currentSeriesName, initialization, bugfix]
---

# 🐛 모달 닫기 시 전역 변수 초기화로 인한 시리즈 갱신 오류 수정

## 1. 버그/개선 내역
- **현상**: 시리즈 모드 메타데이터 적용이 완료된 뒤 상세 뷰 리렌더링 시 여전히 책 개수가 0권이 되고 메타 정보가 빈 상태로 출력됨.
- **원인**:
  - `selectMetadataBook` 함수 내에서 `closeMetadataSearchModal()`을 호출하는데, 이 모달 닫기 함수 내부에는 다음 검색을 위해 `currentSeriesName = null;` 등의 전역 변수 초기화 코드가 포함되어 있음.
  - 하지만 모달 닫기 함수 바로 직후에 `window.openBookDetail(null, currentSeriesName, activeLibId)`을 실행하도록 구성되어 있어, 이미 `null`이 되어버린 시리즈명이 인자로 전달되어 상세 정보 조회(상세 화면 갱신)에 완전히 실패하였음.

## 2. 영향 범위
- 메타데이터 적용 처리 콜백 함수 (`static/js/metadata_search.js`)

## 3. 수정 사항
- **JS 스크립트 수정** (`static/js/metadata_search.js`):
  - `closeMetadataSearchModal()`을 호출하여 전역 변수가 초기화되기 전, 로컬 상수 `seriesNameToRefresh`에 현재 `currentSeriesName` 값을 복사하여 백업해 둠.
  - 모달 닫기 처리가 완료된 후에도 백업해 둔 로컬 변수를 사용하여 `window.openBookDetail`을 호출하게 함으로써 올바른 시리즈명 파라미터가 렌더러에 주입되도록 수정함.

## 4. 해결 사항
- 모달이 안전하게 초기화 닫히면서도, 상세 페이지 갱신 API로 정확한 시리즈명 문자열이 전송되어 정보가 온전히 복구 및 실시간 리렌더링됨.
