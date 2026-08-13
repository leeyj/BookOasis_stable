# CHANGELOG
## v1.9.6
- (mobile) 상/하 제스처 추가 | added up/down movement
- (viewer) 홀수페이지 일때 다음장 넘어가지 않는 버그 수정 | bugfix next chapter logic
- (all) 보스모드 추가(alt+q or qq) | added bossmode (alt+q or qq)
- (all) 코드 리펙토링 최적화 | code refactoring
- (plugin) 관련 api 추가 | added plugin api

## v1.9.5
- (mobile) 확대시 햄버거 메뉴 이슈 수정 | bugfix header button 
- (dashboard) 메뉴 정렬 | align category menu(left)
- (api) 특정 디렉토리 스캔 엔드포인트 추가 | added api endpoint
 * api_endpoint.md 참조.
- (dashboard) 플러그인/카테고리 구분 강화 | diff color plugin/category


## v1.9.4
- (dashboard/category)스마트 추천 기능 추가 | add smart recommendations
- (bug/trash) 휴지통 대량 비우기 시 DB 락 장기 점유로 인한 Lock wait timeout 수정 | fix lock wait timeout from long-held DB lock during bulk trash empty
- (audiobook)쿼리 중앙화 | Query centralization
- (backend) js 모듈 컴포넌트 화 | JavaScript module to component
** 남은이슈
 - lazy 스캐너 쿼리 완전 분리 | Complete separation of lazy scanner queries
 - js Big Object 컴포넌트 화 | Convert the JS Big object to components

## v1.9.3
- (install)설치 오류 수정(긴급) | fix install error

## v1.9.2
- (mobile) 뒤로가기시 햄버거 메뉴 노출 수정 | fix mobile view error
- (dashboard) 대소문자 오류 보정 | Correct for capitalization errors 
- (security) 시그니처 패턴 추가 | added sig sign
- (install) get.sh 추가 (한방설치 툴) | added get.sh (one click install)
    ** curl get.sh 로 실행 | run "curl get.sh"
- (view)RTL 방향에 맞추어 동작 버그 수정 | bugfix RTL movement

## v1.9.1
- (log) 로그 로테이션 정책 적용 | log rotation rule added
- (mariadb) 초기 설치시 admin 계정 보장 | admin id fix
- (mariadb) 초기 설치시 DB 오류 매세지 구체화 | DBMS error message added
- (plugin) 권한해제시 오류 수정 | fix plugin assignment
- (flask)파이썬 버전 호환 확장(3.10~3.14) | support python version (3.10~3.14)

## v1.9.0
- (lazy/mariadb) 스캐너 오류 수정 | fix lazy scanner
- (dashboard) 컬렉션 추가 방식 확장 | expend collection addd method

## v1.8.9
- (dashboard)읽지 않은상태 변경 수정(기준: 시리즈) | unread change fix
- (dashboard)최근 읽은 도서 쿼리 수정 | recently read query fix
- (dashboard)홈 바로가기(타이틀) 추가 | link home dashboard
- (sql/query)쿼리 최적화 | tunes query


## v1.8.8
- (category) 가상그룹 기능 추가 | add virtual group support
- (dashboard) 홈 대시보드에서 시리즈/권수 표시 정상화 | fix dashboard series/books count
- (scanner) 스캔현황 표시 | display scan state

## v1.8.7
- (display) 도서 권수 표시 오류 수정 | fix incorrect book volume count display
- (migration/tooling) DB 이관 도구 MariaDB 호환성 보강 | improve MariaDB compatibility for database migration tools
- (grid/completion) 그리드 뷰에 완독 표시 추가 | add completion indicators to grid view
- (audiobook/playback) 오디오북 백그라운드 재생 지원 | support audiobook background playback
- (cache/config) `.env` 또는 override를 통한 디스크 캐시 설정 지원 | support disk cache configuration through `.env` or overrides
  ```env
  DISK_CACHE_MAX_GB=20
  DISK_CACHE_MAX_FILES=200
  ```
- (filter/genre-tag) 장르/태그 선택지를 현재 카테고리 기준으로 표시 | scope genre and tag options to the current category
- (search) 검색 오류 수정 | fix search errors

## v1.8.6
- (sidebar/category-plugin) 카테고리 레벨 플러그인 탭을 일반 사용자 카테고리와 동일한 드래그 이동 대상으로 확장하고 혼합 순서(`custom+plugin`)를 로컬 저장하여 재접속 시 순서를 유지 | enable category-level plugin tabs to be draggable like user categories and persist mixed custom+plugin sidebar order across reloads
- (performance/all-view) 전체보기 초기 로딩을 전량 선로드(`/api/media/all-list`)에서 서버 페이지네이션(`/api/media/list`) 기반으로 전환하여 대용량 라이브러리 응답 지연 개선 | switch all-view initial loading from full preload to server-side pagination for large library latency reduction
- (performance/filter) 장르/태그 필터를 서버 리스트 API 파라미터(`genres`,`tags`)로 처리하도록 확장하여 페이지네이션 모드에서도 필터 기능 유지 | add server-side genre/tag filters to list API so filtering works with paginated loading
- (dashboard/audiobook) 오디오북 라이브러리에서 연속 독서일수가 0으로 고정되던 문제 수정: streak 날짜 조회를 `user_progress`가 아닌 `audiobook_progress.last_listened_at` 기준으로 분기 처리하고 권한/삭제 조건을 동일 적용 | fix audiobook streak stuck at 0 by using `audiobook_progress.last_listened_at` for distinct read dates with permission and soft-delete filters
- (dashboard/audiobook) 오디오북 대시보드의 연/월 완독 통계 쿼리를 `audiobook_progress` 기준으로 분기 추가 (`is_completed=1`) | add audiobook-specific annual/monthly completion aggregation branches using `audiobook_progress`
- (migration/audiobook) 앱 기동 시 `audiobook_progress.last_listened_at` 누락 레코드 자동 백필 추가 (`current_time > 0` 또는 `is_completed = 1` 대상): `audiobooks.updated_at` 우선, 실패 시 CURRENT_TIMESTAMP로 보정 | add startup-time auto backfill for missing `audiobook_progress.last_listened_at` on active/completed rows
- (migration/tooling) `tools/db_schema_updater.py`에 SQLite/MariaDB 오디오북 진행률 타임스탬프 백필 단계 추가로 커뮤니티 업데이트 경로 자동 적용 강화 | add SQLite/MariaDB audiobook progress timestamp backfill step in schema updater for community upgrade path

## v1.8.5
- (favorite) 즐겨찾기 별 클릭 상세 콘솔 로그 추가 및 단권 도서/유저 ID 매칭 오류 수정 | fix favorite star toggle logging & single book user ID matching
- (category) 카테고리 저장/수정 시 원격 VFS 탐색 os.path.exists 커널 블로킹 및 502 Bad Gateway 수정 | fix category edit VFS os.path.exists kernel hang & 502 Bad Gateway
- (collection) 컬렉션 뷰 하단 무한 스크롤 도서 목록 중복 노출 가드 조건 추가 | fix collection view bottom infinite-scroll book list overlap
- (mariaDB) MariaDB 스키마 DDL Single Source of Truth 통합, collections updated_at 컬럼 보강 및 series_alias 인덱스 추가 | unify MariaDB central DDL schema, add collections updated_at column & series_alias index
- (mariaDB) docker-compose.mariadb.yml 임시 테이블 및 콜레이션 최적화 옵션 추가 | add MariaDB tmp-table-size & collation performance flags
- (mariaDB) 성인도서 대시보드 통계 API 500 에러 수정 | fix adult dashboard 500 error
- (mariaDB) 자동 휴지통 비우기 7일 기준 구문 MariaDB 호환성 수정 | fix auto-prune 7-day SQL 구문 for MariaDB
- 좌측 메뉴 더보기 기능 추가 | add more button to left menu

## v1.8.4
- 뒤로가기 오류 수정 | fix back button error
- 쿼리 오류 수정 | fix query error
- 로그 오류 수정 | fix log error
- 스캔 시작/종료 로그 MariaDB 호환성 대응 | fix log for MariaDB compatibility
- UI 버그 수정 | fix UI bug
- 마이그레이션 툴 오류 수정 | fix migration tool error
## v1.8.3
- (scanner) 대용량 라이브러리 스캔 시 중간 플러시 DB 경합(`Scanner flush failed due to persistent DB contention`) 원천 방지 및 Redis 락 대기 타임아웃/재시도 상향 (`lock_timeout`: 5초, `max_attempts`: 15회), 미획득 시 펜딩 데이터 유예(deferral) 보강 | fix scanner mid-scan flush DB write contention & add lock timeout retry with pending buffer deferral
- (mariaDB) 스캐너 배치 플러시 `ON CONFLICT(file_path) DO UPDATE SET EXCLUDED...` 1064 SQL 구문 오류 자동 변환 (`ON DUPLICATE KEY UPDATE` & `VALUES(...)`) | fix MariaDB scanner bulk insert ON CONFLICT EXCLUDED 1064 SQL syntax error
- (mariaDB) 기동 시 마이그레이션 경고(`PRAGMA table_info` ➔ `SHOW COLUMNS FROM`) 및 `sqlite_master` 1146 에러, `user_progress` 중복 정리 쿼리 MariaDB 호환 개편 | fix MariaDB startup schema auto-migration warnings & sqlite_master 1146 errors
- (mariaDB) `MariadbCursorWrapper.execute()` 커서 체이닝(`cursor.execute(...).fetchone()`) 지원 및 MariaDB 모드 시 SQLite 전용 `PRAGMA integrity_check` 자가 치유(Self-Healing) 오작동 수정 | fix cursor method chaining & prevent false DB self-healing recovery triggers in MariaDB mode
- (log) 스캐너 로그(`scanner.log`) 및 미디어 서버 통합 로그(`media_server.log`)의 전 출력 라인에 `[YYYY-MM-DD HH:MM:SS]` 실시간 타임스탬프 자동 부착 지원 | add automatic timestamp enrichment for scanner & media_server logger
- (collection) 사용자별 맞춤 컬렉션(Collection) 시스템 구축 (DB 영역 격리 권한 안전, 카테고리/폴더 독립 묶음, 카드 우클릭 [➕ 컬렉션에 추가] 모달 지원) | per-user custom collection system support with cross-category grouping & context menu
- (refactor) tab_media_library.js 887라인 거대 코어 구조를 전용 서브 모듈(`library_type_toggle.js`, `search_shortcut_manager.js`)로 컴포넌트화 및 오케스트레이션 슬림화 | refactor tab_media_library.js monolithic architecture into clean modular sub-components
- (refactor) api/library.py 900라인 모놀리식 백엔드 라우터를 3개 도메인별 블루프린트(`library_routes`, `book_routes`, `plugin_routes`)로 구조적 모듈화 분리 | refactor api/library.py into modular domain-driven route blueprints
- (refactor) viewer_txt.js 1,178라인 뷰어 엔진에서 EPUB 챕터 비동기 로더 및 이미지 사전로더를 `epub_loader.js` 서브 모듈로 분리 | refactor viewer_txt.js into modular sub-component epub_loader.js

## v1.8.2
- 브라우저 뒤로가기 버튼 / 모바일 슬라이드 뒤로가기 제스처(`popstate`) 실행 시 뷰어 읽기 진행도 유실 방지 수술 (sendBeacon 및 즉시 flush 훅 탑재) | save reading progress on browser back button & mobile back gesture
- 오디오북 접근 권한(`has_audiobook_access`) 업데이트 백엔드 지원 누락 및 관리자 권한 API 라우트 추가 (`update-audiobook` 엔드포인트 수술 완료로 오디오북 탭 정상 표시 보장) | fix audiobook permission update & tab visibility
- MariaDB 모드 스캔 완료 시 `scan_history` 이력 기록 실패 오류(`Field 'id' doesn't have a default value`) 수정 및 스키마 `AUTO_INCREMENT` 자동 치유 보완 | fix MariaDB scan_history AUTO_INCREMENT schema & self-healing record
- OPDS 카탈로그 검색(Search) 기능 동작 불가 결함 수정 (`user_category_permissions` 기본 접근 권한 검사 오류 및 다양한 검색 파라미터 `q`, `searchTerm`, `keywords` 지원 확충) | fix OPDS catalog search functionality & parameter support
- EPUB/텍스트 뷰어 PC 2페이지(양면 보기) 모드 시 마지막 홀수 페이지에서 다음 챕터로 진행 불가능하던 결함 수정 | fix PC 2-page mode EPUB chapter advance stuck issue
- OPDS 카탈로그 '즐겨찾기' 낱권 나열 구조를 대표 시리즈 그룹핑 카탈로그로 개조 (시리즈 진입 시 하위 권수 목록 출력) | OPDS favorites feed series grouping & navigation feed support
- 도서 카드 우클릭(마우스 2번 버튼) 시 컨텍스트 메뉴 미노출 및 엉뚱한 상세화면 이동 오류 수정 (좌클릭 `e.button === 0` 전용 분기 Enforce) | fix right-click context menu triggering detail navigation
- 코드 감사 리포트 기반 보안 및 무결성 보완 (Proxy Header IP 검증 강화, 401 수신 시 로그인 자동 이동, Audiobook 유저/권한 동기화, Insights 성인 권한 검사) | security & stability fixes from audit report
- 최근 읽은 도서 카드 클릭 역할 분담 원복 (썸네일/배경 ➔ 시리즈 상세화면 이동, 가운데 보라색 아이콘 ➔ 이어읽기 뷰어 오픈) | restore card click behavior separation
- 대시보드 상단 '현재 읽는 중' 동기부여 위젯 카드 클릭 리스너 연결 및 뷰어 오픈 구현 | add click handler and attributes for currently reading insights widget
- MariaDB 대표 시리즈 표지 이미지(cover_image) 최우선 선점 쿼리 적용 | prioritize books with valid cover_image for series representatives
- MariaDB 마이그레이션/스키마 file_path 대소문자 구분(utf8mb4_bin) 콜레이션 적용 | set utf8mb4_bin collation for file_path to support case-sensitive paths

## v1.8.1
- docker-compose.mariadb.yml 부팅 시 3개 미디어 DB 자동 생성 스크립트 보완 | auto-create 3 databases on MariaDB container startup
- 특정 카테고리/전체보기 대표 시리즈 SQL 레벨 그룹핑 최적화 | optimize representative series grouping query for category & all-list
- 스캔시 경고 메시지 보완 | fix warn message in scanner
- mariadb 에러 보완 | fix mariadb error

## v1.8.0
- 대용량 쿼리 최적화 | fix query 

## v1.7.9
- 쿼리문 오타 수정 | fix query 
## v1.7.8
- (db/engine) MariaDB 엔터프라이즈 데이터베이스 엔진 공식 지원 및 대용량 쿼리 쾌속 최적화 | official MariaDB support & high-performance query optimization
- (viewer/epub) EPUB 뷰어 엔진 개선 (이미지 병렬 사전 로딩/디코딩 적용으로 텍스트 밀림 0% 소거) | EPUB reader engine enhancement with image pre-decoding (zero layout shift)
- (ios/refresh) iOS(아이폰/아이패드) Safari 새로고침 시 카테고리 유실 및 오동작 수정 | fix iOS Safari refresh state restoration & category selection issue
- (ios/audio) iOS 화면 잠금 시 Web AudioContext 강제 suspend 후 복귀 누락으로 오디오 끊기는 결함 수정 및 잠금화면 탐색바(seekto) 지원 추가 | fix iOS screen lock AudioContext auto-suspend & add lock screen seekto support


## v1.7.7
- (audio/volume) iOS(아이폰) WebKit 환경에서 HTML5 Audio 볼륨 속성 제한 우회를 위한 Web Audio API GainNode 자체 볼륨 연동 구축 | fix iOS Safari WebKit audio volume control using Web Audio GainNode
- (audio/ui) 오디오북 플레이어 모바일 뷰 하단 툴바 볼륨 수치-Sleep 타이머 버튼 간 UI 겹침 레이아웃 개선 | fix audio player volume slider and sleep timer button UI overlap on mobile

## v1.7.6
- (detail/cover) 메타정보 수동 편집 시 업로드된 신규 표지 이미지가 DB(cover_image)에 미반영되던 결함 및 In-Memory/Redis 캐시 무효화 누락 수정 | fix cover image upload database update & cache invalidation failure

## v1.7.5
- (category/spinner) 하단 속보 푸터 바 전면 제거 및 카테고리 항목/상단 헤더 실시간 뺑글이 스피너(fa-spin) 애니메이션 연동 | remove bottom ticker footer & add category scan spinner animation
- (card/subtext) 도서 카드 하단 불필요한 "신규 추가" 반복 서브텍스트 전면 소거 | remove redundant 'new arrival' subtext from book cards
- (audiobook/unread) 오디오북 "읽지 않은 상태로 변경" 액션 시 audiobook_progress 레코드 미삭제 및 최근 읽은 도서 목록 잔존 결함 수정 | fix audiobook mark unread db record deletion & history removal

## v1.7.4
- (detail/navigation) 상세 뷰에서 목록 돌아가기 및 브라우저 뒤로가기 시 미디어 탭(오디오북/성인/일반) 유실 및 엉뚱한 화면 로딩 결함 수정 | fix media tab loss and wrong view navigation on detail back button
- (system/ticker) 백그라운드 스캔 및 대기열 실행 중 하단 속보 푸터 바(system-ticker-footer) 미노출 결함 수정 및 화면 하단 고정 | fix system ticker scan status footer display & pin to bottom

## v1.7.3
- (audio/transcode) 브라우저 미지원 오디오 포맷(WMA, AC3 등) FFmpeg 실시간 트랜스코딩 엔진 및 DB 재생시간 Fallback 구축 | on-the-fly ffmpeg audio transcoding & duration fallback
- (detail/warn) 시리즈 상세 상단 경고 띠 total_pages=0 조건 제거 및 오프셋 미생성 전용 한정 | remove total_pages=0 from missing page warning banner

## v1.7.2
- pdf 메모리 최적화 및 가상화 렌더링 | pdf virtual rendering
- pdf 스크롤 모드 실시간 페이지 크기(너비) 조절 기능 구축 | pdf scroll mode width control
- pdf 스크롤 모드 휠/터치 핫스팟 간섭 제거 및 네이티브 세로 스크롤 조치 | pdf scroll mode clean scroll
- pdf 스크롤 모드 연속 세로 스크롤 모드 구축 및 연동 | pdf scroll mode continuous vertical scroll

## v1.7.1
- pdf 버그 수정 | bugfix pdf viewer
- 카테고리 편집 저장 버튼 동작 오류 수정 | bugfix save button in category edit modal
- 플러그인 html 오류(inlinehtml) 수정 | bugfix plugin inlinehtml
- 카테고리 삭제/생성 오류 수정 | bugifx category new/delete 

## v1.7.0
- (audiobook/delete) 오디오북 삭제 FK 오류 방지(진행도/트랙 정합성 보강) | prevent audiobook delete FK errors by tightening progress/track integrity
- 코드 안정화 | Stabilize the code
- 컨텍스트 메뉴 호출 버그 수정 | bug fix submenu call function

## v1.6.9
- (permissions/audiobook) 권한관리 탭을 세션별(일반/성인/오디오북) 서브탭으로 분리하고 사용자 접근 플래그에 오디오북 권한을 추가 | split permissions management into session-specific tabs (general/adult/audiobook) and add audiobook access flag to user permissions
- requestments.txt 업데이트 | update requestments.txt


## v1.6.8
- (audiobook/resume) 모바일→PC 이어듣기 복원 개선: 상세/목록 이어듣기에서 서버 저장 트랙/시간(`current_track_id`, `current_time`)을 우선 사용하고 재생 중 10초 주기 진행도 저장 추가 | improve mobile→PC audiobook resume by prioritizing server track/time (`current_track_id`, `current_time`) in continue flows and adding 10s in-play autosave
- (audiobook/stream) 리버스 프록시/Cloudflare 환경 재생 안정화: Range/비-Range 응답을 청크 스트리밍으로 통일하고 무효 Range(416) 처리 및 `no-transform` 헤더 추가 | harden audiobook streaming behind reverse proxy/Cloudflare by chunked Range/non-Range responses, invalid Range(416) handling, and `no-transform` header
- epub,txt 뷰에서 재로딩 로직 보강 | Strengthen reload logic in epub and txt viewer


## v1.6.7
- 도서/오디오북 경로 불일치 등록시 경고 후 확인 추가 | add warning confirm on mismatched book/audiobook path registration
- 오디오 쿼리 레포지토리 분리 | extract audiobook queries into repository layer
- 장르별 ISBN/WEB_ID 저장 및 수정 추가 | add ISBN/WEB_ID save and edit by media type

## v1.6.6
- 카테고리 삭제불가 수정 | fix category deleted
- (scanner/VFS) SMB/CIFS/NFS 마운트 경로를 rclone VFS 대상으로 오인해 RC refresh를 시도하던 문제 수정 | stop treating SMB/CIFS/NFS mounts as rclone VFS refresh targets
- (category) 서버 재기동 시 경로 기반 자동 판별로 원격 드라이브 체크가 다시 켜지던 문제 수정 | preserve remote-drive checkbox across restarts without startup auto-overwrite
- (category) 카테고리 타입과 실제 미디어 경로가 어긋날 때 즉시 차단 대신 경고 후 사용자 확인을 거치도록 조정 | replace hard block with warning-and-confirm flow for obvious category/media path mismatches
- (audiobook) 메타파일 없이 단일 `.m4a` 트랙만 있는 폴더도 오디오북 파서가 인식하도록 회귀 테스트 보강 | add regression coverage for metadata-free single `.m4a` audiobook folder detection
- (refactor/audiobook) 오디오북 상세 조회 및 메타 수정 SQL을 서비스에서 분리해 `repositories/sqlite/audiobook_repository.py`로 이관 | extract audiobook detail/update SQL from service layer into `repositories/sqlite/audiobook_repository.py`
- pixiv 플러그인 추가(develop by 유메미루) | add plugun(pixiv, develop by 유메미루)
- 대시보드에서 오디오트렉 오기 수정 | fix audiobook dashboard track count
## v1.6.5
- (긴급) 스캔시 is_remote 값 참조 무시되는 현상 수정 | (warning) fix error the scanner was is_remote() value
- zip 파일 로딩 로직 최적화 | tune processing zip loaded

## v1.6.4
- (security/policy) 상세 딥링크 새 탭 차단 정책을 해제하고 탭/세션 조건 없이 `#detail?...` 주소 복원을 허용 | remove new-tab detail deep-link blocking policy and always allow `#detail?...` restoration regardless of tab/session state

## v1.6.3
- (mobile/epub) 일시 통신 장애 후 페이지↔스크롤 모드 재전환 시 `챕터 불러오는 중...` placeholder가 고착되는 문제 수정: 가시 범위 챕터 자동 재요청 및 모드 전환 직후 윈도우 하이드레이션 복구 로직 추가 | fix sticky `Loading chapter...` placeholders after transient network failures when re-switching EPUB page↔scroll modes by adding visible-range auto-refetch and post-switch window hydration
- (mobile/audiobook) 오디오북 플레이어 하단 영역 잘림 수정: safe-area 하단 패딩 및 100dvh 기반 레이아웃/스크롤 보정으로 작은 화면(iOS/Android)에서 재생 컨트롤 가시성 복원 | fix mobile audiobook player bottom clipping by applying safe-area bottom padding and 100dvh-based layout/scroll adjustments for small iOS/Android screens
- (scanner/VFS) 카테고리의 원격 드라이브 체크를 해제한 경우 스캔 중 rclone VFS refresh/RC 통신을 시도하지 않도록 조정 | skip rclone VFS refresh/RC communication during scans when the category's remote-drive checkbox is turned off
- 캐시 무효화 자동화: `VERSION.dashboard` 기반 정적 자산 버전 파라미터 자동 주입(`static_asset_url`) 및 릴리스 헤더 동기화 | Cache busting automation: inject release-based asset version from `VERSION.dashboard` and sync release header
- 캐시 정책 정비: `/` 및 `/login` HTML은 no-store, 정적 폰트/이미지/라이브러리 자산은 immutable 장기 캐시 적용 | Cache policy split: no-store for `/` and `/login` HTML, immutable long cache for static font/image/library assets
- CSP 1단계 도입: `Content-Security-Policy-Report-Only` 헤더와 `/api/security/csp-report` 리포트 수집 엔드포인트 추가(환경변수 토글 지원) | CSP phase-1 added: `Content-Security-Policy-Report-Only` header and `/api/security/csp-report` endpoint with env toggles
- CSP 리포트 운영 안정화: 전용 JSONL 파일(`logs/csp_reports.jsonl`) 분리 저장 및 분당 수집량 제한/동일 이벤트 dedup 윈도우 적용 | CSP report operations hardened: dedicated JSONL file (`logs/csp_reports.jsonl`) with per-minute cap and duplicate-event dedup window
- 기본 보안 헤더 강화: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` 기본 적용 | Baseline security headers hardened: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- 플러그인 권한 오류 수정 | Fix plugin permission error
- 각 세션별로 배경색 차별 | identified session color(genaral,adult,audiobook)


## v1.6.2
- 일반사용자도 테마변경 지원 | general users can change theme
- 오디오북 기능 추가(beta) | support audiobook session(beta)
- 상세설명 접기/펼치기 추가 | short / extend the summary
- 카테고리 가져오기/내보내기에 오디오 세션 추가 | category import/export support
** 주의사항: DB 마이그레이션이 진행되므로 업데이트중 강제종료하시거나 강제재시작하시면 DB에 손상이 있을 수 있습니다.


## v1.6.1
- (iOS) 터치영역 오류 수정 | fix touch area bug
- 최근 읽은 도서 개념 수립(series) | fix readed lib (series)

## v1.6.0
- (Android) 롱프레스 컨텍스트 메뉴 미노출 회귀 수정(iOS suppress 범위 분리) | fix Android long-press context menu regression by scoping iOS suppress logic
- (Android) 도서 뷰어 중앙 터치 메뉴 호출 안정화(핫스팟 touchend 폴백 추가) | improve Android viewer center-tap menu reliability with hotspot touchend fallback
- (mobile/iOS) EPUB/TXT 자동 전체화면 진입 제외로 전체화면 종료 후 첫 페이지 강제 이동 회귀 차단(수동 전체화면 유지) | prevent first-page jump after fullscreen exit by skipping auto-fullscreen for EPUB/TXT (manual fullscreen still available)
- (mobile) EPUB 이어읽기 시작점 복원 보강: progress-state no-store 조회 및 epub_session index/percent 우선순위 보정으로 첫 페이지 시작 회귀 차단 | harden EPUB resume on mobile by no-store progress-state fetch and index/percent precedence fix
- (mobile) EPUB/TXT 페이지↔스크롤 전환 시 위치 복원 보강: 앵커 복원 실패 시 전환 직전 뷰포트 비율(top/left ratio)로 폴백 복원 | preserve position across page↔scroll switch using viewport-ratio fallback when anchor restore misses
- (history) 완독 도서 숨김 사용 중에도 같은 시리즈에 미완독 권이 남아 있으면 최근 읽은 책 목록에서 유지되도록 보강 | keep recent-history entries when a completed volume still belongs to an unfinished series
- (history) 최근 읽은 책 목록은 단권은 그대로 유지하고, 2권 이상 읽은 시리즈는 시리즈 카드 단위로 집계해 이어읽기/상세 진입 일관성 개선 | keep single-volume history natural while grouping multi-volume history into series cards
- (iOS Safari) 뷰어 오버레이 빈 배경도 중앙 터치 닫힘 대상으로 처리해 컨트롤 패널 재닫기 동작 복원 | restore overlay close on center tap by making the iOS viewer overlay background tappable
- (refactor) 뷰어 플랫폼 분기 전략 모듈화(platform_profile): input/fullscreen/lifecycle의 iOS/Android 판단 로직을 공통 프로파일로 이관 | modularize viewer platform strategy via platform_profile for iOS/Android decision paths
- (mobile) 카테고리→검색→상세→뒤로가기 동선에서 상단 카테고리/검색 영역이 사라지는 문제 수정(메인 스크롤 컨테이너 기준 복원) | fix mobile back navigation header/category disappearance by restoring the main scroll container