---
title: Task - scanner_timeout
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] 도서 스캔 엔진 (`tools/scanner/core.py`) 대량 파일 최적화 보완
  - [x] 누적 처리 도서 수 카운터 기반 주기적 청크 커밋 (30권 기준) 도입
  - [x] 누적 처리 도서 수 기반 가비지 컬렉터 (50권 기준) 강제 호출 추가
- [x] 버그 리포트 및 문서 갱신
  - [x] `docs/bug/20260628_bugfix_scanner_timeout.md` 내용 보강
  - [x] `walkthrough.md` 갱신
  - [x] `collect_docs.py` 최종 재실행
