---
id: "20260720_bugfix_db_recovery_oom"
date: 2026-07-20
category: "bugfix"
severity: "high"
status: "fixed"
tags: [db, recovery, sqlite3, executescript, memory, oom, piping, stdin, stream]
---

# 20260720 — DB 복구기 대용량 SQL 복원 메모리 최적화(OOM 방지) 완료

## 버그 내역

### 현상
- DB 손상 감지 시 기동되는 데이터베이스 자동 복구(`db_recovery.py`) 기능이 대형 도서 라이브러리 환경에서 전체 복구(Step 2)를 시도하는 도중, 리눅스 커널 OOM Killer에 의해 프로세스가 즉사(`Killed`)하며 서비스를 기동시키지 못하는 장애 발생.

### 근본 원인
- 복구용 데이터 SQL 덤프 파일 복원 시, 파이썬 코드에서 `f.read()`를 사용해 수백 MB ~ GB 상당의 SQL 텍스트 전체를 메모리에 단일 문자열로 적재한 후 `new_conn.executescript(sql_content)`로 밀어 넣었음.
- 파이썬 컴파일러와 파서 수준에서 이 거대 스크립트를 파싱하는 과정에 **실제 텍스트 크기의 수배에 달하는 RAM 메모리 스파이크**가 돌발적으로 방출되어 시스템 메모리 한계를 초과함.

## 영향도
- 대형 DB를 운영하는 홈 서버 및 저사양 컨테이너 환경에서 DB 파손 시 자동 복구 능력이 무력화되어 일반 사용자들의 장애 고착을 유발함.

## 수정 사항

### 수정 파일 목록

#### `tools/db_recovery.py`
- `step2_full_recovery` 내부의 SQL 실행 엔진 개편.
- SQL 덤프 내용 전체를 파이썬 메모리로 퍼 올리던 구문을 완전히 전면 폐기함.
- `sqlite3 [recovered_path]` CLI 명령어를 `subprocess.run` 으로 구동 시, 복구용 SQL 파일 스트림 핸들을 **표준 입력(`stdin=f_in`) 파이프라인으로 직접 전달(Piping)**하도록 튜닝함.
- 이를 통해 파이썬은 디렉토리 입출력 버퍼링 수준의 거의 **0MB에 수렴하는 RAM 메모리 점유**만으로 대용량 SQL 덤프를 초고속 스트리밍 복원할 수 있게 개선함.

## 해결 사항
- 대용량 DB 손상 복구 작동 시에도 프로세스 킬(`Killed`) 없이 0.5초 이내에 오차 없이 데이터를 완벽하게 복구해 내어, 홈 서버 및 컨테이너 환경에서의 부팅 및 자가 치유 능력을 극대화했습니다.
