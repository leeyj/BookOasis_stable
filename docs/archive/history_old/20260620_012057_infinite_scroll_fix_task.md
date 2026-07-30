---
title: Task - infinite_scroll_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 도서 목록 무한 스크롤 미동작 버그 수정 작업 목록

- [x] `tab_media_library.js` 내 무한 스크롤 위치 감지 로직 개선
  - [x] `window.pageYOffset`, `document.body` 등을 포함한 크로스 브라우저 호환 계산식 설계
  - [x] 설정('settings') 탭 노출 시 무한 스크롤 방어 필터 적용
- [x] 버그 수정 내역 문서화 및 수집 자동화
  - [x] `docs/bug/20260620_bugfix_infinite_scroll_not_triggered.md` 신설
  - [x] `docs/workflow.md` 이력 추가
  - [x] `tools/collect_docs.py`를 통한 문서 전역 동기화
- [x] 배포 및 E2E 최종 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재시작
  - [x] 하단 스크롤 시 추가 도서가 정상적으로 페이징 렌더링되는지 확인
