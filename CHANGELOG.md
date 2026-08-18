# CHANGELOG
## v2.1.8
- (fix) TXT/EPUB 2페이지 모드에서 짧은 챕터로 넘어간 직후 빠르게 다시 넘기면 챕터가 건너뛰거나 같은 내용이 반복 표시되던 문제 수정 (챕터 전환 중 재진입을 막는 가드 누락) | fix TXT/EPUB 2-page mode skipping or re-showing already-seen content when tapping next/prev right after landing on a short chapter (missing re-entrancy guard during chapter transitions)
- (fix) TXT/EPUB 2페이지 모드에서 컬럼(페이지) 수가 홀수인 챕터의 마지막 페이지가 직전 페이지 내용을 다시 보여주던 문제 근본 수정 | fix TXT/EPUB 2-page mode re-showing the previous page's content on the last page of chapters with an odd column count
- (fix) 서버 재시작 후 Lazy 스캐너가 간헐적으로 재개되지 않던 문제 수정 — 워커 생존 여부를 PID 존재만으로 판단해, 재사용된 PID를 오인해 작업이 영구히 고착될 수 있었음 | fix the lazy scanner occasionally not resuming after a server restart — worker liveness was checked by PID existence alone, which could misidentify a reused PID and leave a task permanently stuck
- (perf) 오디오북/영상 강좌 포스터를 요청마다 원격 재조회하던 것을 로컬 WebP 캐시로 전환 — 도서 표지와 동일한 방식(캐시 헤더 포함)으로 서빙 | switch audiobook/video course posters from re-fetching remotely on every request to a local WebP cache — now served the same way as book covers, with proper cache headers

## v2.1.7
- (viewer) 만화 뷰어에 스프레드 이미지 좌우 분할 보기 옵션 추가 | add a split-view option for spread images in the comic viewer
- (fix) 시리즈 상세 화면에서 "읽지 않음으로 변경"이 실제로는 반영됐지만 화면(진행률)이 갱신되지 않던 문제 수정(죽은 DOM 참조) | fix "mark as unread" actually working but not refreshing the on-screen progress bar in the series detail view (stale DOM reference)
- (fix) 시리즈 재스캔/도서 재스캔/완독 처리 버튼이 클릭한 버튼이 아닌 document를 참조해 스피너·완료 토스트가 제대로 안 뜨던 문제 수정 | fix series/book rescan and mark-completed buttons referencing document instead of the clicked button, breaking the spinner and completion toast
- (fix) TXT/EPUB 연속된 빈 줄이 1개로 정리되도록 수정 | fix consecutive blank lines not collapsing in TXT/EPUB
- (viewer) TXT/EPUB 행간 설정에 1.2 옵션 추가 | add a 1.2 line-height option to TXT/EPUB
- (fix) 만화 뷰어 오버레이 "보기" 탭 2줄 레이아웃 여백 수정 | fix layout spacing in the comic viewer's "Layout" tab
- (fix) 영상 강좌 정렬 시 카드가 오디오북 스타일로 잘못 바뀌던 문제 수정 | fix video course cards switching to the wrong style on sort
- (perf) EPUB 챕터 캐시 조회 최적화 | optimize EPUB chapter cache lookups
- (chore) 구조 변경 후 남아있던 죽은 코드 2차 정리(오디오 볼륨 팝오버, 뷰어 페이지 정보/여백 패널, 설정의 만화 여백/TTS 항목, 미사용 뷰어 유틸 파일, 예전 페이지 점프 별칭) | second pass removing leftover dead code (audio volume popover, viewer page-info/padding panel remnants, comic-padding/TTS settings fields, an unused viewer utils file, an old page-jump alias)
- (perf) EPUB 챕터 프리페치를 배치 API로 전환해 로딩 속도 개선 | switch EPUB chapter prefetching to a batch API for faster loading
- (feature) 세션 전환 단축키(1/2/3)에 영상 강좌(4) 추가 | add video courses (4) to the session-switch keyboard shortcut (1/2/3)
- (settings) 플러그인 관리 목록을 아코디언 형태로 개편 — 기본은 이름/ID/토글만 보이는 한 줄, 클릭하면 설명·설정 폼이 펼쳐짐(플러그인 많을 때 스크롤 과다 문제 개선) | redesign the plugin management list as an accordion — collapsed by default to a single row (name/ID/toggle), expanding to show description and settings on click (reduces excessive scrolling with many plugins)
- (fix) 컨텍스트 메뉴 플러그인 액션이 이동할 URL 없이 끝나면 미리 열어둔 빈 팝업창이 그대로 남던 문제 수정 (커뮤니티 리포트) | fix a blank placeholder popup window being left open when a context-menu plugin action finishes without an `open_url` to navigate to (community-reported)
- (perf) Lazy 스캐너의 영상 재생시간(ffprobe) 백필/컨테이너 재검증을 스레드풀로 병렬 처리 — 동시 처리 개수를 설정에서 조절 가능(기본 4개), 원격 마운트에서 대량 백로그 처리 속도 대폭 개선 | parallelize the lazy scanner's video duration (ffprobe) backfill and container re-validation with a thread pool — concurrency is now configurable (default 4), greatly speeding up large backlogs on remote mounts
- (chore) 모바일 헤더 표시 문제(해결 완료) 진단용으로 남아있던 사이드바 원격 로깅 3건 제거 — 모니터링 로그 소음 정리 | remove 3 leftover sidebar remote-logging calls added to diagnose the (now-resolved) mobile header visibility bug — cleans up monitoring log noise
- (fix) 배포해도 static/js 파일이 브라우저/중간 캐시에 예전 버전으로 남아있던 문제 근본 수정 — /static/js/**를 매 요청 서버 재검증(Cache-Control: no-cache, must-revalidate)으로 전환 (진입점 스크립트만 버전 쿼리스트링이 붙고 내부 import 229개 중 224개는 안 붙어있던 게 원인) | fix deployed changes under static/js not reliably reaching browsers/intermediate caches — switched /static/js/** to always revalidate with the server (Cache-Control: no-cache, must-revalidate); root cause was that only entry-point scripts got a version query string, while 224 of 229 internal ES module imports had none
- (fix) 라이브러리 목록에서 제목 내림차순 정렬이 페이지 2부터 뒤죽박죽 나오던 문제 수정 — SQL이 항상 오름차순으로 페이지를 가져온 뒤 그 결과만 파이썬에서 뒤집던 구조적 버그(특수문자 때문이 아니었음) | fix title-descending sort in the library list producing scrambled results from page 2 onward — SQL always paginated in ascending order and only reversed that already-wrong page in Python (not a special-character issue)
- (fix) 뷰어를 닫지 않고 사이드바 "홈"/"최근 읽은 도서"로 바로 이동하면 방금 본 책이 대시보드에 한 권 밀려 보이던 문제 수정 — 대기 중인 진행률을 먼저 반영한 뒤 조회하도록 변경(안 그러면 서버의 1시간 캐시가 그 책 빠진 스냅샷으로 굳어버림) | fix the home dashboard/history view showing the last-read book one entry behind when navigating away via the sidebar without closing the viewer first — now flushes any pending progress before fetching (otherwise the server's 1-hour cache could lock in a snapshot missing that book)

## v2.1.6
- (viewer) 모바일 세로 스와이프 방향 수정(위=다음, 아래=이전) | fix mobile vertical swipe direction (up=next, down=previous)
- (viewer) 탭존 방향 좌우/상하 전환 옵션 추가 | add an option to switch tap-zones between horizontal/vertical

## v2.1.5
- (fix) 모바일 사이드바 햄버거 버튼 핀치줌 시 흔들림 수정 | fix sidebar hamburger button jittering on pinch-zoom
- (fix) iOS 헤더가 간헐적으로 사라지던 문제 수정 | fix header intermittently disappearing on iOS
- (video) iOS 영상 강좌 재생 실패 수정(HLS 도입) | fix video course playback failing on iOS (added HLS)
- (fix) 영상 스트리밍 캐시 방지 헤더 누락 수정 | fix missing cache-prevention header on video streaming
- (video) 강좌 제목 HTML 엔티티 노출 수정 | fix raw HTML entities in video course titles
- (fix) SQLite 컬럼/인덱스 자동 보강 회귀 수정 | fix SQLite auto column/index migration regression
- (video) 영상 강좌 잠금화면 백그라운드 재생 미지원 공식화 | video courses officially don't support background playback
- (fix) 오디오북 화면 잠금 시 재생 끊김 수정 | fix audiobook playback cutting out on screen lock

## v2.1.4
- (fix) iOS 영상 강좌 재생 시작 안 되던 문제 수정 | fix video course playback not starting on iOS
- (plugin) 카테고리 플러그인 세션별 노출 제어 추가 | add per-session visibility control for category plugins
- (video) 원격 마운트 트랜스코딩 정체 시 좀비 프로세스 문제 수정 | fix zombie processes on transcoding stalls over remote mounts
- (db) MariaDB GRANT 문제 근본 수정(자동 재부여 컨테이너 추가) | fix MariaDB GRANT issues at the root (auto re-grant container)
- (fix) GRANT 실패 시 로그에 실행 가능한 SQL 출력 | print copy-pasteable SQL in logs on GRANT failure
- (fix) MariaDB 일부 DB GRANT 누락 시 전체 부팅 실패하던 문제 수정 | fix full boot failure from one missing MariaDB grant
- (video) AMD VAAPI 트랜스코딩 실패 수정 | fix AMD VAAPI transcoding failure
- (fix) 핀치줌 시 사이드바 버튼 화면 이탈 수정 | fix sidebar button leaving screen on pinch-zoom
- (fix) 카테고리 이동 시 컬럼 초기화되던 문제 수정 | fix columns resetting on category move

## v2.1.3
- (fix) MariaDB 인덱스 자동 생성 실패 수정 | fix MariaDB auto index creation failing
- (video) mkv 브라우저 직접재생 호환 목록에 추가 | add mkv to browser-direct-play compatible list
- (fix) 영상 강좌 전체보기 검색 0건 버그 수정 | fix video course "browse all" search returning 0 results
- (fix) 영상 강좌 UI 설정(썸네일 크기 등) 미적용 수정 | fix video course screens ignoring UI settings
- (fix) 대시보드 에러 원문 노출 수정 | fix raw error messages leaking on dashboard
- (fix) 영상 재생시간/해상도 백필 미실행 및 로그 문제 수정 | fix video duration/resolution backfill not running plus logging issues
- (fix) 대괄호 태그 제목 초성 점프 오류 수정 | fix alphabet-jump landing wrong on bracket-tag titles
- (fix) 영상 강좌 "전체 읽지 않음 처리" 미동작 수정 | fix "mark unread" not working for video courses

## v2.1.2
- (db) MariaDB GRANT를 와일드카드 패턴으로 변경 | switch MariaDB grants to a wildcard pattern

## v2.1.1
- (video) 영상 강좌 Media Session API(잠금화면 컨트롤) 연동 | add Media Session API integration for video courses
- (tools) 카테고리 내보내기/가져오기에 영상 강좌 지원 추가 | add video course support to category export/import
- (fix) arm64 도커 이미지 빌드 실패 수정 | fix arm64 Docker build failure

## v2.1.0
- (video) 새 미디어 세션 "영상 강좌" 추가 | add new "Video Courses" media session
- (video) 상세/이어보기/즐겨찾기 등 공용 파이프라인 통합 | integrate video courses into the shared detail/resume/favorites pipeline
- (video) 재생시간/해상도 추출을 백그라운드 지연 분석으로 분리 | move duration/resolution extraction to a background lazy-analysis pass
- (video) 브라우저 비호환 파일만 자동 트랜스코딩(VAAPI 지원) | auto-transcode only browser-incompatible files (VAAPI support)
- (video) SMI/SRT 자막 자동 인식 지원 | auto-detect SMI/SRT subtitles
- (fix) 긴 제목이 그리드 카드 크기를 깨던 문제 수정 | fix long titles breaking grid card sizing
- (db) MariaDB video_id 컬럼 마이그레이션 실패 수정 | fix MariaDB video_id column migration failure

## v2.0.6
- (api) DB 엔진 확인용 웹훅 API 추가 | add a webhook API to check the current DB engine

## v2.0.5
- (dashboard) TV용 UI 추가(베타) | add TV UI (beta)
- (category) 카테고리 가상 그룹/드래그 정렬 추가 | add virtual groups and drag-to-reorder for categories
- (plugin) 샘플 플러그인 위치 이동(업데이트 시 유실 방지) | move sample plugins to prevent loss on update
- (docker) 기본 이미지를 GHCR 공식 이미지로 전환 | switch default Docker image to the official GHCR image

## v2.0.4
- (lib) requests 라이브러리 추가 | add requests library

## v2.0.3
- (plugin) 오디오북 스캔 시 웹훅 훅 미호출 수정 | fix webhook hook not firing on audiobook scans
- (plugin) 알림 웹훅 403 차단 및 메시지 가독성 수정 | fix notification webhook being blocked (403) and improve message readability
- 문서 최신화 | update docs

## v2.0.2
- (plugin) 화이트리스트 도메인 웹뷰/다운로드 API 추가 | add whitelisted-domain webview/download API for plugins

## v2.0.1
- (viewer) EPUB/TXT 2페이지 모드 챕터 끝 판정 오류 수정 | fix EPUB/TXT 2-page mode chapter-end miscalculation
- (viewer) EPUB 리사이즈 리스너 누락 수정 | fix missing resize listener in EPUB viewer
- (dashboard) 초성 점프 후 위로 스크롤 안 되던 문제 수정 | fix upward scroll breaking after alphabet-jump
- (dashboard) 다운로드 클릭 시 책이 열리던 문제 수정 | fix download click accidentally opening the book
