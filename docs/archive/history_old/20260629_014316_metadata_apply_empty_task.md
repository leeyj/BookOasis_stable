---
title: Task - metadata_apply_empty
project: BookOasis
category: history
date: 2026-06-29
type: task
---
# 작업 목록 (Task List)

- [x] `static/js/metadata_search.js` 수정
    - [x] `firstBook` 대신 `currentTargetBookId` 기준 도서 매핑으로 타겟북 탐색 수정
    - [x] 시리즈 텍스트 전파를 보장하기 위해 `api.copyMetadata` 전송 흐름의 비동기 실행 및 검사 수정
- [x] 수동 검증 수행
    - [x] 테스트 및 브라우저 E2E 작동성 검증
- [x] 버그/개선 내역 문서 작성
    - [x] `docs/bug/20260629_bugfix_metadata_apply_empty.md` 작성
    - [x] 수집기 실행
- [x] `walkthrough.md` 작성
