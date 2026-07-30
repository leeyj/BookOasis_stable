---
title: Task - scanner_book_movement_records_preservation
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 도서 이동/이름 변경 시 독서 기록 보존 작업 목록

- [x] `tools/scanner.py` 수정
  - [x] `scan_library` 내 파일 매칭을 통한 도서 이동 감지 로직 구현
  - [x] 경로 업데이트(`file_path` UPDATE) 처리 및 신규/삭제 후보 집합 보정
- [ ] 원격 서버 배포 및 서비스 재시작
  - [ ] `python deploy.py` 실행
- [ ] 검증 및 버그 정리 문서 작성
  - [ ] `docs/bug/20260620_bugfix_scanner_book_movement_records_preservation.md` 작성
  - [ ] `docs/workflow.md` 업데이트 및 `tools/collect_docs.py` 전역 연동
