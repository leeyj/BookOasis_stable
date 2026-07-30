---
title: Task - metadata_series_apply_id_mismatch
project: BookOasis
category: history
date: 2026-06-29
type: task
---
# 작업 목록 (Task List)

- [x] `static/js/metadata_search.js` 수정
    - [x] `copyFormData` 전송 시 `target_library_id` 값으로 `targetBook.library_id`를 추출해 실제 정수 ID로 전송하도록 수정
- [x] 수동 검증 수행
    - [x] 대시보드 진입 테스트를 통한 메타 정상 전파 검증
- [x] 버그/개선 내역 문서 작성
    - [x] `docs/bug/20260629_bugfix_metadata_series_apply_id_mismatch.md` 작성
    - [x] 수집기 실행
- [x] `walkthrough.md` 작성
