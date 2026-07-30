---
title: "Bugfix - 도서 상세 화면 재로딩 시 빈 단행본 목록 참조로 인한 TypeError 크래시 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bugfix, modal, javascript]
---

# 버그 트러블슈팅: 도서 상세 화면 재로딩 시 빈 단행본 목록 참조로 인한 TypeError 조치 (modal.js)

## 1. 버그 내역 및 현상
- **현상**: 특정 상황에서 알라딘 메타데이터를 검색하여 적용(매칭)한 후 도서 상세화면(`openBookDetail`)을 다시 로드할 때, 브라우저 개발자 콘솔에 `TypeError: Cannot read properties of undefined (reading 'id')` 에러가 발생하면서 화면 전체가 먹통이 되는 현상이 발생했습니다.
- **원인**: 
  - 메타데이터 변경 혹은 특정 필터 상황에 따라 시리즈 상세 보기 화면이 다시 렌더링될 때, `books` 배열이 비어 있는(empty array `[]`) 상태로 반환될 수 있습니다.
  - 이때 `modal.js` 파일 내의 `[메타정보 검색]` 버튼 클릭 이벤트 바인딩인 `onclick="openMetadataSearchModal(${books[0].id}, ...)"` 코드에서 빈 배열의 첫 번째 요소인 `books[0]`을 검사 과정 없이 다이렉트로 참조하여 자바스크립트 Null Pointer 예외를 발생시켰습니다.

## 2. 영향도
- **영향 범위**: 프론트엔드 도서 상세화면 렌더러 모듈(`static/js/modal.js`).
- **영향 수준**: 상 (High) - 메타데이터 적용 직후 화면이 정지하여 뒤로가기나 리프레시를 수동으로 해야 하는 불편과 시스템 불안정성을 초래합니다.

## 3. 조치 및 수정사항
- **수정 소스 파일**: [modal.js](file:///c:/project/media_server/static/js/modal.js)
- **수정 내용**:
  1. **단행본 배열 및 ID 안전 가드(Null Guard) 수립**:
     - `openBookDetail` API 응답값 파싱 직후 `const books = data.books || [];`와 같이 기본 빈 배열 할당 처리를 공고히 했습니다.
     - `const firstBookId = books.length > 0 ? books[0].id : null;` 안전장치 변수를 명시적으로 선언하여 단행본 목록이 전혀 없거나 비어있는 경우에도 예외 없이 `null` 상태를 반환하도록 조치했습니다.
  2. **HTML 템플릿 참조 교체**:
     - `modal.js` 내 `onclick="openMetadataSearchModal(${books[0].id}, ...)"`를 `onclick="openMetadataSearchModal(${firstBookId}, ...)"`로 교체하여 에러 발생 원인을 원천 차단했습니다.

## 4. 해결 확인 및 E2E 검증
- 수정한 소스를 원격 미디어 서버(`192.168.0.20:5930`) 무중단 프로세스 환경에 무사히 배포 완료했습니다.
- 메타데이터 적용 후 상세화면을 리로딩하는 시나리오를 교차 검증한 결과, 더이상 개발자 도구에 TypeError 예외가 검출되지 않고 안전하게 로딩 처리가 완료되는 것을 최종 수동 검증했습니다.
