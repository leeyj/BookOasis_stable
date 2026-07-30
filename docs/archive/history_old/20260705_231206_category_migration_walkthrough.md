---
title: Walkthrough - category_migration
project: BookOasis
category: history
date: 2026-07-05
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (스케줄러 KST 타임존 패치 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어 닫기 시 잔상 문제 해결과 더불어 **iOS Safari 등 특정 모바일 브라우저에서 세로 스크롤 시 터치 스크롤(쓸어내리기) 제스처가 물리적으로 막히던 사파리 터치 버그**를 완전히 조치했습니다. 추가로, **대시보드 '신규 추가 도서' 섹션에서 한 시리즈의 여러 책이 개별로 무더기 노출되던 화면 중복 현상을 최신 대표권 기준 시리즈 단위 묶음 카드로 그룹화**했습니다. 또한 **도서 우클릭 시 나오는 컨텍스트 메뉴에 '읽지 않은 상태로 변경 (0%)' 메뉴를 추가하여, 진행 정보를 즉시 삭제하고 최근 읽은 목록에서 소거하는 초기화 기능**을 완비했습니다. 마지막으로 **비대하게 용량이 커지던 scanner.log 및 lazy_scanner.log에 대해 10MB 도달 시 자동으로 zip 압축 및 회전시키는 아카이빙 자동화**를 이행했으며, **APScheduler에 타임존을 KST(Asia/Seoul)로 강제 지정하여 크론 백그라운드 주기 실행이 해외 서버 시간 기준으로 지연 동작하던 문제를 완치**했습니다.

## 변경 내용

### 1. 백그라운드 스케줄러(APScheduler) 한국 표준시(KST) 기준 동작 고정
- **원인 발견**: 스케줄러 인스턴스 초기화 시 타임존이 설정되지 않아 OS의 로컬 타임존 환경설정(리눅스 서버들의 기본값인 UTC)을 상속받았습니다. 이로 인해 한국 시간 기준 매일 새벽 5시(`0 5 * * *`) 스케줄이 UTC 새벽 5시(한국 오후 2시)로 잡혀 백그라운드 스캔이 지연/누락되는 버그가 있었습니다.
- **해결 방안**: 
  - [services/scheduler_service.py](file:///c:/project/media_server/services/scheduler_service.py) 에서 `BackgroundScheduler` 인스턴스 생성 시 `timezone=ZoneInfo('Asia/Seoul')` 속성을 명시적으로 고정했습니다.
  - 이를 통해 모든 라이브러리 크론 스케줄과 Lazy 표지 스캐너 주기가 서버 시간과 무관하게 항상 한국 시간(KST)을 기준으로 일치되어 백그라운드에서 구동됩니다.
  - 추가로 [tools/lazy_scanner.py](file:///c:/project/media_server/tools/lazy_scanner.py) 내부 로깅 설정용 DB 커넥션 `sqlite3.connect` 연결 시 `timeout=1.0` 안전망을 설계하여, 혹시 모를 Gunicorn과의 SQLite 락 경합 시 스캐너 기동이 블로킹된 상태로 무한 대기하는 현상을 완벽히 방지했습니다.
  - 세부 내역을 [docs/bug/20260704_bugfix_scheduler_timezone_kst.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_scheduler_timezone_kst.md)에 기술했습니다.

### 2. scanner.log 및 lazy_scanner.log 자동 zip 아카이빙(Rotation) 연동
- **해결 방안**: `ZipRotatingLogger`가 임의의 로그명에 연동되도록 리팩토링하고 스캐너 및 lazy_scanner 인쇄 로깅 핸들러에 통합 결합했습니다. (상세 내역 [docs/bug/20260704_feature_logs_archiving.md](file:///c:/project/media_server/docs/bug/20260704_feature_logs_archiving.md) 참고)

### 3. 도서 우클릭 컨텍스트 메뉴 '읽지 않은 상태로 변경 (0%)' 기능 개발
- **해결 방안**: 백엔드에 `/api/media/unread` [POST] API를 신설하여 독서 진행 상태 테이블의 기록을 즉시 소거하도록 처리했습니다.

### 4. 대시보드 '신규 추가 도서' 시리즈 단위 그룹화 (묶음 처리)
- **해결 방안**: `reading_history_service.py` 내의 `get_recently_added()` 쿼리에 `GROUP BY`와 `INNER JOIN` 대표 ID 필터링을 결합하여, 시리즈별 가장 최신에 스캔된 1개의 도서 카드만 대시보드에 나타나도록 변경했습니다.

## 검증 결과

### 1. 스케줄러 타임존 매핑 확인
- 스케줄러가 재시작될 때 로그를 검증한 결과, 모든 기존 라이브러리 스캔 작업 및 Lazy 표지 추출 작업들이 한국 시간(Asia/Seoul)으로 올바르게 보정 및 등록됩니다.
- 설정된 새벽 크론 시간에 맞추어 백그라운드 스캐너가 지연 없이 제때 깨어나 자동 작업을 집행하게 됩니다.
