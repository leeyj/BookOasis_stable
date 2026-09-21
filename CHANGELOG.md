# CHANGELOG
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

