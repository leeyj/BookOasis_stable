---
title: "이미지 폴더(imgdir) 도서 하단 슬라이더 먹통 결함 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-11
tags: [bugfix, viewer, seekbar, imgdir]
---

# 이미지 폴더(imgdir) 도서 하단 슬라이더 먹통 결함 조치

## 1. 버그 내역 및 증상
- 압축 도서(ZIP, CBZ)가 아닌 이미지 폴더 형식(`__folder__.imgdir`)의 도서를 뷰어 페이지 모드로 감상할 때, 하단 오버레이 슬라이드바(SeekBar)를 조작해도 페이지 이동이 전혀 이루어지지 않고 슬라이더 수치 및 화면이 먹통인 현상.

## 2. 원인 분석
- `[viewer.js](file:///c:/project/media_server/static/js/viewer.js)` 에 등록된 슬라이더 `input` 및 `change` 이벤트 핸들러 내부에서, 도서 포맷(`state.currentViewerFormat`) 분기 시 `zip`과 `cbz` 포맷만 하단 슬라이더 핸들러(`comicSliderInput`/`comicSliderChange`)를 호출하도록 하드코딩되어 있었음.
- 이로 인해 이미지 폴더 포맷(`imgdir`)은 조건문에 일치하지 않아 무시되어, 슬라이더 변경 시 이벤트 핸들러가 미작동하는 결함이 발생함.

## 3. 조치 사항
1. **`imgdir` 분기 조건 추가 (`static/js/viewer.js`)**:
   - `input` 및 `change` 이벤트 리스너 내 분기문 조건을 `fmt === 'zip' || fmt === 'cbz'` 에서 **`fmt === 'zip' || fmt === 'cbz' || fmt === 'imgdir'`** 로 확장하여 이미지 폴더 도서에 대해서도 만화책 슬라이더 제어 로직이 완벽히 작동하도록 호환성을 보장함.

## 4. 해결 확인 및 영향도
- 이미지 폴더 도서(`imgdir`) 감상 중에도 하단 슬라이더를 잡고 드래그하거나 특정 페이지로 점프할 시 정상적으로 즉각적인 툴팁 렌더링 및 페이지 갱신이 완수됨.
