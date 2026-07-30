---
title: Walkthrough - viewer_close_ui_refresh
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: [읽음 완료] 처리 시 완독 정보 즉시 동기화 완료

뷰어 하단 오버레이에서 [읽음 완료] 버튼 클릭 시, alert 완료 얼럿창이 브라우저 스레드를 정지시켜 백엔드로 완독 데이터가 전달되기 전 뷰어가 닫히면서 진행률 저장이 누실되던 버그를 즉시 동기 전송(`flushProgress`) 방식으로 보완 완료했습니다.

## 작업 상세

### 1. 진척도 동기식 즉시 전송 보장 ([viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js))
- `markAsCompleted` 메소드 내에서 `loadComicPage()`를 타기 전, `saveProgress()`를 실행하여 최종 만화책 인덱스를 예약하도록 추가했습니다.
- 예약 직후 `viewer_progress.js` 내의 `flushProgress()`를 임포트하여 즉각 API 호출을 날리게 유도함으로써, 뒤따라오는 `alert()` 완료창이 뜨기 전에 완독 요청이 확실하게 서버로 백그라운드 전송되도록 보정했습니다.

### 2. 버그 문서화 및 이력 수집
- `./docs/bug/20260629_bugfix_viewer_mark_as_completed_sync.md` 문서를 등록하였습니다.
- `workflow.md` 이력 관리 시스템에 작업 로그를 기록하고 `collect_docs.py` 통합 아카이브 프로세스를 집행하였습니다.
