---
title: "PDF 뷰어 로드 실패 및 한글 CMap 폰트 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, viewer, pdf, font, cmap]
---

# PDF 뷰어 로드 실패 및 한글 CMap 폰트 오류 수정

## 1. 버그 내역 및 증상
- 특정 PDF 도서 파일 열람 시 뷰어가 기동되지 않고 `PDF 로드 실패 - updatePageInfo is not defined` 빨간색 에러 모달이 노출되는 현상.
- 한글 등 동아시아 폰트 인코딩이 적용된 PDF 파일 로드 시, 브라우저 콘솔에 `translateFont failed: "UnknownErrorException: CMapReaderFactory not initialized"` 경고가 발생하는 현상.

## 2. 원인 분석
- **`updatePageInfo` 미정의 (ReferenceError)**:
  - `static/js/viewer_pdf.js`에서 페이지 갱신용 `updatePageInfo()`를 호출하지만, 모듈 상단에 해당 함수의 import 구문이 누락되어 있어 실행이 차단됨.
- **CMap 폰트 누락**:
  - `pdfjsLib.getDocument()`로 PDF를 로드할 때 한글 폰트 매핑을 복구하기 위한 `cMapUrl` 및 `cMapPacked` 옵션이 설정되어 있지 않아 동아시아 문자셋 파싱 과정에서 경고가 표출되고 글자가 깨지거나 일부 미출력되는 문제가 발생함.
  - cdnjs CDN 경로 사용 시 교차 출처 리소스 공유(CORS) 정책에 의해 CMap 요청이 거부(`No 'Access-Control-Allow-Origin' header`)되는 추가 부작용이 발견되어, CORS 허용 범위가 넓은 jsDelivr CDN 주소로 매핑함.

## 3. 조치 사항
- **PDF 통합 뷰어 모듈 교정 (`static/js/viewer_pdf.js`)**:
  - 모듈 상단에 `import { updatePageInfo } from './viewer/renderer.js';`를 명시적으로 추가하여 ReferenceError 예외 발생을 차단함.
  - `pdfjsLib.getDocument()` 속성에 CORS를 광범위하게 허용하는 jsDelivr 기반의 CMap URL 주소(`cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@2.16.105/cmaps/'`)와 CMap 압축 파일 로딩 설정(`cMapPacked: true`)을 연동 주입함.

## 4. 해결 확인 및 영향도
- 조치 후 기존에 열리지 않던 한글 PDF 및 특수 폰트 위주의 PDF 파일을 대상으로 정상 구동됨을 수차례 확인했으며, 콘솔에 CMap 관련 CORS 차단 경고 및 글자 누락 없이 완벽히 렌더링되는 것을 최종 검증함.
