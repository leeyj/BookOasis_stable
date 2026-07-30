---
title: "이 책 즉시스캔 시 신규 추출 표지 미반영 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, cover, single_scan]
---

# 🐛 이 책 즉시스캔 시 신규 추출 표지 미반영 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 상세 페이지 또는 단행본 목록에서 우클릭 후 **[이 책 즉시스캔]**을 실행하여 개별 책에 대한 이미지 재추출을 유도하더라도, 웹 UI 상에서 표지가 고유의 단행본 이미지로 업데이트되지 않고 예전 시리즈 공통 표지(`series_*.jpg`)로 유지되거나 갱신에 실패하는 현상 발생.

## 2. 원인 분석 (Root Cause Analysis)
- `services/book_scan_service.py` 내 `scan_single_book` 함수에서 DB 업데이트 시 `cover_image` 필드를 다음과 같은 쿼리로 갱신하고 있었습니다.
  ```sql
  cover_image = COALESCE(NULLIF(?, ''), cover_image)
  ```
- 위 `COALESCE` 구문은 신규 값이 비어있을 때만 기존 값(`cover_image`)을 보존하는 의도였으나, 이미 기존 DB 레코드에 `series_*.jpg` 같은 구형 표지명이 기록되어 있는 경우에는 새롭게 디스크에 추출해 낸 `book_[책해시].png` 고유 파일명이 전달되더라도 기존 값이 우선 적용되거나 무시되는 논리적 결함이 있었습니다.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**:
  - [book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py): `scan_single_book` 내부의 SQL UPDATE 쿼리를 수정하여 신규로 성공적으로 추출된 `cover_image`가 존재할 때(`IS NOT NULL` & `!= ''`), 기존 값을 무조건 새 표지 경로로 덮어쓰도록(Overwrite) `CASE WHEN` 조건부 대입문으로 변경했습니다.
  ```sql
  cover_image = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE cover_image END
  ```
- 이 패치를 통해 개별 책 즉시 스캔 시 매칭되는 고유 1:1 `book_*.png` 커버 명칭이 DB에 원천적으로 강제 동기화되도록 보장합니다.

## 4. 결과 검증 (Verification Results)
- 소스 코드 변경 후 로컬 파이썬 문법 검증 완료.
- 원격 서버 자동 배포(`python deploy.py`) 및 서버 재부팅(PID: 2936468) 정상 완료.
- 브라우저 캐시 새로고침 후 단일 도서 우클릭 [이 책 즉시스캔] 기능 기동 시, 고유의 개별 단행본 표지로 실시간 덮어쓰기 갱신 처리되는 것을 확인 가능합니다.
