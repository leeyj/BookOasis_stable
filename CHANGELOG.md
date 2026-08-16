# CHANGELOG
## v2.1.0
- (video) 오디오북과 나란한 새 미디어 세션 "영상 강좌" 추가 — 폴더당 강좌 1개, `S01E01` 명명 + `show.yaml` 사이드카(Plex TV쇼 스타일)로 에피소드를 인식하며, 전용 DB/스캐너/스트리밍(Range 206) 라우트와 사이드바 세션 토글, 관리자 권한 매트릭스를 갖춤 | add a new "Video Courses" media session alongside audiobooks — one course per folder, episodes recognized via `S01E01` naming + a `show.yaml` sidecar (Plex TV-show style), with its own DB/scanner/streaming (Range 206) routes, a sidebar session toggle, and an admin permission matrix
- (video) 상세페이지·이어보기·즐겨찾기·컬렉션·최근시청·전체보기·홈 대시보드(최근 시청/신규 추가)까지 오디오북과 동일한 공용 파이프라인에 통합 | integrate the detail page, resume-playback, favorites, collections, recently-watched, browse-all, and home dashboard (recent/newly-added rows) into the same shared pipeline used by audiobooks
- (video) 원격(rclone) 드라이브에서도 스캔이 느려지지 않도록 재생시간/해상도 추출을 백그라운드 지연(Lazy) 분석으로 분리 | keep scans fast on remote (rclone) drives by moving duration/resolution extraction into a background lazy-analysis pass instead of doing it synchronously during scan
- (video) 브라우저가 직접 재생 가능한 파일은 원본을 그대로 스트리밍하고, MKV 등 비호환 파일만 ffmpeg로 자동 폴백(CPU 기본, Intel VAAPI 하드웨어 가속 감지 시 자동 전환) — 설정 화면에 VAAPI 지원 여부 점검 버튼 및 커스텀 인코딩 파라미터 입력란 추가 | stream browser-compatible files as-is, and automatically fall back to ffmpeg only for incompatible files like MKV (CPU by default, auto-switching to Intel VAAPI hardware acceleration when detected) — added a VAAPI availability check button and custom encoding-parameter fields to Settings
- (video) SMI/SRT 자막 사이드카(언어 태그 포함 파일명, 예: `.ko.srt`)를 자동 인식해 WebVTT로 변환 후 재생 시 자막으로 표시 | auto-detect SMI/SRT subtitle sidecars (including language-tagged filenames like `.ko.srt`), convert them to WebVTT, and show them as subtitles during playback
- (fix) 그리드 뷰에서 제목이 긴 카드가 그리드 트랙을 밀어 넓히면서 카드 크기가 환경설정의 썸네일 크기를 따라가지 않던 문제 수정(일반 도서/오디오북/영상 강좌 공통) | fix grid cards not respecting the configured thumbnail-size setting when a long title pushed its grid track wider than the rest (affected general books, audiobooks, and video courses alike)
- (db) MariaDB에서 `collection_items.video_id` 컬럼 자동 마이그레이션이 인라인 FK 절 때문에 조용히 실패하던 문제 수정, 스키마 자동 보강 실패 시 로그를 남기도록 개선 | fix `collection_items.video_id` auto-migration silently failing on MariaDB due to an inline foreign-key clause, and make schema auto-repair failures log instead of failing silently

## v2.0.6
- (api) DB 게이트웨이를 거치지 않고 직접 DB에 접속해야 하는 외부 연동 프로그램/플러그인용, 현재 DB 엔진(SQLite/MariaDB)을 확인할 수 있는 웹훅 API(`/api/webhook/system/db-engine`) 추가 | add a webhook API (`/api/webhook/system/db-engine`) so external programs/plugins that must connect to the DB directly (bypassing the API gateway) can check whether the current DB engine is SQLite or MariaDB

## v2.0.5
- (dashboard) TV용 UI 추가(베타) - 사이드바 그룹 드로어, 이어보기/최근추가 홈, 카테고리 그리드(정렬 지원), 킷오스크 리더/플러그인 모드(`/?kiosk=1`), 팝업 로그인/로그아웃, 리모컨(방향키/Enter/ESC) 내비게이션 | added TV app UI (beta) - overlay category drawer, continue-reading/recently-added home rows, sortable category grid, kiosk reader/plugin mode (`/?kiosk=1`), popup login/logout, and remote-control (arrow/Enter/Esc) navigation
- (category) 라이브러리/플러그인 카테고리를 가상 그룹(폴더)에 넣고 드래그로 정렬할 수 있는 기능 추가 | add virtual groups (folders) for library/plugin categories in the sidebar, with drag-to-reorder for both group members and the groups themselves
- (plugin) 저장소가 기본 제공하던 샘플 플러그인 7종을 바인드 마운트 대상인 `plugins/metadata/`에서 마운트되지 않는 `sample_plugins/metadata/`로 이동 — 업데이트(`git pull`/`git clean` 등) 시 사용자가 직접 설치한 플러그인이 유실되던 문제 해결. [설정 > 플러그인] 탭에 "샘플에서 설치" 버튼 추가, 빈 마운트에서도 부팅되도록 프레임워크 필수 파일 자동 시드 로직 추가 | move the 7 bundled sample plugins out of the bind-mounted `plugins/metadata/` into a non-mounted `sample_plugins/metadata/`, fixing user-installed plugins being wiped out on update (`git pull`/`git clean`, etc.) — added an "Install from sample" button in [Settings > Plugins], plus boot-time auto-seeding of required framework files so the app still starts on a completely empty mount
- (docker) 기본 `docker-compose.yml`을 로컬 빌드 대신 GHCR 공식 이미지(`ghcr.io/leeyj/bookoasis:stable`) 사용으로 전환, 소스 직접 빌드용 `docker-compose.build.yml` 및 MariaDB 콤보용 `docker-compose.mariadb.ghcr.yml` 추가 | switch the default `docker-compose.yml` to pull the official GHCR image instead of building locally, and add `docker-compose.build.yml` (source build) and `docker-compose.mariadb.ghcr.yml` (MariaDB combo + GHCR) variants

## v2.0.4
- (lib) requests 라이브러리 추가 | added requests

## v2.0.3
- (plugin) 오디오북 라이브러리 스캔에서 신규 도서 감지 시 웹훅/플러그인 훅(`on_scan_new_books_detected`)이 전혀 호출되지 않던 문제 수정 — 일반/성인 도서 스캔과 동일하게 `services/audiobook_scanner.py`에서 표준 이벤트 및 플러그인 훅을 디스패치하도록 추가 | fix audiobook library scans never dispatching the new-book webhook/plugin hook (`on_scan_new_books_detected`) — `services/audiobook_scanner.py` now dispatches the same standard event and plugin hook as regular/adult book scans
- (plugin) `webhook_new_books_notify` 플러그인이 User-Agent 헤더 없이 요청을 보내 Discord/Cloudflare에서 403(에러 1010)으로 차단되던 문제 수정, 알림 메시지도 원본 JSON을 그대로 보내던 것에서 사람이 읽기 좋은 형태(예: "📚 새 도서 74권 추가됨 - 만화(완결A)" + 샘플 제목 + "...외 N권")로 변경 | fix `webhook_new_books_notify` plugin requests being blocked by Discord/Cloudflare (403 / error 1010) due to a missing User-Agent header, and switch notification messages from raw JSON dumps to human-readable text (e.g. "📚 74 new books added - Comics(CompleteA)" plus sample titles and a "...N more" summary)
- 문서 최신화 | update document

## v2.0.2
- (plugin) 플러그인이 사용자가 직접 등록한 화이트리스트 도메인에 한해 외부 사이트를 앱 내 웹뷰로 열거나, 파일을 다운로드해 라이브러리로 바로 임포트할 수 있는 API(`window.BookOasisPlugin.openWebview`/`downloadToLibrary`) 및 [설정 > 외부 도메인] 관리 탭 추가. 앱은 어떤 도메인도 기본 제공/추천하지 않으며 SSRF 방어(사설 IP 차단, 리다이렉트 재검증, 응답 크기 제한)를 거침 | add plugin API (`window.BookOasisPlugin.openWebview`/`downloadToLibrary`) and a new [Settings > External Domains] tab, letting plugins show an external site in an in-app webview or download a file straight into a library — restricted to domains the user explicitly whitelists (the app ships no default/recommended domains), with server-side SSRF protection (private IP blocking, redirect re-validation, response size caps)
  - 샘플 플러그인 참고: `plugins/metadata/gutenberg_browser` | see sample plugin: `plugins/metadata/gutenberg_browser`



## v2.0.1
- (viewer/epub,txt) 2페이지 보기에서 짧은 챕터/안드로이드 태블릿의 서브픽셀 반올림 오차로 챕터 끝 판정이 틀어져 다음 챕터로 못 넘어가거나 페이지 넘길 때마다 화면이 밀리던 버그 수정 | fix chapter-end miscalculation on short chapters and Android tablets (sub-pixel rounding) that blocked next-chapter advance or caused the page to drift left on every page turn
- (viewer/epub) EPUB 뷰어에 브라우저 리사이즈 리스너가 아예 등록되지 않아 창 크기를 줄이면 2페이지 모드가 1페이지처럼 깨지던 버그 수정 | fix EPUB viewer having no resize listener at all, which broke 2-page mode into a 1-page-like layout when the browser window was resized
- (dashboard) 가나다 정렬에서 초성 바로가기로 중간 페이지에 진입한 뒤 위로 스크롤하면 이전 페이지를 불러오지 못해 더 이상 스크롤되지 않던 문제 수정(위쪽 무한 스크롤 추가) | fix scrolling up getting stuck after jumping to a mid-list page via the A-Z index shortcut by adding upward infinite scroll to load earlier pages
- (dashboard) 다운로드 클릭시 책이 열리는 현상 수정 | fix download button error