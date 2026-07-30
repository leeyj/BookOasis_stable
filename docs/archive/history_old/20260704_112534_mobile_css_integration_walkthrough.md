---
title: Walkthrough - mobile_css_integration
project: BookOasis
category: history
date: 2026-07-04
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (만화 뷰어 이미지 고스팅 버그 조치 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어를 닫을 때 이전 책의 잔상(Ghosting)이 수초 동안 노출되던 화면 깜빡임 버그를 해결했습니다.

## 변경 내용

### 1. 웹 템플릿 연동 및 햄버거 버튼 추가
- [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html) 파일의 기존 스타일시트 로드 구문 밑에 `mobile.css`를 로드하는 코드를 추가했습니다.
  - 미디어 쿼리 속성: `media="screen and (max-width: 1200px)"` (태블릿 가로/프로 라인 대응을 위해 **1200px**로 한계 확장)
- 사이드바 헤더 영역에 모바일 전용 햄버거 메뉴 토글 버튼(`btn-sidebar-toggle`)을 추가했습니다.
- 메인 콘텐츠 상단 영역(`.library-header`)에 데스크톱 전용 사이드바 토글 버튼(`btn-sidebar-toggle-desktop`)을 신규 배치했습니다.

### 2. 데스크톱 사이드바 접기 제어 (JS & CSS)
- **접기 동작 구현**: 자바스크립트 `toggleDesktopSidebar()` 함수를 구현하여 데스크톱 버튼 클릭 시 `.library-sidebar`에 `.collapsed` 클래스를 토글하도록 구현했습니다.
- **상태 기억 기능**: `localStorage`를 연동하여 사용자가 사이드바를 접어둔 상태를 영구 기억(`desktopSidebarCollapsed`)하고, 페이지 새로고침 시에도 동일한 상태가 유지되도록 로직을 추가했습니다.
- [style.css](file:///c:/project/media_server/static/css/style.css)에 사이드바 접힘 상태 스타일(`.library-sidebar.collapsed`)을 정의하여 너비(`width: 0`, `min-width: 0`)와 투명도를 소거하고, `transition` 애니메이션 효과를 부여해 부드럽게 슬라이드 닫기/열기가 되도록 연출했습니다.

### 3. 만화 뷰어 고스팅(이전 이미지 잔류) 버그 픽스
- **원인 발견**: 뷰어를 닫을 때(`closeMediaViewer`) 만화 뷰어의 DOM 내부 영역(`.comic-image-wrapper`) 및 작동 중인 로딩 타이머(`comicLoadingTimer`)를 명시적으로 비워주는 파괴자(Cleanup)가 누락되어 다음 책을 열 때 이전 책 이미지가 깜빡이며 겹쳐 보이는 현상이 발생했습니다.
- **해결 방안**: 
  - `viewer/renderer.js`에 뷰어 정리 함수 `clearComicViewer()`를 신규 구현하여 `.comic-image-wrapper` 내부 HTML을 청소하고, `IntersectionObserver` 관찰을 중단하며, 잔류 로딩 타이머를 해제하도록 조치했습니다.
  - `viewer_comic.js`를 통해 해당 함수를 window 및 외부로 re-export 했습니다.
  - `viewer.js`의 `closeMediaViewer` 최상단에서 `clearComicViewer()`를 명시적으로 실행하여 뷰어가 닫힐 때 이전 잔상을 즉각 휘발시키도록 연출했습니다.
  - 관련 상세 문서를 [docs/bug/20260704_bugfix_comic_viewer_ghosting.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_comic_viewer_ghosting.md)에 상세히 기술했습니다.

### 4. 스타일시트 리팩토링 ([mobile.css](file:///c:/project/media_server/static/css/mobile.css))
- **`!important` 안티패턴 제거**: HTML 마크업 상에 인라인 스타일(`style="..."`)이 강하게 박혀있어 예외적으로 강제 오버라이딩이 불가피한 속성들을 제외하고, 일반적인 모든 컴포넌트 클래스 스타일(`.volume-card`, `.btn-read`, `.settings-tab-btn`, `.detail-header-panel` 등)의 불필요한 `!important`를 완전 제거했습니다.
- **데스크톱 접힘 상태(.collapsed) 모바일 해상도 무시(오버라이드)**: 사용자가 데스크톱에서 사이드바를 접은 상태로 모바일 화면으로 강제 리사이징하더라도 모바일 전용 상단 햄버거 메뉴가 화면에서 증발하지 않도록, `mobile.css`에 `.library-sidebar.collapsed` 클래스의 모든 접힘 속성을 `width: 100%`, `opacity: 1`, `pointer-events: auto` 등으로 초기화시키는 모바일 예외 스타일을 신규 주입했습니다.

## 검증 결과

### 1. 뷰어 이미지 고스팅 버그 개선
- 만화책 A를 본 뒤 닫기 버튼을 누르면 뷰어 내부 DOM이 즉각 청소됩니다.
- 이어서 다른 만화책 B를 열면, 새로운 B의 첫 페이지 이미지 다운로드가 준비되는 동안 로딩 스피너 및 프로그래스 상태가 온전히 지연 시간 없이 노출되며, 이전 A의 만화 이미지가 튀는 현상이 완벽하게 방지됩니다.

### 2. 데스크톱 및 모바일 뷰 통합 동작
- 사이드바를 접은 상태로 화면 크기를 늘리거나 줄여도 모바일 메뉴 및 데스크톱 메뉴가 올바르게 복원되고 햄버거 토글이 매끄럽게 작동합니다.
- `mobile.css` 파일은 핵심 인라인 속성을 제외한 모든 구문에서 `!important`가 정리되어 CSS 개발 정합성이 크게 개선되었습니다.
