---
title: Walkthrough - context_menu_unread_0
project: BookOasis
category: history
date: 2026-07-04
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (우클릭 읽지않음 초기화 기능 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어 닫기 시 잔상 문제 해결과 더불어 **iOS Safari 등 특정 모바일 브라우저에서 세로 스크롤 시 터치 스크롤(쓸어내리기) 제스처가 물리적으로 막히던 사파리 터치 버그**를 완전히 조치했습니다. 추가로, **대시보드 '신규 추가 도서' 섹션에서 한 시리즈의 여러 책이 개별로 무더기 노출되던 화면 중복 현상을 최신 대표권 기준 시리즈 단위 묶음 카드로 그룹화**했습니다. 마지막으로 **도서 우클릭 시 나오는 컨텍스트 메뉴에 '읽지 않은 상태로 변경 (0%)' 메뉴를 추가하여, 진행 정보를 즉시 삭제하고 최근 읽은 목록에서 소거하는 초기화 기능**을 완비했습니다.

## 변경 내용

### 1. 도서 우클릭 컨텍스트 메뉴 '읽지 않은 상태로 변경 (0%)' 기능 개발
- **개발 배경**: 사용자가 실수로 책을 열었거나 독서 히스토리를 초기화하고 싶을 때, 강제로 진척도를 0%로 만들고 '최근 읽은 도서' 및 '이어읽기' 기록에서 바로 빼버릴 수 있는 명시적인 방법이 제공되지 않았습니다.
- **해결 방안**: 
  - 백엔드에 `/api/media/unread` [POST] API를 신설하여 세션 유저의 대상 `book_id`에 속한 진행 상태(`user_progress` 및 `user_reading_log` 통계) 레코드를 완벽히 `DELETE` 소거하도록 트랜잭션을 설계했습니다.
  - 프론트엔드 컨텍스트 메뉴 HTML(`context_menus.html`)에 '읽지 않은 상태로 변경 (0%)' 요소를 추가하고, 클릭 시 이펙트가 돌아가는 동작 함수(`triggerMarkAsUnreadAction`)를 `book_context_menu.js`에 작성해 글로벌 바인딩했습니다.
  - 성공적으로 초기화되면 대시보드(`loadDashboardData`), 최근 읽은 목록(`loadReadingHistory`), 도서 상세 목록(`openBookDetail` / `loadBooksList`)을 자동으로 연쇄 트리거 리로드하여 화면에 실시간으로 반영시킵니다.
  - 세부 내역을 [docs/bug/20260704_feature_context_menu_unread_0.md](file:///c:/project/media_server/docs/bug/20260704_feature_context_menu_unread_0.md)에 기술했습니다.

### 2. 대시보드 '신규 추가 도서' 시리즈 단위 그룹화 (묶음 처리)
- **해결 방안**: `reading_history_service.py` 의 `get_recently_added()` SQL 쿼리를 리팩토링하여, `series_name`이 채워진 행은 시리즈명으로 그룹핑(`GROUP BY`)하고, 비어있는 행은 각 고유 `id` 기준으로 개별 그룹핑하여 최신 대표권 ID 한 개만 노출하도록 `INNER JOIN`을 구현했습니다. (상세 내역 [docs/bug/20260704_bugfix_dashboard_recently_added_grouped.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_dashboard_recently_added_grouped.md) 참고)

### 3. iOS Safari 터치 제스처 스크롤 및 탭 브릿지 고도화 (사파리 특화 패치)
- **해결 방안**: 
  - `viewer.js` 내 `syncHotspotPointerEvents()` 함수를 통해 모바일 환경(<= 1200px)에서 세로 스크롤 작동 시 핫스팟 레이어 자체를 아예 `display: none`으로 제거했습니다.
  - [tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css) 에 `.comic-scroll-img` 속성으로 `pointer-events: none;`, `-webkit-user-drag: none;`, `user-select: none;`을 선언하여, 손가락 드래그 시 이미지 선택을 차단하고 곧바로 부모의 스크롤바 이동으로 100% 제스처를 전달시켰습니다.
  - 스크롤 컨테이너인 `.comic-image-wrapper` 에 `-webkit-overflow-scrolling: touch;`를 선언해 iOS 고유의 매우 미려하고 부드러운 **GPU 가속 관성 스크롤(Momentum scrolling)**을 활성화했습니다.

### 4. 만화 뷰어 고스팅(이전 이미지 잔류) 버그 픽스
- **해결 방안**: 뷰어 종료 시(`closeMediaViewer`) 호출할 `clearComicViewer()` 파괴자를 신규 구현해 만화 렌더러 DOM 내부 이미지를 초기화하고 잔류 타이머를 정리하여 뷰어 재오픈 시 이전 잔상이 튀는 현상을 막았습니다.

## 검증 결과

### 1. 읽지 않은 상태로 변경 (0%) 기능 테스트
- 대시보드의 '최근 읽은 도서' 혹은 상세 도서 볼륨 목록에서 도서 카드를 우클릭하면 신규 추가된 '읽지 않은 상태로 변경 (0%)' 메뉴가 정상 노출됩니다.
- 메뉴 클릭 시 즉각적인 성공 토스트 팝업이 노출되며, 해당 도서는 최근 읽은 목록에서 리렌더링과 동시에 즉각 사라집니다.
- 상세 볼륨 리스트에서는 진척률 배지가 소거되고 0% 기본 카드로 초기화 갱신됩니다.
