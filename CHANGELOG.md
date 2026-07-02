# CHANGELOG

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
