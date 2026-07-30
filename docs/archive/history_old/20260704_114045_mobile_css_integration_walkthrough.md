---
title: Walkthrough - mobile_css_integration
project: BookOasis
category: history
date: 2026-07-04
type: walkthrough
---
# 모바일 및 데스크톱 반응형 CSS 추가 (iOS Safari 터치 스크롤 패치 포함) 워크쓰루

데스크톱용 기존 CSS 코드를 전혀 건드리지 않고 모바일 및 태블릿 환경(최대 가로 너비 1200px 이하)에서 최적화된 레이아웃을 제공함과 동시에, 데스크톱 화면 환경에서 좌측 사이드바를 자유롭게 접고 펼칠 수 있는 인터랙티브 토글 기능을 추가했습니다. 또한, `mobile.css` 소스 전반의 불필요한 `!important` 구문을 걷어내는 명시도 리팩토링을 집행했으며, 만화 뷰어 닫기 시 잔상 문제 해결과 더불어 **iOS Safari 등 특정 모바일 브라우저에서 세로 스크롤 시 터치 스크롤(쓸어내리기) 제스처가 물리적으로 막히던 사파리 터치 버그**를 완전히 조치했습니다.

## 변경 내용

### 1. 웹 템플릿 연동 및 햄버거 버튼 추가
- [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html) 파일의 기존 스타일시트 로드 구문 밑에 `mobile.css`를 로드하는 코드를 추가했습니다.
  - 미디어 쿼리 속성: `media="screen and (max-width: 1200px)"` (태블릿 가로/프로 라인 대응을 위해 **1200px**로 한계 확장)
- 사이드바 헤더 영역에 모바일 전용 햄버거 메뉴 토글 버튼(`btn-sidebar-toggle`)을 추가했습니다.

### 2. iOS Safari 터치 제스처 스크롤 및 탭 브릿지 고도화 (사파리 특화 패치)
- **원인 발견 1 (레이어 차단)**: 뷰어 전면을 투명 핫스팟 레이어(`#common-viewer-hotspot`)가 덮어 손가락 드래그 터치를 가로챘습니다.
- **원인 발견 2 (사파리 이미지 드래그 스크롤 차단 - 결정적)**: iOS Safari에서는 화면을 채운 만화 이미지(`.comic-scroll-img` 태그)를 긁어서 쓸어내릴 때, 브라우저가 이미지를 선택하거나 이동시키려는 드래그 대상으로 잘못 인식하여 부모 스크롤 컨테이너의 드래그 스크롤을 무력화시키는 고유의 WebKit 제한 규정이 작동 중이었습니다.
- **해결 방안**: 
  - `viewer.js` 내 `syncHotspotPointerEvents()` 함수를 통해 모바일 환경(<= 1200px)에서 세로 스크롤 작동 시 핫스팟 레이어 자체를 아예 `display: none`으로 제거했습니다.
  - [tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css) 에 `.comic-scroll-img` 속성으로 `pointer-events: none;`, `-webkit-user-drag: none;`, `user-select: none;`을 선언하여, 손가락 드래그 시 이미지 선택을 차단하고 곧바로 부모의 스크롤바 이동으로 100% 제스처를 전달시켰습니다.
  - 스크롤 컨테이너인 `.comic-image-wrapper` 에 `-webkit-overflow-scrolling: touch;`를 선언해 iOS 고유의 매우 미려하고 부드러운 **GPU 가속 관성 스크롤(Momentum scrolling)**을 활성화했습니다.
  - 핫스팟이 꺼진 상태에서도 뷰어 본체를 가볍게 탭(클릭)하면 백그라운드 클릭 브릿지(`initViewerClickToggle()`)가 정상 동작하여 메뉴를 여닫습니다.
  - 관련 상세 문서를 [docs/bug/20260704_bugfix_comic_touch_scroll.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_comic_touch_scroll.md)에 업데이트 반영했습니다.

### 3. 만화 뷰어 고스팅(이전 이미지 잔류) 버그 픽스
- **해결 방안**: 뷰어 종료 시(`closeMediaViewer`) 호출할 `clearComicViewer()` 파괴자를 신규 구현해 만화 렌더러 DOM 내부 이미지를 초기화하고 잔류 타이머를 정리하여 뷰어 재오픈 시 이전 잔상이 튀는 현상을 막았습니다. (상세 내역 [docs/bug/20260704_bugfix_comic_viewer_ghosting.md](file:///c:/project/media_server/docs/bug/20260704_bugfix_comic_viewer_ghosting.md) 참고)

### 4. 스타일시트 리팩토링 ([mobile.css](file:///c:/project/media_server/static/css/mobile.css))
- **`!important` 안티패턴 제거**: 일반 컴포넌트 클래스 스타일의 불필요한 `!important`를 완전 제거했습니다.

## 검증 결과

### 1. iOS Safari 터치 스크롤 동작 성공
- 아이폰 및 아이패드의 **Safari 브라우저** 환경에서 세로 연속 스크롤 모드를 사용할 때 손가락 쓸기 스크롤이 아무 버벅임 없이 극도로 유려하게 동작합니다.
- 스크롤을 멈춘 뒤 화면을 가볍게 한 번 탭(클릭)하면 오버레이 메뉴 창이 켜지고 꺼집니다.
- 데스크톱 모드 및 모바일 페이지 모드에서는 3분할 핫스팟 영역이 그대로 노출되어 기존 스펙을 완벽하게 유지합니다.
