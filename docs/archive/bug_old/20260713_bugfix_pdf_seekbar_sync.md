---
title: "PDF 뷰어 하단 시크바 및 페이지 정보 연동 오류 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, viewer, pdf, seekbar, sync]
---

# PDF 뷰어 하단 시크바 및 페이지 정보 연동 오류 수정

## 1. 버그 내역 및 증상
- PDF 도서 파일을 뷰어로 열었을 때, 페이지를 이동하거나 슬라이더를 조작하더라도 하단 진행 상황 슬라이더(시크바) 및 오버레이 지시자의 정보가 `1 / 1` 상태로 고정되어 있고 실제 진행 상태를 동기화하지 못하는 현상.

## 2. 원인 분석
- `static/js/viewer_pdf.js` 내 `renderPdfPage` 수행 후 공통 `updatePageInfo()`를 호출하고 있었으나, 공통 함수는 PDF 상태일 때 오버레이 지시자 텍스트를 단순 복사 복제만 할 뿐 시크바 슬라이더 값(`max`, `value` 등)을 업데이트하는 갱신 연산을 수행하지 않고 early return 처리함.
- 아울러 뷰어 하단의 `#pdf-page-info` 엘리먼트 자체를 갱신해주는 처리가 `viewer_pdf.js` 내에 존재하지 않아 기본값인 `1 / 1`로 동결되는 구조였음.

## 3. 조치 사항
- **PDF 전용 페이지 동기화 헬퍼 함수 구현 및 연동 (`static/js/viewer_pdf.js`)**:
  - `updatePdfPageInfo()` 함수를 새롭게 구현하여 `#pdf-page-info`, `#comic-overlay-page-info` 오버레이 라벨에 현재 PDF 페이지 분량(`pdfCurrentPage / pdfTotalPages`)이 바르게 연사되도록 코드를 주입함.
  - 하단 공용 슬라이더 `#viewer-page-slider` 의 최댓값(`max`)을 `pdfTotalPages`로 조율하고, 핸들러 위치(`value`)를 `pdfCurrentPage`로 자동 설정하도록 연계 갱신 루틴을 추가하고 `#seekbar-end-label`도 정상 주입함.
  - `renderPdfPage` 완료 시점에 호출하여 페이지 전환 및 최초 도서 진입 시 시크바 전체 길이가 자동 정렬되도록 개선함.

## 4. 해결 확인 및 영향도
- 수정 후 한글 PDF 파일 등의 도서를 로드했을 때, 하단 시크바 영역이 전체 20페이지 등으로 알맞게 설정되며 드래그 이동 및 버튼 이동에 반응하여 핸들 위치와 라벨이 정상 동기화 갱신되는 것을 최종 확인 완료함.
