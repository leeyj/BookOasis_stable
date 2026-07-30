---
title: "스캐너 오프셋 미수집 버그 및 Lazy 스캐너 커버 재추출 오작동 수정"
project: "BookOasis"
category: "bugfix"
date: 2026-06-25
tags: [scanner, lazy-scanner, offset, performance, cover]
---

# 스캐너 오프셋 미수집 버그 및 Lazy 스캐너 커버 재추출 오작동 수정

## 1. 버그 내역

### 버그 A: Lazy 스캐너가 커버가 존재함에도 불구하고 커버를 재추출하는 문제
- Lazy 스캐너(`tools/lazy_scanner.py`)에서 ZIP/CBZ 도서의 오프셋(`has_offsets=0`)이 없는 경우
  `is_target=True`로 판정하여 커버가 정상적으로 존재하는 도서도 `get_series_cover_fallback_single()`
  전체 파이프라인을 실행(force=True)하여 커버를 불필요하게 재추출하는 문제 발생.
- 106,124권의 도서가 커버 재추출 대상으로 잘못 분류됨.

### 버그 B: 메인 스캐너에서 오프셋 수집 기회 누락
- `core.py`의 파일 단위 처리 루프에서 커버·메타가 완비된 도서는 전체 파이프라인을 실행하되,
  ComicInfo.xml 파싱, 커버 추출 등 비싼 I/O 작업 후에 오프셋을 수집하는 구조였음.
- 초기 개발 당시 오프셋 기능이 없어 등록된 레거시 도서 107,077권이 `has_offsets=0` 상태로
  남아 있었고, `book_offsets` 테이블도 완전히 비어있는 상태.
- `has_offsets` 컬럼 추가 이후 재스캔 시 커버·메타 완비 도서는 커버 추출은 생략되지만
  오프셋만 없는 경우를 위한 전용 경로가 없어 ComicInfo 파싱 등 불필요한 I/O까지 함께 실행됨.

### 버그 C: Lazy 스캐너 오프셋 전용 경로의 원격 경로 체크 누락
- Lazy 스캐너 오프셋 전용 처리 경로에 `is_remote_path()` 체크가 없어,
  rclone/Google Drive 마운트 파일에 대해 `zipfile.ZipFile()`을 열어 Central Directory를
  다운로드하는 Google Drive API 호출이 발생할 수 있는 문제.

## 2. 영향도

- **영향 범위**: 스캐너 전반 (107,077권 오프셋 미수집 상태)
- **오프셋 미수집 현황** (운영 DB 기준):
  - ZIP/CBZ 전체: 153,396권 중 107,077권 미수집 (약 70%)
  - 커버 있음 + 오프셋 없음: 106,124권 (Lazy 스캐너가 커버 재추출 중이던 케이스)
  - 커버 없음 + 오프셋 없음: 953권
- **성능 영향**: 오프셋 없는 도서는 스트리밍 시 Fast Path 미적용 → Fallback 경로(ZipFile 전체 파싱 + `get_zip_read_lock` 직렬화)로 처리되어 동시 접속 시 응답 지연 발생 가능.
- **원인**: 오프셋 기능 추가 이전 등록된 레거시 도서들이 마이그레이션 없이 `has_offsets=0` 기본값으로 방치됨.

## 3. 수정 사항

### [1] Lazy 스캐너 — `offset_only` 분기 도입 (버그 A 수정)

**수정 소스 파일**: [`tools/lazy_scanner.py`](file:///c:/project/media_server/tools/lazy_scanner.py)

- `is_target` 단일 플래그를 `cover_missing`, `offset_missing` 두 가지로 분리
- 커버 정상 + 오프셋 없음(`offset_only=True`): `get_series_cover_fallback_single()` 생략,
  `_collect_zip_offsets_safe()` 만 실행 후 즉시 `continue`
- 로그 레이블도 `[커버]`, `[커버+오프셋]`, `[오프셋 전용]` 세 가지로 명확히 분리
- 오프셋 전용 처리 대기 시간: 3초 → 0.5초 (ZIP Central Directory 읽기만 수행하므로 충분)
- YAML/JSON 메타 파싱도 커버 추출이 필요한 폴더에서만 실행하도록 최적화

### [2] 메인 스캐너 — 오프셋 전용 고속 경로 추가 (버그 B 수정)

**수정 소스 파일**: [`tools/scanner/core.py`](file:///c:/project/media_server/tools/scanner/core.py)

- `process_folder_task()` 파일 루프를 3-way 분기로 변경:
  - `skip=True`: 완전 캐시 도서, 모든 처리 생략 (기존 동일)
  - `offset_only` 조건 (커버·메타 완비 + 오프셋 없음 + 로컬 ZIP/CBZ): ComicInfo 파싱·커버 추출 생략, ZIP Central Directory 읽기만 실행
  - `else`: 전체 파이프라인 (기존 동일)
- `scan_library()` 결과 처리에서 `offset_only` 아이템은 `update_book_metadata()` 생략, `save_book_offsets()`만 호출

### [3] Lazy 스캐너 — 원격 경로 체크 추가 (버그 C 수정)

**수정 소스 파일**: [`tools/lazy_scanner.py`](file:///c:/project/media_server/tools/lazy_scanner.py)

- 오프셋 전용 경로에 `is_remote_path()` 체크 추가
- 원격 경로(rclone/GDrive)는 `collect_zip_offsets_data()` 호출 자체를 스킵
- 원격 파일은 대기 시간도 0초 (이미 스킵했으므로 불필요)
- 로컬 파일만 0.5초 대기 유지

## 4. 해결 사항

- Lazy 스캐너가 커버를 불필요하게 재추출하는 문제 해결 (106,124권 대상 오프셋 전용 처리로 전환)
- 메인 스캐너 재스캔 시 오프셋 누락 도서를 효율적으로 처리하는 전용 경로 확보
- 운영 Lazy 스캐너 실행 결과: `커버 재추출 1,150권 / 오프셋 전용 106,015권` 으로 정상 분류 확인
- 이후 재스캔부터는 오프셋 누락 도서가 점진적으로 해소되어 Fast Path 스트리밍 적용 범위 확대
