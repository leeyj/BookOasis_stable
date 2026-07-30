---
title: "도서 리스트 그리드와 상세 정보 대표 썸네일 이미지 불일치 수정"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [cover-image, get-books-list, SQL, SQLite]
---

# 🧠 도서 리스트 그리드와 상세 정보 대표 썸네일 이미지 불일치 수정

## 1. 개요 및 버그 내용
- **현상**: 메인 보관함 리스트 화면의 책 카드 썸네일 이미지와 책을 클릭하여 진입한 상세 페이지 상단의 대표 썸네일 이미지가 서로 다르게 노출되는 현상 발생.
- **영향**: 사용자에게 썸네일 이미지가 깨져 보이거나 다른 작품처럼 혼동을 유발하는 UX 저하 원인 제공.

## 2. 원인 분석
- **상세 뷰**: [`static/js/modal.js`](file:///c:/project/media_server/static/js/modal.js)에서 해당 시리즈의 전체 단행본 중 **제목 오름차순(사전 순)** 정렬 기준 첫 번째로 표지가 존재하는 책(예: 1권)의 이미지를 대표 표지(`representativeBook.cover_image`)로 바인딩함.
- **리스트 뷰**: [`services/book_service.py`](file:///c:/project/media_server/services/book_service.py)의 `get_books_list` SQL 쿼리들 내에서 단순히 `MAX(cover_image) AS cover_image`를 집계하고 있었음. SQLite의 `MAX`는 문자열 비교에 기반하여 파일명 알파벳 순서가 가장 뒷번호인 임의의 권 표지를 가져오게 되어 불일치 유발.

## 3. 조치 내용
- **[`book_service.py`](file:///c:/project/media_server/services/book_service.py)** 수정:
  - `get_books_list` 함수 내부 쿼리들(총 6개 분기)에서 `MAX(cover_image)` 집계 컬럼을 다음과 같이 동일한 시리즈 내의 첫 번째 권(제목 오름차순) 표지 이미지명을 안전하게 조회하는 서브쿼리로 수정.
  - 서브쿼리 적용 구조:
    ```sql
    (SELECT b2.cover_image 
     FROM books b2 
     WHERE b2.series_name = b.series_name AND b2.cover_image IS NOT NULL AND b2.cover_image != '' 
     ORDER BY b2.title ASC LIMIT 1) AS cover_image
    ```
  - 바깥 테이블에 `books b` 별칭을 지정하여 서브쿼리 내 모호함을 완벽히 제거.

## 4. 결과 및 검증
- 수정 적용 후 원격 홈 서버에 배포 완료.
- 리스트 화면에서 보이는 시리즈별 대표 표지가 상세 페이지를 클릭했을 때 보이는 1권 표지와 정확하게 1:1 매칭되는 것을 정상 검증 완료.
