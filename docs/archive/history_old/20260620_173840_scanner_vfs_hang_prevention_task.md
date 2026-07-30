---
title: Task - scanner_vfs_hang_prevention
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 원격 마운트 경로 스캔 최적화 및 행 방지 작업 목록

- [x] `tools/scanner.py` 수정
  - [x] `process_folder_task`에 `is_remote` 파라미터 전달 및 스킵 분기 적용
  - [x] `get_series_cover_fallback`에서 `is_remote=True` 일 때 zip/epub 내 첫 페이지 강제 추출 로직 스킵 처리
  - [x] `scan_library`에서 `is_remote_path` 판별 후 동적으로 `ThreadPoolExecutor` 스레드 수 조절 및 `process_folder_task`에 `is_remote` 전달
- [x] 원격 서버 배포 및 서비스 재시작
  - [x] `python deploy.py` 실행
- [ ] 검증 및 버그 정리 문서 작성
  - [ ] `docs/bug/20260620_bugfix_scanner_vfs_hang_prevention.md` 작성
  - [ ] `docs/workflow.md` 업데이트 및 `tools/collect_docs.py` 전역 연동
