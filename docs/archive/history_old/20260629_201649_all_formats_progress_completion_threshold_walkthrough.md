---
title: Walkthrough - all_formats_progress_completion_threshold
project: BookOasis
category: history
date: 2026-06-29
type: walkthrough
---
# Walkthrough: 스캔 중 웹 로드 병목(락 교착) 개선 조치 완료

대용량 스캔 구동 시 스캐너의 SQLite 쓰기 독점과 디스크 I/O 포화로 인해 웹 서버의 데이터 요청이 마비(Hang)되는 문제를 데이터베이스 튜닝 및 스로틀링(Throttling) 제어로 조치 완료했습니다.

## 작업 상세

### 1. SQLite 동기화 최적화 ([database.py](file:///c:/project/media_server/database.py))
- DB 연결 획득 시점(`SQLiteConnectionPool.get_connection`)에 `PRAGMA journal_mode=WAL;` 설정 직후 `PRAGMA synchronous = NORMAL;` 쿼리를 추가 실행하도록 개선했습니다.
- 이를 통해 커밋 동작 시 디스크 물리 기록(`fsync`) 대기를 배제하고 OS 캐시에 쓰기를 위임하여, 락 점유 절대 시간을 수 밀리초 수준으로 획기적으로 줄였습니다.

### 2. 스캐너 스로틀링(Throttling) 제어 ([core.py](file:///c:/project/media_server/tools/scanner/core.py))
- 백그라운드 스레드의 도서 1권 기록 완료 분기 시점마다 `time.sleep(0.05)` (50밀리초) 휴식을 강제 부여하였습니다.
- 스캐너 연산 도중에 미세 딜레이가 발생하면서 웹 서버가 요청하는 사용자 조회/진척도 기록용 쿼리 트랜잭션들이 중간 틈새를 통해 락 경쟁 없이 쾌적하게 실행될 수 있는 간격이 구축되었습니다.

### 3. 버그 문서화 및 이력 수집
- `./docs/bug/20260629_bugfix_scan_lock_web_starvation.md` 문서를 등록하였습니다.
- `workflow.md` 이력 관리 시스템에 작업 로그를 기록하고 `collect_docs.py` 통합 아카이브 프로세스를 집행하였습니다.
