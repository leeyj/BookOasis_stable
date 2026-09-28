# CHANGELOG
## v2.8.0
- (feature) 사이드바 "음성 준비됨" - 서버에 미리 만든 음성이 있는 책을 용량·길이와 함께 모아 보고, 바로 듣거나 책 단위로 지우기 | "Ready to Listen" in the sidebar lists books with pre-generated audio (size and length), to listen right away or delete per book
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

