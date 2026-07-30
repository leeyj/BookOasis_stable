---
title: Task - scanner_modularization
project: BookOasis
category: history
date: 2026-06-20
type: task
---
# 스캐너 리팩토링 및 분할 모듈화 작업 목록

- [x] `tools/scanner/` 패키지 디렉토리 생성
- [x] 모듈별 소스 코드 생성
  - [x] `tools/scanner/parser.py` 작성
  - [x] `tools/scanner/cover.py` 작성
  - [x] `tools/scanner/offset.py` 작성
  - [x] `tools/scanner/vfs.py` 작성
  - [x] `tools/scanner/core.py` 작성
  - [x] `tools/scanner/__init__.py` 작성
- [x] `tools/scanner.py` 를 하위 호환 래퍼로 전환 수정
- [x] 서비스 구문 검증 및 빌드 확인
- [ ] 배포 준비 및 정리
  - [ ] `docs/workflow.md` 업데이트 및 `tools/collect_docs.py` 전역 연동
