---
title: Task - infinite_scroll_deadlock_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 무한 스크롤 중복 락 해제 작업 목록

- [x] `tab_media_library.js` 내 스크롤 이벤트 리스너 수정
  - [x] 외부 `state.isLoading = true` 중복 락 설정 코드 제거
- [x] 버그 수정 내역 문서화 및 수집 자동화
  - [x] `docs/bug/20260620_bugfix_infinite_scroll_deadlock.md` 신설
  - [x] `docs/workflow.md` 이력 추가
  - [x] `tools/collect_docs.py`를 통한 문서 전역 동기화
- [x] 배포 및 E2E 최종 검증
  - [x] `python deploy.py` 실행을 통한 홈 서버 원격 배포 및 재시작
  - [x] F12 콘솔에서 무한 스크롤 호출과 추가 도서 렌더링 검증
