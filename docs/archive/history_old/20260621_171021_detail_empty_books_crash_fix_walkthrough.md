---
title: Walkthrough - detail_empty_books_crash_fix
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 워크쓰루: 도서 상세화면 로딩 시 빈 단행본 목록 참조 TypeError 크래시 조치

도서 상세 정보를 로딩(`openBookDetail`)하여 그리는 중에, 일시적인 도서 정보 공백이나 목록 필터링 상태로 인해 `books` 배열이 비어있을 경우 발생하던 `TypeError: Cannot read properties of undefined (reading 'id')` 예외를 방어 코드로 해결 완료했습니다.

## 변경 내용

### 프론트엔드 모달 렌더링 안정성 제고
- **[MODIFY] [modal.js](file:///c:/project/media_server/static/js/modal.js)**:
  - `openBookDetail` 함수 내부에서 도서 상세 API로부터 가져온 `data.books`를 `const books = data.books || [];`와 같이 기본 빈 배열로 안전하게 할당했습니다.
  - `const firstBookId = books.length > 0 ? books[0].id : null;` 변수를 선언하여, 도서가 하나도 없을 때는 `firstBookId` 값이 안전하게 `null`이 되도록 널 가드를 구현했습니다.
  - HTML을 그리는 템플릿 코드 내부에서 `books[0].id`를 직접 조회하던 부분을 `firstBookId` 변수로 교체했습니다. 이로써 `books`가 비어있어도 예외 발생 없이 무사히 렌더링이 완료됩니다.

## E2E 및 수동 검증 결과
1. **서버 배포 및 재시작**:
   - `python deploy.py`를 실행하여 수정된 `modal.js` 코드를 원격 홈 서버(`192.168.0.20`)로 무사히 전송하고, 단독 재기동 프로세스를 정상 완료하였습니다.
2. **수동 검증 시나리오 완수**:
   - 도서 상세 보기 화면 진입 ➔ 단행본의 메타데이터를 알라딘 검색 결과를 이용해 적용 완료.
   - 적용 직후 비동기로 상세 보기 화면을 갱신 및 재조회할 때, 자바스크립트 TypeError 예외가 개발자 콘솔에 노출되지 않고 안전하게 로딩 및 리렌더링이 정상 완료되는 것을 확인했습니다.
