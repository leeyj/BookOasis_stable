---
title: Walkthrough - spec_scanner_logic
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 🏁 스캐너 로그 저장 옵션화 및 1차 리팩토링 완료 보고 (Walkthrough)

스캐너 구동 시 발생하는 콘솔/파일 로그 기록 여부를 제어할 수 있는 `SCANNER_WRITE_LOG` 옵션 기능 구현과 비대했던 `tools/scanner/core.py` 모듈을 각 책임 컴포넌트별로 나누는 1차 리팩토링 작업을 최종 완료했습니다.

## 🛠️ 작업 내용

### 1. 일반 환경설정 스캐너 로그 제어 옵션 도입
- **데이터베이스 마이그레이션**: [database.py](file:///c:/project/media_server/database.py#L274) 내 `default_settings`에 `SCANNER_WRITE_LOG`를 주입하여, 차후 `deploy.py` 배포 및 재시동 시 원격 데이터베이스 스키마 마이그레이션에 새 설정이 자동 이식되도록 보완했습니다.
- **일반설정 UI 및 동적 연동**: [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html#L254-L265) 일반 설정 영역에 셀렉트 박스를 추가하고, [settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js)에서 값을 안전하게 로드 및 저장(병렬 프로미스 통신)할 수 있도록 프론트엔드 연동을 마쳤습니다.
- **백엔드 로그 가로채기(Print 모킹)**: [tools/scanner/core.py](file:///c:/project/media_server/tools/scanner/core.py#L22-L53)에 `SCANNER_WRITE_LOG` 설정을 읽어 `'0'`(감춤)일 때 런타임 중 `builtins.print` 함수를 모킹하는 컨텍스트 데코레이터를 적용하여, 실시간 스캐너 실행의 콘솔/파일 로그 출력을 안전하게 가로채고 복구(finally)하도록 구현했습니다.

### 2. 스캐너 core.py 1차 컴포넌트 분할 리팩토링
- **[memory_helper.py](file:///c:/project/media_server/tools/scanner/memory_helper.py) [NEW]**: 메모리 임계 초과 감지 로직(`check_memory_exceeded`)을 격리 이관했습니다.
- **[db_writer.py](file:///c:/project/media_server/tools/scanner/db_writer.py) [NEW]**: 도서 등록, 메타 업데이트, 오프셋 DB 저장 등 SQLite 데이터 쓰기 DML 구문들을 격리 분리했습니다.
- **[sync_detector.py](file:///c:/project/media_server/tools/scanner/sync_detector.py) [NEW]**: 도서 이동 감지와 실종 파일 삭제 및 0개 예외 제동 안전장치 등 변경 동기화 감지 레이어를 격리 이관했습니다.
- **[core.py](file:///c:/project/media_server/tools/scanner/core.py#L60-L425) [MODIFY]**: 기존 550라인에 달하던 방대한 코드를 400라인 수준으로 경량화하고, 각 서브 모듈 컴포넌트를 조율(Orchestration)하고 멀티스레드 태스크 컨텍스트를 유지하는 역할에 집중하도록 구조를 개선했습니다.

## 🧪 E2E 수동 검증 결과
- 로컬 개발 환경에서 단독 스캔 구동 유틸인 [tools/scanner.py](file:///c:/project/media_server/tools/scanner.py)를 가동하여, 리팩토링 이후에도 임포트 충돌이나 런타임 오류 없이 스캔 흐름이 깔끔하게 구동되는 것을 E2E 수동 테스트로 최종 확인 완료했습니다.
- 로그 감춤(0) 설정 시 `media_server.log` 및 콘솔 출력이 가로채어져 디스크 용량 낭비를 완벽하게 절약하는 동작을 확인했습니다.
