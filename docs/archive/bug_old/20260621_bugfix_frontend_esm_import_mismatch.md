---
title: "프론트엔드 ESM 모듈 임포트 미스매치 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bug, javascript, esm, frontend]
---

# 🐛 프론트엔드 ESM 모듈 임포트 미스매치 오류 조치

## 1. 버그 내역 및 증상
- **오류 메시지**: `Uncaught SyntaxError: The requested module './book_context_menu.js' does not provide an export named 'triggerSearchAladinMetadataAction'`
- **증상**: 프론트엔드 진입 파일인 `tab_media_library.js` 초기화 단계에서 ESM 정적 구문 분석 실패(SyntaxError)가 발생하여, 전체 자바스크립트 실행이 중단됨. 이로 인해 사이드바 카테고리 로딩 및 도서 목록 갱신 등 화면 전체의 인터랙션이 불가능한 먹통 상태가 됨.

## 2. 영향도
- **영향 범위**: 모든 사용자 클라이언트 화면 (웹 프론트엔드 전체 마비)
- **우선순위**: 상 (즉각적인 핫픽스 필요)

## 3. 원인 분석
- `book_context_menu.js`에서 메타데이터 검색 관련 함수를 `triggerSearchMetadataAction`으로 명명하여 내보내기(`export`)를 정의함.
- 하위 호환성을 위해 `window.triggerSearchAladinMetadataAction = triggerSearchMetadataAction;`로 글로벌 바인딩만 부여하였으나, `tab_media_library.js` 상단에서는 이 함수를 ESM 구조분해 임포트(`import { triggerSearchAladinMetadataAction }`) 방식으로 명시적 임포트를 수행하려 함.
- ES Modules 환경 규격상 `export` 구문으로 지정되지 않은 대상을 정적으로 가져오려 할 시 컴파일/파싱 단에서 즉시 `SyntaxError`를 유발함.

## 4. 조치 사항
- **수정 소스 파일**: `static/js/book_context_menu.js`
- **조치 내용**:
  `book_context_menu.js` 파일 하단에 전역 바인딩과 매칭되는 ESM 별칭 내보내기 구문을 추가함.
  ```javascript
  export { triggerSearchMetadataAction as triggerSearchAladinMetadataAction };
  ```
  이로 인해 `tab_media_library.js`가 정상적으로 해당 이름을 정적 구조분해하여 가져올 수 있게 되었으며, 전역 바인딩과의 호환성도 고스란히 유지됨.

## 5. 해결 사항 및 검증 결과
- 수정 후 `deploy.py`를 통해 원격 배포 및 재구동을 진행하였고, 브라우저 subagent 검증 도구를 사용해 E2E 확인을 완료함.
- 개발자 도구 콘솔에서 `Uncaught SyntaxError`가 완전히 사라지고 사이드바 카테고리 전환 및 도서 리스트 조회가 정상 복구됨을 확인하였습니다.
