// tab_media_library.js – 도서관 코어 엔트리 조율기
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail, goBackToList } from './modal.js';
import { updateCurrentCategoryIndicator } from './category_indicator.js';
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
import { initSidebarInteractions, restoreDesktopSidebarState } from './sidebar_manager.js';
import { decodeDetailParams } from './url_obfuscator.js';
import './viewer/viewer_padding.js';
import './audio_player.js';

function canAccessAdultLibrary() {
  const user = state.currentUser || window.currentUser || {};
  const role = String(user.role || '').toLowerCase();
  if (role === 'admin') return true;

  const raw = user.has_adult_access;
  return raw === true || raw === 1 || String(raw) === '1';
}

function applyLibraryTypeToggleVisibility() {
  const toggleGroup = document.getElementById('library-type-toggle-group');
  if (!toggleGroup) return;

  const allowAdult = canAccessAdultLibrary();
  toggleGroup.style.display = allowAdult ? 'inline-flex' : 'none';

  if (!allowAdult && state.currentLibraryType === 'adult') {
    state.currentLibraryType = 'general';
  }

  applyLibraryTypeButtonState(state.currentLibraryType || 'general');
}

function applyLibraryTypeButtonState(type) {
  const safeType = (type === 'adult' || type === 'audiobook') ? type : 'general';
  state.currentLibraryType = safeType;
  window.currentLibraryType = safeType;
  document.documentElement.setAttribute('data-library-type', safeType);

  document.querySelectorAll('#library-type-toggle-group .btn-toggle').forEach(btn => btn.classList.remove('active'));
  if (safeType === 'general') {
    document.getElementById('btn-lib-general')?.classList.add('active');
  } else if (safeType === 'adult') {
    document.getElementById('btn-lib-adult')?.classList.add('active');
  } else if (safeType === 'audiobook') {
    document.getElementById('btn-lib-audiobook')?.classList.add('active');
  }
}

function focusLibrarySearchInput() {
  const searchInput = document.getElementById('library-search');
  if (!searchInput) return;
  searchInput.focus();
  searchInput.select();
}

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

  // 사용자 권한 상태를 유지하면서 타입 토글 표시 복구
  applyLibraryTypeToggleVisibility();

  // hidden 속성/클래스가 어긋난 경우를 보정
  if (sidebarCollapsible) {
    const isOpen = sidebarCollapsible.classList.contains('show');
    sidebarCollapsible.hidden = !isOpen;
  }

  // 헤더가 화면 위로 밀린 경우 상단 기준으로 스크롤 보정
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

let searchShortcutConfig = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };

export function applySearchShortcutSetting() {
  const savedRaw = localStorage.getItem('settings_search_shortcut');
  if (savedRaw) {
    try {
      searchShortcutConfig = JSON.parse(savedRaw);
    } catch (e) {
      console.error('[Shortcut] 단축키 파싱 실패:', e);
    }
  } else {
    searchShortcutConfig = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };
  }

  // 🌟 검색창 인풋의 placeholder 및 title 동적 갱신 연동
  const searchInput = document.getElementById('library-search');
  if (searchInput) {
    const displayShortcut = searchShortcutConfig ? searchShortcutConfig.display : 'Alt + `';
    
    // i18n 다국어 포맷 라이브러리와 연동
    if (window.i18n && typeof window.i18n.t === 'function') {
      const translatedPlaceholder = window.i18n.t('header.search_placeholder', { shortcut: displayShortcut });
      searchInput.setAttribute('placeholder', translatedPlaceholder);
      
      const titleLabel = window.i18n.t('settings.search_shortcut_label') || '검색 단축키 설정';
      searchInput.setAttribute('title', `${titleLabel}: ${displayShortcut}`);
    } else {
      // i18n 번역 리소스 파싱 전 폴백
      searchInput.setAttribute('placeholder', `제목,시리즈,작가 검색...... (단축키: ${displayShortcut})`);
      searchInput.setAttribute('title', `검색 단축키: ${displayShortcut}`);
    }
  }
}
window.applySearchShortcutSetting = applySearchShortcutSetting;

function initLibrarySearchShortcut() {
  if (window.__librarySearchShortcutBound) return;

  applySearchShortcutSetting();

  // 🌟 다국어 팩 전환 시 동적 placeholder 재바인딩
  window.addEventListener('bookoasis_language_changed', () => {
    applySearchShortcutSetting();
  });

  document.addEventListener('keydown', (e) => {
    // 사용자가 현재 설정(일반설정 탭 단축키 입력 등)을 기록 중일 때는 단축키 오발동 차단
    if (document.getElementById('btn-record-shortcut')?.innerText === '입력 대기...') return;

    // 🌟 스코프 유실 방지를 위해 keydown 감지 시점에 LocalStorage 데이터 실시간 로드
    const savedRaw = localStorage.getItem('settings_search_shortcut');
    let currentShortcut = null;
    try {
      currentShortcut = savedRaw ? JSON.parse(savedRaw) : null;
    } catch (err) {
      currentShortcut = null;
    }

    if (!currentShortcut) {
      currentShortcut = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote' };
    }

    // 단축키 매칭 체크
    const isCtrlMatch = e.ctrlKey === currentShortcut.ctrlKey;
    const isAltMatch = e.altKey === currentShortcut.altKey;
    const isShiftMatch = e.shiftKey === currentShortcut.shiftKey;
    const isMetaMatch = e.metaKey === currentShortcut.metaKey;

    const key = String(e.key || '').toLowerCase();
    const targetKey = String(currentShortcut.key || '').toLowerCase();

    const isKeyMatch = (key === targetKey || e.code === currentShortcut.code);

    if (isCtrlMatch && isAltMatch && isShiftMatch && isMetaMatch && isKeyMatch) {
      e.preventDefault();
      focusLibrarySearchInput();
    }
  });

  window.__librarySearchShortcutBound = true;
}

function initLibraryTypeHotkeys() {
  if (window.__libraryTypeHotkeysBound) return;

  document.addEventListener('keydown', async (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey) return;

    const activeTag = (document.activeElement && document.activeElement.tagName)
      ? document.activeElement.tagName.toUpperCase()
      : '';
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable)) {
      return;
    }

    const viewerModal = document.getElementById('media-viewer-modal');
    if (viewerModal && viewerModal.style.display === 'flex') {
      return;
    }

    const key = String(e.key || '').trim();
    if (!['1', '2', '3'].includes(key)) return;

    e.preventDefault();
    if (key === '1') {
      await switchLibraryType('general');
      return;
    }
    if (key === '2') {
      await switchLibraryType('adult');
      return;
    }
    await switchLibraryType('audiobook');
  });

  window.__libraryTypeHotkeysBound = true;
}

// 초기화 함수 분리
async function initTabMediaLibrary() {
  initLibraryShellDelegation();
  initDashboardNavDelegation();
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
        if (onclickAttr.includes("'schedule'") || onclickAttr.includes("'queue'") || onclickAttr.includes("'plugins'") || onclickAttr.includes("'reports'")) {
          btn.style.display = 'none';
        }
      });
    }
  }

  applyLibraryTypeToggleVisibility();

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
  initSidebarInteractions();

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

  const initialHash = window.location.hash || '';
  const isDetailDeepLink = initialHash.startsWith('#detail');

  // URL 딥링크 미디어 탭 파싱 (예: #library=home&type=audiobook)
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

  // 상세 딥링크는 진입 탭/세션 여부와 무관하게 복원 허용

  const initialLibraryId = parseLibraryIdFromUrl() || 'home';
  state.currentLibraryId = initialLibraryId;
  loadLibraries();

  if (isDetailDeepLink) {
    const restored = decodeDetailParams(initialHash);
    if (restored && restored.series) {
      console.log('[History] 상세 딥링크 복원:', restored.series);
      openBookDetail(null, restored.series, restored.libraryId || 'all', restored.repBookId || null, restored.displayTitle || '');
    } else {
      selectCategory(initialLibraryId, true);
    }
  } else {
    selectCategory(initialLibraryId, true);
    const curType = state.currentLibraryType || 'general';
    if (!window.location.hash.startsWith('#detail') && !window.location.hash.startsWith('#viewer')) {
      history.replaceState({ view: 'category', libraryId: state.currentLibraryId || 'home', type: curType }, '', `#library=${state.currentLibraryId || 'home'}&type=${curType}`);
    }
  }
  updateSortButtonUI();

  // 플로팅 필터 모달 초기화
  initFloatingFilter();

  // IntersectionObserver 기반 무한 스크롤 초기화
  initInfiniteScrollObserver();

  // 키보드 단축키
  initKeyboardListener();
  initLibrarySearchShortcut();
  initLibraryTypeHotkeys();


  // 브라우저 및 모바일 하단 OS 뒤로가기/앞으로가기 버튼 감지하여 뷰 라우팅 및 레이아웃 복원
  window.addEventListener('popstate', (event) => {
    console.log('[History] popstate 이벤트 감지:', window.location.hash, event.state);
    
    // 1. 현재 뷰어가 열려있다면 무조건 닫기 (목적지가 뷰어가 아닐 때만)
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
    
    // 2. 목적지 상태가 상세 뷰(detail)인 경우
    if (event.state && event.state.view === 'detail') {
      openBookDetail(null, event.state.series, event.state.libraryId, event.state.repBookId || null, event.state.displayTitle || '');
      handledDetailNavigation = true;
    } else if (window.location.hash.startsWith('#detail')) {
      const restored = decodeDetailParams(window.location.hash);
      if (restored && restored.series) {
        openBookDetail(null, restored.series, restored.libraryId || 'all', restored.repBookId || null, restored.displayTitle || '');
        handledDetailNavigation = true;
      }
    }

    let landedOnCategoryLikeView = false;
    if (!handledDetailNavigation) {
      // 3. 목적지가 목록(카테고리) 뷰인 경우 (현재 상세 뷰가 떠 있다면 먼저 닫음)
      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') {
        goBackToList(false);
      }

      if (event.state && event.state.view === 'category' && event.state.libraryId) {
        landedOnCategoryLikeView = true;
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
        landedOnCategoryLikeView = true;
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

    // 4. 모바일 백 버튼으로 뷰어 종료 시 뷰포트 레이아웃 및 상단 카테고리 헤더 리플로우 보장
    if (viewerWasOpen) {
      document.body.style.cssText = '';
      document.documentElement.style.cssText = '';
      const savedPos = (state.scrollPositions && (state.scrollPositions['last_pos'] ?? state.scrollPositions[state.currentLibraryId])) || 0;

      // 주 스크롤 컨테이너는 .library-main-content 이므로,
      // window/document 스크롤 복원은 상단 카테고리 영역을 화면 밖으로 밀어낼 수 있다.
      const mainContent = document.querySelector('.library-main-content');
      if (mainContent) {
        mainContent.scrollTop = savedPos;
      }

      // 상단 카테고리/헤더가 항상 보이도록 문서 스크롤은 0으로 고정
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    }

    // 모바일 뒤로가기 이후 상단 카테고리/검색 헤더 표시 복구
    recoverTopCategoryUiAfterBack();

    // 일부 모바일 브라우저는 popstate 직후 비동기 렌더에서 display/hidden 상태를 다시 덮어쓴다.
    // 카테고리 뷰 복귀로 판별된 경우 한 번 더 지연 복구를 수행한다.
    if (landedOnCategoryLikeView) {
      setTimeout(() => {
        recoverTopCategoryUiAfterBack();
      }, 120);
    }
  });
}


if (window.i18nReady) {
  initTabMediaLibrary();
} else {
  document.addEventListener('i18nReady', initTabMediaLibrary);
}

// 라이브러리 타입 스위칭 (일반/성인/오디오북)
export async function switchLibraryType(type) {
  if (type === 'adult' && !canAccessAdultLibrary()) {
    if (typeof showToast === 'function') {
      showToast('성인 도서 접근 권한이 없어 이동할 수 없습니다.', 'warning');
    }
    return;
  }

  window.scrollTo(0, 0);
  applyLibraryTypeButtonState(type);

  // 주소창 URL 해시 갱신 (예: #library=home&type=audiobook)
  if (!window.location.hash.startsWith('#detail') && !window.location.hash.startsWith('#viewer')) {
    const curLibId = state.currentLibraryId || 'home';
    const newHash = `#library=${curLibId}&type=${type}`;
    try {
      history.replaceState({ view: 'category', libraryId: curLibId, type: type }, '', newHash);
    } catch (e) {}
  }

  await loadInitialSystemSettings();
  loadLibraries();
  selectCategory('home', true);
}

async function mountCategoryPluginUI(pluginId) {
  const container = document.getElementById('library-plugin-custom-view');
  if (!container) return;

  switchActiveView('plugin_custom');
  container.innerHTML = '<div style="padding: 2rem; text-align: center; color: #94a3b8;"><i class="fa-solid fa-spinner fa-spin fa-2x"></i><p style="margin-top: 0.8rem;">플러그인 UI 로딩 중...</p></div>';

  try {
    const res = await fetch(`/api/media/plugins/${pluginId}/ui`);
    if (!res.ok) throw new Error('UI bundle not found');
    const data = await res.json();
    if (!data.success || !data.bundle) throw new Error(data.error || 'Failed to load bundle');

    const bundle = data.bundle;
    let html = bundle.html || '<p>UI가 정의되지 않았습니다.</p>';

    if (bundle.css) {
      html = `<style>${bundle.css}</style>` + html;
    }

    container.innerHTML = html;

    if (bundle.js) {
      const scriptEl = document.createElement('script');
      scriptEl.textContent = bundle.js;
      container.appendChild(scriptEl);
    }
  } catch (e) {
    container.innerHTML = `<div style="padding: 2rem; text-align: center; color: #ef4444;"><i class="fa-solid fa-triangle-exclamation fa-2x"></i><p style="margin-top: 0.8rem;">플러그인 화면을 불러오지 못했습니다: ${e.message}</p></div>`;
  }
}

// 카테고리 선택 처리
export function selectCategory(rawId, skipHistory = false) {
  const id = String(rawId || '');
  window.scrollTo(0, 0);
  state.currentLibraryId = id;
  const curType = state.currentLibraryType || 'general';
  window.currentLibraryType = curType;
  
  // 브라우저 히스토리에 카테고리 이동 기록 남기기 (SPA 뒤로가기 지원)
  if (!skipHistory) {
    history.pushState({ view: 'category', libraryId: id, type: curType }, '', `#library=${id}&type=${curType}`);
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
  state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
  updateCurrentCategoryIndicator(id, activeItem);

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

  // 카테고리 전환 완료 이벤트 발행 (사이드바/기타 UI 모듈과 느슨한 결합 유지)
  window.dispatchEvent(new CustomEvent('library:category-selected', {
    detail: { id, skipHistory }
  }));
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
// ※ markAsCompleted는 viewer.js의 통합 버전을 사용해야 epub/txt 포맷도 정상 동작함
//   (viewer_comic.js의 버전으로 덮어쓰면 epub/txt에서 comic 페이지 카운트 조건에 걸려 미동작)
import { toggleComicOverlay } from './viewer_comic.js';
window.toggleComicOverlay = toggleComicOverlay;

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

export async function handleLibrarySearchKeydown(event) {
  if (event.key !== 'Enter' || event.isComposing) return;
  event.preventDefault();
  event.stopPropagation();

  const searchInput = event.currentTarget;
  const query = searchInput.value.trim();
  if (!query) return;

  state.searchQuery = query.toLowerCase();
  if (state.currentLibraryId === 'home') {
    selectCategory('all');
  } else {
    await loadBooksList(false);
  }
}
window.handleLibrarySearchKeydown = handleLibrarySearchKeydown;

export { loadLibraries };
