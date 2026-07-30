---
title: Walkthrough - mobile_css_integration
project: BookOasis
category: history
date: 2026-07-04
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (모바일 터치 스크롤 패치 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어 닫기 시 잔상 문제 해결과 더불어 **모바일 기기에서 세로 스크롤 방식으로 만화/소설/PDF 감상 시 터치 스크롤(쓸어내리기) 제스처가 막히던 심각한 사용성 버그**를 조치했습니다.

## 변경 내용

### 1. 웹 템플릿 연동 및 햄버거 버튼 추가
- [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html) 파일의 기존 스타일시트 로드 구문 밑에 `mobile.css`를 로드하는 코드를 추가했습니다.
  - 미디어 쿼리 속성: `media="screen and (max-width: 1200px)"` (태블릿 가로/프로 라인 대응을 위해 **1200px**로 한계 확장)
- 사이드바 헤더 영역에 모바일 전용 햄버거 메뉴 토글 버튼(`btn-sidebar-toggle`)을 추가했습니다.

### 2. 모바일 터치 제스처 스크롤 브릿지 구현 (사용성 버그 패치)
- **원인 발견**: 뷰어 전면에 배치되어 클릭 이벤트(메뉴 활성/비활성, 탭 화면 클릭)를 가로채는 핫스팟 레이어(`#common-viewer-hotspot`)가 `pointer-events: auto`로 화면을 덮고 있어서, 모바일 환경의 손가락 쓸기 스크롤 제스처가 뒷배경 이미지 래퍼로 전혀 전달되지 않는 상태였습니다.
- **해결 방안**: 
  - `viewer.js`에 `initTouchScrollBridge()` 함수를 추가하여 핫스팟 레이어에 `touchstart`, `touchmove`, `touchend` 터치 이벤트 리스너를 결합했습니다.
  - `touchstart`에서 활성화된 뷰어 타입(만화/텍스트/PDF)에 맞춰 타겟 스크롤 엘리먼트(예: `.comic-image-wrapper`, `#txt-scroll-wrapper` 등)를 특정합니다.
  - `touchmove` 발생 시 손가락 터치 이동 거리(`deltaY`)를 계산해 타겟 엘리먼트의 `scrollTop` 속성으로 동적 변환하여 스크롤 중계를 강제 구현했습니다.
  - 모바일 터치 드래그에 의한 기본 바운스 스크롤을 `e.preventDefault()`로 억제하여 부드러운 스크롤 제어감을 부여했습니다.
  - 상세 버그 기술 문서를 [docs/bug/20260704_bugfix_comic_touch_scroll.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_comic_touch_scroll.md)에 상세히 기술했습니다.

### 3. 만화 뷰어 고스팅(이전 이미지 잔류) 버그 픽스
- **해결 방안**: 뷰어 종료 시(`closeMediaViewer`) 호출할 `clearComicViewer()` 파괴자를 신규 구현해 만화 렌더러 DOM 내부 이미지를 초기화하고 잔류 타이머를 정리하여 뷰어 재오픈 시 이전 잔상이 튀는 현상을 막았습니다. (상세 내역 [docs/bug/20260704_bugfix_comic_viewer_ghosting.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_comic_viewer_ghosting.md) 참고)

### 4. 스타일시트 리팩토링 ([mobile.css](file:///c:/project/media_server/static/css/mobile.css))
- **`!important` 안티패턴 제거**: 일반 컴포넌트 클래스 스타일의 불필요한 `!important`를 완전 제거했습니다.

## 검증 결과

### 1. 모바일 터치 스크롤 감도 향상
- 모바일 환경에서 만화 뷰어를 **세로 연속 스크롤 모드**로 변경 시, 손가락으로 화면을 위/아래로 쓸어올리거나 내리면 뒤쪽의 만화 페이지들이 아주 부드럽고 매끄럽게 따라 스크롤됩니다.
- 스크롤 중에도 화면의 정중앙 영역을 가볍게 한 번 탭(클릭)하면 상하단 오버레이 메뉴와 진행 바가 문제없이 켜지고 꺼집니다.

### 2. 뷰어 이미지 고스팅 버그 개선
- 책 전환 시 이전 잔상 노출 없이 깨끗하게 새 책의 로딩 프로그래스가 보여진 후 렌더링을 시작합니다.
