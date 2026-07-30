---
title: "스캔 중 0페이지 만화책 로드 오류 및 우클릭 컨텍스트 메뉴 미동작 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-29
tags: [bug, viewer, fallback, context-menu]
---

# 🧠 [Bugfix] 스캔 중 만화책 0페이지 노출 오류 및 단행본 목록 우클릭 컨텍스트 메뉴 미동작 수정

## 1. 버그 개요 (Issue Overview)
- **발생 환경**: 스캔 작업 중 미완성 도서(total_pages가 0인 상태) 진입 시 및 상세 페이지 내 단행본 카드 우클릭 시
- **장애 현상**:
  1. 스캔 도중 추가되어 데이터베이스 내 `total_pages`가 아직 `0`으로 기입된 도서를 열람 시 뷰어가 빈 화면으로 노출되거나 렌더링 에러가 발생하는 현상.
  2. 도서 상세 페이지의 단행본 카드에서 마우스 우클릭을 클릭해도 단일 스캔 및 메타정보 검색 메뉴가 나타나지 않는 현상.

---

## 2. 영향도 분석 (Impact Analysis)
- 스캔 도중 신규 발견된 만화책을 즉시 읽으려는 사용자의 읽기 동작이 전면 블로킹됩니다.
- 단행본을 단독으로 재스캔하거나 메타데이터를 개별 매핑할 때, 마우스 오른쪽 클릭 컨텍스트 메뉴가 아예 동작하지 않아 편의 기능 접근이 제한됩니다.

---

## 3. 원인 파악 (Root Cause)
- **0페이지 버그**: 신규 도서 감지 시 `insert_new_book_v2`를 통해 DB에 선인서트된 후 오프셋 계산이 끝나기 전까지 혹은 트랜잭션이 커밋되어 디스크에 완전히 반영되기 전까지 `total_pages`가 `0`으로 응답되어 클라이언트 뷰어에 인자가 전달되기 때문입니다.
- **우클릭 메뉴 미동작**: 
  1. `book_context_menu.js`에 정의된 `showBookContextMenu` 함수가 전역 `window` 객체에 바인딩되어 있지 않아, 인라인 `oncontextmenu` 태그가 호출을 시도할 때 `undefined`로 호출에 실패했습니다.
  2. `detail_render.js` 내 인라인 호출문 마지막 매개변수에 `' true'` 형태로 공백 문자가 들어가 문법적인 결함이 있었습니다.

---

## 4. 조치 사항 및 수정 파일 (Resolution & Code Changes)

### [MODIFY] [book_detail_service.py](file:///c:/project/media_server/services/book_detail_service.py#L123-L135)
- 책 상세 조회 시 `total_pages`가 `0`인 책이 있고 해당 파일이 실제로 물리적으로 존재한다면, 백엔드에서 실시간으로 Zip/CBZ 내부의 파일들을 하이브리드 검사하여 실제 이미지 총 개수를 복구해주는 Fallback 방어 코드를 적용했습니다.

### [MODIFY] [book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js#L95-L98)
- `showBookContextMenu`를 전역 `window` 객체에 명시적으로 노출하여 외부 HTML DOM 인라인 태그가 언제든지 호출할 수 있도록 해결했습니다.

### [MODIFY] [detail_render.js](file:///c:/project/media_server/static/js/detail_render.js#L170)
- 우클릭 핸들러 내 `showBookContextMenu`를 호출하는 식에서 마지막 인수로 들어가 있던 공백이 포함된 `' true'`를 올바른 boolean 타입인 `true`로 수정했습니다.

---

## 5. 최종 검증 (Verification)
- DB의 `total_pages`가 `0`인 신규 도서 상태를 가상으로 배치한 후 상세 화면 조회 시 실시간 파일 카운트를 거쳐 정상적인 총 페이지 수로 자동 보완되는지 검증하고, 뷰어가 빈 화면 오류 없이 잘 열리는 것을 확인했습니다.
- 단행본 카드 우클릭 시 컨텍스트 메뉴 레이어가 정상 위치에 즉시 뜨며, 개별 도서 스캔 및 메타데이터 모달 호출이 정상 기동되는 것을 최종 수동 검증하였습니다.
