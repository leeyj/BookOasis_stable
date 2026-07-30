---
title: Walkthrough - scanner_db_connection_ref_error
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 스캐너 DB 연결 함수 오류 조치 (Walkthrough)

스캐너 실행 스크립트(`run_sync_scanner`) 내에서 정의되지 않은 함수(`get_db_connection`)를 참조하여 발생하던 구문 버그를 최종 수정하였습니다.

## 변경 사항 요약 (Changes)

### 백엔드 스캐너

#### [MODIFY] [scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **커넥션 획득 로직 수정**: `run_sync_scanner` 함수 내부에서 `get_db_connection(DB_PATH)` 호출 대신 `database.get_connection('general')` 및 `database.get_connection('adult')`를 사용하도록 수정하였습니다.
- 이로써 `database.py` 모듈 내에 구현되어 있는 안정적인 커넥션 풀을 활용하여 정상 작동하게 됩니다.

## 검증 결과 (Verification Results)
- 컴파일 린트 에러가 완전히 해소되었습니다.
- 테스트 시 데이터베이스 연결이 정상적으로 수립되고 NameError가 재발하지 않음을 확인하였습니다.
