# CHANGELOG

## v0.7.5
### added
- 카테고리 이동기능 추가(일반<->성인) - beta | category move feature added(general <-> adult) - beta
* 제약조건 : 스캔중이면 동작 불가. | constraint : if scan in progress, it doesn't work.
*          이관중에는 대시보드 사용불가 | during migration, dashboard is not available
*          카테고리중복시 속보바(toast)로 경고문구 표시 (일반/성인간 중복경로 존재시) | Duplicate path warning toast displayed after move

## v0.7.4
### added
- 카테고리 아이콘 수정 및 색 변경 기능 추가 | category icon and color change feature added
- 카테고리 정보 수정시 스캔 적용 로직 변경(경로 변경시만 스캔 실행) | category edit scan logic change(scan only when path changes)

### fixed
- 일반도서<->성인도서 전환시 홈 화면 로딩되도록 수정 | general book <-> adult book tab switch fix
- 카테고리 로딩중 다른 카테고리 전환시 무한로딩 오류 수정 | category loading other category tab infinite loading error fix

## v0.7.3
### fixed
- rclone 실행시 ID/패스워드 미사용시 발생하던 오류 조치(basic auth 적용) | rclone id/password not using error fix(basic auth applied)

## v0.7.2
### fixed
- 스캔시 DB 최적화 튜닝시 스캔 큐 락 경합 조치 | scan tune db lock contention fix

## v0.7.1
### fixed
- lazy 스캐너 오작동(offset 정보 채우려는 시도 및 건너뜀 현상) 해소 | lazy scanner incorrect operation(offset information and skipping)
- 대시보드내 오프셋 정보 없을시 경고창 제거 | dashboard offset information warning removal
- lazy 스캐너의 역활은 커버 미검출시 추출하도록 용도 축소(오프셋 검출 제거). 단 zip 파일내 comicinfo.xml 추출은 여전히 포함되어 있음. | lazy scanner role is reduced to extracting only when cover is not detected (offset detection removed). However, extraction of comicinfo.xml within zip files is still included.
- 스캐너 로직을 분리하여 파서를 독립적으로 호출하게 변경 | scanner logic separation and parser independent calling

KR:
* .\tools\scanner\metadata 에 각각의 파서가 존재함.
  (kavita_ymal,info_xml)등
* 추후 새로운 포맷 추가시 해당 폴더에 파서만 추가하면 됨.
* 또는 기존 파서에서 지원하지 않는 포맷 추가시 해당 파서를 수정하여 추가하면 됨.
* 파서 개발 및 수정을 원하시는 경우 **.\docs\guide_scanner_parser.md** 참조.

EN:
* Each parser exists in .\tools\scanner\metadata.
  (kavita_ymal, info_xml), etc.
* When adding new formats in the future, simply add the parser to the corresponding folder.
* Alternatively, if you need to add a format not supported by the existing parser, you can modify the parser to add it.
* Please refer to **./docs/guide_scanner_parser.md** for parser development and modification.

### improved
- epub 보기시 행간,단락 조절기능 추가 | epub viewing line spacing, paragraph spacing adjustment
- epub 보기시 닫기 버튼 플로팅 추가 | epub viewing close button floating
- 뷰어 설정 오버레이, 닫기 버튼 위치 재배치 | viewer setting overlay, close button position rearrangement

## v0.7.0
### improved
- /docs 내 문서 보강 및 최신화 | /docs documents reinforcement and update
- 소스코드 정리 및 모듈화, DB 쿼리 느슨한 연결 구조 변경 | source code cleanup, modularization, DB query loose connection structure change
- 윈도우 서버 사용자를 위한 배치파일 추가 | added batch file for windows server users
- 스캔 일괄 추가 버튼  추가 | added batch add scan button
### fix
- 삼성 브라우저(모바일)에서 상단 여백 오류 수정 | samsung browser (mobile) top margin error fix

## v0.6.9
### fix
- 환경설정의 tab 순서 변경(general, plugins, reports, users, queue, changelog, about) | Environment setting tab order changed(general, plugins, reports, users, queue, changelog, about)
- 영문 사용시 환경설정의 탭이 모두 한글로 나오는 오류 수정 | Fix error that all tabs in environment settings appear in Korean when using English

### improved
- 사용자 카테고리 접근 권한 관리 탭 추가(by 뿌아씨) | user category access permission management tab added

## v0.6.8
### fix
- pdf 뷰어에서 스크롤 동작 오류 수정(전체 뷰포트 사용으로 변경) | pdf viewer scroll error fix(use full viewport)
- 모바일 뷰에서 꾸욱클릭(롱 프레스)시 컨텍스트 메뉴 호출 | mobile view long press context menu call
- info.xml 분석시 특수문자로 인한 정보누락 수정(by 아쿠니스) | info.xml analyze special character info missing fix(by Acunis)

### improved
- 도커 오버라이드 추가 (readme.md 참조) | docker override added (readme.md reference)
- 스캔시 VFS 갱신중일때도 예약조회에 노출됨 | during scan, vfs refresh is displayed in the reservation query
- kavtia 마이그레이션 툴 개선(메타데이터 연동, made by 짜파구리) | kavtia migration tool improvement(meta data interworking, made by Chapaguri)

## v0.6.7
### added
- 모바일 해상도 지원(beta) | Mobile resolution support (beta)
- 왼쪽 사이드 메뉴 접기/펼치기 추가 | Left side menu expand/collapse added
- 읽지 않는 상태 변경 컨텍스트 메뉴 추가 | unread status change context menu added(booklist,dashboard)
### improved
- 로그 아카이빙 대상 확대 | log file zip archiving 대상 확대(scanner.log,lazy_scanner.log 추가)
- 대시보드 신규 추가 도서 목록에서 시리즈 단위로 묶어 보여주는 기능 개선 | dashboard new added book list series grouping
- 타임존 설정 추가(환경설정->일반설정->타임존 설정) | system timezone setting added(Environment setting->General setting->Timezone setting)



## v0.6.6
### added
- 카테고리 등록시 경로 선택 기능 추가 (로컬 및 rclone 원격 드라이브 지원) | Added directory path browser when adding categories (supports local and rclone remote drives)
- 백엔드 경로 탐색 API (`/api/media/browse-paths`) | Backend path browsing API for seamless directory navigation
- RC URL 아래 원격 경로 필수 입력 경고 메시지 추가 | Added mandatory remote path warning message below RC URL input field
- 스캔 시 원격 경로 자동 감지 및 VFS 강제 갱신 기능 추가 | Added automatic remote path detection and forced VFS refresh during scans to ensure data integrity

### improved
- 카테고리 모달에 "찾아보기" 버튼 추가로 UX 개선 | Improved UX by adding browse button to category modal
- VFS 설정 무시 시 발생하는 데이터 미감지 현상 개선 | Enhanced VFS refresh logic to force refresh when remote paths exist, preventing file detection failures

### fix
- 카테고리 내 원격 경로가 있어도 VFS 갱신이 무시되는 버그 수정 | Fixed bug where VFS refresh was ignored when remote paths existed in category (now forces refresh for data consistency)

---

## v0.6.5
### fix
- 책 스캔정보가 부족할 때 시리즈 별 스캔 기능 추가 | Added a series-based scanning feature when book scan data is insufficient.
- 도서 보기중 에러 및 xbox 발생 오류 수정 | Fixed errors occurring during book viewing and X-box errors
- 도서 보기중 페이지보기 ->스크롤보기->페이지보기 전환시 에러 수정 | - Fixed an error when switching from Page View -> Scroll View -> Page View while viewing a book
---


## v0.6.4
### fix
- vfs 리프레시 오류수정(reculsive 추가) 및 미 변동사항 건너뛰기 로직 개선 | vfs update error fix and skip no change items
- DB 구조 변경(mtime 추가) 및 스캔로직 변경 | DB structure change(add mtime) and scan logic change
- 스캔시 디렉토리의 mtime 및 메타파일(yaml,xml등)의 mtime도 동시에 확인하여 변경 여부 판단 로직 개선 | scan directory mtime and metadata file mtime check logic improvement
- 타치요미,미혼등 다음편 미리로드 기능 추가 | tachiyomi,mihone next book preload functionality
---
## v0.6.3
- 버그로 인한 폐기 | remove this version
---

## v0.6.2
### fix
- scanner 동작방식 변경
- as is: yaml스캔->정보 취득->DB 저장 -> commit 
- to be :yaml스캔->정보 취득->jsonl 저장 -> bulk insert(update)
* 개선효과 : 스캔시 대시보드 병목현상 개선(bottleneck fix) | scan dashboard bottleneck fix
* 개선효과 : 스캔시 DB lock 현상 해소 | scan db lock fix

---


## v0.6.1
### fix
- 페이지 넘김시 2장씩 넘어가는 이슈 해결(by 세안파파) | fix page change issue
- 즐겨찾기 토글 안되는 이슈 해결(by 세안파파) | fix favorite toggle issue
- 타치요미용 OPDS Endpoint 추가(/app-opds) | tachiyomi opds endpoint added(/app-opds)
- 타치요미용 OPDS 연동 시 Auth 캐시 동시성 병목(속도 저하) 및 500 에러 현상 수정 | fix tachiyomi app-opds cache stampede bottleneck and 500 error
- 스캐너 로그 저장위치 수정/분리(by 젤리씨) | Scanner log save location modified/separated
- epub 파일 페이지 구성로직 변경(페이지->퍼센테이지) | epub file page composition logic change(page -> percentage)

### added
- 스캐너 큐 로직 도입(환경설정->스캔예약조회) | scanner queue logic introduction(Environment setting->Scan queue view)

---

## v0.6.0
### Changed
- 웹툰(세로 스크롤형)뷰어시 너비 조절 기능 추가(by freebird81) | Added width adjustment feature for webtoon (vertical scroll type) viewer


## v0.5.9
### Changed
- 만화 보기 방향 변경 기능 및 2장씩 보기 추가(by SUIKANO) | Viewer slide change setting add and 1page, or 2page view
- OPDS 속도 개선 (캐시도입 및 쿼리문 개선. by 데브닉스) | OPDS load caching included and query modified

## v0.5.8
### Changed
- 로그인시 자동로그인 기능 추가 | added remember me functionality in login
- 도커실행시 유저권한으로 실행가능하도록 수정 | docker run with custom user permission

## v0.5.7
### Changed
- epub로드시 슬라이드 오류 수정 | epub load slide error fix

---

## v0.5.6
### Changed
- sortable.js 도입 | sortable.js introduced

---
## v0.5.5
### Changed
- 만화뷰어에 페이지 이동용 슬라이드 추가 | Add slide bar for page navigation in comic viewer
- 플러그인 활성화/비활성화 미적용 개선 | Plugin enable/disable apply improvement
- 정렬 기능 저장 | Sort function save

---

## v0.5.4
### Changed
- 단일인덱스를 복합 인덱스 변경 적용 | Apply complex index instead of single index

---


## v0.5.3
### Changed
- DockerFile 내 워커수 1개로 고정 | DockerFile workers 1 fixed

---

## v0.5.2
### Changed
- 환경설정 저장시 오류 수정 | Fix in settings save error

---

## v0.5.1
### Changed
- library_settings.html 모듈화 | library_settings.html modularization
- Font,image,lib 브라우저 캐싱 | Font,image,lib browser caching included
---
## v0.5.0
### Changed
- i18n 다국어 지원 가능(한국어, 영어) | i18n multi-language support (Korean, English)

### Fixed
- 스캐너 엔진 안정화 | Scanner engine stabilization
