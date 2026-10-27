# CHANGELOG
## v3.0.5
- (improvement) 뷰어 메뉴를 한 줄에 설정 하나(이름 … 스위치·선택지·[− 값 +])로 정리하고 패널 폭을 내용에 맞춤 | viewer menu reorganized into one setting per row (name … switch / choice / [− value +]) with the panel sized to its content
- (improvement) 자동 넘김(구 슬라이드)을 EPUB/TXT에서도 쓸 수 있게 함, 넘김 간격(2~120초)·스크롤 속도(10~400px/초)를 자유롭게 조절하는 항목을 설정 > 뷰어에 추가 | auto page turn (formerly Slideshow) now works for EPUB/TXT; Settings > Viewer gets free page-turn interval (2-120s) and scroll speed (10-400px/s) controls

## v3.0.4
- (fix) 구글 링크 카테고리의 웹툰 폴더에 새 회차가 올라오면 책은 등록되지만 커버가 비던 문제 수정 — 시리즈 대표 커버(kavita.yaml, 없으면 series.json 이미지)를 붙임 | fix new episodes in a webtoon folder of a Google link category being added without a cover — they now get the series cover (from kavita.yaml, or the series.json image)
- (improvement) 카테고리 기본 속성에 '웹툰' 추가 — 웹툰 카테고리는 회차가 작품 대표 표지를 같이 쓰고, 표지가 빈 회차는 스캔 끝과 속성을 웹툰으로 바꿀 때 같은 폴더 회차의 표지로 채움(파일 안 받음) | add 'Webtoon' to the built-in category types — episodes in a webtoon category share the series cover, and episodes without a cover get the cover of another episode in the same folder at the end of a scan or when the category is switched to Webtoon (no file downloads)
- (fix) macOS로 만든 ZIP의 `__MACOSX`·`._` 찌꺼기 파일이 페이지로 세져 첫 페이지가 '이미지를 불러오지 못했습니다'로 뜨던 문제 수정(재스캔 필요) | fix `__MACOSX`/`._` leftovers in ZIPs made on macOS being counted as pages, making the first page fail with 'Failed to load image' (rescan needed)
- (improvement) [진단]에 ZIP 안에 영상이 들어 있으면 경고 표시 | [Diagnose] warns when a ZIP contains video files
- (improvement) 관리자가 뷰어에서 오류를 만나면 진단을 자동으로 돌려 걸린 항목과 결론을 오류 자리에 바로 표시 | when an admin hits a viewer error, the diagnosis runs automatically and its failed items and conclusion show right in the error area

## v3.0.3
- (fix) 휴대폰에서 EPUB/TXT를 읽다 앱을 내린 사이 화면 크기가 바뀌고(주소창·회전) 페이지가 새로 열리면 몇 쪽 앞뒤에서 열리던 문제 수정 | fix EPUB/TXT on phones reopening a few pages off when the screen size changed (address bar, rotation) while the app was in the background and the page then reloaded
- (fix) EPUB/TXT를 다른 기기에서 이어 읽을 때 '다른 기기에서 읽던 위치로 이동' 알림은 뜨지만 이 기기의 예전 위치와 번갈아 맞춰지다 몇 쪽 어긋난 채 끝나던 문제 수정(느린 기기·새로 연 페이지) | fix EPUB/TXT resume from another device showing the 'moved to the position read on another device' notice but then alternating with this device's old position and ending a few pages off (slow devices, freshly loaded pages)
- (fix) 만화 스크롤 모드에서 서버가 잠깐 응답하지 못하면(워커 재시작 순간 등) 바로 '이미지를 불러오지 못했습니다' 창이 뜨던 문제 수정 — 두 번까지 다시 받아 봄 | fix the comic scroll mode showing 'Failed to load image' right away when the server briefly fails to respond (e.g. during a worker restart) — the image is retried up to twice
- (performance) 쪽수가 아직 기록되지 않은 PDF(원격 보관함 등)를 처음 열 때 서버가 파일을 열어 쪽수를 다 센 뒤에야 뷰어가 시작되던 문제 수정 — 바로 열고 쪽수는 뷰어가 채움(Google Drive 원격 87MB PDF 첫 쪽 37초 → 14초) | fix PDFs without a recorded page count (e.g. on remote libraries) waiting for the server to open the file and count pages before the viewer started — they now open right away and the viewer fills in the page count (first page of an 87MB PDF on Google Drive: 37s → 14s)

## v3.0.2
- (fix) 영어로 설정해도 한국어로 나오던 화면 문구 번역 — 환경설정 탭의 목록·상태·알림·확인 창(플러그인·권한·스캔 기록·휴지통·외부 도메인·사용자·스케줄·단축키), 상단 줄·계정 메뉴·KOReader 동기화, 홈 위젯, 도서 우클릭 메뉴, 카테고리 추가/수정 창·경로 탐색, 스케줄 도우미 | translate text that stayed Korean in English mode: lists, statuses, alerts and confirmations in settings (plugins, permissions, scan history, trash, external domains, users, schedule, shortcuts), the top bar, account menu and KOReader sync, home widgets, the book context menu, the category add/edit dialog and path browser, and the schedule helper
- (improvement) 검색 접두어를 언어와 상관없이 사용 — 작가는 author:/著者:/作者:, 그림작가는 artist:/illustrator:/作画:, 주제는 topic:도 인식(대소문자 무시, 전각 콜론 허용), 영어 화면 검색창 안내는 영어 접두어로 표시 | search prefixes work in any language — author:/著者:/作者: for author, artist:/illustrator:/作画: for illustrator and topic: for topic are recognized alongside the Korean ones (case-insensitive, full-width colon allowed); the English search hint shows the English prefixes
- (improvement) 서버 로그(logs/의 media_server·scanner·lazy_scanner·scan_history 등)와 관리용 명령줄 도구(db_recovery·migrator·진단 도구 등)의 출력을 영어로 통일 | server logs (media_server, scanner, lazy_scanner, scan_history, etc. in logs/) and the admin command-line tools (db_recovery, migrator, diagnostics, etc.) now print in English
- (fix) 이름 없이 카테고리를 저장하거나 Lazy 스캐너 '지금 실행'을 누르면 알림에 번역 키 이름(category.name_required 등)이 그대로 보이던 문제 수정 | fix raw translation keys (e.g. category.name_required) showing in alerts when saving a category without a name or pressing the Lazy scanner 'Run now'
- (fix) 크론 타임존 설명이 예전 문구(APScheduler 기준)로 보이던 문제 수정 | fix the cron time zone help showing outdated text (APScheduler baseline)

## v3.0.1
- (fix) PC 홈에서 서재 선택 메뉴가 대시보드 통계 카드 아래로 가려지던 문제 수정 | fix the library picker menu showing beneath the home dashboard stat cards on desktop
- (fix) 휴대폰(특히 iOS 사파리)에서 목록 아래쪽에 빈 띠가 남아 화면이 답답해 보이던 문제 수정 — 목록이 화면 끝까지 이어짐 | fix an empty strip at the bottom of lists on phones (notably iOS Safari) — lists now run to the bottom edge
- (improvement) 브라우저 탭 아이콘·홈 화면 아이콘·로고를 새 야자수 마크로 교체 | browser tab icon, home screen icon and logo switched to the new palm mark
- (improvement) 로그인 화면과 정보 탭 제목의 예전 보라색을 앱 기본 테마의 파랑으로 변경, 로그인 버튼은 그라데이션 없는 단색 | the login page and the About tab title drop the old purple for the app's default blue; the login button is a flat color
- (improvement) PC 사이드바 접기 버튼(☰)을 검색창 옆에서 로고 왼쪽으로 옮기고, 로고 줄을 상단 줄과 같은 높이로 맞추며 로고와 첫 메뉴 사이 공백을 줄임(접으면 ☰와 Home 아이콘 표시) | on desktop the sidebar toggle (☰) moves from beside the search box to the left of the logo, the logo row lines up with the top bar and the gap under it is reduced (when collapsed, ☰ and the Home icon remain)
- (improvement) 책 목록 제목 옆 카테고리 정보 버튼과 도서 카드의 정보 버튼을 ⋯ 대신 ⓘ 아이콘으로 변경 | the category info button next to the book list title and the info button on book cards use an ⓘ icon instead of ⋯
- (fix) 홈 섹션 제목(최근 읽은 도서·신규 추가 도서)의 아이콘이 글자보다 위로 떠 보이던 문제 수정 | fix home section title icons (Recently read, New additions) sitting higher than the text
- (fix) 영어로 설정해도 환경설정(기본 시스템·스케줄·권한·휴지통·내 설정·스캔 기록·뷰어·플러그인·외부 도메인)과 사이드바 '컬렉션'에 한국어가 남던 문제 수정 | fix Korean text remaining in English mode in settings (system, schedule, permissions, trash, my settings, scan history, viewer, plugins, external domains) and the sidebar 'Collections' item
- (fix) 계정 메뉴에서 '로그아웃' 글자만 들여쓴 것처럼 어긋나 보이던 문제 수정 | fix 'Log out' looking indented in the account menu
- (fix) 제목 숨김 카드에 마우스를 올리면 정보 버튼이 NEW/+N권 배지와 겹치던 문제 수정 | fix the info button overlapping the NEW/+N badge when hovering a card with hidden titles

## v3.0.0
- (improvement) 홈 섹션의 테두리 상자를 없애고 표지가 바탕에 바로 놓이도록 변경, 섹션 제목 크기·굵기 정리 | home sections no longer sit in bordered boxes so covers lie directly on the background; section titles use consistent size and weight
- (improvement) 책 목록 카드의 테두리 상자를 없애고 표지 중심으로 정리(표지 둥근 모서리·그림자, 마우스를 올리면 살짝 떠오름), 목록 글자 크기·간격 정리 | book cards drop their bordered box so the cover leads (rounded cover with a soft shadow that lifts on hover); list text sizes and spacing made consistent
- (improvement) 도서 상세의 상자(헤더 패널·줄거리·장르/태그 칩·권 목록 줄)를 없애고 정리, 관리용 버튼(메타정보 검색·재스캔·모두 완독/미독·정보 수정 등)은 ⋯ 더보기 메뉴로 이동, 리디북스 링크는 메타 줄의 글자 링크로, 권 목록의 정렬·'안 읽은 권만'은 상자 없는 글자 버튼으로(정렬은 눌러서 전환), 권 썸네일을 작게(휴대폰은 표지 왼쪽·정보 오른쪽 배치), 서버 파일 경로는 관리자에게만 표시 | book detail drops its boxes (header panel, summary, genre/tag chips, volume rows); management actions (metadata search, rescan, mark all read/unread, edit info, etc.) move into a ⋯ More menu, the Ridibooks link becomes a text link in the meta line, the volume list's sort and 'Unread only' controls become plain text buttons (sort flips on click), volume thumbnails are smaller (on phones the cover sits left of the info), and server file paths in the volume list are shown to admins only
- (improvement) 책을 읽을 때 메뉴 위 줄에 시리즈명·권 이름을 표시(2.6.2부터 빠져 있던 제목), 뷰어 메뉴의 버튼 상자·발광 효과를 정리하고 쪽 번호의 보라색 고정 색을 테마 색으로, 여백 탭 글자를 다른 메뉴와 같은 크기로 정리하고 목차·형광펜 버튼이 메뉴 패널을 가리던 문제 수정 | the viewer menu's top bar shows the series and volume name again (missing since 2.6.2); viewer menu buttons drop their boxes and glow, and the page number no longer uses a fixed purple; the margin tab's labels match the other menu text, and the table-of-contents and highlighter buttons no longer cover the menu panel
- (improvement) 왼쪽 메뉴(휴대폰 서랍·PC 사이드바)의 선택 표시 테두리와 카테고리 권수 알약을 없애고 옅은 배경·숫자 글자로 정리 | the left menu (phone drawer and desktop sidebar) drops the selected-item border and the per-category count pills for a soft background and plain numbers
- (improvement) 상단 줄 정리: PC도 서재(일반·성인·오디오북·영상)를 아이콘 4개 대신 선택 버튼 하나로, 정렬·필터·기본|작가별과 카테고리 정보(⋯)는 책 목록 화면의 제목 줄로 옮겨 이름이 보이게(제목·권수도 표시), 상단 줄은 맨 위에선 상자 없이 두고 스크롤할 때만 배경 표시(모서리는 표지와 같은 계열로) | top bar cleanup: on desktop too, the library (general, adult, audiobook, video) is picked from one button instead of four icons; sort, filter, default/by-author and category info (⋯) move to the book list's title row with visible labels (title and count shown); the top bar has no box at the top of the page and only gets a background while scrolling, with corners matching the covers
- (fix) 검색창에 입력 중 스크롤하면 상단 줄이 숨고, 검색 단축키를 눌러도 다시 나타나지 않던 문제 수정 | fix the top bar hiding while typing in the search box and scrolling, and not coming back with the search shortcut
- (fix) 홈 위젯 '배치 잠금' 상태에서도 위젯 제거(×) 버튼과 '+ 위젯 추가' 줄이 보이던 문제 수정 — 잠금을 풀어야 보임 | fix the home widget remove (×) buttons and the '+ Add widget' row showing while the layout is locked — they appear only when unlocked
- (fix) 아이콘이 제자리보다 왼쪽으로 치우쳐 보이던 문제 수정(정사각 버튼의 < > 등) | fix icons drawn left of center (e.g. < > in square buttons)
- (plugin) 글자 크기·굵기·줄 높이·여백 단계 CSS 토큰(--app-fs-*, --app-fw-*, --app-lh-*, --app-space-*) 추가 (contract 1.1.5) | added type size, weight, line-height and spacing CSS tokens (--app-fs-*, --app-fw-*, --app-lh-*, --app-space-*) (contract 1.1.5)

## v2.9.9
- (performance) 출판사·줄거리·표지 중 빈 값이 있는 도서는 스캔 때마다 다시 처리돼, 새 회차 하나에도 폴더 회차 전체를 다시 처리하던 문제 수정 — 책 파일과 폴더의 kavita.yaml·info.xml·series.json·표지 그림이 그대로면 건너뜀, rclone 원격 보관함도 kavita.yaml 변경을 강제 재스캔 없이 반영(업데이트 후 원격 폴더는 첫 스캔 한 번만 예전처럼 처리, 파서가 새로 읽게 된 항목은 강제 재스캔 시 반영) | fix books with an empty publisher, summary or cover being reprocessed on every scan, which made one new episode reprocess the whole folder — books are skipped while the book file and the folder's kavita.yaml, info.xml, series.json and cover images are unchanged; rclone remote libraries now pick up kavita.yaml changes without a forced rescan (after updating, remote folders are processed the old way once; fields newly supported by the parser need a forced rescan)
- (performance) 폴더 단위 스캔(scan-path·스캔 웹훅 path)이 모든 카테고리의 폴더 기록을 읽어 서버 전체 폴더 수에 비례해 느려지던 문제 수정 — 대상 폴더와 하위 기록만 읽음 | folder scans (scan-path, scan webhook path) no longer read the folder records of every category, which made them slower as the server's total folder count grew — only the target folder and its subfolders are read
- (fix) 폴더 단위 스캔(scan-path·스캔 웹훅 path)이 이름이 같은 말로 시작하는 다른 폴더(예: 'A' 스캔 시 'A 외전')의 도서를 휴지통으로 옮기던 문제 수정 | fix folder scans (scan-path, scan webhook path) moving books of other folders whose names start the same (e.g. 'A Side Story' when scanning 'A') to the trash
- (fix) 폴더 단위 스캔에 파일 경로를 주면 아무것도 처리하지 않고 성공으로 끝나던 문제 수정 — 그 파일의 폴더를 스캔 | fix folder scans given a file path finishing as successful without doing anything — the file's folder is scanned instead
- (fix) 이미 등록된 영상 강좌에 추가한 회차가 강제 재스캔 전까지 등록되지 않던 문제 수정 — 파일 목록이 달라진 강좌만 다시 처리 | fix episodes added to an already registered video course not being registered until a forced rescan — courses whose file list changed are processed again

## v2.9.8
- (fix) 폴더 단위 스캔(scan-path)에서 사라진 파일의 휴지통 이동·복구가 저장되지 않아 이름이 바뀐 파일의 이전 도서가 목록에 남던 문제 수정 | fix folder scans (scan-path) not saving trash moves and restores, which left the old entry of a renamed file in the list
- (fix) 리버스 프록시 뒤에서 카테고리 삭제가 타임아웃(504)으로 실패하던 문제 수정 — 카테고리는 바로 목록에서 빠지고 도서 정보는 스캔 대기열의 '카테고리 삭제' 작업이 나눠 지움(재시작 시 이어서 진행), 삭제 실패 시 HTTP 상태를 표시 | fix category deletion timing out (504) behind a reverse proxy — the category leaves the list immediately and its books are removed in batches by a 'Category Delete' task in the scan queue (resumed after a restart); on failure, the HTTP status is shown
- (fix) 카테고리를 일반↔성인 보관함으로 이동하면 '이동할 카테고리 정보가 없습니다'로 실패하던 문제 수정(1.8.9부터 사이드바 순서 저장과 주소가 겹쳤음) — 이동도 스캔 대기열의 '카테고리 이동' 작업이 나눠 처리(끝나면 대상 보관함에 나타남, 재시작 시 이어서 진행), 미분류로 들어가고 두 DB 스키마가 달라도 있는 컬럼만 옮김, EPUB 책갈피·주석·KOReader 동기화도 함께 옮기며 컬렉션에서는 빠지고 미리 만든 TTS 음성은 지워짐 | fix moving a category between the general and adult libraries failing with "no category to move" (its URL collided with sidebar reordering since 1.8.9) — moves now run in batches as a 'Category Move' task in the scan queue (the category appears in the target library when done; resumed after a restart), land ungrouped, copy only columns present in both databases, and carry EPUB bookmarks, annotations and KOReader sync; the books leave their collections and pre-generated TTS audio is removed
- (fix) 카테고리 추가·수정·이동이나 설정 저장 뒤 재시작 전까지 Redis 읽기 진행률 저장·구글 드라이브 보기 캐시 정리·음악 정보 조회 예약 작업이 멈추던 문제 수정 | fix the scheduled Redis reading-progress save, Google Drive view-cache cleanup and music info lookup stopping until restart after adding, editing or moving a category or saving settings
- (fix) 카테고리 삭제 시 EPUB 책갈피·주석·컬렉션 항목·KOReader 동기화·미리 만든 TTS 음성이 남던 문제 수정 | fix deleting a category leaving EPUB bookmarks, annotations, collection items, KOReader sync entries and pre-generated TTS audio behind
- (fix) 카테고리 삭제 시 번호가 비슷한 다른 카테고리(예: 1번 삭제 시 11·21번)의 스캔 기록까지 지워지던 문제 수정 | fix deleting a category also wiping the scan history of other categories with similar IDs (e.g. 11 and 21 when deleting 1)

## v2.9.7
- (fix) 서버 응답이 느릴 때 스캔 상태 조회가 쌓여 화면이 멈추던 문제 수정 | fix scan status polls piling up and stalling the page when the server responds slowly
- (fix) 일반·성인 카테고리 번호가 같으면 스캔 에러 리포트가 서로 섞여 보이던 문제 수정(이전 리포트는 표시되지 않고 다음 스캔부터 분리 저장) | fix scan error reports of general and adult categories with the same ID showing up in each other's viewer (older reports are no longer listed; reports are kept separately from the next scan)
- (improvement) 필터 적용 중 표시줄이 스크롤해도 상단에 따라다니도록 변경 | the active filter bar now stays pinned at the top while scrolling

## v2.9.6
- (removed) 알라딘 Open API 지원 종료에 따라 알라딘 샘플 플러그인(aladin, aladin_new)과 코어의 알라딘 기본값을 삭제 — 기본 메타데이터 공급자 자동 선택·다른 플러그인으로의 자동 대체가 없어지고(.env METADATA_PROVIDER 지정 시만), 플러그인용 window.triggerSearchAladinMetadataAction 별칭과 적용 API의 aladin_item 필드도 제거 | removed the Aladin sample plugins (aladin, aladin_new) and Aladin defaults in core as the Aladin Open API was discontinued — no automatic default metadata provider or silent fallback to another plugin anymore (only when METADATA_PROVIDER is set in .env); the window.triggerSearchAladinMetadataAction alias and the aladin_item field of the apply API were also removed
- (fix) 연속 스캔 등으로 다른 탭을 보는 사이 뜬 마지막 토스트가 돌아와도 사라지지 않던 문제 수정, 토스트가 튕기지 않고 부드럽게 나타나도록 변경 | fix the last toast (e.g. after back-to-back scans) never disappearing when it appeared while the tab was in the background, and make toasts ease in smoothly instead of bouncing
- (fix) 검색용 메타데이터 플러그인이 없을 때 검색 창에 가짜 기본 항목 대신 설치 안내를 표시 | the metadata search dialog now shows an install hint instead of a fake default entry when no search plugin is installed
- (fix) DB 연결이 예외로 반납되지 못하면 슬롯이 영구히 빠지던 문제를 MariaDB에서도 자동 회수하도록 수정(전에는 SQLite만), 남아 있던 반납 누락 가능 지점 58곳을 정리 | fix DB connections that failed to return to the pool on an exception: leaked slots are now reclaimed on MariaDB too (previously SQLite only), and the remaining 58 spots that could skip returning a connection were cleaned up
- (improvement) 오디오북 표지를 처음 볼 때가 아니라 스캔할 때 만들도록 변경(metadata.json 내장 표지·폴더 이미지, 원격 음악의 곡 내장 아트는 지금처럼 처음 볼 때) — 기존 오디오북은 카테고리 강제 재스캔 시 생성 | audiobook covers are now generated during scan instead of on first view (metadata.json embedded covers and folder images; embedded song art on remote music still on first view) — existing audiobooks get covers on a forced rescan

## v2.9.5
- (plugin) 커뮤니티 별점 1.1.0: 별점 결과 5분 캐시, 별점 서버 실패 시 2분간 재호출 안 함, 조회 동시 요청·제한 시간 3초, relay 주소를 바꾸면 인증을 다시 하도록 수정 | community rating 1.1.0: cache ratings for 5 minutes, skip the rating server for 2 minutes after a failure, query in parallel with a 3s timeout, and re-verify when the relay URL changes
- (feature) 진단용 느린 요청·서버 오류 기록 추가(.env DEBUG_REQUEST_LOG=true일 때만, 기본 꺼짐) — logs/request_debug.log, 요약 도구 tools/summarize_request_debug_log.py와 MCP get_request_debug_summary | add an opt-in diagnostic log of slow requests and server errors (only when DEBUG_REQUEST_LOG=true in .env, off by default) — logs/request_debug.log, with a summary tool (tools/summarize_request_debug_log.py) and the MCP tool get_request_debug_summary
- (improvement) 사이드바 가상 그룹 이름을 카테고리와 같은 크기로 맞추고 굵기로 구분, 관리 도구 항목은 차분한 색으로 | sidebar virtual group names now match the category size and stand out by weight; admin tool items use a muted color
- (improvement) 작가별 보기에서 표시할 도서가 없을 때 '도서가 없다' 대신 이유를 알려주고 기본 보기로 바로 전환하는 버튼 표시 | when the by-author view has nothing to show, explain why instead of saying there are no books, with a button to switch back to the default view
- (improvement) 작가별 보기가 켜져 있으면 상단 토글에 '작가별' 글자를 함께 표시 | show the 'By author' label on the top bar toggle while the by-author view is on
- (performance) 앱 글꼴을 조각 92개에서 완성형 한글 2,350자를 담은 파일 하나(475KB)로 바꿔, 한 번만 받고 글꼴이 바뀌며 화면을 다시 그리지 않도록 함 | replace the 92-piece app font with a single file covering the 2,350 common Hangul syllables (475KB), downloaded once and without re-drawing the screen when it loads
- (performance) 글꼴·라이브러리 파일이 1년 캐시 설정에도 매번 서버에 재확인하던 문제 수정 | fix fonts and library files being re-checked with the server on every visit despite their one-year cache setting
- (performance) 앱 스크립트를 버전이 들어간 주소로 불러와 재방문 때 다시 받거나 확인하지 않도록 함 | load app scripts from versioned URLs so revisits no longer re-download or re-check them
- (performance) 관리자 홈의 플러그인 상태 확인이 매번 모든 플러그인 소스를 다시 검사하던 것을 바뀐 파일만 검사하도록 개선 | the admin home's plugin status check now re-scans only changed plugin files instead of every plugin's source each time
- (performance) PDF 라이브러리는 PDF를 열 때, 압축 라이브러리(JSZip)는 첫 화면 뒤에 불러오도록 변경(플러그인이 쓰는 경우 실행 전에 자동으로 불러옴) | load the PDF library when a PDF is opened and the zip library (JSZip) after the first screen, loading them automatically before any plugin code that uses them
- (performance) 뷰어·상세·설정·플레이어 스크립트를 처음 쓸 때 불러와 홈 화면이 받는 스크립트를 절반 가까이 줄임 | load viewer, detail, settings and player scripts on first use, cutting the scripts the home screen loads nearly in half

## v2.9.4
- (improvement) 앱 화면에 Pretendard 글꼴 적용(기기마다 다른 기본 글꼴 대신), 도서 카드 제목을 덜 굵게 하고 단어 단위로 줄바꿈 | use the bundled Pretendard font across the app (instead of each device's default font), with lighter book card titles that wrap between words
- (improvement) 데스크톱 화면의 바깥 테두리 상자를 없애고, 사이드바 Home 줄의 관리 버튼들을 하단 '관리 도구'로 옮김(모바일과 동일) | remove the outer frame on desktop, and move the admin buttons from the sidebar Home row into the collapsible 'Admin tools' section at the bottom (same as mobile)
- (improvement) 앱 아이콘을 Lucide 선 아이콘으로 통일 (플러그인·카테고리 아이콘의 Font Awesome 값은 그대로 지원) | switch app icons to Lucide line icons (Font Awesome values in plugins and category icons keep working)
- (improvement) 상단바의 기본|작가별을 아이콘으로, 세션 탭은 선택된 세션만 이름을 보이고 나머지는 아이콘으로 표시 | show the top bar's Default|By author toggle as icons, and label only the selected session tab (the others show icons)
- (improvement) 상세 화면 버튼을 절제된 색으로 정리(핵심 동작 하나만 강조색, 나머지는 중립) | tone down the detail page buttons (only the main action uses the accent color; the rest are neutral)
- (improvement) 제목 감추기 카드는 마우스를 올리면 표지 위에 제목 표시, 새 카테고리는 제목 감추기가 기본 | hidden-title cards now show the title over the cover on hover, and new categories hide titles by default
- (improvement) 홈의 최근 읽은 도서·신규 추가 도서를 표지만 보이게 하고, 읽은 정도는 표지 아래 진행 막대로 표시 | the home Recently read and Recently added rows show covers only, with reading progress as a bar at the bottom of the cover
- (feat) 홈 배너 샘플 플러그인(home_banner) 추가 - 홈 맨 위에 그림과 한 줄 문구, 기본 그림은 르누아르(퍼블릭 도메인)이고 그림 주소·문구는 플러그인 설정에서 변경. 사용법: 환경설정 > 플러그인 설정 > 샘플에서 설치 > '홈 배너' → 내 설정 > '홈 화면을 플러그인 배치 모드로 전환' 켜기 → 홈 하단 '+ 위젯 추가'에서 '홈 배너' | add the Home banner sample plugin (home_banner): a picture and a one-line message at the top of home; the default picture is a public-domain Renoir, and the image URL and message can be changed in the plugin settings. To use: Settings > Plugin settings > Install from samples > 'Home banner' → My settings > turn on the plugin layout mode for the home screen → '+ Add widget' at the bottom of home → 'Home banner'
- (plugin) home_widget에 frame:'none' 추가 - 제목줄 없이 내용만 보이는 위젯 | add frame:'none' to home_widget for widgets shown without the title bar
- (fix) 라이트 테마에서 알림 패널과 도서 진단 창의 글자가 보이지 않던 이슈 수정 (테마 색을 따름) | fix unreadable text in the notification panel and book diagnosis dialog on the light theme (they now follow the theme colors)
- (improvement) 도서 정보 수정 화면의 항목 이름·입력칸 색을 차분하게 정리 | calmer label and input colors in the book info editor
- (improvement) 사이드바 BookOasis 로고를 선 아이콘으로 바꾸고 메뉴·상단바와 줄을 맞춤 | sidebar BookOasis logo now uses a line icon and lines up with the menu and top bar
- (fix) 2.8.5부터 Moon+ Reader 등 OPDS 앱에서 도서의 읽기 버튼이 사라지던 이슈 수정 (페이지 스트리밍 정보는 KOReader에만 제공) | fix the read button disappearing in OPDS apps such as Moon+ Reader since 2.8.5 (page-streaming info is now sent to KOReader only)

## v2.9.3
- (fix) 오디오북 metadata.json 내장 표지가 images.poster 키로 지정된 경우 표지가 생성되지 않던 이슈 수정 | fix audiobook covers not being created when metadata.json references its embedded cover via images.poster
- (fix) 오디오북 상세의 '이 시리즈 재스캔'과 도서 메뉴의 '즉시 스캔'이 동작하지 않던 이슈 수정 (해당 오디오북 폴더를 다시 스캔) | fix 'Rescan this series' on audiobook details and 'Scan now' in the audiobook card menu not working (they now rescan that audiobook's folder)

## v2.9.2
- (fix) 오디오북·도서 파일 이름을 바꾸면 이어 듣기·읽기 기록을 잃던 이슈 수정 | fix renamed audiobook/book files losing listening/reading progress
- (fix) 오디오북 폴더 안의 파일 변경(이름 변경, 회차 추가)이 일반 스캔에 반영되지 않던 이슈 수정 | fix file changes inside an audiobook folder (renames, new episodes) not being picked up by normal scans
- (fix) 오디오북 폴더 이름을 바꾸면 새 책으로 중복 등록되던 이슈 수정(같은 책으로 옮겨 이어 듣기 유지, 폴더가 사라진 책은 숨김) | fix renamed audiobook folders being registered as duplicate books (the book moves with its progress; books whose folder disappeared are hidden)

## v2.9.1
- (improvement) 쓰기 API가 실패하면 서버 로그(logs/media_server.log)에 [API-FAIL]로 한 줄 기록 | log failed write API requests to the server log (logs/media_server.log) as [API-FAIL]
- (fix) 오디오북·영상 표지를 바꿔도(정보 수정, 같은 이름의 파일로 교체) 옛 표지가 계속 보이던 이슈 수정 | fix audiobook/video covers still showing the old image after a change (info edit, or replacing the file under the same name)
- (fix) 오디오북 정보 수정에서 표지를 함께 올리면 실패하던 이슈 수정, 수정은 그 책에만 적용되고 재스캔이 덮어쓰지 않음(잠금 해제 가능) | fix audiobook info edits failing when a cover was uploaded; edits now apply only to that book and survive rescans (unlockable)
- (fix) 알라딘 샘플 플러그인의 메타데이터 적용이 항상 실패하던 이슈 수정, 실패 시 서버 로그에 원인 기록 | fix the Aladin sample plugin always failing to apply metadata, and log the cause on failure

## v2.9.0
- (improvement) 오디오북 하위 폴더 음원이 한 권으로 합쳐지거나 저장에 실패하면 알림센터에 표시 | show audiobooks merged with their subfolders, and audiobook save failures, in the notification center
- (perf) 원격 드라이브 오디오북 스캔이 오디오 파일을 내려받지 않음 (재생 시간은 재생할 때 채움) | remote-drive audiobook scans no longer download audio files (track lengths are filled in on playback)
- (feat) 오디오북 metadata.json의 내장 표지 사용, cp949·UTF-16 파일 지원, 깨진 경우 audio.json으로 폴백 | use the embedded cover in audiobook metadata.json, read cp949/UTF-16 files, and fall back to audio.json when it is broken
- (fix) 안드로이드 크롬에서 책을 보다 앱을 내린 사이 크롬이 정리(프로세스 종료)되면, 돌아왔을 때 읽던 책이 자동으로 다시 열리지 않던 이슈 수정 - 열린 책 정보를 탭의 방문 기록에 저장 | fix the book not reopening automatically on Android Chrome when Chrome was killed while the app was in the background - the open book is now kept in the tab's history entry
