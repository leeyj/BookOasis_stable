---
title: "Bugfix - 시리즈 이름 부재 시 도서 상세 화면 진입 실패 및 스크립트 충돌 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-21
tags: [bugfix, modal, javascript]
---

# 버그 트러블슈팅: 시리즈 이름 부재 시 도서 상세 화면 진입 실패 조치 (modal.js)

## 1. 버그 내역 및 현상
- **현상**: 특정 도서 카드를 클릭하거나 popstate 이벤트로 상세 보기(`openBookDetail`) 진입 시, 콘솔에 `TypeError: Cannot read properties of null (reading 'replace')` 에러가 기록되며 로딩 표시에서 화면이 멈추는 현상이 식별되었습니다.
- **원인**: 개별 도서 정보에 `seriesName`이 부재하여 `null` 혹은 `undefined`인 상태로 `openBookDetail` 함수에 유입되었습니다. 해당 함수 내부에서 `seriesName.replace(/'/g, "\\'")`를 직접 호출함에 따라 자바스크립트 Null Pointer 예외가 터지게 되었습니다.

## 2. 영향도
- **영향 범위**: 프론트엔드 모듈화 화면(`static/js/modal.js`).
- **영향 수준**: 상 (High) - 시리즈명이 비어 있는 도서를 열거나 브라우저 뒤로가기 탐색 시 도서 상세 창이 무한 로딩 상태에 빠져 먹통이 되는 치명적인 UX 장애를 유발합니다.

## 3. 조치 및 수정사항
- **수정 소스 파일**: [modal.js](file:///c:/project/media_server/static/js/modal.js)
- **수정 내용**:
  1. `openBookDetail` 함수의 진입 시점에 `const safeSeriesName = seriesName || '';` 변수를 정의하여, `seriesName` 파라미터가 유입되지 않거나 null인 경우에도 빈 문자열로 안전하게 치환하여 후속 처리를 진행하게 하였습니다.
  2. 도서 상세 템플릿(HTML innerHTML) 렌더링 시 사용되는 모든 `${seriesName}` 및 `'${seriesName.replace(...)}'` 코드를 `${safeSeriesName}` 및 `'${safeSeriesName.replace(...)}'`로 일괄 리팩토링하였습니다.
  3. 개별 단행본 파일 리스트를 돌 때도 `b.title`이 없을 경우에 대비해 `b.title || ''` 및 `(b.title || '').replace(...)` 처리를 추가하여 원천적으로 렌더링 터짐 현상을 예방했습니다.

## 4. 해결 확인 및 E2E 검증
- 컴파일 점검(`python -m py_compile`)을 마친 후 `python deploy.py`를 실행하여 운영 서버에 배포 완료하였습니다.
- 시리즈명이 누락된 도서를 클릭하거나 뒤로가기 탐색 시 더이상 예외가 발생하지 않고 상세 뷰어가 부드럽게 복구되는 것을 E2E 수동 교차 검증을 통해 확인하였습니다.
