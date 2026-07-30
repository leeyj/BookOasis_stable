---
title: Walkthrough - scanner_book_movement_records_preservation
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 도서 이동/이름 변경 시 독서 기록 보존 결과

## 1. 개요 및 목적
- **이슈**: 책의 경로(`file_path`)가 바뀌었을 때 스캐너가 기존 도서 레코드와 사용자의 소중한 독서 이력(`user_progress`, `user_reading_log`)을 완전히 삭제하고 신규 도서로 오인 등록하는 결함 조치.
- **해결 방안**: DB 동기화 이전에 파일명 매핑 대조를 통해 이동을 자동 감지하고 `file_path`만 업데이트하여 독서 이력을 완전히 보존함.

## 2. 작업 상세 내역
- **스캐너 모듈 수정**: [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - 사라진 도서 경로(`deleted_paths`)와 새로 감지된 도서 경로(`new_paths`)에서 파일명(basename)이 완벽히 일치하는 쌍을 색인.
  - 일치 도서 발견 시 `UPDATE books SET file_path = ? WHERE id = ?`를 통해 DB 경로를 직접 갱신.
  - 갱신된 도서는 삭제 대상 및 신규 후보군 집합에서 제외 처리하여 독서 정보의 완벽한 연속성 유지 보장.

## 3. 검증 결과
- **로컬 검증 완료**: 파이썬 구문 린트 및 컴파일 성공 완료.
- **원격 검증 대기**: 수정 완료 소스는 로컬에 반영되어 있으며, 배포 및 수동 테스트는 사용자 승인 하에 원격지에서 직접 수행 예정.
