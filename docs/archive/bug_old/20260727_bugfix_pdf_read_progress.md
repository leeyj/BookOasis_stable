---
title: PDF 뷰어 진행도 저장 누락 수정
date: 2026-07-27
author: Antigravity
---

# PDF 뷰어 진행도 저장 누락 버그 수정

## 1. 개요
사용자가 PDF 문서를 뷰어로 열고 한두 페이지 정도만 읽은 뒤 바로 뷰어를 닫았을 경우, 해당 도서가 '읽은 도서'에 추가되지 않고 여전히 '안 읽은 도서(0%)'로 표시되는 현상이 발생했습니다.

## 2. 원인 분석
- **현상 파악**: TXT나 코믹 뷰어는 문서를 불러오고 첫 렌더링을 마치는 시점(`renderCurrentChunk` 등)에 `saveProgress` API 호출을 예약(Debounce)합니다. 반면, `viewer_pdf.js`에서는 뷰어를 처음 열고 `renderPdfPage`를 호출할 때 `saveProgress`를 실행하지 않았습니다.
- **영향도**: 사용자가 다음 페이지로 명시적으로 넘기지 않고(Next/Prev 동작 없음) 뷰어를 바로 닫았을 때, 저장될 진행도가 전혀 큐에 쌓이지 않아 뷰어 종료 시(`closeMediaViewer`)에 호출되는 `flushProgress()`가 보낼 데이터가 없는 상태가 됩니다.

## 3. 수정 사항
- **대상 파일**: `static/js/viewer_pdf.js`
- **변경 내용**: `renderPdfPage()` 함수의 마지막 부분(페이지 정보가 UI에 업데이트된 후)에 `saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages)` 호출 로직을 추가했습니다.
- 이를 통해 사용자가 PDF를 열자마자 바로 닫더라도 즉시 진행도(1페이지)가 큐에 쌓여 뷰어 종료 시 서버에 전송되도록 처리했습니다.

## 4. 해결 확인
PDF 문서를 열고 페이지를 넘기지 않은 상태에서 바로 뷰어를 닫았을 때, 도서의 진행률(페이지 위치 0)이 백엔드에 성공적으로 동기화되어 목록에 반영되는 것을 확인했습니다.
