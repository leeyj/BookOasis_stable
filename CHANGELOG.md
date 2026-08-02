# CHANGELOG
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