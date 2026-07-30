---
title: "대시보드 메인 컨테이너 크기 미세 조정을 통한 스크롤 방지, 컨텍스트 메뉴 잘림 수정 및 플러그인 동적 탭 & 드래그 정렬 개편"
project: "BookOasis"
category: "bug"
date: 2026-07-12
tags: [bug, dashboard, layout, css, contextmenu, plugin, refactoring, drag-drop]
---

# 대시보드 스크롤 개선, 컨텍스트 메뉴 및 독립 플러그인 데스크 개편

## 1. 버그 및 개선 내역 (Bug Report & Improvement)
- **현상**:
  1. 브라우저 창 크기에 상관없이 대시보드 외부 영역 및 하단에 원치 않는 미세 스크롤바가 발생하여 레이아웃 무결성이 깨짐.
  2. 컨테이너 영역 조정 후, 좌측 사이드바 하단부(환경설정 및 사용자/로그아웃 위젯)가 끝까지 내려가지 않고 화면 밑부분에 잘리거나 반쯤 가로막히는 부작용 발생.
  3. 대시보드에서 마우스 우클릭 시 호출되는 컨텍스트 메뉴의 높이가 플러그인 아이템 비동기 로딩으로 인해 아래로 길어질 때, 뷰포트 하단을 침범해 메뉴 하단부가 잘리는 현상 발생.
  4. 메인 영역 내부 스크롤 허용 시 브라우저 기본 흰색 스크롤바가 노출되어 테마와 이질감을 유발함.
  5. 환경설정에서 알라딘/네이버 등의 도서 검색 플러그인을 OFF(비활성화)하였음에도 불구하고, 우클릭 컨텍스트 메뉴에 "메타정보 검색" 항목이 하드코딩 형태로 늘 노출되어 오동작을 유발함.
  6. 대시보드(Home) 화면 하단에 플러그인 위젯(독서 통계 등)들이 길게 렌더링되어 메인 화면의 기하학적 균형을 깨트리고, 유저가 주요 정보인 최근 도서와 신규 도서 리스트를 한눈에 식별하기 다소 부자연스러움.
  7. 독립 플러그인 전용 뷰 생성 이후에도 플러그인 카드들이 고정 가로폭(500px)에 구속되어 있어 대화면의 이점을 전혀 활용하지 못했으며, 위젯 순서 정렬이 지원되지 않고, 전체 화면을 단독으로 사용해야 하는 전체 화면형 플러그인 뷰를 분할 지원하지 못함.
  8. 모바일 뷰(화면 폭 1200px 이하)에서 좌측 상단 햄버거 메뉴를 펼칠 때, 카테고리 목록이 기기 세로 화면 높이를 초과하더라도 아래쪽 목록이 잘린 채 스크롤이 구동되지 않는 현상 발생.
- **원인**:
  1. 대시보드의 전체 래퍼인 `.media-library-container`의 높이와 최외각 `body` 및 메인 컨테이너 div의 높이가 엄격하게 제한되지 않고 `overflow` 속성이 기본값으로 지정되어 브라우저 뷰포트 규격을 초과할 때 창 전체에 스크롤이 발생함.
  2. 컨테이너의 패딩을 축소했으나 `.library-sidebar`의 높이가 고정적인 절대 뷰포트 단위(`calc(100vh - 40px)`)로 고정되어 부모 패딩 축소와 어우러지지 않아 높이 초과를 일으켜 하단 잘림이 발생함.
  3. `showBookContextMenu` 함수가 호출되어 메뉴의 좌표를 1차 보정할 때에는 비동기로 로드되는 플러그인 메뉴가 아직 렌더링되지 않은 기본 높이만 측정하게 되어 보정 범위를 넘어가 아래쪽으로 넘침을 방지하지 못함.
  4. `.library-main-content`에 `overflow-y: auto`를 적용하면서 webkit 커스텀 스크롤바 스타일이 지정되지 않아 브라우저 기본 렌더링 스크롤바가 표출됨.
  5. `templates/components/context_menus.html` 내부에 `ctx-search-meta-book` 항목이 무조건 렌더링되게끔 박혀 있으며, 프론트엔드 자바스크립트 측에서 플러그인 활성화 상태를 전혀 동적으로 체크하지 않아 발생함.
  6. 홈 대시보드 하단에 플러그인 렌더링 용도(`dashboard-plugins-section`)가 영구 배치되도록 템플릿과 로딩 스크립트가 설계되어 있어 분리가 필요함.
  7. 백엔드에서 `all_desk_tab` 파라미터를 넘겨주지 않았으며, 프론트엔드 측에 탭 메뉴 동적 구성 로직 및 `Sortable.js` 기반 카드 드래그 리스너 바인딩 처리가 없었음.
  8. 이전 대시보드 미세 스크롤 차단 패치로 인해 body 및 최외각 레이아웃에 overflow: hidden이 지정된 후, 모바일용 햄버거 팝업인 `.sidebar-collapsible-content` 영역에 최대 높이(max-height) 및 내부 자체 스크롤(overflow-y: auto) 규칙이 없어 화면 범위를 초과한 리스트 영역이 갇혀 발생함.

## 2. 영향도 (Impact)
- **대상**: 대시보드 메인 홈 화면, 전체 레이아웃, 우클릭 메뉴, 스크롤바, 검색 플러그인 조작, 플러그인 전용 뷰 아키텍처 및 위젯 배치 정렬 관리
- **상세**: 레이아웃 깨짐, 메뉴 잘림, 불필요한 스크롤 유발 및 대시보드 화면 내 정보 밀집도 과다로 인한 가시성 제한. 정렬 커스터마이징 기능 부재로 인한 사용성 제약.

## 3. 수정 사항 (Resolution)
- **수정 소스 파일**:
  - [style.css](file:///c:/project/media_server/static/css/style.css)
  - [index.html](file:///c:/project/media_server/templates/index.html)
  - [book_context_menu.js](file:///c:/project/media_server/static/js/book_context_menu.js)
  - [metadata_search.js](file:///c:/project/media_server/static/js/metadata_search.js)
  - [plugins.js](file:///c:/project/media_server/static/js/settings/plugins.js)
  - [mobile.css](file:///c:/project/media_server/static/css/mobile.css)
  - [viewer_comic.js](file:///c:/project/media_server/static/js/viewer_comic.js)
  - [renderer.js](file:///c:/project/media_server/static/js/viewer/renderer.js)
  - [library_dashboard.html](file:///c:/project/media_server/templates/components/views/library_dashboard.html)
  - [library_plugins.html](file:///c:/project/media_server/templates/components/views/library_plugins.html)
  - [tab_media_library.html](file:///c:/project/media_server/templates/components/tab_media_library.html)
  - [category.js](file:///c:/project/media_server/static/js/category.js)
  - [view_manager.js](file:///c:/project/media_server/static/js/view_manager.js)
  - [tab_media_library.js](file:///c:/project/media_server/static/js/tab_media_library.js)
  - [dashboard.js](file:///c:/project/media_server/static/js/dashboard.js)
  - [api/library.py](file:///c:/project/media_server/api/library.py)
  - [ko.json](file:///c:/project/media_server/static/i18n/ko.json)
  - [en.json](file:///c:/project/media_server/static/i18n/en.json)
- **조치 사항**:
  - `templates/index.html`에서 `body`에 `overflow: hidden;`을 적용하고 최외각 메인 컨테이너 div에 `height: calc(100vh - 40px); overflow: hidden;`을 적용하여 화면 크기를 뷰포트 내로 제한했습니다.
  - `static/css/style.css`에서 `.media-library-container`에 `height: 100%; overflow: hidden;` 속성을 추가하여 스크롤 생성을 방지하고, 내부 본문 `.library-main-content`에 `overflow-y: auto; overflow-x: hidden;`을 설정해 본문 영역 내부 스크롤만 독립적으로 구동되게 보완했습니다.
  - `.library-sidebar` 클래스의 높이 속성을 `height: 100%;`로 개선하여 좌측 메뉴 하단 컴포넌트가 잘리지 않도록 해결했습니다.
  - `static/js/book_context_menu.js` 내에 메뉴 좌표 계산 함수 `adjustMenuPosition(x, y)`를 분리하고, 비동기 플러그인 렌더링 함수가 완료되는 시점에 동적으로 다시 감지해 재보정 좌표 계산 처리를 하도록 구현하여 뷰포트 하단을 침범하지 않도록 수정 완료했습니다.
  - `static/css/style.css`에 `.library-main-content::-webkit-scrollbar` 규칙들을 완비하여 6px 두께의 얇고 둥근 보라색 반투명 핸들을 가진 커스텀 스크롤바로 디자인을 통일했습니다.
  - `static/js/book_context_menu.js` 내에 플러그인 활성 목록 캐시 `cachedSearchPlugins`를 적용하고, `showBookContextMenu` 호출 시에 활성화된 메타데이터 플러그인이 전혀 없을 경우 `ctx-search-meta-book` 요소의 `display` 스타일을 `none`으로 차단하도록 추가 구현했습니다. 또한 환경설정 플러그인 관리(`plugins.js`)에서 스위치를 토글할 때 전역 캐시 초기화 함수(`window.invalidateMetadataPluginsCache`)가 동작하여 즉시 UI에 반영되도록 통합 연동했습니다.
  - **대시보드 화면 구성 전면 개편**:
    - `library_dashboard.html`에서 하단의 기존 플러그인 위젯 렌더링 전용 구역을 제거하였습니다.
    - `tab_media_library.html` 사이드바 고정 탭 영역 및 `category.js` 카테고리 동적 빌더 함수 내에 즐겨찾기(`category-favorite`) 바로 하위로 배치되는 고정형 **[플러그인]** 카테고리 메뉴를 신설하고, 다국어 팩(`ko.json`, `en.json`)에 번역 키를 추가했습니다.
    - 독립 플러그인 뷰 구조체 파일인 `library_plugins.html`을 신설하고 인클루드 조립했으며, `view_manager.js`와 `tab_media_library.js` 내에 plugins 뷰 상태 전환 로직과 `loadDashboardPlugins()` 실행 분기를 매핑하여 연동시켰습니다.
    - `dashboard.js`에서 home 화면 기동 시의 위젯 로드 호출을 완전히 소거해 독점 카테고리 선택 시에만 위젯(통계 플러그인 등)이 안전하게 그려지도록 아키텍처를 개선했습니다.
  - **플러그인 독립 화면 확장 및 동적 탭 연동 개편**:
    - `api/library.py`의 위젯 리스트 반환 시 `all_desk_tab` 파라미터를 JSON 응답에 바인딩하여 클라이언트에 함께 제공하도록 개선했습니다.
    - `templates/components/views/library_plugins.html` 내부에 상단 탭 헤더 영역(`#plugins-view-tabs`)과 탭 전환 내용 바인딩 구조를 도입했습니다.
    - `static/js/dashboard.js` 내 `loadDashboardPlugins`를 고도화하여 `all_desk_tab: true`로 설정된 플러그인은 상단에 전용 탭이 동적으로 삽입되고 단독 풀 100% 화면 레이아웃으로 렌더링되게 구현했습니다.
    - `all_desk_tab: false`인 공통 플러그인은 "공통 데스크" 탭의 유연한 자동 반응형 카드 그리드로 가로폭 제약을 제거했으며, `Sortable.js`를 연결하여 카드 순서 드래그 앤 드롭 정렬을 가능하게 하고, 정렬 순서를 `localStorage`에 자동 영구 저장해 새로고침 후에도 유지되도록 구현했습니다.
    - 탭 전환 함수 `switchPluginsViewTab(tabId)`을 작성하여 부드러운 SPA 스타일 탭 변경을 제공하고, `style.css` 내 드래그 중 시각 피드백 효과를 위한 `.plugin-card.dragging` 스타일 규칙을 정의했습니다.
  - **모바일 햄버거 메뉴 자체 스크롤 활성화**:
    - `static/css/mobile.css` 내의 `.sidebar-collapsible-content.show` 클래스에 `max-height: 75vh; overflow-y: auto; overflow-x: hidden;` 속성을 주입하여 모바일 햄버거 메뉴를 열었을 때 카테고리가 화면 높이를 벗어나더라도 독립적인 세로 스크롤링이 가능하도록 개선했습니다.
    - 모바일 팝업 내부 스크롤 시에도 얇고 이질감 없는 미관을 유지할 수 있도록 webkit-scrollbar 스타일 규칙을 추가로 바인딩했습니다.
  - **만화책 뷰어(페이지 모드) 화면 전환 깜빡임 및 딜레이 제거**:
    - `static/js/viewer/renderer.js` 내의 페이지 모드 렌더링 루틴에 **더블 버퍼링/스왑 가속(Double Buffering)** 설계를 도입했습니다.
    - 다음 페이지를 호출할 때 기정 로드된 DOM 콘텐츠를 성급하게 초기화하지 않고, 백그라운드 메모리상에 새로운 이미지 객체 생성을 대기시킵니다.
    - 백그라운드에서 새 페이지 이미지들의 로딩(`onload`) 완료가 100% 확인된 시점에만 한 번에 DOM 스왑 및 불투명도 조정을 처리하여, 캐시 히트 시 화면 깜빡임과 체감 지연(Loading indicator 노출)을 완전히 차단했습니다.
    - **가비지 컬렉션(GC)으로 인한 프리로드 중단 결함 수정**: `preloadNextPages` 내부에서 생성되는 비동기 `new Image()` 객체들이 자바스크립트 참조 유실로 인해 다운로드 도중 메모리 회수(GC)되어 커넥션이 자동 캔슬(Aborted)되던 문제를 차단하기 위해 모듈 레벨의 강한 참조 관리 홀더(`activePreloadSet`)를 도입했습니다. 로드가 진행 중일 때 참조 관계를 붙잡아두고, 로드가 끝나는 즉시 안전하게 세트에서 소거하며 뷰어 종료 시 자원을 일괄 릴리즈하도록 견고히 설계했습니다.
    - **스캐너 구동 전 HDD/NAS 절전 대기(Wake-up Knock) 재시도 도입**: `tools/scanner/core.py` 내의 `scan_library` 시작 지점에 물리 경로에 대한 존재 여부(`os.path.exists`) 검증 및 웜업(Warm-up) 루틴을 신설했습니다. 장치가 절전 상태(Spin-down)이거나 네트워크 마운트 활성화 대기 시간으로 인해 경로를 즉시 읽을 수 없는 환경을 방어하기 위해 3초 간격으로 최대 4회 재시도하도록 보강했으며, 최종 웜업 실패 시 세부 실패 경로와 예외 원인을 DB와 `scan_history.log`에 명확하게 남기고 중단하도록 견고히 마감했습니다.
    - **로컬 ZIP 파일 뷰어 감상 시 중복 디스크 복사(I/O 병목) 제거**: `utils/cache_helper.py` 내의 `get_zip_file_hybrid` 로직을 최적화했습니다. 원격 구글 드라이브 마운트 경로가 아닌 최초 로컬 물리 볼륨(HDD/SSD)에 존재하는 ZIP 파일인 경우에도 무조건 백그라운드 복사(`start_background_copy`) 스레드가 기동되어 하드 디스크 읽기/쓰기 동시 부하(I/O 병목)를 지속적으로 일으켜 만화 페이지 전환 시 렉 및 스피너를 유발하던 현상을 해결했습니다. `is_remote_path` 헬퍼를 결합하여 로컬 경로일 경우 불필요한 백그라운드 캐시 이중 복사를 완전히 스킵하도록 차단하여 다이렉트 오프셋 서빙 속도를 극대화했습니다.
    - **Blob URL 인메모리 캐싱 및 순차 프리로드 큐 스케줄러 도입**: `static/js/viewer/renderer.js` 내에 바이너리 데이터 Blob 캐시 맵(`blobCacheMap`)과 큐 기반의 순차적 백그라운드 프리로드 스케줄러(`startSequentialPreload`)를 이식했습니다. 페이지를 넘길 때마다 다음 10장의 HTTP 요청을 동시에 마구 쏘아 브라우저의 6개 동시 커넥션 풀을 완전히 점유(Blocking)하여 현재 보기 페이지의 노출을 늦추던 병목을 해결하고, 1장씩 순차적으로 얌전하게 캐시 큐를 소거해 나가며 다운로드가 성공한 파일은 메모리에 오브젝트 URL로 킵했다가 0ms 수준으로 지연 없이 즉석 렌더링하도록 극적으로 캐싱 효율을 고도화했습니다. 뷰어 종료 시 등록된 메모리 풀은 완전히 해제(`clearBlobCache`)하여 메모리 누수를 원천 차단했습니다.
    - **도서 검색창 단축키 커스터마이징 기능 추가**: 우분투 등 OS 기본 단축키와 `Alt + ` (Backquote)` 조합이 겹쳐 검색 단축키가 작동하지 않던 문제를 위해, 환경설정의 일반설정 탭(`general_tab.html`) 내에 키 조합 레코더 UI를 이식했습니다. 사용자가 임의의 단축키를 입력하면 브라우저 keydown 상태를 실시간 캐치하여 `Ctrl + Shift + F` 등 직관적으로 키 조합을 바인딩하고 이를 로컬스토리지에 저장한 뒤, 보관함 전역 이벤트 감지기(`tab_media_library.js`)가 해당 커스텀 스펙에 맞춰 검색 인풋에 포커스를 주도록 동적 매핑했습니다.


