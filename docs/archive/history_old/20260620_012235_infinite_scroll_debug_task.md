---
title: Task - infinite_scroll_debug
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 무한 스크롤 디버깅 로그 추가 작업 목록

- [x] `tab_media_library.js` 내 무한 스크롤 디버깅 로그 추가
  - [x] 스크롤 높이(`scrollTop`), 화면 높이(`clientHeight`), 전체 문서 높이(`scrollHeight`) 로깅 추가
  - [x] API 락 플래그(`isLoading`, `hasMore`) 출력 추가
- [x] 배포 및 E2E 모니터링
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재시작
  - [x] F12 개발자 도구 콘솔 로그 관측 결과 수집
