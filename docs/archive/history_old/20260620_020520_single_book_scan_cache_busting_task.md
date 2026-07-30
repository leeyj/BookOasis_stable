---
title: Task - single_book_scan_cache_busting
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 중복 export 구문 오류 수정 작업 목록

- [x] `tab_media_library.js` 중복 export 구문 수정
  - [x] 파일 최하단의 중복 `initInfiniteScrollObserver` 내보내기 제거
- [x] 버그 수정 및 개선 내역 문서화
  - [x] `docs/bug/20260620_bugfix_duplicate_export_syntax_error.md` 신설
  - [x] `docs/workflow.md` 이력 추가
  - [x] `tools/collect_docs.py`를 통한 문서 전역 동기화
- [x] 배포 및 최종 E2E 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재시작
  - [x] F12 콘솔의 SyntaxError 해소 여부 확인 및 무한 스크롤 연동 동작 재확인
