# 스캔 후 DB 튜닝 경쟁으로 인한 간헐 스캔 실패 수정

## 증상

- 홈 서버 및 커뮤니티 사용자 환경에서 스캔이 간헐적으로 실패했습니다.
- 운영 로그에는 `disk I/O error`, `file is not a database` 같은 SQLite 계열 예외가 섞여 기록되었습니다.

## 원인

- 스캔 성공 직후 `tools/scanner/core.py`, `tools/scanner/engine.py`가 백그라운드 `database.optimize_database()`를 매번 자동 실행하고 있었습니다.
- `optimize_database()`는 `ANALYZE`, `REINDEX`, `VACUUM`을 수행합니다.
- 큐 기반 워커는 직전 스캔 종료 직후 곧바로 다음 스캔을 시작할 수 있으므로, 다음 스캔이 같은 DB 파일에 접근하는 시점과 백그라운드 튜닝이 겹치는 경쟁 상태가 발생했습니다.
- 운영 로그에서 실제 스캔 실패 직전후로 `Database defragmentation and optimization tuning successful!`, `disk I/O error`, `file is not a database`가 인접하게 관찰되었습니다.

## 조치

- 스캔 경로에서 매 스캔 후 자동 DB 튜닝 스레드 실행을 제거했습니다.
- DB 최적화는 여전히 삭제/이관 등 관리성 작업에서만 별도로 수행됩니다.

## 영향 파일

- tools/scanner/core.py
- tools/scanner/engine.py

## 검증 근거

- 운영 서버 로그에서 실패 시점과 자동 DB 튜닝 로그가 직접 인접한 것을 확인했습니다.
- 코드상으로도 스캔 완료 직후 비동기 `VACUUM`이 항상 기동되도록 구현돼 있음을 확인했습니다.