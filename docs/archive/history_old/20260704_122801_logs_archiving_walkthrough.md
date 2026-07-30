---
title: Walkthrough - logs_archiving
project: BookOasis
category: history
date: 2026-07-04
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (로그 아카이빙 자동화 패치 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어 닫기 시 잔상 문제 해결과 더불어 **iOS Safari 등 특정 모바일 브라우저에서 세로 스크롤 시 터치 스크롤(쓸어내리기) 제스처가 물리적으로 막히던 사파리 터치 버그**를 완전히 조치했습니다. 추가로, **대시보드 '신규 추가 도서' 섹션에서 한 시리즈의 여러 책이 개별로 무더기 노출되던 화면 중복 현상을 최신 대표권 기준 시리즈 단위 묶음 카드로 그룹화**했습니다. 또한 **도서 우클릭 시 나오는 컨텍스트 메뉴에 '읽지 않은 상태로 변경 (0%)' 메뉴를 추가하여, 진행 정보를 즉시 삭제하고 최근 읽은 목록에서 소거하는 초기화 기능**을 완비했습니다. 마지막으로 **비대하게 용량이 커지던 scanner.log 및 lazy_scanner.log에 대해 10MB 도달 시 자동으로 zip 압축 및 회전시키는 아카이빙 자동화**를 이행했습니다.

## 변경 내용

### 1. scanner.log 및 lazy_scanner.log 자동 zip 아카이빙(Rotation) 연동
- **원인 발견**: `media_server.log`는 `ZipRotatingLogger`를 통해 10MB 단위로 안전하게 아카이빙되고 있었으나, `scanner.log`와 `lazy_scanner.log`는 일반 파일 추가 쓰기(`with open`) 형태로 설계되어 용량이 각각 164MB, 80MB로 무한 비대해지는 리스크가 있었습니다.
- **해결 방안**:
  - `utils/logger.py` 의 `ZipRotatingLogger` 클래스가 전달된 원본 파일명에 연동되어 `[파일명]_[timestamp].zip` 형태로 동적 아카이빙을 수행하도록 범용화 리팩토링을 수행했습니다.
  - `tools/scanner/logger.py` 및 `tools/lazy_scanner.py` 내부의 커스텀 출력 래퍼에 `ZipRotatingLogger(log_file_path, 10 * 1024 * 1024)`를 결합해, 10MB 초과 시 자동으로 zip 회전 압축 처리가 수행되도록 개선했습니다.
  - 패치 배포 완료 즉시, 원격 서버의 기존 164MB 및 80MB 분량의 로그들을 1회성 명령어로 즉각 zip 압축 아카이빙 처리하여 디스크 용량을 전량 회수했습니다.
  - 세부 내역을 [docs/bug/20260704_feature_logs_archiving.md](file:///c:/project/media_server/docs/bug/20260704_feature_logs_archiving.md)에 기술했습니다.

### 2. 도서 우클릭 컨텍스트 메뉴 '읽지 않은 상태로 변경 (0%)' 기능 개발
- **해결 방안**: 백엔드에 `/api/media/unread` [POST] API를 신설하여 세션 유저의 대상 `book_id`에 속한 진행 상태(`user_progress` 및 `user_reading_log` 통계) 레코드를 완벽히 `DELETE` 소거하도록 설계했습니다. (상세 내역 [docs/bug/20260704_feature_context_menu_unread_0.md](file:///c:/project/media_server/docs/bug/20260704_feature_context_menu_unread_0.md) 참고)

### 3. 대시보드 '신규 추가 도서' 시리즈 단위 그룹화 (묶음 처리)
- **해결 방안**: `reading_history_service.py` 의 `get_recently_added()` SQL 쿼리를 리팩토링하여, `series_name`이 채워진 행은 시리즈명으로 그룹핑(`GROUP BY`)하고, 비어있는 행은 각 고유 `id` 기준으로 개별 그룹핑하여 최신 대표권 ID 한 개만 노출하도록 `INNER JOIN`을 구현했습니다. (상세 내역 [docs/bug/20260704_bugfix_dashboard_recently_added_grouped.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_dashboard_recently_added_grouped.md) 참고)

### 4. iOS Safari 터치 제스처 스크롤 및 탭 브릿지 고도화 (사파리 특화 패치)
- **해결 방안**: `viewer.js` 내 `syncHotspotPointerEvents()` 함수를 통해 모바일 환경(<= 1200px)에서 세로 스크롤 작동 시 핫스팟 레이어 자체를 아예 `display: none`으로 제거했습니다.

## 검증 결과

### 1. 로그 아카이빙 자동화 및 디스크 용량 확보
- 원격 서버 배포 직후 강제 아카이빙 기동 결과, 기존의 164MB/80MB 거대 로그 파일이 `scanner.log_[timestamp].zip` / `lazy_scanner.log_[timestamp].zip`으로 즉각 성공적으로 아카이빙 압축되었습니다.
- 로그 폴더 내 디스크 용량이 대폭 전량 확보되었으며, 원본 로그 파일의 크기는 0 바이트로 리셋 및 신규 정상 작동 중입니다.
