---
title: Task - spec_scanner_logic
project: BookOasis
category: history
date: 2026-06-21
type: task
---
# 작업 목록 (task.md)

- [x] 메모리 감시 도구 모듈 분리
  - [x] `tools/scanner/memory_helper.py` 생성 및 `check_memory_exceeded` 이관
- [x] DB 트랜잭션 갱신 레이어 분리
  - [x] `tools/scanner/db_writer.py` 생성 및 도서 등록/수정/오프셋 저장 함수 구현
- [x] 이동/삭제 동기화 감지 레이어 분리
  - [x] `tools/scanner/sync_detector.py` 생성 및 이동/삭제 전처리 및 안전장치 구현
- [x] core.py 코드 다이어트 및 조율 기능만 남기기
  - [x] `tools/scanner/core.py` 수정 및 신규 모듈들 임포트 연동
- [x] 로컬 기능 검증 및 완료 보고
  - [x] 스캐너 가동 E2E 수동 검증 수행
  - [x] walkthrough.md 작성 및 이력 갱신
