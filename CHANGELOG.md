# CHANGELOG
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