# 플러그인 전용 모드 (Plugin-Only Mode) 검토

- 상태: **가능성 검토 완료 / 미구현** (코드 변경 없음)
- 검토일: 2026-09-21
- 결론: 기술적 장애물 없음. `.env` 한 줄로 켜는 "메뉴만 숨김" 방식으로 가볍게 구현 가능.

## 1. 왜 이 검토를 했나

BookOasis는 현재 두 가지 역할을 함께 맡고 있다.

1. 도서 관리 / 뷰어
2. 플러그인 기반의 다양한 서비스 (공식 플러그인만 50여 개: 미니게임, 노래방, 주식창, 라디오, 유튜브 재생, 날씨 위젯 등)

일부 사용자는 도서 관리를 전혀 쓰지 않고 플러그인만 활용한다. 이 사용자에게는 비어 있는 도서 화면(빈 카테고리, 최근 읽은 도서, 신규 추가 도서, 검색창 등)이 그대로 노출되어 어색하다.

이런 사용을 막을 이유가 없으므로, `.env` 값 하나로 도서 관련 메뉴를 숨기는 모드가 가능한지 확인했다.

### 이번 결정의 범위 (가볍게)

- **메뉴만 숨긴다.** 백엔드 동작(스캐너, 스케줄러, API)은 건드리지 않는다.
- **환경설정은 그대로 둔다.** 설정 탭은 이번에 숨기지 않는다.
- 숨긴 뒤 남기는 것: 홈(대시보드) + 플러그인 카테고리(`category_tab`) 폴더 + 관리자 환경설정.
- 플러그인 카테고리는 지금처럼 `category_tab`을 선언한 플러그인이 사이드바 폴더에 자동으로 들어오는 방식을 그대로 쓴다. 사용자가 노출할 플러그인을 따로 고르는 기능은 이번 범위가 아니다.

### 관련 원칙과의 관계

- 코어는 뷰어/스캔/카테고리만 맡고 나머지는 플러그인이라는 원칙과 방향이 같다 (코어 기능 하나를 끌 수 있게 하는 것).
- 플러그인 계약(탭 순서, 홈 위젯 슬롯 등)은 바꾸지 않고, 도서 쪽만 조건부로 숨긴다.
- 영상 강좌를 별도 제품으로 분리하는 논의(2026-10-14경 재검토 예정)와는 별개다. 분리 없이 "도서 없는 모드"로 같은 수요 일부를 채우는 가벼운 대안이다.

## 2. 조사 결과 요약

### 2.1 이미 있는 기반

| 항목 | 내용 |
|---|---|
| `.env` 로딩 | `core.py:9-10`에서 `load_dotenv()`, 이후 `os.environ.get(...)`로 읽음. 별도 설정 모듈은 없음 |
| 서버 변수 → 템플릿 | `api/routes/system_routes.py`의 `index()` (`/`, `/media-library`)가 `render_template`에 값을 넘김. 공통 변수는 `core.py`의 `inject_feature_flags` |
| 서버 변수 → JS | `templates/index.html:44-61`에서 `window.VIEW_LOG`, `window.DEVELOP_MODE`를 설정하는 패턴이 이미 있음. 모듈 스크립트보다 먼저 실행됨 |
| 홈 대시보드 플러그인 모드 | `mode: 'plugin'`이면 도서 기본 위젯 없이 플러그인 카드만 렌더링. 이 모드를 항상 켜면 됨 |
| 방어 코드 선례 | `selectCategory`가 `smart_rec` 비활성 시 `home`으로 돌려보내는 코드가 이미 있음 (`tab_media_library.js:696-698`) |
| 플러그인 폴더 | `/api/media/category-plugins` (`plugin_routes.py:567-640`) 결과로 그려지며 도서 라이브러리와 독립적 |

### 2.2 사이드바

- 정적 항목 7개(`tab_media_library.html:39-53`): home, history, favorite, collection, smart_rec, plugins, all. JS 로드 전에만 보이고 이후 통째로 교체됨.
- 동적 렌더링은 `static/js/category/index.js`의 `loadLibraries()` (`:461-642`).
  - `:515-536` 시스템 항목, `:538-562` 라이브러리 정렬/그룹, `:566-583` 플러그인 탭 분류, `:585-613` 그룹/미분류 렌더링, `:619` `sidebar.innerHTML`.
  - 라이브러리 목록과 플러그인 목록을 병렬로 가져오며, 둘 다 같은 `if (data.success)` 블록 안에서 그린다. 라이브러리 fetch를 건너뛸 때는 이 조건을 재구성해야 플러그인 탭이 같이 사라지지 않는다.
- `id="category-plugins"` 항목은 `category_tab` 폴더가 아니라 플러그인 대시보드 화면(`library_plugins.html`)으로 가는 시스템 항목이며, 도서와 무관하므로 유지한다.
- `sidebar_manager.js`는 접기/모바일 토글만 담당하여 수정 불필요.

### 2.3 시작 화면 결정과 도서 화면으로 들어가는 경로

시작 화면은 `initTabMediaLibrary()` (`tab_media_library.js:337-575`)가 정한다.

- 미디어 타입: `?type=` → 해시 → `localStorage.last_selected_library_type`
- 카테고리: `?library=` → 해시 → `localStorage.last_selected_library_id`
- 기본값은 `state.currentLibraryId = 'home'` (`state.js:5`)
- **id 검증이 없다.** 이전에 쓰던 `all`, 숫자 라이브러리 ID, `history`, `collection` 등이 남아 있으면 숨겨진 도서 화면으로 들어간다.

도서 화면에 닿을 수 있는 경로:

1. 시작 시 복원 (`:569-574`), 상세 딥링크 `#detail...` (`:561-566`)
2. `popstate` (`:375-537`): 예전 history 엔트리 복원, 폴백이 `'all'`
3. `selectCategory` (`:695-872`): `home/collection/smart_rec/settings/plugins/plugin_*` 외 전부 `:852-866`에서 도서 그리드로 이동
4. 사이드바 클릭 위임 (`:85-87`)
5. `switchLibraryType` (`library_type_toggle.js:100-127`)
6. 검색 입력/이동 (`search_navigation.js`, `book_list.js:418`, `search_overlay.js`)
7. 키오스크 모드 `?kiosk=1&book=` (`:298-324`), `/tv` 페이지

### 2.4 헤더의 도서 전용 컨트롤

모두 `templates/components/global_header.html`에 있다.

- 검색창 `.library-search-box` (`:24-38`)
- 필터 `#btn-open-filter` (`:47-51`), 정렬 `#btn-lib-sort` (`:75-79`)
- 그룹 토글 `#group-mode-toggle-group` (`:41-45`)
- 라이브러리 타입 토글 `#library-type-toggle-group` (`:51-57`)
- 알림(🔔, 예전 "스캔 활동") 버튼 `.scan-activity-wrap` (`:56-72`), 카테고리 정보 `#btn-category-info`, 총계 `#library-total-count`
- 유지: 설정 톱니, 계정 메뉴 (`.library-controls-persistent`)
- 관련 템플릿: `#active-filter-bar`, `#floating-filter-modal` (`tab_media_library.html`), `library_modal.html`, `library_kinds_modal.html`

단축키:

- 숫자 키 1~4 (`initLibraryTypeHotkeys`, `search_shortcut_manager.js:141-162`)
- 검색 포커스 Alt+` (`initLibrarySearchShortcut`)
- 두 초기화 호출이 `tab_media_library.js:372-373`에 있다.

JS가 헤더 요소의 `display`를 직접 바꾸는 곳이 여러 군데라 개별 요소 숨김은 되살아날 수 있다.

- `switchActiveView` (`view_manager.js:53-65`): 홈/그리드에서는 `removeProperty('display')`
- `recoverTopCategoryUiAfterBack` (`tab_media_library.js:145-197`)
- `applyLibraryTypeToggleVisibility` (`library_type_toggle.js:55-79`)

### 2.5 홈 대시보드

- 도서 행: `templates/components/views/library_dashboard.html:22-46`
  - `core_recent_slot` (`#dashboard-history-row`), `core_new_slot` (`#dashboard-new-row`), `core_reading_insights_slot`
- `loadDashboardData()` (`dashboard.js:39-160`)가 총계/읽은 기록/신규 추가를 병렬 fetch한 뒤 렌더링하고 `#library-total-count`까지 채운다. 도서가 없어도 빈 행으로 성공하고, 실패하면 "서버 연결 오류"가 뜨므로 이 모드에서는 fetch 자체를 건너뛴다.
- 플러그인 위젯: `loadHomeDashboardLayout` (`dashboard.js:296`), `/api/media/home-layout`, `HomeDashboardService.get_layout` (`services/home_dashboard_service.py`)
  - 사용자 설정 `HOME_DASHBOARD_PLUGIN_MODE == '1'`일 때만 `plugin` 모드이므로, 이 모드에서는 설정과 무관하게 강제해야 한다 (`system_routes.py:76-84`, `settings/general.js:184`).

### 2.6 "라이브러리가 최소 1개 있다"는 가정

- 차단하는 첫 실행 마법사는 없음. 빈 라이브러리 처리는 사소한 수준(영상 빈 상태 문구, 홈 항목의 라이브러리 추가 버튼, 빈 그룹 표시 규칙).
- 스캐너/스케줄러/상태 폴링은 라이브러리가 없어도 오류 없이 돈다 (할 일이 없을 뿐).
- `loadLibraries()`는 오류를 `console.error`로만 처리한다. 라이브러리 fetch 실패 시 플러그인 탭까지 그려지지 않는 구조 (2.2 참고).
- 설정 탭 중 `schedule`, `reports`, `trash`, `permissions`는 도서/라이브러리 관련이나, 이번 결정대로 그대로 둔다.

## 3. 수정 범위 (안)

### 서버

- `api/routes/system_routes.py` `index()` 또는 `core.py` `inject_feature_flags`: 플래그 추가 (환경변수 예: `PLUGIN_ONLY_MODE=1`)
- `services/home_dashboard_service.py`, `/api/media/home-layout`: 플러그인 모드 강제, `core.recent` / `core.new` / `core.reading_insights` 제외

### 템플릿

- `templates/index.html:44-61`: `window.PLUGIN_ONLY_MODE` 추가, `<html>`에 `plugin-only` 클래스
- `templates/components/global_header.html`: 도서 전용 컨트롤 조건부 렌더링
- `templates/components/tab_media_library.html:39-53`: 정적 사이드바에서 도서 항목 제외 (깜빡임 방지)
- `templates/components/views/library_dashboard.html`: 도서 슬롯 조건부 제외

### JS

- `static/js/state.js`: 플래그 반영
- `static/js/category/index.js` `loadLibraries()`: history/favorite/collection/smart_rec/all, 도서 라이브러리, 라이브러리 추가/그룹 추가 버튼 건너뛰기. 플러그인 fetch가 라이브러리 성공 여부에 묶이지 않도록 재구성
- `static/js/tab_media_library.js`: 시작 화면 복원, `popstate`, `selectCategory`에 "허용 목록 밖이면 홈" 방어 (`home`, `settings`, `plugins`, `plugin_*`만 허용). 검색/타입 전환 위임 정지
- `static/js/dashboard.js` `loadDashboardData()`: 도서 fetch 3종 생략
- `static/js/search_shortcut_manager.js`, `library_type_toggle.js`: 단축키/타입 전환 비활성
- `static/js/settings/general.js:184`: 홈 플러그인 모드 강제 반영
- `static/css/style.css`: `html.plugin-only`일 때 도서 전용 컨트롤 `display: none !important`

### 권장 구현 원칙

- 서버 렌더링 단계에서 뺀다 (JS 로드 후 숨기면 메뉴가 잠깐 보였다 사라진다).
- 그리고 `html.plugin-only` + CSS `!important`로 한 번 더 감싼다 (JS의 inline `display` 되돌림 방지).
- 시작 시 `localStorage.last_selected_library_id` / `last_selected_library_type`가 허용 목록 밖이면 무시(필요하면 정리).

## 4. 위험 요소

1. **깜빡임**: 정적 사이드바/헤더가 JS보다 먼저 렌더링됨 → 서버에서도 제외.
2. **inline display 덮어쓰기**: 2.4의 세 함수 → CSS 클래스 방식으로 대응.
3. **오래된 내비게이션 상태**: localStorage, URL 해시, history 엔트리로 도서 화면에 도달 → 시작/popstate/selectCategory 세 곳에 방어.
4. **플러그인 세션 제약**: 플러그인은 `sessions`(general/adult/audiobook/video)로 노출 세션을 선언한다. 타입 토글을 숨기면 일반 세션만 남아, 오디오북/영상 전용으로 선언된 탭에 접근할 수 없다 (`plugin_routes.py:567`). 이 모드에서 모든 세션의 플러그인 탭을 보여줄지, 한계로 문서화할지 결정 필요.
5. **API는 열려 있음**: 도서 API(`/api/media/books...`, `/api/media/libraries`), OPDS, `/tv`, 키오스크는 그대로 접근 가능. "메뉴만 숨김"이라는 방침과는 맞지만 주소 직접 입력으로 도서 화면에 갈 수 있다는 점을 문서에 밝힌다.
6. **`window.loadLibraries()` 의존**: 라이브러리 CRUD, 세션 전환, 스캔 후 다른 코드가 호출하므로 이 모드에서도 동작해야 한다.
7. **도서 데이터 의존 플러그인**: 통계, 독서 메이트, 독후감, 스마트 추천, 컬렉션 등은 이 모드에서 비거나 오류 화면이 될 수 있다. 문서로 안내한다.

## 5. 이번에 하지 않는 것

- 스캐너/스케줄러/요약 테이블 재생성 등 백그라운드 중단 (2단계 후보, 저사양 서버 수요가 확인될 때)
- 도서 관련 API 차단 (플러그인이 도서 데이터를 쓸 수 있으므로 하지 않는 편이 낫다)
- 환경설정 탭 숨김
- 사이드바에 노출할 플러그인을 사용자가 직접 고르는 기능

## 6. 다음 단계

1. 플래그 이름 확정 (제안: `.env`에 `PLUGIN_ONLY_MODE=1`)
2. 위험 4번(플러그인 세션 제약)의 처리 방침 결정
3. 구현 시 순서 제안: 플래그/템플릿 → 사이드바 → 시작 화면 방어 → 대시보드 → 단축키/CSS → 문서(`.env.example`, guide_plugins)
