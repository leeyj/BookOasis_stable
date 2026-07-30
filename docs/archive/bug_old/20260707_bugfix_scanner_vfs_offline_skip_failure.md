---
title: "원격 드라이브 VFS 오프라인 상태일 때 이미 캐싱된 도서가 스킵되지 않는 버그 해결"
date: "2026-07-07"
type: "bugfix"
status: "completed"
tags: ["scanner", "vfs", "skip", "sync"]
---

# 원격 드라이브 VFS 오프라인 상태일 때 이미 캐싱된 도서가 스킵되지 않는 버그 해결

## 1. 개요 및 증상
- **현상**: 원격 드라이브(VFS) 환경에서 스캔을 구동할 때, VFS 캐시 갱신 실패 등으로 파일 실제 접근이 일시적으로 차단되거나 오프라인 상태가 되는 경우가 있습니다. 이 상태에서 재스캔을 구동할 때, 이미 정상적으로 한 번 스캔 완료되어 데이터베이스에 메타데이터, 커버, mtime 등이 완전하게 기록되어 있음에도 불구하고, 스캐너가 해당 파일의 `os.path.getmtime` 호출 중 발생하는 파일 부재 예외(FileNotFoundError 등)로 인해 조기 스킵하지 못하고 파일 분석 파이프라인을 타게 되어 에러를 유발하거나 오동작하는 버그가 발생했습니다.

## 2. 원인 분석
- `tools/scanner/tasks.py` 내의 `process_folder_task`에서 파일의 변동 여부를 비교하는 early skip 로직 내부에 `try-except` 블록이 존재합니다.
- `os.path.getmtime(full_path)` 및 `os.path.getsize(full_path)`를 시도하는 과정에서 VFS 오프라인으로 인해 예외가 발생할 경우, 예외 핸들러가 이를 `pass` 처리만 하고 조기 스킵 목록(`skipped_files`)에 추가하지 않았습니다.
- 이로 인해 `skipped_files`에 누락되어 해당 파일의 `skip = True` 조건이 충족되지 않고 파일 처리 파이프라인을 그대로 실행하게 되어 에러가 발생합니다.

## 3. 해결 방안
- **[tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py)**:
  - 파일 정보 확인 과정 중 `Exception`이 발생하였을 때, 해당 드라이브가 원격 드라이브(`is_remote`)이며 이미 DB에 해당 도서의 커버와 메타데이터가 정상 등록(`full_path in db_meta_full`)되어 있고 기존에 기록된 `c_mtime`이 유효(> 0.0)한 상태라면, 비록 예외가 발생했더라도 변동 사항이 없는 완료 도서로 간주하여 조기 스킵 목록(`skipped_files`)에 추가하도록 예외 분기를 개선했습니다.

## 4. E2E 검증 결과
- VFS 갱신에 실패하여 물리적으로 임시 오프라인이 된 원격 드라이브 파일들을 대상으로 스캔을 재실행했을 때, 파일 접근 실패 예외 상황에서도 DB 캐시 정보를 신뢰하여 불필요한 분석 시도나 에러 로그 수집 없이 부드럽고 안전하게 조기 스킵되는 것을 확인했습니다.
