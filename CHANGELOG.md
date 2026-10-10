# CHANGELOG
## v2.8.8
- (fix) 만화 다음 권 이어보기 때 전체화면 버튼으로 켠 전체화면이 풀리던 이슈 수정 | fix fullscreen (entered via the fullscreen button) exiting when continuing to the next comic volume
- (fix) 만화 다음 권 이어보기 때 보기 모드(높이/너비 맞춤)가 표지 비율에 따라 바뀌던 이슈 수정 - 직접 고른 맞춤 모드를 기억 | fix the comic fit mode (height/width) switching by cover ratio when continuing to the next volume - the fit mode you pick is now remembered

## v2.8.7
- (feature) 장르/태그 필터를 2개 이상 선택했을 때 '필터 적용 중(AND)'을 눌러 AND(모두 포함)/OR(하나라도 포함)로 전환 | when 2+ genre/tag filters are selected, click "Active Filters (AND)" to switch between AND (match all) and OR (match any)

## v2.8.6
- (feature) 완독·재생 완료 기준(%)을 내 설정에서 조절 - 도서, 오디오북 트랙, 영상 에피소드 공용 (50~100, 기본 95) | the finished threshold (%) is now adjustable in My Settings for books, audiobook tracks and video episodes (50-100, default 95)
- (improvement) 뷰어 메뉴 상단에 전체화면 전환 버튼 추가 - F11을 누르기 어려운 태블릿(Windows 포함)에서도 전환 가능. 기존 '보기' 탭의 모바일 전용 버튼을 대체 | add a fullscreen toggle to the top of the viewer menu so tablets (including Windows) can switch without F11; replaces the mobile-only button in the Layout tab
- (fix) Docker에서 플러그인 계약 파일(plugins/metadata/base.py)이 업데이트되지 않아 새 계약(음악 앨범 정보 조회 등)이 "has no attribute" 오류로 실패하던 이슈 수정 - 계약 코드를 이미지 쪽(plugin_framework/)으로 옮기고 플러그인 import 경로는 그대로 유지 | fix new plugin contracts (music album lookup, etc.) failing with "has no attribute" on Docker because the bind-mounted plugins/metadata/base.py never got updated - the contract code now lives in the image (plugin_framework/) with the plugin import path unchanged

## v2.8.5
- (feature) KOReader 연동 - OPDS 만화 페이지 스트리밍(OPDS-PSE, 페이지 수를 아는 ZIP/CBZ/이미지 폴더)과 KOReader 진행 상황 동기화(kosync 호환, 서버 주소 /kosync, 계정 메뉴에서 동기화 비밀번호 설정). 만화·PDF는 웹 뷰어와 양방향, EPUB·TXT는 KOReader 기기끼리 | KOReader support - OPDS comic page streaming (OPDS-PSE, for ZIP/CBZ/image folders with a known page count) and KOReader progress sync (kosync-compatible, server address /kosync, sync password set in the account menu); comics/PDF sync both ways with the web viewer, EPUB/TXT between KOReader devices
- (security) OPDS 다운로드 링크 서명 키가 공개 저장소의 고정값이던 문제 수정 - 앱 SECRET_KEY를 사용 | OPDS download link tokens were signed with a fixed key published in the repository; they now use the app SECRET_KEY
- (fix) OPDS 카탈로그 제목이 "My Supporter"로 나오던 이슈 수정 | fix the OPDS catalog title showing "My Supporter"
- (improvement) 원격 드라이브(GDS 등)의 음악 카테고리는 스캔 때 곡 파일을 열지 않음 - rclone은 태그만 읽어도 파일 전체를 받아 공유 드라이브에 부담이 컸음. 제목은 album.yaml/파일명, 커버는 폴더 이미지/album.yaml 포스터, 길이·태그는 재생할 때 채움 | music categories on remote drives (GDS, etc.) no longer open song files during scans - rclone downloaded whole files just to read tags; titles come from album.yaml/file names, covers from folder images/album.yaml posters, and durations/tags are filled in when a song is played
- (fix) 경로 지정 즉시 스캔(scan-path, 웹훅 path 스캔, 플러그인 웹뷰 다운로드 등록)으로 추가한 도서가 검색에는 나오는데 그리드에는 다음 전체 스캔 전까지 안 보이던 이슈 수정 - 즉시 스캔 뒤에도 시리즈 목록을 갱신 | fix books added by direct path scans (scan-path, webhook path scans, plugin webview downloads) showing in search but not in the grid until the next full scan - the series list is now refreshed after direct scans too
- (feature) 음악 모드 - 오디오북 세션에서 카테고리 속성 "음악"을 고르면 폴더=앨범(폴더 이름=제목)으로 스캔하고 곡 태그로 제목/아티스트 표시, 정사각 커버, 재생 중인 곡의 커버, 셔플/반복, 가사(album.yaml → 곡 태그, 싱크 가사는 현재 줄 강조), 이어듣기·배속 없음. 앨범 폴더의 album.yaml이 있으면 아티스트/발매일/소개를 채움 | music mode - pick the "music" kind on an audiobook-session category to scan folders as albums (folder name = title) with song titles/artists from tags, square covers, the playing song's cover, shuffle/repeat and lyrics (album.yaml then song tags; synced lyrics highlight the current line), without resume or speed; album.yaml fills artist/release date/summary
- (improvement) 카테고리 커버 비율에 정사각(1:1) 추가 | add a square (1:1) category cover ratio
- (fix) 앨범 아트 블록이 깨진 FLAC이 Chrome에서 재생되지 않던 이슈 수정 - 재생에 필요한 헤더와 오디오만 보냄 | fix FLAC files with a broken embedded-art block not playing in Chrome - only the headers needed for playback and the audio are sent
- (security) 오디오 트랙 목록의 제목을 이스케이프 (곡 태그/파일명이 그대로 HTML로 들어가던 문제) | escape track titles in the audio track lists
- (plugin) 선택 계약 lookup_music_album 추가 - album.yaml이 없는 음악 앨범의 아티스트/연도/장르/커버를 코어가 백그라운드로 물어 빈 칸에만 표시. iTunes 샘플 플러그인(music_itunes, 키 불필요) | add the optional lookup_music_album contract - the core asks in the background for artist/year/genre/cover of music albums without album.yaml and shows them only in empty fields; iTunes sample plugin (music_itunes, no key)
- (fix) 네트워크 순단 때마다 "원격 드라이브 연결 끊김" 알림이 떴다 사라지던 이슈 수정 - 10분 넘게 끊겨 있을 때만 표시하고, 순단으로 실패한 스캔은 '스캔 실패'로 따로 알리지 않음 (삭제 보류는 즉시). 오디오북/영상 카테고리도 같은 카드로 알림 | fix the "remote drive disconnected" notification flashing on and off on every network blip - it now shows only after 10+ minutes offline and blip-failed scans are no longer listed as scan failures (the deletion hold still applies immediately); audiobook/video categories use the same card

## v2.8.4
- (improvement) 스캔 안전장치: 한 번의 스캔에서 카테고리 도서의 20% 이상(20권 이상)이 새로 사라지면 휴지통 이동을 보류하고 알림에 "대량 이동/삭제 의심" 카드를 띄움(확인 후 아직 없는 파일만 휴지통으로). 카테고리 폴더/마운트에 접근할 수 없으면 도서를 지우지 않고 "원격 드라이브 연결 끊김" 카드를 띄우며, 연결이 돌아온 뒤 스캔하면 자동으로 사라짐 | scan safety: if 20%+ (and 20+) of a category's books newly disappear in one scan, moving them to the trash is held and a "possible mass move/delete" card appears (confirm to trash only the files still missing); if the category folder/mount is unreachable, no books are removed and a "remote drive disconnected" card appears that clears itself on the next scan after it comes back
- (improvement) 알림의 문제 카드(휴지통으로 옮긴 사라진 파일, 손상 파일, 표지 추출 실패 등)를 펼쳐 시리즈별 → 도서별로 보고 모두 재스캔/시리즈 재스캔/재스캔/알고 있음으로 처리, 다음 스캔에서 정상이면 자동 해제. MCP 도구 list_problems/get_problem_card 추가 | notification problem cards (missing files moved to trash, corrupt files, cover failures, ...) expand per series and per book with rescan-all/rescan-series/rescan/got-it actions and clear automatically once the next scan finds them healthy; new MCP tools list_problems/get_problem_card
- (improvement) 상단 "스캔 활동"을 "알림"으로 개편 - 스캔·음성 생성·시스템 경고를 한 목록에 종류별 색과 라벨(에러/진행/대기/신규/완료/취소)로 표시, 카테고리 스캔 결과(새 도서·실패 수)를 7일간 "최근 완료"로 보여 줌, 새 알림 표시와 읽음 처리, 일반 계정은 본인 음성 생성만 보이고 알림이 없으면 아이콘이 흐려짐. 목록 카드의 NEW 배지는 파랑, +N권 배지는 중립색으로 변경 | the top "Scan activity" is now "Notifications" - scans, voice generation and system warnings in one list with per-kind colors and labels (error/running/queued/new/done/cancelled), category scan results (new/failed books) kept for 7 days as recent items, unread markers, and regular accounts only see their own voice generation with a dimmed icon when there is nothing to show; the card NEW badge is now blue and the +N badge neutral
- (fix) 태블릿 등에서 텍스트/EPUB을 페이지 모드로 읽다가 앱을 내렸다 올리거나 화면을 돌리면 2~3페이지 앞뒤로 밀리던 이슈 수정 (보던 글자 기준으로 위치 유지). 같은 방식으로 보기 모드 전환·듣기 위치 이어가기도 화면에 보이던 문장 기준으로 더 정확해짐(2장 모드·긴 문단 포함) | fix TXT/EPUB page mode jumping 2-3 pages after switching apps or rotating on tablets (position now follows the text you were reading); view-mode switching and read/listen position sync now use the exact on-screen sentence too (incl. two-page mode and long paragraphs)
- (fix) 모바일에서 메뉴(드로어)가 화면 바깥 테두리 안쪽에 갇혀 겹쳐 보이던 이슈 수정 (e-paper 테마 등) - 폰 화면은 바깥 테두리·여백 없이 화면 전체를 사용 | fix the mobile menu drawer being trapped inside the outer frame and overlapping it (e.g. e-paper theme) - phones now use the full screen without the outer border and margin
- (fix) 자주 스캔하는 카테고리에서 휴지통 7일 자동 비우기가 일어나지 않던 이슈 수정 (스캔마다 휴지통 도서의 삭제 시각이 다시 찍히던 문제) | fix the 7-day trash auto-cleanup never running for frequently scanned categories (each scan re-stamped the deletion time of books already in the trash)
- (improvement) 도서 [진단] 추가 (관리자, 도서 메뉴·알림 문제 카드) - DB 기록/원격 연결/파일 존재/파일 형식을 점검해 원인과 재스캔 버튼을 보여 줌. MCP 도구 diagnose_book 추가 | add book [Diagnose] (admin, book menu and notification problem cards) - checks DB record / remote connection / file exists / file format and shows the cause with a rescan button; new MCP tool diagnose_book
- (improvement) 뷰어에서 도서를 열다 오류가 나면 그 자리에 [관리자에게 알리기] 표시 (관리자에겐 [진단]) - 신고는 관리자 알림에 "사용자 신고" 카드로 모이고 [해결됨]으로 닫음 | when a book fails to open in the viewer, a [Notify admin] button appears in place ([Diagnose] for admins) - reports gather as a "User report" card in the admin notifications and are closed with [Resolved]
- (plugin) 선택 계약 report_problem/resolve_problem 추가 - 플러그인이 관리자 알림에 문제 카드(플러그인 이름 표시, 조치 버튼은 기존 액션 RPC)를 올리고 해결. spotify_mood 샘플에 계정 연결 만료 카드 적용 | new optional contract report_problem/resolve_problem - plugins can raise and resolve problem cards in the admin notifications (plugin name shown, action button via the existing action RPC); the spotify_mood sample raises a connection-expired card
- (improvement) 알림 머리말에 [지우기] 추가 - 최근 완료 기록은 내 목록에서 숨기고 참고 알림 카드는 '알고 있음'으로 처리(진행 중·조치 필요 항목은 그대로), 토스트에서 되돌리기 가능 | add a [Clear] button to the notifications header - hides finished items from your list and marks notice cards as acknowledged (running and action-required items stay), with Undo in the toast
- (internal) 백그라운드 작업 실패 경고 저장 위치를 새 문제 기록 테이블로 옮김 (알림센터 개편 준비, 화면 변화 없음) | move background-task failure warnings to a new problem-record table (groundwork for the notification center, no visible change)
- (internal) 스캔 이력에 결과 요약(새 도서 수·에러 수)과 스캔 출처(수동/예약/자동/웹훅)를 기록하고, 90일 지난 스캔 이력은 서버 시작 시 정리 | scan history now records a result summary (new books, errors) and the trigger source (manual/scheduled/lazy/webhook); scan history older than 90 days is pruned at server start


## v2.8.3
- (fix) 경로 지정 스캔(scan-path) 등에서 처리·커버 생성·스캔 성공까지 끝났는데 도서가 DB에 등록되지 않던 이슈 수정 (MariaDB, 스캔 도중 다른 작업이 해당 도서 기록을 지운 경우 자동 재등록, 끝내 등록 실패 시 scan-path는 오류 반환) | fix books processed successfully (cover generated, scan reported success) but never registered in the DB, e.g. via scan-path (MariaDB; a record removed by another task mid-scan is now re-registered, and scan-path returns an error if it still can't be saved)
- (fix) 7일 지난 휴지통 자동 비우기가 파일이 다시 존재하는 도서까지 영구 삭제하던 이슈 수정 (삭제 대신 복구) | fix the 7-day trash auto-cleanup permanently deleting books whose files exist again (they are now restored instead)
- (fix) 서버가 주기적으로 작업 프로세스를 교체할 때 Google Drive에서 읽던 요청이 걸려 있으면 최대 5분간 응답하지 않던 이슈 수정 (교체 시 읽기 진행도 저장 등 정리 후 바로 종료) | fix the server becoming unresponsive for up to 5 minutes when its worker was periodically recycled while a Google Drive read was in progress (the worker now saves reading progress and cleans up, then exits right away)

- (improvement) 모바일 상단을 카드 한 장으로 개편 - ☰·검색·계정 줄은 항상 보이고, 기본/작가별과 세션 선택·필터·스캔 활동 줄은 아래로 스크롤하면 접힘. 세션은 "일반 도서 ⌄"를 눌러 바로 전환 (상단 로고 줄과 🔍 버튼 제거) | mobile top bar is now a single card - the ☰/search/account row always stays, while the Default/By author row and the session picker/filter/scan activity row collapse when scrolling down; switch sessions directly from "General Books ⌄" (the logo row and 🔍 button are gone)
- (improvement) 사이드바 Home 아래 고정 메뉴(최근 읽은 도서~전체보기)를 하위 메뉴로 들여 쓰고 Home 줄의 화살표로 접기 (기본 접힘, 상태 기억) | the fixed sidebar items under Home (Recently read to View all) are now an indented sub-menu that collapses via the arrow on the Home row (collapsed by default, state remembered)

## v2.8.2
- (fix) 추가일이 비어 있는 도서가 하나라도 있으면 일반 도서 카테고리 목록이 갱신되지 않아 새로 스캔한 책·카테고리가 "등록된 도서가 없습니다"로 보이던 이슈 수정 (비어 있는 추가일은 서버 시작 시 자동 보정) | fix general-library category lists no longer updating when any book had an empty added date, which made newly scanned books/categories show as "no books" (empty added dates are now filled in automatically on startup)
- (improvement) 시리즈 카드에 최근 7일 추가 배지 표시 - 새 작품은 `NEW`, 기존 시리즈에 권이 추가되면 `+N권` (처음 스캔한 카테고리는 제외) | series cards show a badge for additions in the last 7 days - `NEW` for new titles, `+N` when volumes were added to an existing series (skipped for freshly scanned categories)
- (improvement) 관리자 전용: 시리즈 목록 갱신이 계속 실패하면 상단 스캔 활동 아이콘에 빨간 점과 경고 표시 (다음 성공 시 자동 해제) | admin-only: a red dot and warning on the Scan activity icon while series list refresh keeps failing (clears automatically on the next success)

## v2.8.1
- (fix) 이전 스캔 진행 기록 때문에 경로 지정 스캔(scan-path)이 지정한 폴더를 건너뛰던 이슈 수정(force 여부 무관, 새 회차 추가도 무시되던 문제 포함), 부분 스캔이 진행 기록을 남겨 다음 전체 스캔이 해당 폴더를 건너뛰던 이슈 수정 | fix path scans (scan-path) skipping the requested folder because of leftover scan-progress records (with or without force, including newly added episodes), and partial scans leaving progress records that made the next full scan skip those folders
- (fix) 이미 스캔된 폴더에 나중에 kavita.yaml/info.xml을 추가하거나 수정하면 일반 스캔에서도 새 메타데이터가 반영되도록 수정(로컬 경로) | metadata from a kavita.yaml/info.xml added or edited after a folder was scanned is now applied by a normal scan too (local paths)
- (fix) 도서 상세의 재스캔/시리즈 재스캔이 태그·장르·연령등급·연재상태를 저장하지 않던 이슈 수정 | fix Rescan / Rescan series on the book detail page not saving tags, genre, age rating and publication status

## v2.8.0
- (feature) 사이드바 "음성 준비됨" - 서버에 미리 만든 음성이 있는 책을 용량·길이와 함께 모아 보고, 바로 듣거나 책 단위로 지우기(beta, 버그 많음) | "Ready to Listen" in the sidebar lists books with pre-generated audio (size and length), to listen right away or delete per book
- (improvement) 미리 만든 음성을 책·챕터 단위 파일로 모아 저장(문장마다 파일 하나 → 챕터마다 하나), 용량 초과 시 오래 안 들은 책부터 통째로 정리, 관리자 설정에 음질 추가(표준 64kbps / 절약 32kbps, 용량 절반). 이전 버전에서 만든 음성은 자동으로 지워지므로 다시 만들어야 함 | pre-generated audio is now stored per book and chapter (one file per chapter instead of per sentence), the disk cap removes least recently played books as a whole, and admins can pick the audio quality (Standard 64kbps / Compact 32kbps, half the size). Audio made by earlier versions is removed automatically and must be generated again
- (improvement) 모바일 메뉴를 좌측 슬라이드 드로어로 개편 (메뉴/보관함 검색, 탐색·보관함 구분, 관리 도구 접기, 하단 스캔 활동·환경설정·계정) + 검색·세션 탭·작가별은 상단 🔍를 누를 때만 표시해 화면을 넓게 사용 (드럼쟁이 님 포크 UI 기반) | mobile menu is now a left slide-out drawer (menu/library search, Browse/Libraries sections, collapsible admin tools, Scan activity/Settings/Account at the bottom); search, session tabs and grouping now appear only when tapping 🔍 at the top for more screen space (based on 드럼쟁이's fork UI)
- (fix) 모바일에서 카테고리 추가 등 창의 닫기(X)가 주소창에 가려지던 이슈, 환경설정을 끝까지 스크롤하면 상단 메뉴가 밀려 사라지던 이슈 수정 | fix the close (X) button of dialogs such as Add category being hidden under the mobile address bar, and the top menu scrolling away at the end of Settings on mobile
- (improvement) 모바일 카테고리 경로 입력에서 찾아보기·링크 연결 테스트 버튼을 입력칸 아래 줄로 배치 | on mobile, the Browse / Test link buttons for category paths now sit below the input
- (fix) iPhone에서 모바일 상단 일반/성인/오디오북/영상 강좌 탭 글자가 왼쪽으로 쏠리던 이슈 수정 | fix mobile library tabs (General/Adult/Audiobooks/Videos) text leaning left on iPhone


## v2.7.9
- (feature) 듣기 서버 미리 만들기 - 관리자가 켜면 도서 메뉴에서 지정한 도서를 서버가 미리 음성으로 만들어 둠. 진행·완료는 스캔 활동에 표시하고 웹훅(`tts.ready`)으로도 알림, 미리 만든 챕터는 기기에서 모델을 불러오지 않음 (기본 꺼짐) | Listen server pre-generation - when enabled by the admin, the server pre-generates audio for books users pick from the book menu; progress and completion show in Scan activity and via webhook (`tts.ready`), and pre-generated chapters play without loading the model on the device (off by default)
- (improvement) 듣기 기본 음질을 "보통"으로 변경 ("좋음"과 차이가 작고 생성은 두 배 빠름, 직접 고른 설정은 유지) | Listen now defaults to Normal quality (barely distinguishable from Best, twice as fast to generate; a chosen setting is kept)
- (fix) iPhone/iPad에서 음성으로 듣기가 화면을 끄면 멈추거나 한동안 뒤 "음성 만드는 중"에서 멈추던 이슈 수정 (iOS는 WebGPU 대신 WASM으로 합성, 화면을 꺼도 계속 재생) | fix Listen on iPhone/iPad stopping when the screen turns off or hanging on "generating" after a while (iOS now synthesizes with WASM and keeps playing with the screen off)
- (fix) WASM으로 음성을 만드는 동안 화면이 굳어 버튼이 눌리지 않던 이슈 수정 | fix the Listen screen freezing (buttons unresponsive) while synthesizing with WASM
- (improvement) 음질 "빠름" 제거 (소리가 뭉개져 사용 불가), iPhone은 15 Pro 이상 권장 안내 추가 | removed the "Fast" quality (too garbled to use); docs now recommend iPhone 15 Pro or newer
- (improvement) WASM으로 합성할 때 기본 음질을 "보통"으로 낮춰 끊김 없이 재생 (직접 고르면 그대로) | WASM synthesis defaults to normal quality for gap-free playback (a manual choice is kept)


## v2.7.8
- (feature) TXT/EPUB 음성으로 듣기 정식 도입 - 브라우저에서 직접 음성 합성(서버 CPU 미사용), 읽는 문장 강조 + 자동 스크롤, 뷰어/도서 메뉴에서 열기, 읽던 위치와 듣던 위치 동기화 | Listen (TXT/EPUB read-aloud) is now a regular feature: speech is synthesized in the browser (no server CPU), the current sentence is highlighted and followed, opens from the reader or the book menu, reading and listening positions stay in sync
- (improvement) 플러그인이 "음성으로 듣기"를 열 수 있는 전역 함수 추가 (`window.openListen`, `window.canListen` — guide_plugins 참고) | plugins can open Listen via `window.openListen` / `window.canListen` (see guide_plugins)
- (improvement) 음성으로 듣기에서 한자만 쓴 단어(運命, 天下第一 등)를 한국식 음으로 읽음 (두음법칙 적용, 화면에는 원문 한자 그대로) | Listen reads standalone hanja (e.g. 運命) with Korean readings, applying initial-sound rules (the screen still shows the original hanja)
- (improvement) 음성으로 듣기로 들은 위치가 읽기 진행도(목록 진행 막대·완독·최근 읽은 도서)에도 반영됨 | listening now also updates reading progress (list progress bar, completion, recently read)
- (improvement) 음성 모델을 Hugging Face에서 받지 못하는 브라우저는 서버가 한 번 받아 둔 모델을 대신 받음 (외부 도메인 허용 목록과 무관, 서버 방화벽이 외부 접속을 막으면 `huggingface.co`·`*.hf.co` 허용 필요) | browsers that cannot download the voice model from Hugging Face fall back to a copy the server downloads once (independent of the domain whitelist; if a server firewall blocks outbound traffic, allow `huggingface.co` and `*.hf.co`)
- (fix) 음성으로 듣기에서 "아....그건" 같은 아주 짧은 문장이 튀거나 빠지던 이슈 수정 (짧은 문장은 앞뒤 문장과 함께 합성, 제목만 있는 속표지는 건너뜀) | fix very short sentences (e.g. "Ah.... that") being garbled or skipped in Listen (short sentences are synthesized together with their neighbours; title-only pages are skipped)
- (fix) CBZ/ZIP 안에 표지 이미지(`cover`/`folder`/`표지` 이름, ComicInfo.xml `FrontCover` 지정)가 있어도 페이지가 숫자로 시작하면 첫 페이지를 표지로 뽑던 이슈 수정 | fix CBZ/ZIP cover extraction picking the first page even when the archive contains a cover image (`cover`/`folder`/`표지` name or ComicInfo.xml `FrontCover`) and pages start with digits
- (fix) OPF가 `opf:` 접두사 네임스페이스를 쓰는 EPUB(웹 서점 뷰어 저장본 등)이 챕터 0개로 인식되어 열리지 않던 이슈 수정 | fix EPUBs whose OPF uses an `opf:`-prefixed namespace (e.g. saved from web store readers) being parsed as 0 chapters and failing to open
- (fix) 목록에서 메타정보 검색 결과를 적용하면 카테고리 맨 위로 이동하던 이슈 수정 (스크롤 위치 유지) | fix applying a metadata search result from the list jumping back to the top of the category (scroll position kept)
- (improvement) 샘플 플러그인 `naver_webtoon` → `webtoon_search`로 이름 변경, 카카오페이지/카카오웹툰 표지 검색 추가 (선택 설치) | sample plugin `naver_webtoon` renamed to `webtoon_search`, adds KakaoPage/Kakao Webtoon cover search (optional)


## v2.7.7
- (fix) 오디오북/영상 강좌 목록에서, 같은 제목으로 여러 권이 한 시리즈로 묶이는 경우 무한 스크롤이 실제로는 수천 개가 남았어도 중간에 영구히 멈추던 이슈 수정 | fix audiobook/video list infinite scroll permanently stopping partway through even with thousands of series remaining, when multiple rows collapse into one grouped series


## v2.7.6
- (fix) 오디오북/영상 강좌 표지가 없을 때 뜨는 대체 이미지에 캐시 헤더가 없어 매 요청마다 재생성되던 이슈 수정, 커버 API의 중복 DB 조회 제거 | fix the audiobook/video fallback cover image missing cache headers (regenerated on every request), and remove a duplicate DB lookup in the cover API
- (fix) 카드 썸네일이 원본 비율과 안 맞으면 이미지를 늘려서 채우던 것을 되돌리고 크롭 방식으로 복원 (필요하면 커버 정렬 메뉴 사용) | revert card thumbnails stretching mismatched-ratio covers to fill the frame; back to cropping (use the cover-align menu if needed)
- (improvement) 메인 목록에서 개별 권 카드를 다중 선택하면 "커버 정렬"을 한 번에 일괄 적용 가능 (시리즈 집계 카드는 제외) | multi-selecting individual volume cards in the main list now lets "cover align" be applied to all of them at once (series-aggregate cards excluded)


## v2.7.5
- (improvement) MCP `search_books`에 `sort`(최근 추가순 등) 추가, `get_random_book` 도구 추가 | MCP `search_books` gains a `sort` option (e.g. newest first) and a new `get_random_book` tool
- (fix) 표지 리사이즈 백필이 보스키 위장 화면(`fake_screen.png`)과 배너까지 축소해 해상도가 깨지던 이슈 수정 | fix the cover resize backfill also shrinking the boss-key decoy image (`fake_screen.png`) and banners, which degraded their resolution
- (fix) MCP `search_books`가 요청한 limit보다 1건 더 반환하던 이슈 수정 | fix MCP `search_books` returning one more result than `limit`
- (improvement) 검색창에서 Enter로 제목/주제/회차별 검색 결과를 가로 행 오버레이로 표시, `주제:` 검색(장르/태그) 추가, 책 상세 화면에서 검색하면 목록으로 이동 | Enter in the search box opens an overlay with title/topic/episode result rows, add `주제:` (genre/tag) search prefix, and searching from the book detail view now navigates to the list
- (improvement) 관리자 전용: 카드 좌측 하단 `...` 버튼(호버 시 표시)으로 도서 경로/카테고리/추가일/포맷 확인, 카드 잠금 배지는 하단 중앙으로 이동 | admin-only `...` button on card bottom-left (shown on hover) showing path/category/added date/format; the lock badge moves to bottom-center

## v2.7.4
- (fix) MariaDB에서 신규 테이블(`library_kinds`, `mcp_pending_changes`)이 생성되지 않아 사이드바 라이브러리/카테고리가 사라지던 이슈 수정 | fix new tables (`library_kinds`, `mcp_pending_changes`) not being created on MariaDB, which made sidebar libraries/categories disappear
- (improvement) MariaDB 테이블 생성 실패가 조용히 무시되지 않고 로그에 남도록 개선 | log MariaDB CREATE TABLE failures instead of silently ignoring them
- (fix) EPUB 목차의 하위 항목(예: "제2부 > 강변에서")이 앵커 없이 챕터 시작으로만 이동하던 이슈 수정 (`<a id>` 앵커 보존) | fix EPUB TOC sub-items still jumping to the chapter start (preserve `<a id>` anchors in chapter HTML)
- (fix) EPUB 목차에서 하위 항목을 선택해도 상위 항목이 하이라이트되던 이슈 수정 | fix EPUB TOC highlighting the parent item after selecting a sub-item

## v2.7.3
- (fix) 시리즈 카드에서 스캔 시 대표 도서 1권만 처리되던 이슈 수정 (시리즈 전체 스캔) | fix series-card scan processing only the representative book (scan the whole series)
- (fix) 스캔 완료 후 목록/상세 화면이 갱신되지 않던 이슈 수정 | fix library list and detail view not refreshing after a scan completes
- (improvement) 전체 목록/초성 이동 로딩 속도 개선 (시리즈마다 반복하던 설정 조회 제거) | speed up full-list build and initial-letter jump (stop re-reading a setting per series)
- (fix) SQLite에서 홈 최근 읽은 도서 조회가 진행 기록이 많을수록 수 초~십수 초 걸리던 이슈 수정, 홈에서 스캔 완료/즐겨찾기 변경 시 홈이 갱신되지 않던 이슈 수정 | fix multi-second home reading-history query on SQLite and home not refreshing after scan completion or favorite toggle
- (fix) 모바일에서 사이드바 메뉴 항목/로고를 눌렀을 때 메뉴가 늦게 닫히던 이슈 수정 | fix mobile sidebar menu closing late after tapping a library item or the logo
- (fix) PDF 즉시 스캔/시리즈 스캔이 결과 확인 없이 성공 처리되거나 뒤 권이 빠지던 이슈 수정 (격리 프로세스 1회로 묶어 처리, 기존 표지 보존) | fix PDF immediate/series scan reporting success without checking, dropping later volumes, and risking existing covers
- (improvement) 즉시 스캔(권/시리즈)에서 CBZ ComicInfo.xml·EPUB 내장 메타로 비어 있는 필드만 채움 | immediate scan now fills only empty fields from embedded CBZ ComicInfo.xml / EPUB metadata
- (fix) 라이브러리 스캔 중 스캔 활동창이 내내 "book_scan"만 보이던 이슈 수정 (폴더 탐색 수, 도서 파일 완료/전체·남은 권수 표시) | fix scan activity showing only "book_scan" for the whole library scan (now shows folders visited and files done/total)
- (fix) 카드의 즐겨찾기 별을 연속으로 눌러도 해제되지 않던 이슈와, 요청 실패 시 별 모양이 복원되지 않던 이슈 수정 | fix card favorite star not toggling back on consecutive clicks and not reverting after a failed request
- (fix) 시리즈 상세 화면에서 검색해도 결과가 보이지 않던 이슈 수정 (검색 결과로 이동, 뒤로가기로 상세 복귀) | fix searching from a series detail view showing no results (now opens results; Back returns to the detail)
- (fix) 폴더 표지(cover.jpg 등)·배너를 대소문자 구분 없이 찾고(Windows에서 만든 `Cover.JPG` 등), 폴더 목록을 한 번만 읽어 원격 마운트의 파일 확인 호출을 줄임 | find folder covers/banners case-insensitively (e.g. `Cover.JPG` on Linux) and read the folder listing once instead of probing every candidate name
- (feature) 카테고리 속성(만화/도서/잡지 등) 추가 - 관리자가 종류를 정의하고 카테고리마다 선택 지정, 플러그인이 분류 기준으로 읽을 수 있도록 API/DB로 노출 (기본 종류 4개, 신규 생성 시 입력은 선택) | add category types (manga/book/magazine, ...): admin-defined kinds assignable per category, exposed via API/DB as a classification criterion for plugins (4 built-in kinds; optional when creating a category)


## v2.7.2
- (fix) 최신 추가순 카테고리 로딩이 느린 이슈 수정 (목록의 has_metadata 계산 제거, `include_has_metadata=1`로 선택 계산) | fix slow category loading on newest-first sort (drop has_metadata from list queries; opt-in via `include_has_metadata=1`)
- (fix) MariaDB에서 MCP `run_readonly_query`가 동작하지 않던 이슈 수정 | fix MCP `run_readonly_query` failing on MariaDB
- (improvement) MCP 툴 추가/개선 (`get_version`, `SHOW`/`DESCRIBE` 쿼리 허용) | add MCP `get_version` and allow `SHOW`/`DESCRIBE` queries

## v2.7.1
- (fix) 카테고리 로딩이 권한체크 이슈로 느려지는 이슈 수정 | fix category loading slowdown caused by permission-check issue
- (improvement) 사용자 권한 기능 개선 (권한 복사 기능 추가) | improve user permission features (add permission copy feature)
- (improvement) 컨텍스트 메뉴에서 미독/완독 상태에 따라 노출되는 메뉴(상태 변경) 항목 변경 | change context menu items shown based on unread/completed status

## v2.7.0
- (fix,Emergency) lazyscanner 버그 픽스 (이미지 축소 백필 한계 증량) | lazyscanner bug fix
- (improvement) 도서 카드 그리드의 "메타데이터 미연결" 표시를 제거하고 상세화면 헤더로 이동 | remove the "no metadata" indicator from the book card grid and move it to the detail page header

