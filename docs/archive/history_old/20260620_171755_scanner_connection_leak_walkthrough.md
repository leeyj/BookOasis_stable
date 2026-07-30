---
title: Walkthrough - scanner_connection_leak
project: BookOasis
category: history
date: 2026-06-20
type: walkthrough
---
# 스캐너 DB 커넥션 누수 조치 (Walkthrough)

스캐너(`scan_library`) 정상 흐름 종료부에서 데이터베이스 커넥션 닫기가 누락되어 웹 서버의 커넥션 풀을 소진시키고 API 500 장애를 유발하던 누수 버그를 최종 조치하였습니다.

## 변경 사항 요약 (Changes)

### 백엔드 스캐너

#### [MODIFY] [scanner.py](file:///c:/project/media_server/tools/scanner.py)
- **자원 회수 보장**: `scan_library` 함수의 물리 스캔 완료 및 삭제 감시 처리 루프 뒤에 `conn.commit()` 및 `conn.close()` 구문을 확실하게 추가해 주었습니다.
- 이로써 각 스캔 세션이 끝날 때 미결 변경 사항이 반영되고 DB 커넥션 자원이 커넥션 풀로 정상 반환되도록 흐름이 정상화되었습니다.

## 검증 결과 (Verification Results)
- 수정본을 원격 홈 서버에 배포 완료했습니다.
- 로컬 진단 스크립트를 통해 `/api/media/libraries` 가 타임아웃 및 500에러 없이 200 OK와 올바른 도서관 JSON 정보를 즉각 반환함을 최종 교차 확인 완료했습니다.
