---
title: "스캐너 OOM 프로세스 종료 방지 및 GC 최적화"
project: "BookOasis"
category: "bug"
date: 2026-06-20
tags: [bugfix, scanner, oom, memory-optimization]
---

# 🐛 스캐너 OOM 프로세스 종료 방지 및 GC 최적화 (Bugfix Report)

## 1. 장애 현상 (Problem Description)
- 도서 라이브러리 전체 스캔 과정 중 Gunicorn 워커 프로세스(`python3`)가 커널 OOM Killer에 의해 강제 종료(`SIGKILL`)되는 현상 발생.
- `dmesg` 상에서 `anon-rss:12718080kB` (실제 물리 메모리 12.13GB 초과 점유) 상태로 종료되었음이 확인됨.

## 2. 원인 분석 (Root Cause Analysis)
- `MAX_SCANNER_THREADS = 8`로 다수의 무거운 스캔 스레드가 압축 파일(`.zip`, `.cbz`, `.epub`)의 압축 해제 및 이미지 디코딩 처리를 병렬적으로 진행하면서 메모리가 급격히 팽창함.
- 파이썬 가비지 컬렉터가 백그라운드 세대 청소를 수행하기 전에 대용량 바이너리 객체들이 누적되어 단시간에 OS 물리 메모리 상한 임계치를 돌파함.

## 3. 조치 사항 (Resolution Details)
- **수정 소스 파일**: [scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - `MAX_SCANNER_THREADS` 값을 `8`에서 `4`로 낮추어 동시 메모리 사용 피크치를 제한함.
  - `process_folder_task` 스레드 작업 함수가 반환되는 마지막 시점에 `gc.collect()`를 명시적으로 호출하여 폴더별 처리가 끝난 버퍼 메모리를 해제함.
  - `scan_library`의 DB 커밋 동기화 루프 내부에서 `processed_count % 50 == 0` (50권 처리 시마다) 조건으로 수동 가비지 컬렉션을 수행하도록 강제 튜닝함.

## 4. 결과 검증 (Verification Results)
- 증분 스캔을 통해 오프셋 정보가 부재한 도서들부터 선별적으로 스캔이 재개됨을 확인함.
- 메모리 사용 한계가 제어되고 스레드가 4개로 안정화됨에 따라 추가적인 OOM `SIGKILL` 현상 없이 완료됨을 확인.
