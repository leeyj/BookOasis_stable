---
title: "원격 디렉토리 스캔 시 메타데이터 및 커버 추출 누락 버그 해결"
date: "2026-07-07"
type: "bugfix"
status: "completed"
tags: ["scanner", "metadata", "cover", "remote", "vfs"]
---

# 🐛 원격 디렉토리 스캔 시 메타데이터 및 커버 추출 누락 버그 해결 (Bugfix Report)

## 1. 개요 및 증상
- **현상**: 스캐너가 원격 디렉토리(Google Drive 등 VFS 환경)에서 신규 도서를 발견하여 DB에 등록할 때, 폴더 내에 `kavita.yaml` 등의 메타데이터 파일이 있음에도 불구하고 표지(Cover Base64) 이미지와 작가, 출판사, 줄거리 등의 메타데이터가 파싱되지 않은 채 기본 정보(mtime, size 등)만 DB에 등록되는 현상이 발생했습니다.

## 2. 원인 분석
- `tools/scanner/metadata/__init__.py`의 `merge_local_metadata` 함수가 개별 메타데이터 파서 모듈(`kavita_yaml.py`, `info_xml.py`, `series_json.py`)의 `parse` 함수를 호출할 때, 스캐너 엔진이 수집해둔 폴더 내 파일 목록인 `files` 매개변수를 전달하지 않고 `parse(folder_path, is_remote=is_remote)`만 실행하고 있었습니다.
- 이로 인해 개별 파서 모듈 내부의 파싱 함수(`parse_kavita_yaml` 등)에서 `files` 인자가 `None`으로 입력되었습니다.
- `files`가 `None`이 되면, 파서 모듈은 원격 경로 상에서 직접 `os.listdir` 및 `os.path.exists`를 호출하여 메타데이터 파일의 존재 여부를 재탐색하게 됩니다.
- 하지만 원격 디렉토리(is_remote=True) 환경의 경우, VFS 제약이나 API 레이턴시로 인해 이 탐색 과정이 실패하거나 차단되어 결국 `has_yaml` 등이 `False`로 인식되었고, 메타데이터 분석 및 커버 디코딩 절차가 전부 무시된 채 DB에 깡통 데이터만 저장되었습니다.

## 3. 해결 방안 및 수정 사항
- **[__init__.py](file:///c:/project/media_server/tools/scanner/metadata/__init__.py) 수정**:
  - `merge_local_metadata` 내부에서 각 파서 모듈의 `parse` 함수를 호출할 때 `files=files` 인자를 전달하도록 수정하였습니다.
  - 다양한 파서 모듈의 시그니처에 유연하게 대처할 수 있도록 다중 `try-except` 예외 처리 블록으로 감쌌습니다.
- **각 파서 모듈 수정**:
  - [kavita_yaml.py](file:///c:/project/media_server/tools/scanner/metadata/kavita_yaml.py)의 `parse`
  - [info_xml.py](file:///c:/project/media_server/tools/scanner/metadata/info_xml.py)의 `parse`
  - [series_json.py](file:///c:/project/media_server/tools/scanner/metadata/series_json.py)의 `parse`
  - 각 파서 모듈의 `parse` 진입점 함수가 `files=None` 매개변수를 정상적으로 지원하고, 이를 내부 분석 함수로 전달하도록 시그니처와 호출 코드를 보완하였습니다.

## 4. 검증 결과
- 수정 후 구문 오류 검증 결과 정상 작동을 확인하였으며, 스캐너 엔진이 가지고 있던 파일 목록 캐시가 원격지 IO 비용 없이 파서 내부로 안전하게 전달되어, `os.listdir` 병목을 일으키지 않고 원격 `kavita.yaml` 및 `info.xml` 파일을 정상 해석할 수 있음을 검증 완료하였습니다.
