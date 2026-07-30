---
title: "PDF 뷰어 하단 슬라이더 핸들러 누락 먹통 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, pdf, seekbar]
---

# PDF 뷰어 하단 슬라이더 핸들러 누락 먹통 결함 조치

## 1. 버그 내역 및 증상
- PDF 도서를 뷰어로 감상할 때, 하단 오버레이 슬라이더바(SeekBar)를 조작해도 페이지 이동이 전혀 작동하지 않고 콘솔에 `[Viewer-Core] pdfSliderChange not available` 경고만 뿜으며 먹통인 현상.

## 2. 원인 분석
- `[viewer.js](file:///c:/project/media_server/static/js/viewer.js)` 의 슬라이더 `change` 이벤트 핸들러에서는 `pdf` 포맷에 대해 `viewer_pdf.js` 의 `pdfSliderChange` 를 가져와 호출하도록 설계되어 있었으나, 실제 `[viewer_pdf.js](file:///c:/project/media_server/static/js/viewer_pdf.js)` 모듈 내부에는 이 핸들러가 누락된 채 정의되어 있지 않았음.

## 3. 조치 사항
1. **`pdfSliderChange` 핸들러 정의 구현 (`static/js/viewer_pdf.js`)**:
   - `viewer_pdf.js` 내부에 `pdfSliderChange(slider, val)` 함수를 새롭게 설계 및 추가하여, 사용자가 슬라이더 조작 시 툴팁을 숨기고 기존 `pdfJumpToPage(val)` 내부로 자연스럽게 이동을 위임하도록 조치함.

## 4. 해결 확인 및 영향도
- PDF 도서 감상 시에도 하단 슬라이더바를 잡고 챕터나 임의의 페이지로 드래그하면, 툴팁 연동 및 손을 떼는 시점에 타겟 PDF 페이지로 무리 없이 즉시 전환 렌더링이 이루어짐.
