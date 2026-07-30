---
title: "이미지 폴더 스캔 시 튜플 언패킹(expected 3, got 2) 오류 조치"
project: "BookOasis"
category: "bugfix"
date: 2026-07-13
tags: [bugfix, scanner, unpack, imgdir]
---

# 🐛 이미지 폴더 스캔 시 튜플 언패킹(expected 3, got 2) 오류 조치

## 1. 버그 내역 및 증상
- 이미지 폴더 가상 책(`__folder__.imgdir`)에 대해 개별 재스캔이 트리거되면, 물리 파일 시스템에 `__folder__.imgdir` 파일이 존재하지 않아 물리 검사 에러를 뿜으며 조기 실패를 유도합니다.
- 이때 `BookScanService.scan_single_book` 내부에서 `(False, "에러 메시지")`와 같이 2개짜리 튜플을 리턴하게 되는데, API 라우터(`scan_routes.py`)는 3개짜리 언패킹(`success, message, cover_image = ...`)을 수행하려 하여 `expected 3, got 2` 언패킹 예외와 함께 스캔이 비정상 중단되는 현상이 발생했습니다.

## 2. 원인 분석
- **물리 경로 존재 검사 실패**: 이미지 폴더 가상 책의 DB 경로는 `/.../__folder__.imgdir` 이며, 이는 가상의 논리적 파일이므로 `os.path.exists()`를 수행하면 무조건 `False`가 납니다.
- **반환 튜플 개수 불일치**: `BookScanService` 에러 반환 로직의 일부 분기문에서 2개 원소 튜플을 반환하고 있어, 라우터 스택에서 3개 언패킹 도중 파이썬 런타임 언패킹 오류가 발생했습니다.

## 3. 조치 사항
- **[book_scan_service.py](file:///c:/project/media_server/services/book_scan_service.py)**:
  - 가상 책(`imgdir` 포맷 혹은 확장자가 `.imgdir`인 경우) 감지 시, `__folder__.imgdir` 파일 경로 대신 부모 폴더 디렉토리(`os.path.dirname(file_path)`)가 물리적으로 존재하는지 검증하도록 방어 코드를 적용했습니다.
  - `scan_single_book` 의 모든 조기 에러 반환 구문에 대해 3개 원소 `(False, "에러 메시지", None)`을 명시적으로 맞춰서 반환하도록 일관성을 부여했습니다.

## 4. 해결 확인 및 영향도
- 가상 책 스캔 시 물리적인 가상 파일 부재로 인한 에러를 정상 방어하며, 튜플 길이 불일치 예외 없이 부모 디렉토리 기반의 메타데이터와 표지 복원이 정상 완료됩니다.
