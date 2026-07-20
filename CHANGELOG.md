# CHANGELOG
## v1.2.7
- 스캔시 변동없는 폴더(도서)는 DB 스캔 진행률(scanner_progress) 테이블 업데이트 로직 제외 | Exclude DB scan progress(scanner_progress) table update logic for folders (books) with no changes during scanning
- 스캔시 Redis 참조 못하는 버그 수정 | Fix bug where Redis could not be referenced during scanning
- 스캔시 과도한 DB 엑세스 부하 90% 이상 감소 | Reduced excessive DB access load by over 90% during scanning
## v1.2.6
- EPUB/PDF/TXT/ZIP 종료 후 최근 읽은 도서 및 이어읽기 위치 반영 개선 | Improved recent-history and resume-position updates after closing EPUB/PDF/TXT/ZIP viewers
- TXT 0% 구간 재오픈 시 이전 위치로 되감기던 문제 수정 | Fixed TXT reopening regression that could restore an older position while progress still showed 0%
- 최근 읽은 도서 캐시에 Redis 최신 진행률 병합 적용 | Merged live Redis progress into recent-history cache responses

## v1.2.5
- 모바일 뷰에서 카테고리 선택시 ui 겹침현상 수정 | Fix overlapping UI issue when selecting a category on mobile view
- 읽지않음으로 변경 기능 버그 수정 | Fix bug for switching to "Unread"
- 카테고리 삭제시 즐겨찾기 항목있어도 삭제 | Delete category even if there are bookmark items
---
## v1.2.4 
- FTS 가상 테이블 제거(opds 검색기능 차단) | Removed FTS virtual table (disabling OPDS search functionality)
- 시작/재시작시 오류 수정 | Fixed errors occurring at startup/restart
- DB 무결성 검증 로직 강화 | Strengthened DB integrity verification logic


## v1.2.3
- 서비스 재시작시 DB 무결성 검증 강화 | Enhanced DB integrity verification during service restart
- DB 복구 프로세스 안정성 및 무결성 강화 | Improved stability and integrity of the DB recovery process
- Redis 도입범위 확대(스캔대게열,도서읽은범위,도서읽은 책) | Expanded Redis implementation scope (Scan queue, Book read range, Book read range)
- 모바일 뷰에서 카테고리 선택시 ui 불편사항 수정 | Fixed UI inconvenience when selecting a category in mobile view


## v1.2.2
- 서비스 재시작시 스캔 대기열 초기화 이슈 수정 | Fixed issue where scan queue was reset during service restart
- 도서상세리스트에  재스캔 버튼 추가 및 기능 연동 | Added rescan button to book detail list and linked functionality

## v1.2.1
- Redis 도입 | Redis implementation
 * 도커사용자는 자동 적용 / 네이티브 사용자는 .env에 REDIS_URL=redis://redis_ip:6379/0 추가 및 Redis 서버 구동 필요 | Docker users automatically apply / Native users need to add REDIS_URL=redis://redis_ip:6379/0 to .env and run Redis server
- Redis를 사용하지 않는 경우, DB Lock 발생시 recovery 1회만 진행 | If Redis is not used, only one recovery will be performed when DB Lock occurs
- Redis 적용 범위(도서 진행현황,대시보드, 스캔 상태) | Redis scope (book progress, dashboard, scan status)
- 도커 컴포즈에 레디스 관련 내용 추가 | added redis related content to docker compose

## v1.2.0
- bash 환경변수 추가(manage.sh) | Add bash environment variables(manage.sh)

## v1.1.9
- 스트림 GET(`/api/media/stream`)을 읽기 전용으로 정리하여 프리패치 호출이 진행률을 갱신하지 않도록 수정 | fixed the issue where prefetch calls would not update the progress
- 스트림/TXT/PDF/EPUB 파일 조회 경로에 카테고리 권한(`user_category_permissions`) 검사와 삭제 도서 제외 조건을 서비스 레벨에 중앙화 | Centralized category permission checks and deleted book exclusions for stream/TXT/PDF/EPUB file access in the service level
- 스캐너 경로 정규화 유틸(`canonical_path`, `join_canonical`)을 도입해 Windows 경로 혼용으로 인한 이동/삭제 오탐 가능성 완화 | Introduced canonical path utilities to mitigate misidentification of move/delete operations caused by mixed Windows paths
- 스캐너 실패 전파 보강: `run_scan_job` 실패 재전파 및 lazy scanner 비정상 종료코드 검증으로 큐 `completed` 오판정 방지 | scanner scan_job failure re-transmission and lazy scanner abnormal termination code validation to prevent queue completed misjudgment
- SQLite 연결 초기화 시 `PRAGMA foreign_keys=ON` 적용으로 참조 무결성 강제 | SQLite connection initialization `PRAGMA foreign_keys=ON` applied for forced referential integrity
- 단일 PDF 재스캔에서 `db_type` 인자 누락을 보강하여 격리 스캔이 요청 DB 범위(`general`/`adult`)를 정확히 따르도록 수정 | Reinforced `db_type` argument for single PDF rescan to ensure isolated scans accurately follow the requested DB range (`general`/`adult`)
- 휴지통 비우기 시 표지 파일 물리 삭제를 참조수 0인 경우로 제한하여 공유 커버 오삭제 방지 | Trash cleanup now only physically deletes cover files when the reference count is 0 to prevent accidental deletion of shared covers
- 스캐너 폴더 순회 부분 실패(`os.walk` 경고) 시 해당 회차의 move/delete 동기화를 건너뛰는 안전 가드 추가 | Added safety guard to skip move/delete synchronization for episodes when folder traversal fails (`os.walk` warning)
- 도커 엔트리포인트에서 웹 health 확인 후 워커를 지연 기동하도록 변경하고, `manage.sh start`에서도 웹 기동 실패 시 워커 단독 기동을 차단 | Docker entrypoint now delays worker startup after web health check, and `manage.sh start` blocks standalone worker startup if web startup fails
- 프로세스 종료 시그널(SIGTERM/SIGINT)이 도커 컨테이너에 전달될 때 하위 프로세스(Web/Worker)에 즉시 전파되지 않던 문제를 해결하고, 최대 15초간의 Graceful Shutdown 대기 로직 구현 | Fixed issue where process termination signals (SIGTERM/SIGINT) were not propagated to child processes (Web/Worker) in Docker containers; implemented a Graceful Shutdown waiting logic of up to 15 seconds

## v1.1.8
- 스캔 상태 표시 개선: 대기열(pending)만 있을 때는 '동작중'으로 표시하지 않도록 조정
- EPUB 스크롤 모드에서 초기 스크롤 직후 첫 목차 이동이 빗나가던 문제 안정화(초기 복원 타이머 충돌 방지)
- EPUB 목차 챕터 이동 시 이전 페이지 오프셋이 남아 다음 화 2페이지로 열리던 문제 수정(챕터 시작점 강제)
- EPUB 목차에서 상위 챕터 항목 클릭 시 anchor 오프셋을 무시하고 챕터 시작점으로 이동하도록 보강(하위 소제목 anchor는 유지)
- VFS 로그 용어 정리: enabled/should_refresh 대신 flag_enabled/effective_refresh로 분리 표기


## v1.1.5
- 스캔 완료 후 간헐적으로 대기상태에 머무르는 현상 수정 | Issue where the system remains in an intermittent idle state after scanning completion
- 모바일 뷰에서 뒤로가기/닫기시 즉시 상태저장 안되는 현상 수정 | Issue where the status is not immediately saved upon back navigation or closing on mobile view
- VFS 갱신시 우선순위 조정 및 로그 표시 상태 수정 | Priority adjustment and log status correction during VFS updates
- DB lock 상태 발견시 방어로직 개선(기존 2회 ->5회 및 6회차부터 로그에 기록) | Improved defense logic when DB lock status is detected (increased retries from 2 to 5, then 6, with logging from the 6th attempt)
- 스캐너 메모리 임계값 설정 조회 안정화(db_type 반영, 캐시/로그 스로틀 추가) | Stabilized scanner memory-threshold settings reads (db_type-aware lookup, cache and log throttling)

## v1.1.4
- epub에서, 목차선택시 정상적으로 이동하지 않는 현상 수정 | Fixed issue where selection in the EPUB table of contents did not navigate correctly
- epub에서, 목차 부분 스크롤 안되는 현상 수정 | Fixed issue where scrolling within the EPUB table of contents area was not working
- epub에서, 하단 여백이 제대로 적용되지 않는 현상 수정(전체화면 제외) | Fixed issue where bottom margins were not applied correctly in EPUB view (except in fullscreen mode)
- epub,txt에서 스크롤 모드일때 처음으로가 동작하지 않는 현상 수정(iOS)| Scroll mode not working on the first page in epub and txt formats(iOS).
-epub에서, 목차 이동후 다시 원복되는 현상 수정(공통) | Issue where EPUB content was reverted after moving through the table of contents(common)
-epub에서, 기기간 이동시 이어서 읽기 동기화 기능 개선 | Improved synchronization for continuous reading during period navigation in EPUB format
* 제약사항: 읽던 책을 닫아야 정상적으로 동기화 됩니다. | Synchronization for continuous reading during period navigation now requires closing the book being read

## v1.1.3
- DB 복구시 인덱스 재빌드 과정 추가 | added index rebuild process during db recovery

## v1.1.2
- 일반/성인 도서 전환시 디바운스 추가 | debounce added for general/adult toggle
- DB 복구 툴 추가(/tools/db_recovery.py) | added db recovery tool

## v1.1.1
- 도서 스캔 및 엔드포인트에 ISBN 정보 추가 | add ISBN info
- 워커 구동 안정화 및 DB경합 이슈 완화 | worker restart issue fix
- 기존 카테고리에 신규 경로 추가시 간헐적으로 발생하는 스캔 오류 수정 | Fix scan error when adding new path to existing category
- 대시보드 튕김 현상(DB lock, Worker timeout) 개선 | Fix dashboard crash(DB lock, Worker timeout)
- 로컬 스캔시 HDD의 스핀-업 시간 개선 | improvehdd spin-up time for local scan
## v1.1.0
- 워커 구동 방식 변경(웹,스캐너 분리) | worker process separated(web, scanner)
- 도커 이미지내 plugin VOLUME 삭제 | remove plugin volume from docker image
- 모바일 크롬에서 닫기/목차 버튼 겹침 버그 수정 | Mobile browser button overlap fix
- 모바일 크롬에서 하단 영역 가려짐 현상 개선 | Mobile browser bottom area display fix
- 모바일 크롬에서 캐시로 인한 뷰어 화면 미갱신 버그 수정 | Mobile browser cache miss fix
- ymal 오류시에 경고리포트 남김 |
- 로컬 고속 스캔 시 발생하던 일시적 DB 경합(persistent contention) 재시도(최대 3회, 2.0s/4.0s)로 실패 오탐 완화 확인 | Verified mitigation of false scan failures on fast local scans via transient DB contention retry (up to 3 attempts with 2.0s/4.0s backoff)

## v1.0.9
- 모바일 헤더 줄바꿈 개선: 도서보관함+카테고리는 1줄 유지, 전체 권수는 다음 줄 표시 | Mobile header wrap fix: title+category stay on one line, total count moves to next line
- EPUB 전체화면에서 목차(목록보기) 아이콘이 보이지 않던 문제 수정 | Fixed EPUB TOC button visibility in fullscreen mode
- EPUB 목차 패널 자동 노출/클릭 불가(z-index·터치 이벤트) 수정 및 TOC 점프 정확도 개선(스크롤 모드 위치 보정, 앵커 id 보존) | Fixed EPUB TOC auto-open/click issues and improved TOC jump accuracy (scroll-mode targeting, anchor id preservation)


## v1.0.8
- 추가 안정화
- 즐겨찾기를 계정별로 분리 저장하도록 변경 (사용자별 독립) | Favorites are now isolated per account


## v1.0.7
- 최신,과거추가순일때 초성바로가기 감춤 | Data_desc,Data_asc sort-> hide quickmatch
- 카테고리->기본커버로 보이게 하기 추가 | default cover view logic add
- 스케줄 설정 모달에 스케줄 도우미 추가(매일/평일/주말/요일/매월) | Added easy schedule helper in scan settings modal (preset to Cron)
- 도서 완독 후 중간으로 이동시 버그 수정 | Fixed navigation bug after completing a book read
- 모바일 뷰어 전체화면 API 연동(지원 환경에서 하단 시스템바 최소화) | Connected viewer fullscreen API to minimize mobile system navigation bar where supported
- 모바일 뷰어 진입시 자동 전체화면 시도 추가(지원 환경) | Added automatic fullscreen attempt on mobile viewer open where supported
- viewer.js 입력 계층 분리(키보드/휠/핫스팟/클릭 토글) | Split viewer input layer into input_controller (keyboard/wheel/hotspot/click)
- viewer.js 시크바/라이프사이클 분리 및 파사드 축소 | Split viewer seekbar/lifecycle into controllers and reduced viewer.js to facade
- 일부 하드코딩된 텍스트를 언어팩으로 분리 | Moved hardcoded strings to a separate language pack module
- 디스크 웜업 설정 추가(환경설정->일반설정) | Added disk warm-up settings (Settings > General)
- 환경설정 및 사용자 계정 위치 조절 기능 추가 | Added ability to adjust positions of environment settings and user accounts

## v1.0.6
- 대시보드 버전 1.0.6으로 상향 | Bumped dashboard version to 1.0.6
- OWASP 기준 보안 충족(보안 패치) | patch to OWASP guide.
- 원격 디렉토리 인식 구조 개선(루트마운트 외 폴더마운트도 지원) | Improved remote directory detection to support both root mounts and subfolder mounts
- 웹훅 엔드포인트 추가(문서 참조) | add webhook end_point(check md)
---
## v1.0.5
- 선택한 카테고리 하이라이트 추가 | Added selected category highlight
- docker entrypoint.sh 에 logs 폴더 권한 변경 추가 | Added logs folder permission update in docker entrypoint.sh
- 기본 관리자 삭제 지원(단, 다른 관리자권한이 있는 경우) | Allowed deleting the default admin account only when another admin exists
- opds에 즐겨찾기 추가 | Added favorites to OPDS
- 대시보드에서 0-001등 잘못표기되는 오류 수정(시리즈 이름으로 통일) | Fixed incorrect labels like 0-001 on dashboard by unifying to series name display
- 성인도서 권한이 없는 경우 전환버튼 감춤 | Hid the general/adult library switch for users without adult permission
- epub의 경우, 목차 아이콘 기본 감춤 | Hid the EPUB TOC icon by default
- epub의 경우, 목차에 현재 챕터 하이라이트 됨 | Added current chapter highlight in EPUB TOC
- txt의 경우, 목차 제거 | remove the txt TOC icon by default
- 웹훅 플러그인 예제 추가(beta) | add webhook sample plugin
- 플러그인 자동 업데이트 지원(beta, 문서 참조) | plugin auto update suppport(beta, check the md)

---
## v1.0.4
### fxed
- 기본 커버를 제목 조합으로 변경 | Change default cover to title and author combination
- 대시보드에서 도서권수 표시 오류 수정 | Fix incorrect book count display on dashboard
- 대시보드에서 종종 잘못된 커버 표시 오류 수정 | Fix intermittent incorrect cover display on dashboard
- TXT 커버 이미지 미검출 경고를 분리하고 단계별로 표시하도록 개선 | Split missing-cover warnings for TXT and display them by severity level

### added
- 환경설정 -> 일반설정에 TXT 무커버 안내 배너 표시/숨김 옵션 추가 | Added a toggle in Settings > General to show or hide the TXT no-cover info banner
---
## v1.0.3
- 도커이미지 지원 | support docker image update

## v1.0.2
### fixed
- 문리더등 호환 패치 및 검색 지원 | Monnreader support,(search..)
- 스캔시 시리즈이름 오류 정정 로직 추가 | scanner fixed series name update error
- .dockerignore 추가

### improved
- DB 컬럼 추가(books.metadata_locked) | add columm(books.metadata_locked)
  * 재시작시 자동 추가, 사용자가 수정한 메타정보는 스킵함 | restart auto upgrade, user edited metadata is skip the scanner

## v1.0.1
### added
- OPDS내 검색버튼 연동 | OPDS search button integration
- epub,txt의 처음으로,완독처리 이벤트 연결 | epub, txt book events connection
- 플러그인 내 html 일부 허용(plugin_README.MD 참조) | plugins allow some html

## v1.0.0
### added
- 릴리즈 전환(정식 버전) | release transition(official version)
- PWA등 닫기버튼 위치 조정 | Close button position adjustment for PWA etc
- 종료시 안전한 DB 저장 로직 추가 | Add graceful shutdown logic for safe DB storage