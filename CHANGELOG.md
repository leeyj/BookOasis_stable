# CHANGELOG
## v2.6.1
- (fix) 로컬 EPUB 스캔 시 `[Scanner-EPUB-Precache] Notice: name 'db_type' is not defined` 로그가 반복 출력되던 문제 수정 — 매개변수 누락으로 미정의 변수를 참조하던 버그였고, 기존 도서(재스캔) 케이스는 이미 알고 있는 book_id를 함께 전달해 EPUB 사전 캐싱이 실제로 동작하도록 근본 수정 | fix repeated `[Scanner-EPUB-Precache] Notice: name 'db_type' is not defined` log spam during local EPUB scans — was referencing an undefined variable due to a missing parameter; also fixed EPUB pre-caching to actually take effect for already-known (re-scanned) books by passing along their existing book id
- (fix) 영상 강좌 그리드에서 커버가 실제로는 존재하는데도 화면에 표시되지 않던 문제 수정 — 카드 커버 이미지의 페이드인 표시 처리(`is-loaded`)가 이 화면에만 누락되어 있었음 | fix video course grid covers not displaying even though the files existed — the card cover's fade-in reveal (`is-loaded`) was missing only on this screen
- (fix) 새 카테고리 경로 탐색기에서 rclone FUSE 마운트 드라이브(예: M:) 하나가 `[WinError 1005]`로 실패하면 C:/D: 등 정상 드라이브까지 목록 전체가 500 오류로 안 뜨던 문제 수정 — 드라이브/하위 항목별로 `realpath()` 예외를 개별 처리해 문제 있는 항목만 건너뛰도록 함 | fix the new-category path browser failing its entire drive listing with a 500 error whenever a single rclone FUSE-mounted drive (e.g. M:) raised `[WinError 1005]` — realpath() failures are now caught per drive/entry so only the problematic one is skipped instead of breaking the whole request

## v2.6.0
- (fix) 도서 스캔 완료 직후 새 표지가 강제 재스캔 전까지 그리드에 안 보이던 문제 수정 — 스캐너 워커(별도 프로세스)의 캐시 무효화가 웹 프로세스까지 전달되지 않던 문제, 공유 캐시 신호(epoch) 도입으로 해결 | fix newly scanned book covers not appearing in the grid until a forced rescan — the scanner worker's cache invalidation wasn't reaching the web process; fixed with a shared cache-epoch signal
- (fix) 도서 카드 즐겨찾기 별 클릭 시 이벤트 위임 구조로 인해 간헐적으로 발생하던 `TypeError` 수정 | fix an intermittent `TypeError` when clicking a book card's favorite star, caused by the click event-delegation setup
- (fix) 목록 카드 커버 지연 로딩 시 플레이스홀더 이미지 기준으로 로드 완료 판정이 먼저 붙어버려, 실제 커버가 늦게 뜨거나 실패하면 빈 배경(검은색)으로 계속 남던 문제 수정 | fix list-card lazy cover loading marking itself "loaded" against the tiny placeholder image before the real cover request even started, leaving the card stuck on a blank/black background whenever the real cover loaded slowly or failed
- (fix) 한국어 Windows(CP949 콘솔)에서 로그의 한글/이모지가 깨지거나 `UnicodeEncodeError`가 나던 문제 수정 — 웹/스캐너 워커/레이지 스캐너 각 프로세스 진입점에서 stdout/stderr를 UTF-8로 강제 | fix Korean text/emoji in logs getting mangled or raising `UnicodeEncodeError` on Korean Windows (CP949 console) — force UTF-8 stdout/stderr at each process entry point (web, scanner worker, lazy scanner)
- (improvement) 부문(일반/성인/오디오북/영상) 전환 시 사이드바 갱신 속도 대폭 개선 — 사이드바 플러그인 탭 목록 조회가 각 플러그인의 전체 UI 번들 파일까지 매번 읽어오던 것을 메타데이터만 조회하도록 분리, 빠른 연속 전환 시 오래된 응답이 최신 화면을 덮어쓰지 않도록 레이스 가드 추가 | greatly speed up sidebar refresh when switching sections (general/adult/audiobook/video) — the plugin tab listing no longer reads each plugin's full UI bundle files on every call (metadata-only now), plus added a race guard so a stale response from a previous switch can't overwrite the current view


## v2.5.9
- (feature) 홈 대시보드에 신규 `home_widget` 플러그인 계약 추가 — "내 설정"에서 켜면 코어 위젯(독서 인사이트/최근 읽은 도서/신규 추가 도서)과 플러그인 위젯을 홈 화면에서 함께 드래그로 재배치 가능, 기본값은 기존 고정 레이아웃 그대로 유지. 위젯마다 `layout: 'full'`(1열 전체)/`'grid'`(카드처럼 한 행에 나란히, `size`로 1~3칸 폭 선택 가능)을 선언 가능. 플러그인 위젯은 자동 노출 대신 "+ 위젯 추가" 목록에서 직접 골라야 하고, 코어 섹션(최근/신규 등)도 × 버튼으로 닫았다가 나중에 다시 추가 가능 | add a new `home_widget` plugin contract for the home dashboard — opt in via "My Settings" to drag-reorder core widgets (reading insights/recently read/newly added) together with plugin widgets right on the home screen; default stays the existing fixed layout. Each widget can declare `layout: 'full'` (spans the row) or `'grid'` (sits as a card alongside others, with `size` choosing a 1-3 column span). Plugin widgets must be picked from a "+ Add widget" list rather than appearing automatically, and core sections (recent/new, etc.) can likewise be closed with an × and re-added later

## v2.5.8
- (fix) 플러그인 카테고리 매니페스트에서 `order: 0`이 무시되고, 매니페스트 하나의 오류가 전체 동적 카테고리 목록을 무너뜨리던 문제 수정 | fix plugin category manifests ignoring `order: 0` and a single malformed manifest breaking the entire dynamic category list
- (fix) 사이드바 "컬렉션" 카테고리에 누락되어 있던 다국어(i18n) 번역 키 추가 | add the missing i18n translation key for the sidebar "Collection" category
- (fix) "내 설정" 탭의 도서 상세 그리드 보기 등 사용자 개인화 체크박스들이 저장해도 적용되지 않던 문제 수정 — 전역 설정에 값이 없는 사용자 전용 설정이 공개 설정 API 응답에서 통째로 누락되던 버그와, 저장 직후 메모리 상태가 갱신되지 않던 버그를 함께 수정 | fix "My Settings" personalization checkboxes (e.g. detail volume grid view) not taking effect after saving — fixed both a public-settings API bug that dropped user-only overrides with no global default, and stale in-memory state right after saving
- (breaking) 도서 상세 페이지의 "이 작가의 다른 도서" 사이드바를 코어에서 완전히 분리해 `detail_sidebar_widget` 플러그인 계약으로 전환 — 참조 구현은 `sample_plugins/metadata/author_other_books`로 제공되며, 필요 시 `plugins/metadata/`로 복사해 활성화해야 함 | (breaking) fully separate the book detail page's "More by this author" sidebar from core into a `detail_sidebar_widget` plugin contract — the reference implementation ships as `sample_plugins/metadata/author_other_books` and must be copied into `plugins/metadata/` to enable it
- (feature) 여러 플러그인이 도서 상세 사이드바에 위젯을 동시에 등록할 수 있으며(순서대로 병렬 표시), 대시보드 위젯과 동일한 아이템 스키마(도서 연결/외부 링크/자유 형식 카드)를 공유해 "관련도서", "유사한 태그 도서"는 물론 도서와 무관한 위젯도 자유롭게 구현 가능 | add support for multiple plugins to register book detail sidebar widgets simultaneously (stacked in order), sharing the same item schema as dashboard widgets (book-linked / external link / free-form card) so "related books", "similar tags", or even non-book widgets can be built freely
- (fix) 도서 상세 사이드바 위젯이 3초 이상 늦게 뜨던 문제 수정 — 목록/데이터 조회 API를 1회 왕복으로 통합하고, 기본 제공 플러그인의 전체 테이블 스캔 쿼리에 Redis 캐시(TTL 30분)를 추가 | fix book detail sidebar widgets taking 3+ seconds to appear — merged the list/data API calls into a single round trip and added a 30-minute Redis cache to the bundled plugin's full-table-scan query

## v2.5.7
- (fix) e-paper 테마에서 불투명 배경 버튼 글자가 안 보이던 문제들을 근본 수정 — 원인이었던 전역 텍스트색 강제 규칙 제거 | fundamentally fix invisible button text on opaque backgrounds in the e-paper theme by removing the overly broad global text-color rule that caused it
- (feature) 실험적 페이지 넘김(page-flip) 뷰어에 순차 로딩 진행률 표시와 읽기 방향/속도 설정 기억 기능 추가 | add sequential loading progress display and persisted reading-direction/speed preferences to the experimental page-flip viewer

## v2.5.6
- (fix) 모바일(안드로이드 Chrome)에서 새로고침/뒤로가기 시 상단 검색창이 화면 밖으로 스크롤된 채 시작해 브라우저 주소창에 가려 보이던 문제 수정 | fix the mobile (Android Chrome) top search bar starting scrolled off-screen behind the browser's address bar after a reload or back navigation
- (fix) iOS에서 만화 스크롤 모드로 마지막 페이지(다음권/닫기) 상태일 때 뷰어를 닫으면 배경이 예전 스크롤 위치에 고정되어 화면이 안 움직이고 터치도 안 먹던 문제 수정 | fix the iOS comic scroll-mode viewer leaving the background page stuck at a stale scroll position and unresponsive to touch when closed from the last-page (next episode/close) overlay
- (security) 메타데이터 플러그인의 subprocess/os.system 등 외부 프로세스 실행을 기본 차단하고, `ALLOW_PLUGIN_SUBPROCESS=true` 설정 시에만 허용하되 파일 로그로만 기록 | block metadata plugins from spawning external processes (subprocess, os.system, etc.) by default; allow only when `ALLOW_PLUGIN_SUBPROCESS=true` is set, logging each case to a file only

## v2.5.5
- (feature) 사용자가 YAML 파일로 커스텀 테마를 등록할 수 있는 기능 추가 (`themes/` 디렉토리에 넣으면 자동 인식, 관리자 재스캔 버튼 지원) | add support for user-authored custom themes via YAML files dropped into `themes/` (auto-detected, with an admin rescan button)
- (feature) 커버 이미지 저장 경로를 다른 마운트 디스크로 바꿀 수 있는 설정 추가, 기존 커버 파일을 새 경로로 옮기는 이관 도구 포함 | add a configurable cover image storage path for routing to a separate mounted disk, including a tool to migrate existing cover files to the new location
- (fix) e-paper 등 일부 테마에서 불투명 배경 위 텍스트가 배경과 같은 색이라 안 보이던 문제 수정 | fix text becoming invisible against opaque backgrounds in some themes (e.g. e-paper) due to matching colors
- (chore) DB 스키마 마이그레이션 로직 중복 정리 및 설정 화면 JS 모듈 분리 등 소스 정리 | source cleanup: consolidate duplicated DB schema migration logic and split up the settings-page JS module

## v2.5.4
- (feature) 뷰어 오버레이 조작 패널에 드래그로 위치를 옮길 수 있는 앵커 추가 | add a drag handle to the viewer's overlay control panel so it can be repositioned
- (feature) PDF/만화 뷰어 2쪽보기 모드에 "한 장 밀기" 기능 추가 — (9,10)(11,12)처럼 고정되던 페이지 짝을 한 장씩 밀어 원하는 스프레드(예: 10,11)를 볼 수 있음, 단축키 Shift+스페이스/방향키 지원 | add a "shift by one page" control to PDF/comic viewer two-page spread mode — nudges the fixed page pairing (e.g. (9,10)(11,12)) by one page so a spread like (10,11) can be viewed, with a Shift+Space/Arrow keyboard shortcut

## v2.5.3
- (feature) 환경설정을 시스템 전역 설정과 "내 설정"(사용자별 개인화) 탭으로 분리, 일반 사용자도 테마/뷰어/사이드바 등 취향 설정을 직접 저장 가능 | split settings into system-wide settings and a "My Settings" tab for per-user personalization — non-admins can now save their own theme/viewer/sidebar preferences
- (improvement) 일반/성인/오디오북/영상 DB에 각각 중복 저장되던 시스템 설정값을 general DB 하나로 단일화 (라이브러리 DB 구조 자체는 기존과 동일) | unify system settings values into a single store on the general DB, previously duplicated across the general/adult/audiobook/video databases (the library DB structure itself is unchanged)
- (improvement) 외부 도메인 허용 목록을 사용자별 목록에서 관리자 전용 전역 목록으로 전환 | convert the external domain whitelist from a per-user list to an admin-managed global list
- (improvement) 권한 없는 관리자 전용 설정 탭 버튼이 일반 사용자 화면에 노출되지 않도록 변경 | hide admin-only settings tab buttons entirely for non-admin users instead of just disabling them

## v2.5.2
- (improvement) 기본 테마 팔레트를 보라/네이비 톤에서 무채색+블루 포인트 톤으로 변경 | change the default theme palette from purple/navy to a neutral + single blue accent tone
- (improvement) 상단 툴바를 한 줄 레이아웃으로 재구성하고 필터/정렬 버튼을 아이콘 전용으로 압축 | restructure the top toolbar into a single row and compress the filter/sort buttons to icon-only
- (improvement) 사이드바 하단의 환경설정/계정 메뉴를 상단 헤더 아이콘으로 이동 | move the sidebar's settings/account menu to top-header icons
- (feature) 상단 헤더를 전역 컴포넌트로 분리해 플러그인 화면에서도 항상 노출, 플러그인용 세션 조회 API(`window.BookOasisPlugin.getSession()`, `bookoasis:session-change` 이벤트) 추가 | split the top header into a global component always shown on plugin screens, and add a plugin-facing session API (`window.BookOasisPlugin.getSession()`, `bookoasis:session-change` event)
- (fix) CSS 정적 파일이 배포 후에도 브라우저에 캐시되어 반영이 안 되던 문제 수정 | fix CSS static files staying browser-cached after deploy instead of picking up changes
- (feature) 도서 상세 페이지에 "이 작가의 다른 도서" 사이드바 추가 (2단 레이아웃) | add a "more by this author" sidebar to the book detail page (two-column layout)
- (feature) 라이브러리별 자동 스캔 스케줄 ON/OFF 토글 추가 — 꺼두면 수동 스캔은 그대로 두고 예약 실행만 건너뜀 | add a per-library ON/OFF toggle for the scheduled scan — manual scans still work while off, only the scheduled run is skipped
- (feature) 설정에 "도서 추천기능" 체크박스 추가 — 해제 시 "이 작가의 다른 도서" 표시 안 함 | add a "book recommendations" checkbox to settings — disables the "more by author" sidebar when off
- (improvement) 더 이상 쓰이지 않는 "사이드바 환경설정/계정 상단 배치" 옵션 제거 | remove the now-unused "place sidebar settings/account at top" option

## v2.5.1
- (improvement) PDF 커버를 표지 표시 크기의 2배로 렌더링한 뒤 축소(수퍼샘플링)해 불필요한 대형 비트맵 생성은 피하면서 텍스트 선명도 유지 | improve PDF cover rendering to render at 2x the display size then downscale (supersampling), avoiding unnecessarily large intermediate bitmaps while keeping text crisp
- (breaking) PDF 처리 엔진을 PyMuPDF(AGPL)에서 pypdfium2(Apache-2.0/BSD, 크롬과 동일한 Pdfium 엔진)로 교체 | (breaking) switch PDF engine from PyMuPDF (AGPL) to pypdfium2 (Apache-2.0/BSD, the same Pdfium engine used by Chrome)
- (fix) PDF 뷰어에서 페이지를 넘길 때마다 흰 화면이 잠깐 보였다가 내용이 채워지던 깜빡임 수정 — 새 페이지 렌더링이 끝날 때까지 이전 페이지를 유지 | fix a white-flash-then-fill flicker on every PDF page turn — the previous page now stays visible until the new one finishes rendering
