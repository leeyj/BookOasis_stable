# CHANGELOG
## v2.4.3
- (fix) 도커 PUID 사용 시 앱 계정(media_user)과 rclone.conf를 설정한 계정(root)의 홈 디렉토리가 달라 리모트를 못 찾던 문제 수정 (실험적, DEVELOP=true 전용) | fix the app (media_user) failing to find rclone.conf configured under root's home when running with a Docker PUID (experimental, DEVELOP=true only)

## v2.4.2
- (fix) "Drive에서 복사해오기" dest_path 불일치 무음 처리 문제 — 경고 로그 추가 (실험적, DEVELOP=true 전용) | fix "Copy from Drive" silently swallowing dest-path mismatches — added a warning log (experimental, DEVELOP=true only)
- (feature) `RCLONE_CONFIG_PATH`/`RCLONE_CONFIG` 환경변수로 rclone.conf 경로 직접 지정 (실험적, DEVELOP=true 전용) | add `RCLONE_CONFIG_PATH`/`RCLONE_CONFIG` env vars to set a custom rclone.conf path (experimental, DEVELOP=true only)
- (fix) 마운트 루트 매칭에 심볼릭 링크·대소문자 차이 허용 (실험적, DEVELOP=true 전용) | fix mount-root matching to tolerate symlinks and case differences (experimental, DEVELOP=true only)
- (fix) 도커 rclone RC 연결 실패 문제 — 기본 후보에 `host.docker.internal` 추가, 실패 로그에 안내 힌트 추가 (실험적, DEVELOP=true 전용) | fix rclone RC connections failing in Docker — added `host.docker.internal` as a default fallback and a hint in failure logs (experimental, DEVELOP=true only)

## v2.4.1
- (fix) 도커 환경에서 "Drive에서 복사해오기"의 마운트 루트 자동 감지가 실패하던 문제 — 마운트 루트 직접 입력 필드 추가 (실험적, DEVELOP=true 전용) | fix mount-root auto-detect failing for "Copy from Drive" in Docker setups — added a manual mount-root input field (experimental, DEVELOP=true only)

## v2.4.0
- (refactor) 구글 드라이브 책 단위 사전복사를 REST API 직접 호출 대신 rclone CLI(`backend copyid`/`copy`) 기반으로 교체 (실험적, DEVELOP=true 전용) — 로컬 마운트가 실제로 보여주는 경로 체계와 항상 일치해 이전 세션들에서 반복된 root_folder_id/마운트 서브경로 스코핑 버그가 원천적으로 사라짐 | switch Google Drive per-book pre-copy from direct REST API calls to the rclone CLI (`backend copyid`/`copy`) (experimental, DEVELOP=true only) — always matches the path scheme the local mount actually shows, eliminating the class of root_folder_id/mount-subpath scoping bugs hit in prior sessions
- (제약사항/known limitation) 구글 드라이브 공유 카테고리에서 zip/cbz로 묶이지 않은 낱장 이미지 폴더(이미지 폴더 책)는 지원하지 않습니다 — 이미지 폴더를 공유받았다면 "Drive에서 복사해오기"로 폴더째 내 드라이브에 복사한 뒤, 그 폴더를 가리키는 일반 카테고리를 새로 만들어 보세요(로컬 이미지 폴더는 정상 지원). | (limitation) Google Drive share categories don't support loose image-folder books (comics not packaged as zip/cbz) — if you've been shared one, use "Copy from Drive" to copy the whole folder into your own Drive first, then create a regular category pointing at it (local image-folder books are fully supported)
- (제약사항/known limitation) 구글 드라이브 책 단위 사전복사(뷰어에서 열 때 자동 복사)는 일반/성인 서재의 zip/cbz·epub·txt·pdf 도서에만 적용됩니다 — 오디오북/영상 강좌는 별도 스캐너·스트리밍 경로를 쓰기 때문에 해당 카테고리에 구글 드라이브 공유 링크를 넣어도 지원되지 않습니다(생성 자체는 막혀 있지 않지만 스캔 결과가 0권으로 끝남). 오디오북/영상을 공유받았다면 "Drive에서 복사해오기"로 내 드라이브에 먼저 복사한 뒤 로컬 카테고리로 등록해 주세요. | (limitation) Google Drive per-book pre-copy (auto-copy on viewer open) only applies to zip/cbz, epub, txt, and pdf books in general/adult libraries — audiobooks and video courses run separate scanner/streaming pipelines and don't support it (creating such a category isn't blocked, it just scans 0 books). If you've been shared an audiobook or video course, use "Copy from Drive" to copy it into your own Drive first, then register it as a regular local category
- (fix) 구글 드라이브 사본 뷰어가 "복사 성공"으로 기록되고도 실제 파일은 로컬 마운트에 영원히 안 나타나던 문제 수정 (실험적, DEVELOP=true 전용) — 카테고리의 "로컬 마운트 루트"에 순수 마운트 지점이 아니라 정리용 하위 폴더까지 포함한 경로를 넣으면, Drive 쪽 캐시는 항상 진짜 루트에 만들어지고 로컬 조회만 그 하위 폴더에서 찾아서 서로 어긋났음. 이제 그 하위 폴더 차이를 감지해 Drive 쪽에도 동일하게 만들어 정리되도록 함 (겸사겸사 rclone 리모트가 root_folder_id로 스코핑된 경우의 별개 버그도 같이 수정) | fix Google Drive view-copy logging "success" while the file never actually appears under the local mount (experimental, DEVELOP=true only) — setting a category's "local mount root" to a tidy subfolder instead of the bare mount point caused the Drive-side cache to always land at the true root while local lookup searched inside that subfolder, so they pointed at different places. Now the extra subfolder is detected and mirrored on the Drive side too (also fixed a separate bug for rclone remotes scoped via root_folder_id)
- (feature) 구글 드라이브 "폴더 전체 복사"를 카테고리와 무관한 독립 동작으로 분리 (실험적, DEVELOP=true 전용) — 더 이상 복사 전용 카테고리를 미리 만들어둘 필요 없이 리모트 + 저장 폴더만 지정하면 실행되고, 복사해온 파일을 카테고리로 등록할지는 완료 후 자유롭게 결정. 카테고리 모달의 구글 드라이브 연결은 "책 열 때 그 1권만 복사"하는 뷰어 전용 용도로 단순화 | decouple Google Drive "copy whole folder" from categories (experimental, DEVELOP=true only) — no longer requires pre-registering a copy-only category, just pick a remote + destination folder and run it; whether to register the copied files as a category is a free choice made afterward. The category modal's Drive connection is simplified to its one remaining purpose: per-book copy-on-open
- (fix) 브라우저 탭 파비콘이 로고 원본(여백 큼)을 그대로 써서 작게 보이던 문제 수정 — 홈 화면 아이콘용으로 이미 만들어둔 꽉 찬 아이콘을 재사용 | fix the browser tab favicon looking small (it used the padded logo source) — reuse the already-cropped home-screen icon
- (fix) TXT/EPUB에서 형광펜 모드를 한 번 켠 뒤 zip(이미지) 도서를 열면 형광펜 토글 버튼이 그대로 남아 뜨던 문제 수정 — 뷰어를 열 때마다 포맷에 맞춰 버튼 표시 여부를 다시 동기화 | fix the highlight-mode toggle button staying visible in zip (image) viewers after being shown once in a TXT/EPUB session — button visibility is now re-synced to the format on every viewer open
- (feature) 구글 드라이브 복사/뷰-복사 플러그인 연동 API 추가 (실험적, DEVELOP=true 전용) — 책 단위 사전복사 상태 조회(`/api/gdrive-view-copy/status`), 뷰어를 열지 않고 미리 복사(`/api/gdrive-view-copy/prefetch`), gdrive 공유 카테고리 목록 조회(`/api/gdrive-view-copy/libraries`) 신설, 기존 일괄 복사 API(`/api/gdrive-copy/*`)도 함께 플러그인 가이드에 정식 문서화 | add a plugin integration API for the Google Drive copy/view-copy features (experimental, DEVELOP=true only) — new per-book pre-copy status lookup (`/api/gdrive-view-copy/status`), prefetch-without-opening-the-viewer (`/api/gdrive-view-copy/prefetch`), and gdrive-share category listing (`/api/gdrive-view-copy/libraries`); also formally documented the existing batch-copy API (`/api/gdrive-copy/*`) in the plugin guide

## v2.3.3
- (fix) 홈 화면 아이콘이 다른 앱들보다 유독 작아 보이던 문제 수정 — 여백 없이 꽉 채운 전용 아이콘 + PWA 매니페스트 추가 | fix the home-screen icon looking noticeably smaller than other apps — added a properly full-bleed icon set + PWA manifest
- (fix) 모바일에서 형광펜(하이라이트) 모드 진입 시 본문을 가리거나 페이지 넘김이 안 되는 등 여러 터치 충돌이 발생하던 문제 — 모바일에서는 형광펜 기능을 비활성화 (데스크톱은 그대로 유지) | fix multiple touch conflicts (button covering text, broken page-turn touch) when entering highlight mode on mobile — the highlight/annotation feature is now disabled on mobile (desktop unaffected)

## v2.3.2
- (fix) 확장자는 mp3지만 실제 컨테이너/코덱이 다른(MPEG-TS 등) 오디오북 파일이 재생되지 않던 문제 수정 — 실시간 트랜스코딩 및 seek 지원 추가, 트랜스코딩 중에는 플레이어에 경고 배너 표시 | fix audiobook files with a `.mp3` extension but a mismatched actual container/codec (e.g. MPEG-TS) failing to play — added on-the-fly transcoding with seek support and an in-player warning banner while transcoding
- (feature) 구글 드라이브 사본 뷰어 로컬 캐시에 24시간 고정 TTL 자동 정리 작업 추가 | add a fixed 24-hour TTL auto-cleanup job for the Google Drive view-copy local cache
- 카테고리 메뉴 전면 개편
    -구글 링크 등록 기능등
    -카테고리 추가/수정 모달에 "구글 드라이브 사본 뷰어 연결" 설정을 별도 접이식 섹션으로 분리
    
## v2.3.1
- (fix) 단건/경로 단위 도서 스캔 후 대시보드 "신규 추가 도서" 캐시가 갱신되지 않아 표지가 기본 폴백으로 보이던 문제 수정 | fix the dashboard "newly added" widget showing a fallback cover after a single-book/path scan — the recent-added Redis cache wasn't being invalidated on that path
- (feature) 구글 드라이브 공유 폴더를 카테고리로 등록해 바로 스트리밍하는 기능 추가 (실험적, DEVELOP=true 전용) | add registering a Google Drive share folder as a category for direct streaming (experimental, DEVELOP=true only)
- (feature) 구글 드라이브 공유 폴더를 사용자 자신의 드라이브로 서버사이드 복사한 뒤 로컬처럼 스캔하는 기능 추가 (실험적, DEVELOP=true 전용) | add server-side copying a Google Drive share folder into your own Drive, then scanning it like a local mount (experimental, DEVELOP=true only)



## v2.3.0
- (feature) EPUB/TXT 뷰어에 하이라이트(형광펜) 기능 추가 — 형광펜 모드 토글로 페이지/스크롤 모드 모두 지원 | add highlight support to the EPUB/TXT viewer — a dedicated toggle mode works in both page and scroll reading modes
- (feature) 하이라이트 우클릭/롱프레스 메뉴에 플러그인 확장 지점 추가 — 커뮤니티 플러그인이 옵시디언/노션 등으로 내보내기 가능, 입력이 필요한 액션(prompt 응답)도 지원. 자세한 내용은 [플러그인 개발 가이드](docs/guide_plugins.md#7-하이라이트주석-컨텍스트-메뉴-확장-계약) 참조 | add a plugin extension point to the highlight context menu (right-click/long-press) so community plugins can export highlights to Obsidian, Notion, etc., including actions that need user text input. See the [plugin developer guide](docs/guide_plugins_en.md#7-annotation-highlight-context-menu-extension-contract) for details
- (settings) 하이라이트 모드 전환용 `H` 단축키 추가, 설정 > 단축키 탭에 재지정 불가한 고정 단축키(뷰어/오디오플레이어/TV모드/이스터에그) 안내 섹션 신설 | add the `H` shortcut to toggle highlight mode, and a new read-only reference section in Settings > Shortcuts listing all fixed (non-remappable) shortcuts across the viewer, audio player, TV mode, and easter egg

## v2.2.1
- (fix) 영상 강좌 커버 누락 시 세로형 책 폴백 이미지가 16:9로 잘려 텅 비어 보이던 문제 수정 — 영상 전용 가로형 폴백 이미지 추가 | fix the missing-cover fallback looking empty/cropped on video courses (portrait book template squeezed into 16:9) — added a dedicated landscape fallback for video
- (fix) 특정 kavita.yaml 생성 도구가 출력하는 깨진 search 블록 때문에 커버(Base64) 정보를 통째로 못 읽던 문제 수정 | fix a malformed search block from a specific kavita.yaml generator breaking cover (Base64) parsing entirely


## v2.2.0
- (fix) 대용량/원격 라이브러리에서 Lazy 스캐너가 시간 초과로 조용히 멈추던 문제 수정 | fix lazy scanner silently stopping on timeout for large/remote libraries
- (fix) 영상 강좌 탭 대시보드에 일반 도서 위젯이 표시되던 문제 수정 | fix general-book widgets showing on the video course dashboard
- (fix) 영상 강좌/오디오북 보관함 총계에서 편·트랙 수가 강좌 수와 항상 같게 나오던 문제 수정 | fix library total count always showing the same number for courses and episodes/tracks
- (perf) Lazy 스캐너가 커버 실패 도서를 매번 재검사하지 않도록 개선 | lazy scanner no longer re-checks cover-extraction failures on every run
- (feature) 보스키(Alt+Q/qq) 위장 화면 이미지를 `/covers/fake_screen.png`로 이전 — 같은 파일명으로 덮어써서 임의 교체 가능 | move the boss-key (Alt+Q/qq) decoy screen image to `/covers/fake_screen.png` — overwrite the same filename to customize it
- (feature) 영상 강좌 썸네일을 16:9 비율로 표시 — 전체보기/즐겨찾기/최근/대시보드/컬렉션 전 구간에 일관 적용, 해당 구간에서 영상이 오디오북으로 오인되어 재생 버튼이 깨지던 문제도 함께 수정 | display video course thumbnails at 16:9 across browse-all/favorites/history/dashboard/collections, also fixing videos being misidentified as audiobooks (broken play button) in those views
- (fix) 영상 강좌 카테고리 삭제 시 관련 데이터(videos/video_episodes/video_progress/video_episode_progress)가 정리되지 않아 전체보기에 계속 남아있던 문제 수정 | fix deleting a video course category leaving its rows behind in browse-all — related tables were never cleaned up on category delete
- (fix) 트래픽이 많은 서버에서 gunicorn 워커 재활용(`--max-requests`) 시 신호가 같은 프로세스 그룹의 Lazy 스캐너까지 새어 들어가 스캔이 반복적으로 중단되던 문제 수정 — 스캐너 워커를 `setsid`로 분리된 세션에서 구동 | fix the lazy scanner repeatedly getting killed mid-run on high-traffic servers when gunicorn recycled a worker (`--max-requests`) — signals were leaking into the scanner worker's shared process group; it now runs in its own session via `setsid`

## v2.1.9
- (fix) 오래된 버전부터 업데이트해온 MariaDB 사용자에서 신규 오디오북 저장이 `(1364, "Field 'title' doesn't have a default value")`로 실패하던 문제 수정 — 구형 스키마의 `audiobook_tracks.title` NOT NULL 제약이 남아있던 것이 원인, 재시작 시 자동 보정 | fix new audiobooks failing to save with `(1364, "Field 'title' doesn't have a default value")` on MariaDB installs upgraded from older versions — caused by a leftover NOT NULL constraint on `audiobook_tracks.title` from a legacy schema, now auto-corrected on restart
- (fix) Ultra-fast skip된 폴더에서 스캐너가 `UnboundLocalError`로 조용히 실패하고, 부분 경로 스캔(scan-path)의 폴더 처리 오류가 삼켜져 API가 성공을 반환하던 문제 수정 | fix the scanner silently failing with `UnboundLocalError` on ultra-fast-skipped folders, and folder-processing errors during partial path scans being swallowed so the API returned success anyway

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
