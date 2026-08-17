// tab_media_library.js – 도서관 코어 엔트리 오케스트레이터 및 메인 라우터
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail, goBackToList } from './modal.js';
import { updateCurrentCategoryIndicator } from './category_indicator.js';
import { openReader, closeMediaViewer, toggleFullscreenViewer, setComicFitMode, changeFontSize, toggleReaderTheme, initKeyboardListener, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, epubPrevPage, epubNextPage, prevTxtPage, nextTxtPage } from './viewer.js';
import { switchActiveView } from './view_manager.js';

// category.js CRUD 임포트
import { loadLibraries, triggerAddLibrary, triggerEditLibrary, triggerDeleteLibrary, closeLibraryModal, submitLibraryForm, triggerScanLibrary, triggerScanLibraryCovers, triggerCancelScanLibrary } from './category.js';
import { applySidebarShowMore } from './category/index.js';

// scheduler.js 임포트
import { loadLibrarySchedules, saveLibrarySchedule, runLibraryScanNow } from './scheduler.js';

// 서브 모듈 임포트
import { loadDashboardData, loadDashboardPlugins, switchPluginsViewTab } from './dashboard.js?v=20260809-unread-series-v3';
import { initScrollableRowNavDelegation } from './scrollable_row_nav.js';
import { initInfiniteScrollObserver } from './infinite_scroll.js';
import { showBookContextMenu, triggerScanSingleBookAction, triggerSearchAladinMetadataAction, triggerMarkAsUnreadAction } from './book_context_menu.js?v=20260809-unread-series-v5';
import { openMetadataSearchModal, closeMetadataSearchModal, performMetadataSearch } from './metadata_search.js';

// book_list.js 임포트
import { loadBooksList, loadReadingHistory, filterBooks, toggleLibrarySort, resumeSeries, updateSortButtonUI } from './book_list.js?v=20260809-unread-series-v3';

// plugin_custom_view.js 임포트
import { mountCategoryPluginUI } from './plugin_custom_view.js';
import { switchSettingsTab, loadInitialSystemSettings, loadGeneralSettings, submitGeneralSettings, initReportsTab, loadReportList, loadReportDetail, loadViewerSettings, submitViewerSettings } from './settings_tab.js';

// 장르/태그 및 사이드바 제어 모듈
import { initFloatingFilter, toggleFilterModal } from './genre_tag_filter.js';
import { initSidebarInteractions, restoreDesktopSidebarState, toggleDesktopSidebar, syncSidebarResponsiveControls } from './sidebar_manager.js';
import { decodeDetailParams } from './url_obfuscator.js';
import { remoteLog } from './remote_log.js';

// 모듈화로 분리한 미디어 타입 토글 및 검색 단축키 제어부 임포트
import { canAccessLibraryType, applyLibraryTypeToggleVisibility, applyLibraryTypeButtonState, switchLibraryType } from './library_type_toggle.js';
import { focusLibrarySearchInput, applySearchShortcutSetting, initLibrarySearchShortcut, handleLibrarySearchAction, handleLibrarySearchKeydown, initLibraryTypeHotkeys } from './search_shortcut_manager.js';

import './viewer/viewer_padding.js';
import './audio_player.js';
import './video_library.js';
import './video_player.js';
import './plugin_webview_api.js';

function initLibraryShellDelegation() {
  if (window.__libraryShellDelegationBound) return;

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="mobile-brand-home"], [data-role="sidebar-category-static"], [data-role="desktop-sidebar-toggle"], [data-role="library-search-action"], [data-role="library-open-filter"], [data-role="library-sort-toggle"], [data-role="library-type-toggle"], [data-role="library-filter-reset"], [data-role="detail-back-to-list"]')
      : null;
    if (!target) return;

    event.preventDefault();

    const role = target.getAttribute('data-role');
    if (role === 'mobile-brand-home') {
      if (window.matchMedia('(max-width: 1200px)').matches) return selectCategory('home');
      return;
    }
    if (role === 'sidebar-category-static') {
      return selectCategory(target.getAttribute('data-category-id') || 'home');
    }
    if (role === 'desktop-sidebar-toggle') {
      return toggleDesktopSidebar();
    }
    if (role === 'library-search-action') {
      return handleLibrarySearchAction();
    }
    if (role === 'library-open-filter') {
      return toggleFilterModal();
    }
    if (role === 'library-sort-toggle') {
      return toggleLibrarySort();
    }
    if (role === 'library-type-toggle') {
      return switchLibraryType(target.getAttribute('data-library-type') || 'general');
    }
    if (role === 'library-filter-reset') {
      return window.resetAllFilters?.();
    }
    if (role === 'detail-back-to-list') {
      return goBackToList();
    }
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const target = event.target?.closest?.('[data-role="mobile-brand-home"]');
    if (!target || !window.matchMedia('(max-width: 1200px)').matches) return;
    event.preventDefault();
    selectCategory('home');
  });

  document.addEventListener('input', (event) => {
    const target = event && event.target;
    if (!target) return;
    if (target.matches && target.matches('[data-role="library-search-input"]')) {
      filterBooks();
    }
  }, true);

  document.addEventListener('keydown', (event) => {
    const target = event && event.target;
    if (!target) return;
    if (target.matches && target.matches('[data-role="library-search-input"]')) {
      handleLibrarySearchKeydown(event);
    }
  }, true);

  window.__libraryShellDelegationBound = true;
}

function recoverTopCategoryUiAfterBack() {
  const isMobileLayout = window.matchMedia('(max-width: 1200px)').matches;
  if (!isMobileLayout) return;

  const libraryHeader = document.querySelector('.library-header');
  const searchCenter = document.querySelector('.library-search-center');
  const libraryControls = document.querySelector('.library-controls');
  const sidebarCollapsible = document.getElementById('sidebar-collapsible-content');

  if (libraryHeader) libraryHeader.style.display = 'grid';
  if (searchCenter) searchCenter.style.display = 'block';
  if (libraryControls) libraryControls.style.display = 'flex';

  applyLibraryTypeToggleVisibility();
  // 뷰어 전체화면 종료 등으로 상단 사이드바(햄버거 메뉴)의 표시 상태가
  // 어긋난 채로 남는 경우를 대비해 back 복귀 시점에 항상 강제 재동기화한다.
  syncSidebarResponsiveControls();

  if (sidebarCollapsible) {
    const isOpen = sidebarCollapsible.classList.contains('show');
    sidebarCollapsible.hidden = !isOpen;
  }

  // 스크롤 복구 판정을 .library-header(검색/필터 카드) 하나만으로 하면, 그보다 더 위에
  // 있는 .sidebar-header-wrapper(BookOasis 로고+햄버거)가 화면 밖으로 스크롤됐어도
  // .library-header 자체는 아직 화면 안에 남아있어 복구 조건을 못 만족하는 경우가
  // 있었다(실사용자 리포트로 확인: headerRect.top이 -30~-59까지 나가는데도 복구가
  // 트리거 안 됨). html/body가 overflow:hidden이라도 iOS Safari는 키보드 표시/숨김,
  // 주소창 접힘 등으로 여전히 창을 스크롤시킬 수 있다 - 두 헤더 중 더 위에 있는
  // sidebarHeader 기준으로 판정하고, 임계값도 완화한다.
  const mainContent = document.querySelector('.library-main-content');
  const sidebarHeader = document.querySelector('.sidebar-header-wrapper');
  const rectsOutOfView = [libraryHeader, sidebarHeader].some((el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    return rect.bottom <= 0 || rect.top < -4;
  });
  if (rectsOutOfView) {
    if (mainContent) mainContent.scrollTop = 0;
    // y=0 대신 y=1: iOS Safari는 스크롤 위치가 정확히 0일 때 주소창을 펼치며
    // 페이지 콘텐츠 위에 겹쳐 그리는 버그가 있다.
    window.scrollTo(0, 1);
  }

  requestAnimationFrame(() => {
    window.dispatchEvent(new Event('resize'));
  });
}

function parseMediaTypeFromUrl() {
  try {
    const searchParams = new URLSearchParams(window.location.search);
    const qType = searchParams.get('type') || searchParams.get('media') || searchParams.get('db_type');
    if (qType) {
      const parsed = normalizeMediaType(qType);
      if (parsed) return parsed;
    }
  } catch (e) {}

  try {
    const rawHash = (window.location.hash || '').trim();
    if (rawHash) {
      const cleanHash = rawHash.replace(/^#/, '');
      if (cleanHash.includes('=')) {
        const hashParams = new URLSearchParams(cleanHash);
        const hType = hashParams.get('type') || hashParams.get('media') || hashParams.get('db_type');
        if (hType) {
          const parsed = normalizeMediaType(hType);
          if (parsed) return parsed;
        }
      }
      const lowerHash = cleanHash.toLowerCase();
      if (lowerHash.includes('audiobook') || lowerHash.includes('audio')) return 'audiobook';
      if (lowerHash.includes('adult') || lowerHash.includes('r18')) return 'adult';
      if (lowerHash.includes('general') || lowerHash.includes('book')) return 'general';
    }
  } catch (e) {}

  try {
    const savedType = localStorage.getItem('last_selected_library_type');
    if (savedType) {
      const parsed = normalizeMediaType(savedType);
      if (parsed) return parsed;
    }
  } catch (e) {}

  return null;
}

function parseLibraryIdFromUrl() {
  try {
    const searchParams = new URLSearchParams(window.location.search);
    const qLibrary = searchParams.get('library') || searchParams.get('library_id');
    if (qLibrary) return String(qLibrary).trim();
  } catch (e) {}

  try {
    const rawHash = (window.location.hash || '').trim();
    if (rawHash) {
      const cleanHash = rawHash.replace(/^#/, '');
      if (cleanHash.includes('=')) {
        const hashParams = new URLSearchParams(cleanHash);
        const hLibrary = hashParams.get('library') || hashParams.get('library_id');
        if (hLibrary) return String(hLibrary).trim();
      }
    }
  } catch (e) {}

  try {
    const savedLib = localStorage.getItem('last_selected_library_id');
    if (savedLib) return String(savedLib).trim();
  } catch (e) {}

  return null;
}

function parseKioskParamsFromUrl() {
  try {
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.get('kiosk') !== '1') return null;
    const bookId = (searchParams.get('book') || '').trim();
    const pluginId = (searchParams.get('plugin') || '').trim();
    if (!bookId && !pluginId) return null;
    return {
      bookId,
      pluginId,
      type: normalizeMediaType(searchParams.get('type')) || 'general',
      returnUrl: (searchParams.get('return') || '').trim()
    };
  } catch (e) {
    return null;
  }
}

function injectKioskBackButton(returnUrl) {
  if (!returnUrl || document.getElementById('kiosk-back-btn')) return;
  const btn = document.createElement('button');
  btn.id = 'kiosk-back-btn';
  btn.type = 'button';
  btn.className = 'kiosk-back-btn';
  btn.title = '돌아가기';
  btn.innerHTML = '<i class="fa-solid fa-arrow-left"></i>';
  btn.addEventListener('click', () => {
    window.location.href = returnUrl;
  });
  document.body.appendChild(btn);
}

async function bootKioskMode({ bookId, pluginId, type, returnUrl }) {
  document.body.classList.add('kiosk-mode');
  if (returnUrl) {
    window.__kioskReturnUrl = returnUrl;
    injectKioskBackButton(returnUrl);
  }
  state.currentLibraryType = type;
  await loadInitialSystemSettings();

  if (pluginId) {
    mountCategoryPluginUI(pluginId);
    return;
  }

  try {
    const res = await fetch(`/api/media/books/${encodeURIComponent(bookId)}/reader-info?type=${encodeURIComponent(type)}`);
    const data = await res.json();
    if (!data.success) {
      console.error('[Kiosk] 도서 정보를 불러오지 못했습니다:', data.error);
      return;
    }
    const book = data.book;
    openReader(book.id, book.file_format, book.title, book.pages_read, book.total_pages);
  } catch (e) {
    console.error('[Kiosk] 리더 부팅 실패:', e);
  }
}

function normalizeMediaType(val) {
  if (!val) return null;
  val = String(val).toLowerCase().trim();
  if (['audiobook', 'audio', 'sound'].includes(val)) return 'audiobook';
  if (['video', 'course', 'lecture'].includes(val)) return 'video';
  if (['adult', 'r18'].includes(val)) return 'adult';
  if (['general', 'book', 'books', 'normal'].includes(val)) return 'general';
  return null;
}

// 메인 초기화 함수
async function initTabMediaLibrary() {
  const kioskParams = parseKioskParamsFromUrl();
  if (kioskParams) {
    // 킷오스크 모드: 사이드바/설정 등 라이브러리 UI를 전혀 부팅하지 않고 지정된 책의 리더 또는 플러그인 화면만 즉시 연다.
    await bootKioskMode(kioskParams);
    return;
  }

  initLibraryShellDelegation();
  initScrollableRowNavDelegation();

  if (window.currentUser) {
    state.currentUser = window.currentUser;
    const usernameEl = document.getElementById('session-username-display');
    if (usernameEl) usernameEl.innerText = state.currentUser.username;
    
    if (state.currentUser.role === 'admin') {
      const usersTabBtn = document.getElementById('settings-tab-btn-users');
      if (usersTabBtn) usersTabBtn.style.display = 'block';
      const permissionsTabBtn = document.getElementById('settings-tab-btn-permissions');
      if (permissionsTabBtn) permissionsTabBtn.style.display = 'block';
      
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const onclickAttr = btn.getAttribute('onclick') || '';
        if (onclickAttr.includes("'schedule'") || onclickAttr.includes("'queue'") || onclickAttr.includes("'general'") || onclickAttr.includes("'plugins'") || onclickAttr.includes("'reports'")) {
          btn.style.display = 'block';
        }
      });
    } else {
      document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        const onclickAttr = btn.getAttribute('onclick') || '';
        if (onclickAttr.includes("'schedule'") || onclickAttr.includes("'queue'") || onclickAttr.includes("'plugins'") || onclickAttr.includes("'reports'")) {
          btn.style.display = 'none';
        }
      });
    }
  }

  applyLibraryTypeToggleVisibility();

  document.querySelectorAll('.library-modal').forEach(modal => {
    document.body.appendChild(modal);
  });

  await loadInitialSystemSettings();

  restoreDesktopSidebarState();
  initSidebarInteractions();
  initFloatingFilter();
  initInfiniteScrollObserver();
  initKeyboardListener();
  initLibrarySearchShortcut();
  initLibraryTypeHotkeys();

  window.addEventListener('popstate', (event) => {
    recoverTopCategoryUiAfterBack();

    const viewerModal = document.getElementById('media-viewer-modal');
    let viewerWasOpen = false;
    let handledDetailNavigation = false;
    if (viewerModal && viewerModal.style.display === 'flex') {
      if (!event.state || event.state.view !== 'viewer') {
        closeMediaViewer(false); 
        viewerWasOpen = true;
      } else {
        return;
      }
    }
    
    if (event.state && event.state.view === 'detail') {
      const targetType = event.state.type || state.currentLibraryType || 'general';
      if (state.currentLibraryType !== targetType) {
        applyLibraryTypeButtonState(targetType);
        loadLibraries();
      }
      openBookDetail(null, event.state.series, event.state.libraryId, event.state.repBookId || null, event.state.displayTitle || '');
      handledDetailNavigation = true;
    } else if (window.location.hash.startsWith('#detail')) {
      const restored = decodeDetailParams(window.location.hash);
      if (restored && restored.type && state.currentLibraryType !== restored.type) {
        applyLibraryTypeButtonState(restored.type);
        loadLibraries();
      }
      if (restored && restored.series) {
        openBookDetail(null, restored.series, restored.libraryId || 'all', restored.repBookId || null, restored.displayTitle || '');
        handledDetailNavigation = true;
      }
    }

    if (!handledDetailNavigation) {
      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') {
        goBackToList(false);
      }

      if (event.state && event.state.view === 'category' && event.state.libraryId) {
        if (event.state.type) {
          if (!canAccessLibraryType(event.state.type)) {
            applyLibraryTypeButtonState('general');
          } else {
            applyLibraryTypeButtonState(event.state.type);
          }
          loadLibraries();
        }
        if (state.currentLibraryId !== event.state.libraryId) {
          selectCategory(event.state.libraryId, true);
        }
      } else if (!event.state && (window.location.hash === '' || window.location.hash.startsWith('#library='))) {
        const hashType = parseMediaTypeFromUrl();
        if (hashType) {
          const resolvedType = canAccessLibraryType(hashType) ? hashType : 'general';
          applyLibraryTypeButtonState(resolvedType);
          if (resolvedType === 'video') {
            if (typeof window.loadVideoLibraryView === 'function') window.loadVideoLibraryView();
          } else {
            loadLibraries();
          }
        }
        if (state.currentLibraryId !== 'home') {
          selectCategory('home', true);
        }
      }
    }

    // 브라우저 뒤로가기 클릭 시 상단 헤더(로고+햄버거)가 사라진다는 확실한 재현 리포트를
    // 진단하기 위한 임시 로깅. recoverTopCategoryUiAfterBack()이 맨 앞에서 헤더를 정상
    // 상태로 되돌리는데, 이 popstate 핸들러 뒷부분(loadLibraries/selectCategory 등 비동기
    // 재렌더링 포함)에서 뭔가 그 상태를 다시 망가뜨리는지 확인하기 위해 즉시/지연 두
    // 시점에 헤더 상태를 다시 찍는다.
    const logHeaderStateAfterBack = (tag) => {
      const header = document.querySelector('.sidebar-header-wrapper');
      const sidebar = document.querySelector('.library-sidebar');
      const btn = document.getElementById('btn-sidebar-toggle');
      remoteLog(tag, {
        headerDisplay: header ? getComputedStyle(header).display : 'not-found',
        sidebarDisplay: sidebar ? getComputedStyle(sidebar).display : 'not-found',
        btnDisplay: btn ? getComputedStyle(btn).display : 'not-found',
        headerRect: header ? (() => { const r = header.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) }; })() : null,
        eventState: event.state
      });
    };
    logHeaderStateAfterBack('popstate-header-check-immediate');
    window.setTimeout(() => logHeaderStateAfterBack('popstate-header-check-delayed'), 300);
  });

  const initialHash = window.location.hash || '';
  const isDetailDeepLink = initialHash.startsWith('#detail');
  const targetMediaType = parseMediaTypeFromUrl();

  if (targetMediaType) {
    if (!canAccessLibraryType(targetMediaType)) {
      applyLibraryTypeButtonState('general');
    } else {
      applyLibraryTypeButtonState(targetMediaType);
    }
  } else {
    applyLibraryTypeButtonState(state.currentLibraryType || 'general');
  }

  // 중요: 초기 라이브러리 로드는 타입 적용 후에 수행해야
  // 강력새로고침 시 좌측 메뉴 타입과 상세 타입이 어긋나지 않는다.
  if (state.currentLibraryType === 'video') {
    if (typeof window.loadVideoLibraryView === 'function') await window.loadVideoLibraryView();
  } else {
    await loadLibraries();
  }

  if (isDetailDeepLink) {
    const restoredDetail = decodeDetailParams(initialHash);
    if (restoredDetail && restoredDetail.series) {
      openBookDetail(null, restoredDetail.series, restoredDetail.libraryId || 'all', restoredDetail.repBookId || null, restoredDetail.displayTitle || '');
      return;
    }
  }

  const targetLibraryId = parseLibraryIdFromUrl();
  if (targetLibraryId && targetLibraryId !== 'home') {
    selectCategory(targetLibraryId, true);
  } else {
    selectCategory('home', true);
  }
}

export function selectCategory(id, skipHistory = false) {
  if (id === 'smart_rec' && state.smartRecommendEnabled === false) {
    id = 'home';
  }
  state.currentLibraryId = id;
  try {
    localStorage.setItem('last_selected_library_id', id);
  } catch (e) {}

  document.querySelectorAll('#sidebar-categories .menu-item').forEach(item => {
    item.classList.remove('active');
  });

  let activeItem = document.querySelector(`#sidebar-categories .menu-item[data-category-id="${id}"]`);
  if (!activeItem) {
    activeItem = document.getElementById(`category-${id}`);
  }
  if (activeItem) {
    activeItem.classList.add('active');
    // 활성 카테고리가 숨겨진 영역에 있는 경우 자동 전개
    const sidebarEl = document.getElementById('sidebar-categories');
    if (sidebarEl) applySidebarShowMore(sidebarEl, id);
  }
  state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
  updateCurrentCategoryIndicator(id, activeItem);

  // 정렬 버튼 라벨을 실제 상태(state.currentSortDirection)와 동기화.
  // 이전에는 toggleLibrarySort()를 눌러야만 라벨이 갱신되어, 카테고리 전환 시
  // 실제로는 "최신 추가순" 등으로 정렬된 채로 로드되는데도 버튼엔 항상
  // 초기 HTML의 "가나다 오름차순" 텍스트가 그대로 남아있는 문제가 있었다.
  updateSortButtonUI();

  goBackToList();

  if (id === 'home') {
    // 영상 세션도 오디오북과 동일하게 공용 대시보드(최근 시청/신규 추가)를 그대로 재사용한다.
    // series_repository/reading_progress_repository가 이미 db_type='video' 분기를 갖고 있어
    // 별도 전용 홈 화면 없이도 targetType='video'로 정상 동작한다.
    switchActiveView('dashboard');
    loadDashboardData();
  } else if (id === 'collection') {
    switchActiveView('grid');
    import('./tab_collections.js').then((colls) => {
      colls.renderCollectionsView();
    });
  } else if (id === 'smart_rec') {
    switchActiveView('grid');
    import('./tab_smart_recommend.js').then((mod) => {
      mod.renderSmartRecommendView();
    });
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
  } else if (id.startsWith('plugin_')) {
    const pluginId = id.replace('plugin_', '');
    mountCategoryPluginUI(pluginId);
  } else {
    switchActiveView('grid');
    if (state.currentLibraryType === 'video' && !['history', 'all', 'favorite'].includes(id)) {
      const numericId = parseInt(id, 10);
      if (Number.isFinite(numericId) && typeof window.loadVideoCourseGrid === 'function') {
        window.loadVideoCourseGrid(numericId);
      } else {
        const container = document.getElementById('books-list-container');
        if (container) container.innerHTML = '<div class="loading-spinner">좌측에서 영상 강좌 라이브러리를 선택하거나, 없다면 + 버튼으로 추가해 주세요.</div>';
      }
    } else if (id === 'history') {
      loadReadingHistory();
    } else {
      loadBooksList(false);
    }
  }

  window.dispatchEvent(new CustomEvent('library:category-selected', {
    detail: { id, skipHistory }
  }));
}

// 글로벌 전역 함수 노출
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

document.addEventListener('DOMContentLoaded', () => {
  initTabMediaLibrary();
});
