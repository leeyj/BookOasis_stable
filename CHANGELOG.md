# CHANGELOG
## v1.1.5
- 스캔 완료 후 간헐적으로 대기상태에 머무르는 현상 수정 | Issue where the system remains in an intermittent idle state after scanning completion
- 모바일 뷰에서 뒤로가기/닫기시 즉시 상태저장 안되는 현상 수정 | Issue where the status is not immediately saved upon back navigation or closing on mobile view
- VFS 갱신시 우선순위 조정 및 로그 표시 상태 수정 | Priority adjustment and log status correction during VFS updates
- DB lock 상태 발견시 방어로직 개선(기존 2회 ->5회 및 6회차부터 로그에 기록) | Improved defense logic when DB lock status is detected (increased retries from 2 to 5, then 6, with logging from the 6th attempt)

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