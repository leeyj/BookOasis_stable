---
title: Walkthrough - scanner_vfs_exists_api_bottleneck
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 원격 마운트 VFS exists API 병목 해결 결과

## 1. 개요 및 목적
- **이슈**: 원격 드라이브 스캔 시, `os.walk` 탐색이 완료된 후 각 폴더별 메타데이터 파일(`kavita.yaml`, `info.xml`)의 존재 여부를 `os.path.exists()`로 개별 조회하면서 클라우드 API 호출량 초과 및 레이턴시 병목으로 인해 스캐너가 대기(Hang) 상태에 빠진 버그 해결.
- **해결 방안**: 이미 메모리에 로드된 `files` 리스트를 재활용하여 파일시스템에 대한 중복 쿼리를 완전히 방지함.

## 2. 작업 상세 내역
- **스캐너 모듈 수정**: [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - `parse_info_xml`, `parse_kavita_yaml` 함수에 `files` 매개변수 옵션을 추가하여, 메모리 내 `files` 배열에서 대소문자 매칭을 통해 파일 유무 판별.
  - `process_folder_task`에서 메타데이터 파서 호출 시 해당 폴더의 `files` 인자를 전달하도록 전파.
  - 파일시스템에 직접 접근하는 `os.path.exists` 사용을 원천 차단하여 I/O 비용 획기적 제거.

## 3. 검증 결과
- **E2E 동작 확인**: 수동 스캔 기동 시, 행 현상 없이 순식간에 물리 폴더 분석 및 DB 동기화가 안전하게 끝나는 것을 확인.
