---
title: Task - image_load_infinite_loop_and_scroll_lag_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 이미지 로드 에러 무한 루프 및 스크롤 끊김 수정 작업 목록

- [x] `static/js/ui.js` 이미지 onerror 추가
  - [x] `createBookCard` 내 `<img>` 태그에 `onerror="this.onerror=null; this.src='...';"` 삽입
- [x] `static/js/modal.js` 이미지 onerror 무한 루프 차단
  - [x] `detail-cover-sm` 이미지에 `this.onerror=null;` 삽입
  - [x] `volume-thumb` 이미지에 `this.onerror=null;` 삽입
- [x] 배포 및 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재구동
- [x] 버그 수정 이력 문서화 및 전역 동기화
  - [x] `docs/bug/20260620_bugfix_image_load_infinite_loop.md` 신설
  - [x] `docs/workflow.md` 이력 업데이트
  - [x] `walkthrough.md` 결과 문서 작성
  - [x] `tools/collect_docs.py` 실행
