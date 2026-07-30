---
title: Task - frontend_cover_pollution
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 모달창 화면 이탈 및 고정 스크롤 버그 조치 작업 목록

- [x] `static/js/tab_media_library.js` 수정
  - [x] DOMContentLoaded 이벤트 내 모든 `.library-modal` 돔 엘리먼트를 body 최하단으로 강제 이동(Append)하도록 보완
- [x] 검증 및 버그 정리 문서 작성
  - [x] `docs/bug/20260620_bugfix_modal_viewport_scroll_offset_fix.md` 작성
  - [x] `docs/workflow.md` 업데이트 및 `tools/collect_docs.py` 전역 연동
