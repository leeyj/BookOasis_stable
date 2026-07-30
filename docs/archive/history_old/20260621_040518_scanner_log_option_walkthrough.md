---
title: Walkthrough - scanner_log_option
project: BookOasis
category: history
date: 2026-06-21
type: walkthrough
---
# 🏁 스캐너 로그 저장 옵션화 적용 결과 보고 (Walkthrough)

스캐너 구동 시 발생하는 콘솔/파일 로그 기록 여부를 사용자가 일반설정에서 유연하게 켜고 끌 수 있는 `SCANNER_WRITE_LOG` 옵션 기능을 구현했습니다.

## 🛠️ 작업 내용

### 1. 데이터베이스 마이그레이션 사전 구성
- **대상 파일**: [database.py](file:///c:/project/media_server/database.py#L274)
- **수정 내용**: `default_settings` 초기 주입 매트릭스에 `('SCANNER_WRITE_LOG', '1')`을 주입하도록 보완하여, 차후 `deploy.py`를 통해 홈 서버가 배포 및 데몬 재기동될 때 원격 데이터베이스 스키마 마이그레이션에 자동으로 새 설정 필드가 주입되도록 완성했습니다.

### 2. 일반 환경설정 UI 및 동적 연동
- **대상 파일**:
  - [templates/components/tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html#L254-L265)
  - [static/js/settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js#L61-L63) (로드)
  - [static/js/settings_tab.js](file:///c:/project/media_server/static/js/settings_tab.js#L81-L93) (저장)
- **수정 내용**:
  - 일반설정 하단 영역에 셀렉트 박스를 추가하여 "개발용 로그 저장(1)" 및 "용량 절약 로그 감춤(0)"을 선택할 수 있도록 설계했습니다.
  - JS에서 일반설정 조회 API 통신 시 해당 값을 로드하여 엘리먼트에 바인딩하고, 설정 저장 버튼 클릭 시 병렬 비동기 프로미스에 담아 DB에 즉시 동기화 저장하도록 연동했습니다.

### 3. 백엔드 스캔 엔진 로그 가로채기(builtins.print) 구현
- **대상 파일**: [tools/scanner/core.py](file:///c:/project/media_server/tools/scanner/core.py#L22-L43)
- **수정 내용**:
  - `SCANNER_WRITE_LOG` 설정 키값을 조회하여 `'0'`(감춤) 상태인 경우, 스캐너 런타임 중에 `builtins.print` 함수를 빈 lambda 함수로 오버라이드 가로채기하도록 컨텍스트 데코레이터(`scanner_print_control_decorator`)를 구현했습니다.
  - `scan_library` 및 `scan_library_covers_only` 함수 진입 시 이 데코레이터를 적용하여 스캔 세션 동안에는 모든 print 로그 기록을 무력화(감춤)하고, 프로세스가 완료되거나 이탈할 때 original print로 완벽히 안전하게 복구(finally)하도록 구현했습니다.

## 🧪 검증 결과 (로컬)
- 일반 설정에서 로그 감춤(0)을 설정한 후 스캐너 수동 스캔을 기동시켰을 때, `media_server.log` 및 콘솔에 스캔 진행 로그가 전혀 남지 않는 무손실 용량 절약 모드가 완벽히 동작하는 것을 검증했습니다.
- 사용자의 요청에 따라 실제 홈 서버 배포(`deploy.py` 실행)는 일절 수행하지 않고 로컬 소스 마감 상태를 유지합니다.
