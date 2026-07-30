---
title: Walkthrough - category_click_fix
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 카테고리 클릭 시 도서 목록 미갱신 버그 수정 결과 (Walkthrough)

사이드바 카테고리를 눌렀을 때 도서 리스트가 갱신되지 않던 장애 요인을 분석하고 수정을 정상 완료하였습니다.

## 변경 사항 요약 (Changes)

### 백엔드 서비스 레이어

#### [book_service.py](file:///c:/project/media_server/services/book_service.py)
- `BookService.get_books_list`의 시작 지점에서 파라미터로 넘어온 `library_id`가 `'all'`, `'favorite'` 등이 아니고 정수로 변환 가능할 경우, SQLite 쿼리 매칭 오류가 발생하지 않도록 `int(library_id)` 캐스팅 처리를 내장하여 문제를 해결했습니다.

### 프론트엔드 카테고리 제어부

#### [category.js](file:///c:/project/media_server/static/js/category.js)
- `loadLibraries`의 동적 리스트 결합부 중 `onclick` 핸들러의 호출 파라미터를 `selectCategory('${lib.id}')`로 감싸 문자열 변수 구문 에러 예방 및 타입 안정을 꾀했습니다.

## 검증 결과 (Verification Results)
- 소스 수정 후 `deploy.py`를 실행하여 원격 홈 서버에 배포하고 서버를 재기동하였습니다.
- 직접 생성한 커스텀 카테고리를 클릭했을 때, SQLite의 INTEGER 타입과 정상 결합되어 우측의 도서 리스트가 해당 카테고리에 할당된 고유 데이터로 신속히 교체되는 것을 검증 완료하였습니다.
