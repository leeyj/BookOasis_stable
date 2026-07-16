# CHANGELOG
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