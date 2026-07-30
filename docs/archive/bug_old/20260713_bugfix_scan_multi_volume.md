---
title: "스캐너 다중 권수 등록 오류 수정"
project: "BookOasis"
category: "bug"
date: 2026-07-13
tags: [scanner, path, bugfix]
---

# 🐛 스캐너 다중 권수 등록 오류 수정

## 1. 버그 내역
- 만화책 등 이미지 파일만 들어있는 개별 디렉토리를 가상 책(`__folder__.imgdir`) 형태로 등록할 때, 스캐너 내부의 OS 경로 구분자(백슬래시 `\` 와 슬래시 `/`)가 혼용되어 발생한 경로 불일치 문제입니다.
- Windows 환경에서 슬래시와 백슬래시가 혼용된 기괴한 가상 파일 경로(예: `/data/mainserver_comics/comics/.../데스노트 컬러판 01권\__folder__.imgdir`)가 생성되고, 이것이 DB에 인서트되었습니다.
- 이로 인해 2권부터는 경로 캐시 매칭 실패 및 소프트 딜리트 복구 실패가 발생하여 정상적으로 책이 등록되지 않고 오직 1권만 목록에 보여지는 버그가 발생했습니다.

## 2. 영향도
- 이미지 디렉토리 기반의 만화책 또는 웹툰 스캔 시, 다중 권수(단행본 목록) 중 1권 외에는 정상 노출 및 서재 등록이 이루어지지 않음.

## 3. 수정 사항
- **[tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py)**:
  - `process_folder_task` 의 시작 부분에서 `root` 경로를 받아올 때, 백슬래시(`\`)를 슬래시(`/`)로 강제 변환하여 파일 시스템 및 가상 파일 경로 빌드 시 항상 슬래시 스타일의 통일된 정규화 경로가 생성되도록 수정함.
- **[engine.py](file:///c:/project/media_server/tools/scanner/engine.py)**:
  - `_scan_library_internal`의 `os.walk` 루프 시작 시 `root` 경로를 슬래시 스타일로 정규화함.
  - `process_batch` 내부에서 SQLite DB에 데이터를 삽입(`bulk_insert_books`)하거나 업데이트(`bulk_update_books`)하기 직전에 `d['full_path'].replace('\\', '/')`를 수행하여, 슬래시가 누락되거나 백슬래시가 혼용되어 인서트되는 현상을 원천 차단함.

## 4. 해결 사항
- 모든 파일 및 가상 이미지 디렉토리 책 경로가 `/` 구분자로 정규화되어 데이터베이스에 통일되게 기록됩니다.
- 경로 불일치 문제가 완전히 해결되어 1권뿐만 아니라 2권~12권 및 단편집 등 모든 하위 권수 폴더가 올바르게 인덱싱되고 중복 제거 및 소프트 딜리트 복구가 정상 작동합니다.
