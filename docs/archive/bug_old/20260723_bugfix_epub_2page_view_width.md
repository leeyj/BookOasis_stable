---
title: "EPUB/TXT 페이지 2장 보기 모드 가로폭 확장 및 시원한 펼침 보기 적용"
category: "bugfix"
date: 2026-07-23
severity: "low"
affected_files:
  - "static/js/viewer/txt_settings_apply.js"
  - "static/js/viewer/viewer_padding.js"
tags: [epub, viewer, 2page-view, max-width, UI]
---

# 버그 내역

## 증상

EPUB 및 TXT 뷰어에서 페이지 보기 모드 중 '2장 보기(2열)'를 선택했을 때, 가로폭 제한이 1장 보기용으로 축소되어 양쪽 펼침 본문이 답답하게 좁아 보이던 현상.

## 근본 원인 분석

- `txt_settings_apply.js` 및 `viewer_padding.js`에서 2장 보기일 때 `maxWidth` 최대 허용치가 충분히 확보되지 않았거나, 1장 보기용 동적 너비 계산이 상위 래퍼에 공통 적용되었음.

---

## 수정 사항

1. **`static/js/viewer/txt_settings_apply.js`**:
   - `pageStep === '2'` (2장 보기) 모드 시 `scrollWrapper`의 `maxWidth` 제한을 **`1600px`**(`Math.min(targetWidth, 1600)`)로 확장하여 대형 화면에서 양쪽 책장이 시원하게 펼쳐지도록 수정.
2. **`static/js/viewer/viewer_padding.js`**:
   - 여백 조절판 적용 시에도 `pageStep` 모드를 탐지하여 1장 보기(`800px`), 2장 보기(`1600px`) 너비를 동기화하고 중앙 정렬 적용.

---

## 해결 결과

- EPUB/TXT 2장 보기 이용 시 책을 크게 펼쳐 읽듯이 양쪽 페이지가 시원하게 너비를 확보하여 최상의 독서 가독성을 제공함.
