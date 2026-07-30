---
title: "수동 스캔 시 VFS 캐시 새로고침 미동작 조치"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, vfs, rclone, manual-scan]
---

# 🐛 수동 스캔 시 VFS 캐시 새로고침 미동작 조치 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 스캐너가 미동작하여 CLI 터미널이나 웹의 즉시 동기화 버튼을 통해 수동 기동 시, `[Scanner] 물리 폴더 트리 탐색 중...` 단계에서 멈춘 채 스캔이 더 이상 진행되지 않고 먹통(Hang)이 되는 장애 발생.
- 웹상에서 기동 시 `logs/scan_history.log` 에 `스캔 기동 시작` 로그는 기록되나 완료 로그가 영원히 생성되지 않음.

## 2. 원인 분석 (Root Cause Analysis)
- 대상 경로인 `/home/az001a/sjva/NAS_BACKUP/books/소설` 및 구글 드라이브 라이브러리들은 rclone FUSE 기반 마운트 드라이브(가상 파일 시스템)로 연동되어 있음.
- 백본 스케줄러(`scheduler_service.py`)를 통해 기동될 때는 rclone API 캐시 갱신(`vfs/refresh`) 구문이 호출되나, 사용자가 CLI(`python3 scanner.py`)로 기동하거나 개별 스캔 트리거 시에는 이 갱신 로직을 타지 않고 바로 `scan_library` -> `os.walk`를 수행함.
- VFS 캐시가 갱신되지 않은 대규모 원격 클라우드 드라이브를 `os.walk`로 재귀 탐색 시, 매 디렉토리 진입마다 실시간 동기식 API 대기 지연이 발생해 스캔이 정지된 것처럼 극심한 병목 현상이 일어남.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - 스캔의 핵심 시작 진입점인 `scan_library` 도입부에 `trigger_vfs_refresh(db_path, library_id, physical_path)` 연동을 내재화함.
  - 해당 함수를 통해 대상 경로가 원격지(`is_remote_path`)이면서 DB 설정상 사전 갱신(`vfs_refresh_before_scan == 1`)이 활성화되어 있을 때, 스캔 직전 rclone RC API를 호출하여 해당 디렉토리 영역만 **핀포인트로 부분 캐시 갱신**을 수행하도록 조치함.

## 4. 결과 검증 (Verification Results)
- 코드를 원격 홈 서버에 배포한 후 터미널 상에서 `python3 -u scanner.py`를 실행하여 수동 스캔 테스트를 검증함.
- `[Scanner-VFS] VFS 캐시 사전 새로고침을 시작합니다` 구문과 함께 `VFS 캐시 갱신 성공 - 대상: 'NAS_BACKUP/books/소설'` 갱신이 성공하고, 직후 `물리 폴더 트리 탐색 중...` 단계가 대기 시간 없이 단 1초도 걸리지 않고 순식간에 통과하여 다음 라이브러리 스캔으로 빠르게 정상 진행됨을 확인 완료함.
