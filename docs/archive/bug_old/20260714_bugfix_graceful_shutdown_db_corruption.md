---
title: "시스템 업데이트 시 SQLite DB 손상 방지 - Graceful Shutdown 구현"
project: "BookOasis"
category: "bugfix"
date: 2026-07-14
tags: [db, sqlite, graceful-shutdown, docker, wal, progress]
---

# 시스템 업데이트 시 SQLite DB 손상 방지

## 버그 내역

사용자가 뷰어에서 책을 열어 읽고 있는 상태에서 시스템 업데이트(Docker 컨테이너 재시작, manage.sh restart 등)를 수행하면 SQLite 데이터베이스에 오류가 발생하는 현상이 다수 보고됨.

### 주요 증상
- 재시작 후 `database is locked` 또는 `database disk image is malformed` 오류 발생
- WAL(-wal) / SHM(-shm) 파일이 불완전한 상태로 남아 있음
- 읽기 진행률이 유실되거나 부분 기록됨

## 영향도

- **심각도**: 높음
- **영향 범위**: 모든 사용자 환경 (Docker, 네이티브 설치 모두)
- **발생 빈도**: 시스템 업데이트/재시작 시마다 발생 가능

## 근본 원인

1. **Graceful Shutdown 핸들러 부재**: 서버 프로세스가 SIGTERM을 수신해도 커넥션 풀의 활성 연결을 정리하거나 WAL 체크포인트를 수행하지 않음
2. **Docker 종료 유예 시간 미설정**: 기본 10초 후 SIGKILL 강제 종료
3. **클라이언트 진행률 디바운스**: 3초 대기 중 서버가 죽으면 진행률 유실
4. **SQLite WAL 모드 구조적 특성**: `synchronous = NORMAL` 설정에서 비정상 종료 시 WAL 파일 불완전 가능

## 수정사항

### 서버 측
- **database.py**: `SQLiteConnectionPool.shutdown()` 메서드 추가 — 유휴 커넥션에 WAL 체크포인트(TRUNCATE) 수행 후 물리적 닫기. `shutdown_all_pools()` 함수로 전체 풀 일괄 종료.
- **core.py**: `atexit.register(shutdown_all_pools)` 및 `SIGTERM`/`SIGINT` 시그널 핸들러 등록. 스케줄러 중지 → DB 풀 shutdown → 프로세스 종료 순서 보장.

### Docker 설정
- **Dockerfile**: `STOPSIGNAL SIGTERM` 명시, Gunicorn에 `--graceful-timeout 15` 옵션 추가
- **docker-compose.yml**: `stop_grace_period: 30s` 추가

### 클라이언트 측
- **viewer_progress.js**: `pagehide` 및 `visibilitychange` 이벤트 리스너 추가 — 페이지 이탈/탭 전환 시 대기 중인 진행률을 즉시 서버로 전송

## 수정 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `database.py` | `shutdown()` / `shutdown_all_pools()` 추가 |
| `core.py` | `atexit` / `signal` 핸들러 등록 |
| `Dockerfile` | `STOPSIGNAL SIGTERM`, `--graceful-timeout 15` 추가 |
| `docker-compose.yml` | `stop_grace_period: 30s` 추가 |
| `static/js/viewer_progress.js` | `pagehide` / `visibilitychange` 핸들러 추가 |

## 해결 확인 방법

1. 뷰어에서 책을 열어 읽는 중 서버 재시작 수행
2. 서버 로그에 `[DB-Shutdown] WAL 체크포인트 완료` 메시지 출력 확인
3. 재시작 후 DB 무결성 에러 없이 정상 기동 확인
4. 읽기 진행률이 보존되는지 확인
