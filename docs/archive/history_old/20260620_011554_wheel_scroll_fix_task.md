---
title: Task - wheel_scroll_fix
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 휠 스크롤 및 페이지 전환 제어 버그 수정 작업 목록

- [x] `viewer.js`에 마우스 휠 이벤트 리스너 연동 설계
  - [x] `common-viewer-hotspot` 요소 가져오기
  - [x] 휠 이벤트 캡처 및 이벤트 전파 제어 (`preventDefault` 및 뷰어 컨테이너 전파)
  - [x] 스크롤 방식 및 모드 식별 로직 작성
- [x] 페이지 전환 모드 휠 쓰로틀링(Throttling) 로직 구현
  - [x] 휠 방향에 따른 `prevPage()`, `nextPage()` 호출
  - [x] 600ms Throttling 타임 락 변수 적용
- [x] 세로 스크롤 모드 스크롤 연동 구현
  - [x] TXT, PDF, EPUB, Comic(너비 맞춤) 각 컨테이너별 타겟 스크롤 요소 정의
  - [x] 휠 `deltaY` 값을 타겟 스크롤 요소에 직접 `scrollBy`로 전달
- [x] 버그 수정 이력 문서화 및 등록
  - [x] `docs/bug/20260620_bugfix_viewer_wheel_scroll.md` 신설
  - [x] `docs/workflow.md`에 이력 기록 추가
  - [x] `tools/collect_docs.py` 스크립트를 통한 전역 동기화
