---
title: "원격 마운트(VFS) 경로 스캔 시 파일 존재 확인(os.path.exists) API 병목으로 인한 스캐너 행 방지"
project: "BookOasis"
category: "bugfix"
date: 2026-06-20
tags: [scanner, vfs, performance, exists, bottleneck, bugfix]
---

# 원격 마운트(VFS) 경로 스캔 시 파일 존재 확인(os.path.exists) API 병목으로 인한 스캐너 행 방지

## 1. 버그 내역 및 현상
- **현상**: 스캔 경로가 원격 마운트(VFS)인 경우, 스캔 스레드를 1개로 직렬화하고 압축 파일 내부 I/O를 생략했음에도 불구하고 `ThreadPoolExecutor` 내부에서 지속해서 멈추는(Hang) 상태가 나타남.
- **원인**:
  1. `process_folder_task` 루프 내에서 폴더의 메타데이터 파일(`kavita.yaml` 및 `info.xml`) 유무를 판별하기 위해 `os.path.exists`를 개별적으로 매번 호출함.
  2. 이미 `os.walk` 탐색 단계에서 해당 폴더의 전체 파일 목록(`files` 리스트)을 벌크로 수집하여 메모리에 들고 있음에도, 파일 유무를 파일시스템에 재요청하는 비효율이 발생함.
  3. 이로 인해 수천 번의 개별 파일 탐색 API 요청이 원격 저장소에 가해졌고, 지연 누적 및 클라우드 API 호출량 제한(Rate Limit)에 걸려 네트워크 I/O가 멈추게 됨.

## 2. 영향도
- **영향**: 원격 저장소 라이브러리를 스캔할 때 파일 수가 많은 경우, API 레이턴시로 인해 스캐너가 대기 상태에서 빠져나오지 못하게 됨.

## 3. 수정 사항
- **대상 파일**: [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **조치 사항**:
  1. **메모리 기반 존재 판별**: `parse_info_xml(folder_path, files=None)` 및 `parse_kavita_yaml(folder_path, files=None)` 로 매개변수를 확장하고, `files` 리스트가 전달되면 `os.path.exists` 대신 메모리 상의 `files` 목록에서 대소문자 구분 없이 파일명의 존재 여부를 직접 탐색하도록 우회.
  2. **목록 전파**: `process_folder_task` 내부에서 메타데이터 파서들을 호출할 때 이미 들고 있던 `files` 리스트를 넘겨주도록 변경하여 디스크 I/O 재요청 횟수를 `0`으로 제거.

## 4. 해결 확인 및 검증
- 원격 배포 후 라이브러리 스캔 시 수십 초 내에 행(Hang) 없이 동기화 작업이 완수됨을 확인.
