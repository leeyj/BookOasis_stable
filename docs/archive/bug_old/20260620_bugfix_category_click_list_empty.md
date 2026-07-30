---
title: "카테고리 클릭 시 도서 목록 미갱신 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, sidebar, sqlite-affinity]
---

# 🐛 카테고리 클릭 시 도서 목록 미갱신 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 사이드바에서 커스텀 카테고리(예: 사용자가 생성한 책장)를 마우스로 클릭해도 우측 목록 영역에 도서 데이터가 표시되지 않거나 갱신이 되지 않는 먹통 버그 발생.

## 2. 원인 분석 (Root Cause Analysis)
- **프론트엔드**: `static/js/category.js`에서 사이드바 카테고리 템플릿 스트링을 동적으로 결합할 때, `onclick="selectCategory(${lib.id})"` 형태로 자바스크립트의 따옴표 처리가 누락되어 문자열 전달 에러 혹은 구문 에러를 유발할 우려가 있었음.
- **백엔드**: 프론트엔드에서 수신받은 `library_id` 파라미터가 `"1"` 같은 문자열 형태인 상태로 SQLite 쿼리에 직접 매핑됨. SQLite는 엄격하게 데이터 타입을 식별하여 `books` 테이블의 정수(INTEGER) 컬럼인 `library_id`와 문자열 `"1"`을 불일치로 감지해 빈 목록이 조회됨.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**:
  1. [category.js](file:///c:/project/media_server/static/js/category.js): 동적 렌더링 시 `onclick="selectCategory('${lib.id}')"` 로 따옴표 설정을 완료하여 변수 전달을 안정화함.
  2. [book_service.py](file:///c:/project/media_server/services/book_service.py): `BookService.get_books_list`의 초입 부분에서 수신받은 `library_id`가 숫자로 변환될 수 있는 값일 경우, 강제적으로 정수(`int`)로 캐스팅하는 방어 코드를 내장시켜 데이터 타입 불일치를 원천 방지함.

## 4. 결과 검증 (Verification Results)
- 코드를 적용한 뒤 홈 서버에 원격 배포하여 재시작한 후, 사이드바에서 커스텀 카테고리를 클릭하였을 때 해당 카테고리에 할당된 도서 목록이 즉시 안정적으로 조회됨을 확인 완료함.
