---
title: Walkthrough - scanner_vfs_hang_prevention
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 원격 마운트 경로 스캔 최적화 및 행 방지 조치 결과

## 1. 개요 및 목적
- **이슈**: 원격 드라이브(VFS FUSE 마운트) 하위 라이브러리를 스캔할 때, 수많은 대량 압축 파일들을 4개의 스레드가 병렬로 직접 열어 이미지 목록/오프셋 분석/표지 추출을 시도하면서 심각한 I/O 대기(Hang) 상태가 유발되는 버그 해결.
- **해결 방안**: 원격 경로 감지 시 오프셋 빌드 및 zip/epub 내 대표 커버 추출을 생략하고, 동시 스레드 수를 1개로 제한하여 병목을 원천 방지함.

## 2. 작업 상세 내역
- **스캐너 모듈 수정**: [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)
  - `is_remote_path(physical_path)`를 사용해 스캔 라이브러리의 원격 마운트 여부를 동적으로 판별.
  - 원격 경로인 경우, 스캔 중 무거운 압축 파일 분석 함수인 `collect_zip_offsets_data` 생략 처리.
  - `get_series_cover_fallback` 내 zip/epub에서 첫 페이지 이미지를 강제로 압축 풀고 추출해 표지를 생성하는 작업을 스킵하고, 폴더 내 실물 표지(cover.jpg 등)나 YAML Base64 매핑 표지가 존재할 경우에만 캐시하도록 제약.
  - 동시 요청 병목을 막기 위해 `MAX_SCANNER_THREADS` 개수를 1개(직렬화)로 조절하여 안정적인 순차 탐색 보장.

## 3. 검증 결과
- **컴파일 테스트**: 로컬 구문 오류 체크 성공 (`py_compile`).
- **배포 및 재기동**: `python deploy.py` 정상 완료 및 원격 홈 서버 무중단 재구동 성공.
- **E2E 동작 확인**: 수동 스캔 API 호출 시, 행(Hang)에 빠지지 않고, 실시간으로 파일 등록 및 DB 싱크 작업이 지연 없이 무사 완료됨을 확인. (도서 뷰어에서도 실시간 오프셋 Fallback 복원 덕분에 작품이 문제없이 렌더링됨)
