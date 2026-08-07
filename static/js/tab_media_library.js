// tab_media_library.js – 도서관 코어 엔트리 오케스트레이터 및 메인 라우터
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail, goBackToList } from './modal.js';
import { updateCurrentCategoryIndicator } from './category_indicator.js';
import { openReader, closeMediaViewer, toggleFullscreenViewer, setComicFitMode, changeFontSize, toggleReaderTheme, initKeyboardListener, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, epubPrevPage, epubNextPage, prevTxtPage, nextTxtPage } from './viewer.js';
import { switchActiveView } from './view_manager.js';

// category.js CRUD 임포트
import { loadLibraries, triggerAddLibrary, triggerEditLibrary, triggerDeleteLibrary, closeLibraryModal, submitLibraryForm, triggerScanLibrary, triggerScanLibraryCovers, triggerCancelScanLibrary } from './category.js';

// scheduler.js 임포트
import { loadLibrarySchedules, saveLibrarySchedule, runLibraryScanNow } from './scheduler.js';

// 서브 모듈 임포트
import { loadDashboardData, scrollDashboardRow, loadDashboardPlugins, switchPluginsViewTab } from './dashboard.js';
import { initInfiniteScrollObserver } from './infinite_scroll.js';
import { showBookContextMenu, triggerScanSingleBookAction, triggerSearchAladinMetadataAction, triggerMarkAsUnreadAction } from './book_context_menu.js';
import { openMetadataSearchModal, closeMetadataSearchModal, performMetadataSearch } from './metadata_search.js';

// book_list.js 임포트
import { loadBooksList, loadReadingHistory, filterBooks, toggleLibrarySort, resumeSeries, updateSortButtonUI } from './book_list.js';

// plugin_custom_view.js 임포트
import { mountCategoryPluginUI } from './plugin_custom_view.js';
import { switchSettingsTab, loadInitialSystemSettings, loadGeneralSettings, submitGeneralSettings, initReportsTab, loadReportList, loadReportDetail, loadViewerSettings, submitViewerSettings } from './settings_tab.js';

// 장르/태그 및 사이드바 제어 모듈
import { initFloatingFilter, toggleFilterModal } from './genre_tag_filter.js';
import { initSidebarInteractions, restoreDesktopSidebarState, toggleDesktopSidebar } from './sidebar_manager.js';
import { decodeDetailParams } from './url_obfuscator.js';

// 모듈화로 분리한 미디어 타입 토글 및 검색 단축키 제어부 임포트
import { canAccessAdultLibrary, applyLibraryTypeToggleVisibility, applyLibraryTypeButtonState, switchLibraryType } from './library_type_toggle.js';
import { focusLibrarySearchInput, applySearchShortcutSetting, initLibrarySearchShortcut, handleLibrarySearchAction, handleLibrarySearchKeydown, initLibraryTypeHotkeys } from './search_shortcut_manager.js';

import './viewer/viewer_padding.js';
import './audio_player.js';

function initLibraryShellDelegation() {
  if (window.__libraryShellDelegationBound) return;

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="sidebar-category-static"], [data-role="desktop-sidebar-toggle"], [data-role="library-search-action"], [data-role="library-open-filter"], [data-role="library-sort-toggle"], [data-role="library-type-toggle"], [data-role="library-filter-reset"], [data-role="detail-back-to-list"]')
      : null;
    if (!target) return;

    event.preventDefault();

    const role = target.getAttribute('data-role');
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

function initDashboardNavDelegation() {
  if (window.__dashboardNavDelegationBound) return;

  document.addEventListener('click', (event) => {
    const btn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="dashboard-row-nav"]')
      : null;
    if (!btn) return;

    event.preventDefault();
    const row = btn.getAttribute('data-row') || 'history';
    const dir = btn.getAttribute('data-dir') || 'left';
    scrollDashboardRow(row, dir);
  }, true);

  window.__dashboardNavDelegationBound = true;
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

  if (sidebarCollapsible) {
    const isOpen = sidebarCollapsible.classList.contains('show');
    sidebarCollapsible.hidden = !isOpen;
  }

  const mainContent = document.querySelector('.library-main-content');
  if (libraryHeader && mainContent) {
    const headerRect = libraryHeader.getBoundingClientRect();
    if (headerRect.bottom <= 0 || headerRect.top < -12) {
      mainContent.scrollTop = 0;
      window.scrollTo(0, 0);
    }
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

function normalizeMediaType(val) {
  if (!val) return null;
  val = String(val).toLowerCase().trim();
  if (['audiobook', 'audio', 'sound'].includes(val)) return 'audiobook';
  if (['adult', 'r18'].includes(val)) return 'adult';
  if (['general', 'book', 'books', 'normal'].includes(val)) return 'general';
  return null;
}

// 메인 초기화 함수
async function initTabMediaLibrary() {
  initLibraryShellDelegation();
  initDashboardNavDelegation();

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
          if (event.state.type === 'adult' && !canAccessAdultLibrary()) {
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
          if (hashType === 'adult' && !canAccessAdultLibrary()) {
            applyLibraryTypeButtonState('general');
          } else {
            applyLibraryTypeButtonState(hashType);
          }
          loadLibraries();
        }
        if (state.currentLibraryId !== 'home') {
          selectCategory('home', true);
        }
      }
    }
  });

  await loadLibraries();

  const initialHash = window.location.hash || '';
  const isDetailDeepLink = initialHash.startsWith('#detail');
  const targetMediaType = parseMediaTypeFromUrl();

  if (targetMediaType) {
    if (targetMediaType === 'adult' && !canAccessAdultLibrary()) {
      applyLibraryTypeButtonState('general');
    } else {
      applyLibraryTypeButtonState(targetMediaType);
    }
  } else {
    applyLibraryTypeButtonState(state.currentLibraryType || 'general');
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
  }
  state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
  updateCurrentCategoryIndicator(id, activeItem);

  goBackToList();

  if (id === 'home') {
    switchActiveView('dashboard');
    loadDashboardData();
  } else if (id === 'collection') {
    switchActiveView('grid');
    import('./tab_collections.js').then((colls) => {
      colls.renderCollectionsView();
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
    if (id === 'history') {
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

document.addEventListener('DOMContentLoaded', () => {
  initTabMediaLibrary();
});
