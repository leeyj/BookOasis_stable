// tab_media_library.js – 도서관 코어 엔트리 조율기
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail, goBackToList } from './modal.js';
import { openReader, closeMediaViewer, toggleFullscreenViewer, setComicFitMode, changeFontSize, toggleReaderTheme, initKeyboardListener, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, epubPrevPage, epubNextPage, prevTxtPage, nextTxtPage } from './viewer.js';
import { switchActiveView } from './view_manager.js';

// category.js 신설 모듈로부터 CRUD 제어부 임포트
import { loadLibraries, triggerAddLibrary, triggerEditLibrary, triggerDeleteLibrary, closeLibraryModal, submitLibraryForm, triggerScanLibrary, triggerScanLibraryCovers, triggerCancelScanLibrary } from './category.js';


// scheduler.js 모듈로부터 스케줄 제어부 임포트
import { loadLibrarySchedules, saveLibrarySchedule, runLibraryScanNow } from './scheduler.js';

// 신규 리팩토링 분리 서브 모듈 임포트
import { loadDashboardData, scrollDashboardRow, loadDashboardPlugins } from './dashboard.js';
import { initInfiniteScrollObserver } from './infinite_scroll.js';
import { showBookContextMenu, triggerScanSingleBookAction, triggerSearchAladinMetadataAction, triggerMarkAsUnreadAction } from './book_context_menu.js';
import { openMetadataSearchModal, closeMetadataSearchModal, performMetadataSearch } from './metadata_search.js';

// book_list.js 모듈로부터 도서 목록 제어부 임포트
import { loadBooksList, loadReadingHistory, filterBooks, toggleLibrarySort, resumeSeries, updateSortButtonUI } from './book_list.js';

// settings_tab.js 모듈로부터 환경설정 제어부 임포트
import { switchSettingsTab, loadInitialSystemSettings, loadGeneralSettings, submitGeneralSettings, initReportsTab, loadReportList, loadReportDetail, loadViewerSettings, submitViewerSettings } from './settings_tab.js';

// 장르 및 태그 플로팅 필터 모달 임포트
import { initFloatingFilter, toggleFilterModal } from './genre_tag_filter.js';
import { initSidebarAutoClose, restoreDesktopSidebarState } from './sidebar_manager.js';
import './viewer/viewer_padding.js';

function focusLibrarySearchInput() {
  const searchInput = document.getElementById('library-search');
  if (!searchInput) return;
  searchInput.focus();
  searchInput.select();
}

function initLibrarySearchShortcut() {
  if (window.__librarySearchShortcutBound) return;

  document.addEventListener('keydown', (e) => {
    const key = String(e.key || '').toLowerCase();
    const isBackquote = key === '`' || e.code === 'Backquote';

    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || !isBackquote) return;

    e.preventDefault();
    focusLibrarySearchInput();
  });

  window.__librarySearchShortcutBound = true;
}

// 초기화 함수 분리
async function initTabMediaLibrary() {
  // 로그인 사용자 세션 연동
  if (window.currentUser) {
    state.currentUser = window.currentUser;
    const usernameEl = document.getElementById('session-username-display');
    if (usernameEl) usernameEl.innerText = state.currentUser.username;
    
    // 어드민 전용 사용자 관리 및 권한 관리 탭 버튼 노출
    if (state.currentUser.role === 'admin') {
      const usersTabBtn = document.getElementById('settings-tab-btn-users');
      if (usersTabBtn) usersTabBtn.style.display = 'block';
      const permissionsTabBtn = document.getElementById('settings-tab-btn-permissions');
      if (permissionsTabBtn) permissionsTabBtn.style.display = 'block';
      
      // 어드민용 탭 노출
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const onclickAttr = btn.getAttribute('onclick') || '';
        if (onclickAttr.includes("'schedule'") || onclickAttr.includes("'queue'") || onclickAttr.includes("'general'") || onclickAttr.includes("'plugins'") || onclickAttr.includes("'reports'")) {
          btn.style.display = 'block';
        }
      });
    } else {
      // 일반 사용자는 어드민 전용 탭 숨김 처리
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const onclickAttr = btn.getAttribute('onclick') || '';
        if (onclickAttr.includes("'schedule'") || onclickAttr.includes("'queue'") || onclickAttr.includes("'general'") || onclickAttr.includes("'plugins'") || onclickAttr.includes("'reports'")) {
          btn.style.display = 'none';
        }
      });
    }
  }

  // fixed 모달창들이 transform 조상 컨테이너 내부에서 스크롤을 이탈하는 버그 방지 (body 최하단으로 강제 이동)
  document.querySelectorAll('.library-modal').forEach(modal => {
    document.body.appendChild(modal);
  });

  // 최초 시스템 설정 로드하여 화면 썸네일 크기 및 Limit 적용
  // [버그수정] await 없이 호출하면 설정 로드 전에 대시보드가 렌더링되어
  //           state.hideCompletedInHistory = false 상태로 100% 완독 도서가 노출됨
  await loadInitialSystemSettings();

  // 사이드바 상태 복원 및 리스너 등록
  restoreDesktopSidebarState();
  initSidebarAutoClose();

  state.currentLibraryId = 'home';
  loadLibraries();
  selectCategory('home');
  updateSortButtonUI();

  // 플로팅 필터 모달 초기화
  initFloatingFilter();

  // IntersectionObserver 기반 무한 스크롤 초기화
  initInfiniteScrollObserver();

  // URL 해시 파라미터 파싱 헬퍼
  function getHashParams() {
    const hash = window.location.hash;
    if (!hash || !hash.includes('?')) return {};
    const queryString = hash.split('?')[1];
    const params = {};
    const pairs = queryString.split('&');
    for (const pair of pairs) {
      const [key, val] = pair.split('=');
      if (key) params[key] = decodeURIComponent(val || '');
    }
    return params;
  }

  // 새로고침 시 URL 해시 기반 상세 화면 자동 재진입
  const hashParams = getHashParams();
  if (window.location.hash.startsWith('#detail') && hashParams.series) {
    const restoreSeries = hashParams.series;
    const restoreLibraryId = hashParams.libraryId || 'all';
    console.log('[History] 해시 주소 기반 복원 감지 - 상세 뷰 복구:', restoreSeries);
    setTimeout(() => {
      openBookDetail(null, restoreSeries, restoreLibraryId);
    }, 150);
  }

  // 키보드 단축키
  initKeyboardListener();
  initLibrarySearchShortcut();


  // 브라우저 뒤로가기/앞으로가기 버튼 감지하여 뷰 라우팅 복원 처리
  window.addEventListener('popstate', (event) => {
    console.log('[History] popstate 이벤트 감지:', window.location.hash, event.state);
    
    // 1. 현재 뷰어가 열려있다면 무조건 닫기 (목적지가 뷰어가 아닐 때만)
    const viewerModal = document.getElementById('media-viewer-modal');
    if (viewerModal && viewerModal.style.display === 'flex') {
      if (!event.state || event.state.view !== 'viewer') {
        closeMediaViewer(false); 
      }
      return;
    }
    
    // 2. 목적지 상태가 상세 뷰(detail)인 경우
    if (event.state && event.state.view === 'detail') {
      openBookDetail(null, event.state.series, event.state.libraryId);
      return;
    }
    
    // 3. 목적지가 목록(카테고리) 뷰인 경우 (현재 상세 뷰가 떠 있다면 먼저 닫음)
    const detailView = document.getElementById('book-detail-view');
    if (detailView && detailView.style.display !== 'none') {
      goBackToList(false);
    }
    
    if (event.state && event.state.view === 'category' && event.state.libraryId) {
        // 히스토리에 저장된 이전 카테고리로 복원 (히스토리 스택 중복 방지를 위해 skipHistory = true 전달)
        selectCategory(event.state.libraryId, true);
    } else if (!event.state && (window.location.hash === '' || window.location.hash.startsWith('#library='))) {
        // 해시가 비어있거나 library 진입인 경우 상태가 없어도 home으로 복원
        selectCategory('home', true);
    }
  });
}

if (window.i18nReady) {
  initTabMediaLibrary();
} else {
  document.addEventListener('i18nReady', initTabMediaLibrary);
}

// 라이브러리 타입 스위칭 (일반/성인)
export function switchLibraryType(type) {
  window.scrollTo(0, 0);
  state.currentLibraryType = type;
  document.querySelectorAll('.btn-toggle').forEach(btn => btn.classList.remove('active'));
  if (type === 'general') {
    document.getElementById('btn-lib-general').classList.add('active');
  } else {
    document.getElementById('btn-lib-adult').classList.add('active');
  }
  loadLibraries();
  selectCategory('home');
}

// 카테고리 선택 처리
export function selectCategory(id, skipHistory = false) {
  window.scrollTo(0, 0);
  state.currentLibraryId = id;
  
  // 브라우저 히스토리에 카테고리 이동 기록 남기기 (SPA 뒤로가기 지원)
  if (!skipHistory) {
    history.pushState({ view: 'category', libraryId: id }, '', `#library=${id}`);
  }
  
  // 장르 및 태그 필터 초기화
  state.currentGenre = null;
  state.currentTag = null;

  document.querySelectorAll('#sidebar-categories .menu-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.sidebar-settings-wrap .menu-item').forEach(el => el.classList.remove('active'));
  
  const activeItem = document.getElementById(`category-${id}`) || document.querySelector(`[data-id="${id}"]`);
  if (activeItem) {
    activeItem.classList.add('active');
  }

  goBackToList();

  if (id === 'home') {
    switchActiveView('dashboard');
    loadDashboardData();
  } else if (id === 'settings') {
    switchActiveView('settings');
    if (state.currentUser && state.currentUser.role === 'admin') {
      loadLibrarySchedules();
      switchSettingsTab('schedule');
    } else {
      switchSettingsTab('about');
    }
  } else if (id === 'plugins') {
    switchActiveView('plugins');
    loadDashboardPlugins();
  } else {
    switchActiveView('grid');
    if (id === 'history') {
      loadReadingHistory();
    } else {
      loadBooksList(false);
    }
  }
}

// 글로벌 함수 노출 (HTML 인라인 핸들러용)
window.scrollDashboardRow = scrollDashboardRow;
window.selectCategory = selectCategory;
window.switchLibraryType = switchLibraryType;
window.filterBooks = filterBooks;
window.openReader = openReader;
window.openBookDetail = openBookDetail;
window.goBackToList = goBackToList;
window.setComicFitMode = setComicFitMode;
window.closeMediaViewer = closeMediaViewer;
window.toggleFullscreenViewer = toggleFullscreenViewer;
window.changeFontSize = changeFontSize;
window.toggleReaderTheme = toggleReaderTheme;
window.nextComicPage = nextComicPage;
window.prevComicPage = prevComicPage;
window.nextPdfPage = nextPdfPage;
window.prevPdfPage = prevPdfPage;
window.epubPrevPage = epubPrevPage;
window.epubNextPage = epubNextPage;
window.prevTxtPage = prevTxtPage;
window.nextTxtPage = nextTxtPage;
window.toggleLibrarySort = toggleLibrarySort;
window.resumeSeries = resumeSeries;
window.saveLibrarySchedule = saveLibrarySchedule;
window.runLibraryScanNow = runLibraryScanNow;
window.loadLibrarySchedules = loadLibrarySchedules;

// 단일 도서 우클릭 스캔 및 컨텍스트 메뉴 매핑
window.showBookContextMenu = showBookContextMenu;
window.triggerScanSingleBook = async () => {
  if (typeof window.triggerScanSingleBookAction === 'function') {
    await window.triggerScanSingleBookAction();
  } else {
    console.error('[Global Trigger ERROR] window.triggerScanSingleBookAction 함수가 바인딩되지 않았습니다.');
  }
};

window.triggerSearchAladinMetadata = async () => {
  if (typeof window.triggerSearchAladinMetadataAction === 'function') {
    await window.triggerSearchAladinMetadataAction();
  } else {
    console.error('[Global Trigger ERROR] window.triggerSearchAladinMetadataAction 함수가 바인딩되지 않았습니다.');
  }
};

window.triggerMarkAsUnread = async () => {
  if (typeof window.triggerMarkAsUnreadAction === 'function') {
    await window.triggerMarkAsUnreadAction();
  } else {
    console.error('[Global Trigger ERROR] window.triggerMarkAsUnreadAction 함수가 바인딩되지 않았습니다.');
  }
};
window.openAladinSearchModal = openMetadataSearchModal;
window.closeAladinSearchModal = closeMetadataSearchModal;
window.performAladinSearch = performMetadataSearch;
window.openMetadataSearchModal = openMetadataSearchModal;
window.closeMetadataSearchModal = closeMetadataSearchModal;
window.performMetadataSearch = performMetadataSearch;

// 즐겨찾기 글로벌 함수 매핑
import { toggleFavorite } from './api.js';
window.toggleFavoriteAction = async (bookId, isFavorite) => {
  try {
    const res = await toggleFavorite(state.currentLibraryType, bookId, isFavorite);
    return res;
  } catch (err) {
    console.error('즐겨찾기 업데이트 실패:', err);
    return { success: false, error: err.message };
  }
};

import { toggleSeriesFavorite } from './api.js';
window.toggleSeriesFavoriteAction = async (seriesName, isFavorite) => {
  try {
    const res = await toggleSeriesFavorite(state.currentLibraryType, seriesName, isFavorite);
    return res;
  } catch (err) {
    console.error('시리즈 즐겨찾기 업데이트 실패:', err);
    return { success: false, error: err.message };
  }
};

// CRUD 글로벌 함수 매핑 (category.js에 위임)
window.triggerAddLibrary = triggerAddLibrary;
window.triggerEditLibrary = triggerEditLibrary;
window.triggerDeleteLibrary = triggerDeleteLibrary;
window.triggerScanLibrary = triggerScanLibrary;
window.triggerScanLibraryCovers = triggerScanLibraryCovers;
window.triggerCancelScanLibrary = triggerCancelScanLibrary;
window.closeLibraryModal = closeLibraryModal;
window.submitLibraryForm = submitLibraryForm;

// 신규 뷰어 오버레이 함수 매핑 (viewer_comic.js에 위임)
import { toggleComicOverlay, markAsCompleted } from './viewer_comic.js';
window.toggleComicOverlay = toggleComicOverlay;
window.markAsCompleted = markAsCompleted;

// 갱신 시 무한 스크롤 옵저버 다시 바인딩 헬퍼용 노출
window.initInfiniteScrollObserver = initInfiniteScrollObserver;

// 환경설정 글로벌 함수 매핑 (settings_tab.js에 위임)
window.switchSettingsTab = switchSettingsTab;
window.loadGeneralSettings = loadGeneralSettings;
window.submitGeneralSettings = submitGeneralSettings;
window.loadViewerSettings = loadViewerSettings;
window.submitViewerSettings = submitViewerSettings;
window.initReportsTab = initReportsTab;
window.loadReportList = loadReportList;
window.loadReportDetail = loadReportDetail;

export function handleLibrarySearchAction() {
  const searchInput = document.getElementById('library-search');
  if (!searchInput) return;
  const query = searchInput.value.trim();
  if (query) {
    searchInput.value = '';
    filterBooks();
    searchInput.focus();
  } else {
    searchInput.focus();
  }
}
window.handleLibrarySearchAction = handleLibrarySearchAction;

export { loadLibraries };
