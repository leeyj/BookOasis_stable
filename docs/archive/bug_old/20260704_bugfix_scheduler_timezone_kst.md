---
name: scheduler_dynamic_timezone
description: 환경설정 ➔ 일반설정에 시스템 타임존 드롭다운을 제공하여 글로벌 서버 백그라운드 스케줄 크론 실행 시 타임존 동적 매핑 구현
---

# 🕰️ [기능개선] 일반설정 내 시스템 타임존(Timezone) 선택 드롭다운 추가 및 백엔드 동적 스케줄링 연동

기존 스케줄러 시간대 하드코딩 고정 방식을 탈피하고, 다국적 글로벌 사용자를 지원하기 위해 **일반설정 메뉴에서 직접 타임존을 선택·저장하고 이를 백엔드 스케줄러(APScheduler)에 실시간으로 동적 갱신(Re-configure) 적용**하는 메커니즘을 이행했습니다.

## 1. 분석 및 설계
* **현상**: 서버 운영체제(OS)의 로컬 시간 설정(예: UTC)에 따라 웹 관리자 화면에서 지정한 스캔 주기가 어긋나게 작동하던 기존 문제의 근본 원인을 해소하기 위해, 고정 시간대 주입 대신 유저가 본인의 로컬 기준 시간대를 설정할 수 있도록 설계했습니다.
* **해결 방안**:
  * 프론트엔드 일반설정 화면에 주요 대륙별 표준 타임존 목록(Seoul, Tokyo, Shanghai, New York, Los Angeles, London, Paris 등)을 내장한 드롭다운 UI 요소를 신설했습니다.
  * 백엔드 API에서 `TIMEZONE` 키값 변경을 탐지하면 즉각 백그라운드 스케줄러를 동적으로 리빌드하고, 모든 등록된 작업(라이브러리 스캔, Lazy 표지 스캐너)을 신규 타임존 기준으로 리셋하도록 기능을 조율했습니다.

## 2. 세부 조치 내용
* **[general_tab.html](file:///c:/project/media_server/templates/components/settings/general_tab.html)**:
  * '시스템 타임존 (Timezone)' 드롭다운 셀렉트 박스를 탑재했습니다. (기본값: `UTC`)
* **[general.js](file:///c:/project/media_server/static/js/settings/general.js)**:
  * 일반설정 최초 조회 시 DB 속성 `TIMEZONE` 값을 렌더링하고, 설정 저장 시 변경된 값을 함께 취합해 업데이트 API로 전송하게 연동했습니다.
* **[api/routes/settings_routes.py](file:///c:/project/media_server/api/routes/settings_routes.py)**:
  * `key == 'TIMEZONE'` 속성의 추가/갱신 처리가 들어오면 백그라운드 스케줄러 갱신 함수(`SchedulerService.reload_all_jobs()`)가 즉각적으로 동시 실행되도록 필터를 추가했습니다.
* **[services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py)**:
  * 백그라운드 스케줄러를 최초 기동하거나 설정값 변경으로 인해 스케줄이 재적재될 때, DB 설정값의 `TIMEZONE`을 읽어와 `scheduler.configure(timezone=ZoneInfo(tz_str))`를 통해 실시간으로 실행 타임존 구조를 동적 갱신 및 보정합니다.

## 3. 수정 파일 목록
* [templates/components/settings/general_tab.html](file:///c:/project/media_server/templates/components/settings/general_tab.html) (타임존 UI 추가)
* [static/js/settings/general.js](file:///c:/project/media_server/static/js/settings/general.js) (타임존 연동 및 API 전송 추가)
* [api/routes/settings_routes.py](file:///c:/project/media_server/api/routes/settings_routes.py) (API 트리거 갱신 조건 확장)
* [services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py) (스케줄러 동적 타임존 리컴파일 추가)
