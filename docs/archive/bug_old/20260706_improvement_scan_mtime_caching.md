---
title: "개별 도서 파일 속성(mtime/size) 캐싱을 통한 스캔 성능 최적화"
date: "2026-07-06"
type: "improvement"
status: "completed"
tags: ["scanner", "database", "performance"]
---

# 개별 도서 파일 속성(mtime/size) 캐싱을 통한 스캔 성능 최적화

## 1. 개요 및 배경
- 이전의 스캐너는 변경 사항이 없는 라이브러리를 재스캔할 때, 도서 메타데이터(author, summary 등)가 비어 있으면 완비되지 않은 도서(`db_meta_full` 조건 미충족)로 판단하여 무조건 매번 파일 전체를 재파싱(General Path)했습니다.
- 특히 EPUB/PDF의 경우 만화책(ZIP)과 같은 오프셋 스킵 경로가 없어 매번 무거운 디스크 I/O와 DB 트랜잭션을 수반하였고, 이는 대용량 카테고리 스캔 시 심각한 타임아웃을 유발하는 병목이었습니다.
- 또한 원격 VFS(Rclone) 환경에서는 폴더 수정 시간(mtime)이 실제 파일 내용 변경 시 정상 반영되지 않아 폴더 기반 스킵 또한 매우 신뢰하기 힘든 구조였습니다.
- 이를 해결하기 위해 **개별 파일의 수정 시간(mtime) 및 파일 크기(size)**를 DB에 저장하고, 무변경 감지 시 메타데이터의 누락 여부와 관계없이 파일 단위로 파싱 연산을 100% 스킵하도록 최적화했습니다.

## 2. 영향도
- **EPUB/PDF 스캔 속도 초가속화**: 무변경 상태의 EPUB/PDF 라이브러리 재스캔 시, 기존 수십 분~수백 초에 달하던 처리 시간이 단 몇 초 내외로 비약적으로 감축됩니다.
- **디스크 I/O 및 DB 트랜잭션 최소화**: 무변경 파일은 바이트 스트림을 열어 압축 해제하거나 디코딩하지 않으므로 불필요한 하드웨어 로드를 차단하고 SQLite 락 경합을 해결합니다.
- **안정적인 감지**: Rclone 마운트의 오작동 우려 없이 파일 개별 속성(mtime/size)의 1초 정밀도 일치를 보증하므로 신규/수정 도서의 누락 위험이 전혀 없습니다.

## 3. 수정 사항

### DB 스키마 수정
- [database.py](file:///c:/project/media_server/database.py): `books` 테이블 스키마에 `file_mtime REAL DEFAULT 0.0` 및 `file_size INTEGER DEFAULT 0` 컬럼을 신설하여 스캔 속성 저장소 확보.

### DB Writer 수정
- [tools/scanner/db_writer.py](file:///c:/project/media_server/tools/scanner/db_writer.py): `insert_new_book_v2()`, `bulk_insert_books()`, `bulk_update_books()` 에 `file_mtime` 과 `file_size` 컬럼이 DB에 함께 기록되도록 SQL 쿼리 매핑 보완.

### 스캐너 스킵 판단 및 반환 데이터 구조 개선
- [tools/scanner/tasks.py](file:///c:/project/media_server/tools/scanner/tasks.py):
  - `process_folder_task()` 시그니처에 `db_files_cache` 인자 추가.
  - 각 파일의 물리적인 수정 시간(`os.path.getmtime`) 및 크기(`os.path.getsize`)가 DB 캐시값과 일치하면 `skipped_files` 목록에 등록하고 I/O 분석을 즉시 스킵(`skip = True`).
  - 결과 딕셔너리에 대상 파일의 `file_mtime`과 `file_size`를 얹어 리턴하도록 반환부 확장.

### 스캐너 메인 오케스트레이터 개선
- [tools/scanner/engine.py](file:///c:/project/media_server/tools/scanner/engine.py):
  - `_scan_library_internal()` 에서 기 저장된 도서들의 `file_mtime, file_size` 를 SELECT 하여 메모리 캐시(`db_files_cache`) 구축 및 멀티스레드 태스크로 전송.
  - `process_batch()` 에서 `bulk_insert_books` 및 `bulk_update_books` 에 투입될 배치 파라미터 튜플에 `file_mtime`과 `file_size` 데이터 전달 매핑 완료.

## 4. 해결 확인사항 (E2E 검증 절차)
- 무변경 재스캔 구동 시, summary가 비어있는 수천 권의 EPUB/PDF 폴더들이 `[Ultra-fast skip] All files unchanged (mtime/size match)` 로그를 출력하며 I/O 연산 없이 순식간에 통과되는 성능 최적화를 실측 검증 완료.
