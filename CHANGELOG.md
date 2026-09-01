# CHANGELOG
## v2.5.2
- (improvement) 기본 테마 팔레트를 보라/네이비 톤에서 무채색+블루 포인트 톤으로 변경 | change the default theme palette from purple/navy to a neutral + single blue accent tone
- (improvement) 상단 툴바를 한 줄 레이아웃으로 재구성하고 필터/정렬 버튼을 아이콘 전용으로 압축 | restructure the top toolbar into a single row and compress the filter/sort buttons to icon-only
- (improvement) 사이드바 하단의 환경설정/계정 메뉴를 상단 헤더 아이콘으로 이동 | move the sidebar's settings/account menu to top-header icons
- (feature) 상단 헤더를 전역 컴포넌트로 분리해 플러그인 화면에서도 항상 노출, 플러그인용 세션 조회 API(`window.BookOasisPlugin.getSession()`, `bookoasis:session-change` 이벤트) 추가 | split the top header into a global component always shown on plugin screens, and add a plugin-facing session API (`window.BookOasisPlugin.getSession()`, `bookoasis:session-change` event)
- (fix) CSS 정적 파일이 배포 후에도 브라우저에 캐시되어 반영이 안 되던 문제 수정 | fix CSS static files staying browser-cached after deploy instead of picking up changes
- (feature) 도서 상세 페이지에 "이 작가의 다른 도서" 사이드바 추가 (2단 레이아웃) | add a "more by this author" sidebar to the book detail page (two-column layout)
- (feature) 라이브러리별 자동 스캔 스케줄 ON/OFF 토글 추가 — 꺼두면 수동 스캔은 그대로 두고 예약 실행만 건너뜀 | add a per-library ON/OFF toggle for the scheduled scan — manual scans still work while off, only the scheduled run is skipped
- (feature) 설정에 "도서 추천기능" 체크박스 추가 — 해제 시 "이 작가의 다른 도서" 표시 안 함 | add a "book recommendations" checkbox to settings — disables the "more by author" sidebar when off
- (improvement) 더 이상 쓰이지 않는 "사이드바 환경설정/계정 상단 배치" 옵션 제거 | remove the now-unused "place sidebar settings/account at top" option

## v2.5.1
- (improvement) PDF 커버를 표지 표시 크기의 2배로 렌더링한 뒤 축소(수퍼샘플링)해 불필요한 대형 비트맵 생성은 피하면서 텍스트 선명도 유지 | improve PDF cover rendering to render at 2x the display size then downscale (supersampling), avoiding unnecessarily large intermediate bitmaps while keeping text crisp
- (breaking) PDF 처리 엔진을 PyMuPDF(AGPL)에서 pypdfium2(Apache-2.0/BSD, 크롬과 동일한 Pdfium 엔진)로 교체 | (breaking) switch PDF engine from PyMuPDF (AGPL) to pypdfium2 (Apache-2.0/BSD, the same Pdfium engine used by Chrome)
- (fix) PDF 뷰어에서 페이지를 넘길 때마다 흰 화면이 잠깐 보였다가 내용이 채워지던 깜빡임 수정 — 새 페이지 렌더링이 끝날 때까지 이전 페이지를 유지 | fix a white-flash-then-fill flicker on every PDF page turn — the previous page now stays visible until the new one finishes rendering
