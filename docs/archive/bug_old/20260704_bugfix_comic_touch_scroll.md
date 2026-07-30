---
name: comic_touch_scroll_fix
description: 만화 뷰어 세로 스크롤 모드에서 모바일 터치 제스처 스크롤이 작동하지 않던 버그 조치
---

# 🐛 [버그수정] 만화 뷰어 스크롤 모드 모바일 터치 스크롤 미동작 문제 (iOS Safari 대응 완료)

만화책 뷰어(또는 텍스트/PDF 뷰어)의 세로 연속 스크롤 모드 상태일 때, 모바일 및 태블릿 환경에서 화면을 쓸어내리는 터치 드래그 제스처로 스크롤링이 불가능하던 사용성 버그를 조치했습니다.

## 1. 버그 분석 및 영향도
* **원인 1 (레이어 차단)**: 뷰어 전면에는 탭/클릭 기반 영역(좌우측 터치 시 이전/다음 페이지 전환 및 오버레이 메뉴 토글 등)을 제어하기 위한 투명한 핫스팟 레이어(`#common-viewer-hotspot`)가 `pointer-events: auto` 상태로 화면 전체를 덮고 있어, 손가락 쓸기 터치 드래그 제스처가 백그라운드 이미지 래퍼(`.comic-image-wrapper`)까지 닿지 못했습니다.
* **원인 2 (iOS Safari 이미지 드래그 잠금 - 핵심)**: iOS Safari 브라우저의 경우, 화면의 대다수를 차지하는 뷰어 이미지(`.comic-scroll-img`) 위에 손가락을 대고 쓸어내리려 할 때, 브라우저가 이미지 자체를 드래그 앤 드롭 대상(선택 상태)으로 인지하여 부모 스크롤바의 터치 이동 제스처를 즉시 무력화(묵살)시키는 WebKit 특유의 이미지 스크롤 제한 제약이 존재합니다.
* **영향 범위**: 모바일/태블릿 터치 디바이스 접속자 중 만화 스크롤/웹툰 뷰, PDF 뷰, 텍스트 스크롤 뷰 사용자 전체 (특히 iOS Safari 사용자군)

## 2. 해결 방법
1. **[viewer.js](file:///c:/project/media_server/static/js/viewer.js)**:
   * `syncHotspotPointerEvents()` 함수를 갱신하여, 모바일 환경(<= 1200px)에서 세로 스크롤 모드 구동 시 핫스팟 레이어 자체를 아예 `display: none`으로 렌더링 트리에서 탈락시키도록 변경했습니다. 이로 인해 iOS Safari가 터치 이벤트를 핫스팟 레이어에 뺏기지 않고 백그라운드로 전달합니다.
   * `initViewerClickToggle()` 함수를 통해 핫스팟이 꺼진 상태에서 화면 빈 곳을 탭(클릭)했을 때 백그라운드 영역인 `#viewer-body-container` 가 이벤트를 수신하여 오버레이 메뉴 토글(`toggleComicOverlay()`)을 정상 중계해주도록 구현했습니다.
2. **[tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css)**:
   * `.comic-scroll-img` 이미지의 CSS 정의에 `pointer-events: none;`, `-webkit-user-drag: none;`, `user-select: none;` 속성을 주입하여 손가락으로 드래그할 때 이미지가 선택되지 않고 곧바로 부모인 `.comic-image-wrapper` 의 세로 스크롤바로 드래그 제스처가 전도되도록 강제 조치했습니다.
   * 스크롤 래퍼(`.comic-image-wrapper.scroll-mode`)에 `-webkit-overflow-scrolling: touch;`를 부여하여 Safari에서도 가속화된 고유의 **부드러운 관성 스크롤(Momentum scrolling)**이 완전히 구동되도록 정돈했습니다.

## 3. 수정 파일 목록
* [static/js/viewer.js](file:///c:/project/media_server/static/js/viewer.js)
* [static/css/tab_media_library_viewer.css](file:///c:/project/media_server/static/css/tab_media_library_viewer.css#L216-L237)
