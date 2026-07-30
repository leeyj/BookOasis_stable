---
title: Task - localize_default_cover_image
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 기본 도서 표지 로컬 이미지 전환 작업 목록

- [x] 로컬 디렉터리 생성 및 기본 이미지 파일 다운로드
  - [x] `static/images/` 생성 및 `default_cover.jpg` 다운로드 진행
- [x] 프론트엔드 정적 경로 전환 수정
  - [x] `static/js/ui.js` 내 Unsplash CDN 경로를 `/static/images/default_cover.jpg`로 수정
  - [x] `static/js/modal.js` 내 Unsplash CDN 경로를 `/static/images/default_cover.jpg`로 수정
- [x] 배포 및 최종 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재구동
- [x] 작업 이력 문서 정리 및 전역 동기화
  - [x] `docs/bug/20260620_bugfix_localize_default_cover_image.md` 신설
  - [x] `docs/workflow.md` 이력 추가
  - [x] `walkthrough.md` 결과 문서 작성
  - [x] `tools/collect_docs.py` 실행
