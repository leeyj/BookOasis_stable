---
title: "시리즈 상세 뷰 내 메타데이터 검색 시 라이브러리 ID 불일치로 인한 전파 실패 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-29
tags: [metadata, copy_metadata, library_id, mismatch, bugfix]
---

# 🐛 시리즈 상세 뷰 내 메타데이터 검색 시 라이브러리 ID 불일치로 인한 전파 실패 조치

## 1. 버그/개선 내역
- **현상**: 대시보드(Home) 화면에서 시리즈 도서 카드의 상세 페이지로 진입하여 "메타정보 검색"을 수행하고 "적용"을 눌렀을 때, 책 설명 및 표지 이미지가 화면에 즉시 적용되지 않고 그대로 빈칸으로 노출되는 현상이 유지됨.
- **원인**:
  - 대시보드에서 상세 뷰를 오픈한 경우 `state.currentLibraryId`의 상태값이 실존하는 정수형 라이브러리 ID(예: `1`, `2` 등)가 아닌 시스템 예약어 문자열인 `'home'`으로 지정됨.
  - 이 값이 `metadata_search.js` 내의 `api.copyMetadata` 전송 데이터(`target_library_id`)로 그대로 들어가며 백엔드로 날아감.
  - 백엔드 데이터베이스 갱신 시 `WHERE series_name = ? AND library_id = ?` 쿼리문 내 `library_id` 바인딩 인자에 정수가 아닌 `'home'` 문자열이 지정됨에 따라 갱신 대상 레코드가 0건 매칭되어 전체 전파 처리가 무산됨.

## 2. 영향 범위
- 메타데이터 일괄 복사 전사 스크립트 (`static/js/metadata_search.js`)

## 3. 수정 사항
- **JS 스크립트 수정** (`static/js/metadata_search.js`):
  - 메타데이터 복사 전송 객체(`copyFormData`) 생성 시, `target_library_id` 파라미터 값으로 `state.currentLibraryId`를 직송하던 부분을 수정함.
  - 상세 데이터 갱신 결과인 `targetBook` 객체의 `library_id` 속성을 동적으로 탐색하여 실제 물리적인 라이브러리 정수 ID(`targetBook.library_id`)가 파라미터로 할당되도록 예외 처리를 보강함.

## 4. 해결 사항
- 대시보드 등의 특수 경로('home', 'all', 'favorite' 등)에서 상세 페이지에 진입하여 메타데이터를 수동으로 갱신하더라도, 해당 책이 속한 실제 라이브러리를 동적으로 파악해 내어 시리즈 내 모든 볼륨으로 메타데이터 텍스트가 빈틈없이 복사 전파됨.
- E2E 갱신이 원활해짐에 따라 메타 정보 적용 완료 즉시 상세 페이지의 썸네일과 설명 텍스트가 정상 서빙됨.
