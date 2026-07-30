---
title: "스캔 시 단행본별 fallback 표지 이미지 중복 오버라이트 오류 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, cover, fallback]
---

# 🐛 단행본별 fallback 표지 이미지 중복 오버라이트 오류 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 라이브러리 스캔을 수행한 후 웹 UI의 단행본(각 권) 목록에서 1권부터 6권까지 개별 표지가 다르게 보이지 않고, 특정 권의 표지 한 장으로 전체 도서 표지가 통일되거나 제각각 꼬여서 나타나는 오류 발생.

## 2. 원인 분석 (Root Cause Analysis)
- `tools/scanner/core.py` 내의 스캔 루프에서 개별 책 파일의 커버 이미지를 결정할 때 `get_series_cover_fallback(series_name, root)`을 호출함.
- `tools/scanner/cover.py` 내 `get_series_cover_fallback`의 구현은 개별 책 파일명이 아닌 `series_name`을 인자로 받아 해시를 만들어 `series_[시리즈해시].jpg` 파일명 하나로 커버를 추출 및 저장하고 있었음.
- 이로 인해 스캔 시 시리즈 내 모든 단행본들이 `series_[시리즈해시].jpg`라는 단 하나의 동일한 물리 파일 경로를 공유하게 되어, 최종적으로 디스크에 남은 특정 단행본(예: 5권 혹은 6권)의 이미지 한 장만 강제로 전 권의 표지로 매핑되는 병목이 발생함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: 
  - [cover.py](file:///c:/project/media_server/tools/scanner/cover.py): `get_series_cover_fallback` 함수에 `filename` 파라미터를 추가했습니다. 만약 `filename`이 전달될 경우, 시리즈 해시 대신 개별 책 파일명의 MD5 해시를 사용하여 `book_[책파일해시].png` 고유 파일명으로 커버 이미지를 디스크에 격리 추출하도록 튜닝했습니다.
  - [core.py](file:///c:/project/media_server/tools/scanner/core.py): 스캔 루프(`process_folder_task` 및 `scan_library_covers_only` 내 `process_cover_task`)에서 `get_series_cover_fallback`을 호출할 때 `filename=filename` 인자를 추가로 전달하도록 맵핑 조치했습니다.
- 이로 인해 모든 단행본이 자신의 파일명을 기준으로 정확히 독립된 개별 `book_*.png` 표지 파일명과 DB 이미지 필드를 갖게 됩니다.

## 4. 결과 검증 (Verification Results)
- 수정 후 로컬 환경 파이썬 구문 정적 린트 컴파일 검사 성공 완료.
- 사용자 실운영 배포 후 **[표지 새로고침] (스캔-커버 전용)** 기능을 수행하면, 전 권의 책 파일에서 첫 페이지가 `book_*.png`로 각각 독립적으로 매끄럽게 추출되어 1권부터 6권까지 각기 다른 고유 표지가 꼬임 없이 브라우저에 즉시 매핑됩니다.
