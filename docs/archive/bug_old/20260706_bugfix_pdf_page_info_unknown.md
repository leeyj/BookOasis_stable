---
title: "PDF 뷰어 로드 시 페이지 번호가 물음표(?)로 뜨는 현상 수정"
date: "2026-07-06"
type: "bugfix"
status: "completed"
tags: ["viewer", "pdf", "page-count"]
---

# PDF 뷰어 로드 시 페이지 번호가 물음표(?)로 뜨는 현상 수정

## 1. 개요 및 증상
- **현상**: PDF 뷰어를 열었을 때, 페이지 레이블 및 오버레이 메뉴에 총 페이지 수가 정확한 숫자가 아닌 `?` (물음표)로 표시되는 현상이 발생했습니다. (예: `1 / ?`)

## 2. 원인 분석
- 뷰어 공용 페이지 정보를 업데이트하는 `viewer/renderer.js` 내의 **`updatePageInfo()`** 함수에서, `epub` 포맷에 대한 조기 탈출(early return) 분기는 있었으나 **`pdf` 포맷에 대한 분기 처리가 누락**되어 있었습니다.
- 이로 인해 PDF 도서 로드 시에도 만화책 전용 로직을 그대로 거치게 되었고, 만화책 전체 페이지 변수(`comicTotalPages`)가 존재하지 않아 `comicTotalPages || '?'` 구문에 의해 강제로 `?` 가 할당되어 공용 오버레이가 덮어씌워졌습니다.

## 3. 해결 방안
- [viewer/renderer.js](file:///c:/project/media_server/static/js/viewer/renderer.js): `updatePageInfo()`의 상단 포맷 스위칭 블록에 `pdf` 조건 검사를 추가했습니다.
- PDF 뷰어 구동 상태인 경우, `viewer_pdf.js`에서 세팅한 순정 `#pdf-page-info` 엘리먼트 텍스트 값을 추출해 공용 오버레이에 안전하게 복사하고 즉각 반환(return)되도록 수정하여 오버레이 덮어쓰기 오작동을 근본적으로 차단했습니다.

## 4. E2E 검증 결과
- PDF 도서 뷰어 진입 시, 상단 타이틀바와 하단 시크바 영역 및 현재 페이지 카운트가 `?` 없이 `X / Y` (예: `3 / 48`) 형태로 명확하게 싱크되어 표시됨을 E2E 검증 확인했습니다.
