---
title: Walkthrough - viewer_mark_as_completed_sync
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: 모든 도서(ZIP, EPUB, TXT) 완독 판정 기준 오차 보정 완료

도서 열람 시 뷰어별 백분율 환산 및 로딩 오차로 인해 `is_completed = 1` 상태가 누락되어 이력에서 자동 삭제되지 않던 현상을 일괄 해결했습니다.

## 작업 상세

### 1. 포맷 무관 95% 완독 임계값 적용 ([stream_service.py](file:///c:/project/media_server/services/stream_service.py))
- `record_progress` 메소드 내부의 완독 판별 기준을 수정하여, EPUB/TXT 뿐만 아니라 ZIP 형식 도서까지 포함하여 전체 페이지 중 **95% 이상** (`pages_read / total_pages >= 0.95`) 읽었거나 물리적 끝에 도달하면 무조건 `is_completed = 1`로 인정하도록 조치하였습니다.
- 이를 통해 마지막 챕터 시작부 백분율 환산 오차(EPUB) 및 스크롤 모드 시 마지막 광고 페이지 미로딩(ZIP) 등의 한계 상황을 말끔히 해결하고 이력 삭제 옵션을 정상 작동시킵니다.

### 2. 버그 문서화 및 이력 수집
- `./docs/bug/20260629_bugfix_all_formats_progress_completion_threshold.md` 문서를 등록하였습니다.
- `workflow.md` 이력 관리 시스템에 작업 로그를 기록하고 `collect_docs.py` 통합 아카이브 프로세스를 집행하였습니다.
