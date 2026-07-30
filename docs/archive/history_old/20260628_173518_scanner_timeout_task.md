---
title: Task - scanner_timeout
project: BookOasis
category: history
date: 2026-06-28
type: task
---
# 작업 계획 (Task)

- [x] 도서 스캔 엔진 (`tools/scanner/core.py`) 개선 및 최적화
  - [x] OOM 감지 시 `sys.exit(0)`을 `os._exit(0)`으로 변경하여 스레드 join 교착 해제
  - [x] SQLite3 `conn.commit()` 호출을 개별 도서 단위에서 폴더 단위로 묶어 트랜잭션 빈도 및 락 경합 완화
- [x] EPUB/커버 추출 (`tools/scanner/cover.py`) 예외 처리 강화
  - [x] EPUB 표지 추출 관련 안정성 보강 및 방어 로깅 추가
- [x] 버그 리포트 문서화 및 검증
  - [x] `docs/bug/` 하위에 YYYYMMDD_bugfix_scanner_timeout.md 버그 분석 문서 작성
  - [x] `docs/workflow.md` 및 `.agent.md` 연동 수집 처리
