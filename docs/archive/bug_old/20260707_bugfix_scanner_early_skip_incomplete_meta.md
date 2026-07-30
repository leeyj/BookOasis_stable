---
title: "스캔 도중 중단된 도서의 메타데이터 및 커버 미추출 조기 스킵 버그 해결"
date: "2026-07-07"
type: "bugfix"
status: "completed"
tags: ["scanner", "metadata", "cover", "skip", "sync"]
---

# 스캔 도중 중단된 도서의 메타데이터 및 커버 미추출 조기 스킵 버그 해결

## 1. 개요 및 증상
- **현상**: 스캐너가 신규 도서를 발견하여 DB에 파일 경로 등의 최소 기본 정보(mtime, size 등)는 등록하였으나, 스캔 도중 중단 등의 원인으로 인해 메타파일(kavita.yaml, info.xml)로부터 메타 정보 및 표지 이미지 추출을 끝내지 못한 상태의 도서들이 존재합니다. 이후 재스캔을 돌렸을 때 해당 도서들의 파일 mtime과 size가 DB 기록과 일치하면 스캐너가 이미 완료된 책으로 오인하여 조기에 건너뜀(Skip)으로써, 메타데이터 입력과 커버 추출이 영원히 미완성으로 남는 버그가 발생했습니다.

## 2. 원인 분석
- `tools/scanner/tasks.py` 내의 `process_folder_task` 50~65라인 부근의 조기 스킵 로직은 파일의 물리 `mtime`과 `size`가 DB 캐시(`db_files_cache`)와 완벽하게 일치하면 해당 파일을 `skipped_files` 세트에 즉시 추가해버립니다.
- 하지만 DB에 `file_path`, `mtime`, `size`만 존재하고 정작 메타 정보(`author`, `publisher`, `summary`)와 `cover_image`가 완성되지 않은 책(`db_meta_full`에 미포함)이 있을 때도 mtime/size가 같다는 이유만으로 스킵 대상이 되는 맹점이 존재했습니다.

## 3. 해결 방안
- **[tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py)**:
  - 파일의 mtime과 size가 같더라도, DB상에 표지 및 메타데이터가 완성되지 않은 책(`full_path not in db_meta_full`)이라면 조기 스킵하지 않고 파이프라인(`continue` 분기)을 타도록 차단 가드를 삽입했습니다.
  - 이제 미완성 도서는 무조건 메타데이터 갱신 및 커버 추출 프로세스를 정상적으로 거치게 되어 누락 없이 완벽한 정수 좌표 범위의 메타데이터가 확보됩니다.

## 4. E2E 검증 결과
- DB에 정보만 등록되고 표지/메타데이터가 유실된 채 방치되었던 미완성 도서들이, 재스캔 구동 시 스킵되지 않고 로컬 메타파일(kavita.yaml, info.xml)을 완벽히 읽어 표지 파일 생성 및 작가, 출판사, 줄거리 정보 저장을 최종 완수함을 확인했습니다.
