// state.js – 공유 상태 정의
export const state = {
  // 라이브러리/타입
  currentLibraryType: 'general',
  currentLibraryId: 'home', // 기본값: 홈 화면 (Kavita 대시보드)
  currentLibraryHideCovers: false,

  // 도서 데이터
  currentBooksData: [],
  allBooksData: [], // 카테고리 내 전체 도서 목록 선로드 메모리 캐시
  filteredBooksData: [], // 검색 및 정렬이 완료된 데이터 (인덱스 점프용)
  activeBookId: null,

  // 저장된 스크롤 위치 (라이브러리별)
  scrollPositions: {},

  // 페이지네이션
  currentPage: 1,
  hasMore: true,
  isLoading: false,
  LIMIT: 120,
  searchQuery: '',
  currentSortDirection: localStorage.getItem('library_sort_direction') || 'asc', // 로컬 캐시 연동 (기본값: 오름차순)
  
  // 시스템 전역 설정
  systemSettings: {},
  hideCompletedInHistory: false,
  tagFilterSearchInAll: false,
  showTxtNoCoverInfoBanner: true,
  sidebarTopControls: false,
  hddAggressiveWarmup: false,
  detailSeriesName: '',
  detailLibraryId: null,
  detailRepresentativeBookId: null,
  detailDisplayTitle: '',
  
  // 로그인 사용자 세션 정보
  currentUser: {
    username: '',
    role: ''
  }
};
