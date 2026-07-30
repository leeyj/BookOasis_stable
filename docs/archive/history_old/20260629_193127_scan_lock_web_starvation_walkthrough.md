---
title: Walkthrough - scan_lock_web_starvation
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: 디스크 캐시 LRU 정리 대상 예외 필터 처리 완료

백그라운드 파일 복사 작업 진행 중에 임시 파일(`.tmp`)이 디스크 공간 확보 과정에서 지워져 발생하는 복사 실패 버그를 해결했습니다.

## 작업 상세

### 1. 정리 대상 스캔 조건 변경 ([cache.py](file:///c:/project/media_server/api/cache.py))
- `DiskCacheManager.clean_up_if_needed` 내부의 `listdir` 폴더 검사 루프에서 완료 지시자 파일인 `.done`과 마찬가지로, 다운로드가 한창 진행 중인 임시 캐시 파일 `.tmp`도 정리 및 삭제 수집 대상에서 완전히 예외(스킵) 처리하도록 수정했습니다.
- 이를 통해 백그라운드 복사가 안전하게 끝나서 완전한 `.zip` 형태로 확정될 때까지는 LRU 삭제 대상이 되지 않으므로 복사 도중 임시 파일 소실 장애가 더 이상 유발되지 않습니다.

### 2. 버그 문서화 및 이력 수집
- `./docs/bug/20260629_bugfix_temp_cache_file_eviction.md` 문서를 등록하였습니다.
- `workflow.md` 이력 관리 시스템에 작업 로그를 기록하고 `collect_docs.py` 통합 아카이브 프로세스를 집행하였습니다.
