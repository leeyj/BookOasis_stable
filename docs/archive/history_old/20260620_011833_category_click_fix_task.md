---
title: Task - category_click_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 카테고리 클릭 시 도서 목록 미갱신 버그 수정 작업 목록

- [x] 백엔드 `BookService`의 `library_id` 정수 변환 처리
  - [x] `services/book_service.py` 내 `get_books_list` 함수 수정
  - [x] `library_id` 값에 대해 `int()` 캐스팅 방어 코드 적용
- [x] 프론트엔드 `category.js` 카테고리 onclick 파라미터 따옴표 보강
  - [x] `static/js/category.js` 내 `loadLibraries`의 커스텀 리스트 렌더링부 수정
- [x] 버그 수정 내역 문서화 및 수집 자동화
  - [x] `docs/bug/20260620_bugfix_category_click_list_empty.md` 신설
  - [x] `docs/workflow.md` 이력 추가
  - [x] `tools/collect_docs.py`를 통한 문서 전역 동기화
- [x] 배포 및 E2E 최종 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재시작
  - [x] 실제 커스텀 카테고리 클릭 테스트 검증
