---
title: Walkthrough - temp_cache_file_eviction
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: 스트리밍 API DB 커넥션 누수 차단 완료

이미지 로드 및 도서 정보 탐색 시 예외가 발생할 때 DB 커넥션 반환이 이루어지지 않아 발생하던 Connection Leak 장애를 `try-finally` 자원 해제 구문을 통해 해결했습니다.

## 작업 상세

### 1. 안전 클로징 강제 ([stream_service.py](file:///c:/project/media_server/services/stream_service.py))
- **`get_file_path`**: 쿼리 실패 및 예외 유발 여부에 상관없이 `finally` 블록에서 `conn.close()`가 반드시 한 번 실행되어 풀로 복귀되도록 안전 조치했습니다.
- **`extract_page`**: 오프셋 고속 스트리밍 쿼리 영역에 `try-finally` 예외 차단 블록을 도입하여, SQLite 락 경합 시 오류가 발생하더라도 해당 커넥션이 누수되지 않고 정상 소거되도록 수정했습니다.

### 2. 버그 문서화 및 이력 수집
- `./docs/bug/20260629_bugfix_stream_db_connection_leak.md` 문서를 등록하였습니다.
- `workflow.md` 이력 관리 시스템에 작업 로그를 기록하고 `collect_docs.py` 통합 아카이브 프로세스를 집행하였습니다.
