---
title: Task - scanner_vfs_exists_api_bottleneck
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 원격 마운트 경로 스캔 최적화 및 행 방지 작업 목록 (2차 - 파일 존재 확인 최적화)

- [x] `tools/scanner.py` 수정
  - [x] `parse_info_xml` 함수에 `files` 매개변수 추가 및 메모리 탐색 구현
  - [x] `parse_kavita_yaml` 함수에 `files` 매개변수 추가 및 메모리 탐색 구현
  - [x] `process_folder_task`에서 메타데이터 파싱 시 `files` 목록 전파
- [x] 원격 서버 배포 및 서비스 재시작
  - [x] `python deploy.py` 실행
- [ ] 검증 및 버그 정리 문서 작성
  - [ ] `docs/bug/20260620_bugfix_scanner_vfs_exists_api_bottleneck.md` 작성
  - [ ] `docs/workflow.md` 업데이트 및 `tools/collect_docs.py` 전역 연동
