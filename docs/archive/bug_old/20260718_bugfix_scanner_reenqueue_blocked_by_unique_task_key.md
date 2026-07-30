# 스캐너 재등록 차단 버그 수정

## 증상

- 홈 서버에서 동일 라이브러리에 대해 스캔 명령을 다시 내려도 스캐너 큐에 정상 등록되지 않는 경우가 발생했습니다.
- API 또는 로그상으로는 enqueue 성공처럼 보일 수 있었지만, 실제로는 새 pending 작업이 생성되지 않는 경로가 있었습니다.

## 원인

- scanner_tasks 테이블은 task_key에 UNIQUE 제약을 가지고 있습니다.
- services/scanner_queue.py의 enqueue는 pending/running만 중복 검사한 뒤 INSERT OR IGNORE를 수행하고, 실제 삽입 여부를 확인하지 않은 채 성공을 반환했습니다.
- 따라서 같은 task_key의 completed/failed/cancelled 이력이 남아 있으면 신규 삽입이 무시되어도 성공으로 오인될 수 있었습니다.

## 조치

- services/scanner_queue.py의 enqueue 로직을 수정했습니다.
- pending/running은 기존처럼 중복 거절합니다.
- completed/failed/cancelled 이력이 있으면 해당 행을 pending 상태로 재사용하면서 started_at, finished_at, stage, error_message를 초기화합니다.
- 실제 DB row 반영이 없으면 실패로 처리하도록 rowcount 검증을 추가했습니다.
- database.py의 풀 반환 로직을 수정해 close 시 rollback을 수행하도록 했습니다.
- 이로써 워커가 풀에서 재사용한 SQLite 연결의 오래된 읽기 스냅샷 때문에 신규 pending 작업을 보지 못하던 문제를 차단했습니다.
- manage.sh에서 스캐너 워커를 앱 health 응답 이후에 기동하도록 변경했습니다.
- 이로써 앱 startup의 DB 정리 및 auto-resume와 워커의 실제 큐 소비가 경쟁하면서 실행 중 스캔이 다시 pending으로 보이던 상태 불일치를 차단했습니다.

## 영향 파일

- services/scanner_queue.py
- database.py
- manage.sh

## 검증

- 로컬 임시 SQLite DB에서 completed 상태의 동일 task_key를 다시 enqueue했을 때 pending으로 정상 복구되는 회귀 검증을 수행했습니다.