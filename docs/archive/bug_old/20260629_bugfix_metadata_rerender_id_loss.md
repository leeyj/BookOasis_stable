---
title: "메타데이터 적용 완료 후 상세 화면 리렌더링 시 라이브러리 ID 유실 오류 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [metadata, rerender, library_id, undefined, bugfix]
---

# 🐛 메타데이터 적용 완료 후 상세 화면 리렌더링 시 라이브러리 ID 유실 오류 수정

## 1. 버그/개선 내역
- **현상**: 상세 페이지에서 수동으로 메타데이터를 일괄 적용한 후 모달이 닫히며 즉시 반영되어야 하나, 여전히 책 설명 및 표지가 날아가며 단행본 목록마저 `0권`으로 텅 비어 보임.
- **원인**:
  - `selectMetadataBook` 완료 콜백 내에서 `window.openBookDetail` 함수를 재호출할 때, 리렌더링 대상 라이브러리 ID(`activeLibId`)를 브라우저의 `history.state.libraryId`로부터 추출해 내도록 구현되어 있었음.
  - 하지만 메타 검색 팝업 조작 과정이나 해시(`#detail`) 중복 진입 시 `history.state` 상태 정보가 초기화되거나 유실되어 `libraryId`가 `undefined`로 평가됨.
  - 이로 인해 프론트엔드가 `/api/media/detail`을 요청할 때 `library_id=undefined` 문자열을 보내게 되고, 백엔드에서는 이를 적합하지 않은 유효값으로 취급하여 매칭 레코드를 찾지 못해 빈(empty) 정보와 0권의 단행본 데이터를 반환함으로써 빈 화면이 그려지는 현상이 발생함.

## 2. 영향 범위
- 메타데이터 적용 완료 콜백 함수 (`static/js/metadata_search.js`)

## 3. 수정 사항
- **JS 스크립트 수정** (`static/js/metadata_search.js`):
  - 메타데이터 일괄 적용 완료 후 상세 페이지 렌더러를 리로드할 때, 브라우저 History API의 불확실한 `history.state.libraryId`를 더 이상 신뢰하지 않고, 방금 직접 백엔드 조회를 성공적으로 끝마친 `targetBook.library_id` (실제 정수 ID) 데이터를 직접 넘겨주도록 변경하여 값 꼬임 현상을 제거함.

## 4. 해결 사항
- 적용 프로세스가 끝난 직후, 실제 소속 라이브러리 정수 ID를 기반으로 시리즈 상세 API가 즉각 정상 재호출됨.
- 메타데이터 정보가 한 권도 유실되지 않고 100% 실시간으로 상세 페이지와 표지 썸네일에 노출되도록 조치됨.
