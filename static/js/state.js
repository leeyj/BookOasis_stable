// state.js – 공유 상태 정의
export const state = {
  // 라이브러리/타입
  currentLibraryType: 'general',
  currentLibraryId: 'home', // 기본값: 홈 화면 (Kavita 대시보드)
  currentLibraryHideCovers: false,
  libraryGroups: [],

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
  firstLoadedPage: 1, // 현재 그리드에 로드된 첫 페이지 번호 (초성 점프로 중간 페이지부터 로드된 경우 1보다 큼)
  hasPrevious: false, // firstLoadedPage 이전에 아직 안 불러온 페이지가 있는지
  isLoadingPrevious: false,
  isLoading: false,
  LIMIT: 120,
  searchQuery: '',
  currentSortDirection: localStorage.getItem('library_sort_direction') || 'asc', // 로컬 캐시 연동 (기본값: 오름차순)
  groupMode: localStorage.getItem('library_group_mode') || 'default', // 'default'(시리즈) | 'author'(작가별 모음)
  authorKeyFilter: '', // 작가별 카드 클릭 드릴다운용 정규화 작가 키(기본 그리드로 전환 시에만 사용)
  
  // 시스템 전역 설정
  systemSettings: {},
  hideCompletedInHistory: false,
  tagFilterSearchInAll: false,
  showTxtNoCoverInfoBanner: true,
  sidebarTopControls: false,
  showSidebarCategoryAll: true,
  hddAggressiveWarmup: false,
  audioMiniPlayerMode: 'mini',
  audioRightDockDimEnabled: false,
  detailVolumeGridView: false,      // 도서 상세 목록 그리드 보기 (기본값: 리스트)
  collapseDetailGenreTags: false,   // 태그/장르 축소 (기본값: 해제)
  smartRecommendEnabled: true,      // 스마트 추천 기능 사용 여부 (기본값: 사용)

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
