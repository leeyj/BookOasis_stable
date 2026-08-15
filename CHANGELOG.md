# CHANGELOG
## v2.0.1
- (viewer/epub,txt) 2페이지 보기에서 짧은 챕터/안드로이드 태블릿의 서브픽셀 반올림 오차로 챕터 끝 판정이 틀어져 다음 챕터로 못 넘어가거나 페이지 넘길 때마다 화면이 밀리던 버그 수정 | fix chapter-end miscalculation on short chapters and Android tablets (sub-pixel rounding) that blocked next-chapter advance or caused the page to drift left on every page turn
- (viewer/epub) EPUB 뷰어에 브라우저 리사이즈 리스너가 아예 등록되지 않아 창 크기를 줄이면 2페이지 모드가 1페이지처럼 깨지던 버그 수정 | fix EPUB viewer having no resize listener at all, which broke 2-page mode into a 1-page-like layout when the browser window was resized
- (dashboard) 가나다 정렬에서 초성 바로가기로 중간 페이지에 진입한 뒤 위로 스크롤하면 이전 페이지를 불러오지 못해 더 이상 스크롤되지 않던 문제 수정(위쪽 무한 스크롤 추가) | fix scrolling up getting stuck after jumping to a mid-list page via the A-Z index shortcut by adding upward infinite scroll to load earlier pages
- (dashboard) 다운로드 클릭시 책이 열리는 현상 수정 | fix download button error