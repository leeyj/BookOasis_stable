// book_context_menu.js – 도서 우클릭/롱프레스 컨텍스트 메뉴: 열기/닫기, 위치, 터치·iOS 가드, 항목 클릭 분기.
// 항목 표시 규칙은 book_menu/menu_rules.js, 실행 동작은 book_menu/actions.js,
// 플러그인 항목은 book_menu/plugin_items.js에 있다.
import { state } from './state.js';
import { canListen } from './tts_launcher.js';
import * as api from './api.js';
import { hideFloatingMenu, isFloatingMenuOpen, positionMenuAtPoint } from './context_menu_manager.js';
import { clearBookSelection, getSelectedBookTargets, isBookCardSelected } from './book_selection.js';
import { computeBookMenuState } from './book_menu/menu_rules.js';
import { BOOK_MENU_ACTIONS, canDiagnoseFromCurrentBookMenu, canRunLazyScanFromCurrentBookMenu } from './book_menu/actions.js';
import {
  cancelPluginContextMenuLoad,
  clearPluginContextMenuItems,
  loadPluginContextMenuItems,
  runBookContextPluginAction,
} from './book_menu/plugin_items.js';

let currentTargetBook = null;
let contextMenuSuppressUntil = 0;
let dismissPointerGuardUntil = 0;
let longPressTimer = null;
let touchStartX = 0;
let touchStartY = 0;
const touchMoveThreshold = 10;
let menuOpenedByTouchUntil = 0;
let lastEventX = 0;
let lastEventY = 0;
let cachedSearchPlugins = null;
let suppressBookCardClickUntil = 0;

function isIOSDevice() {
  const ua = navigator.userAgent || '';
  const platform = navigator.platform || '';
  const maxTouchPoints = navigator.maxTouchPoints || 0;
  // iPadOS desktop UA 대응: MacIntel + touch
  return /iphone|ipad|ipod/i.test(ua) || (platform === 'MacIntel' && maxTouchPoints > 1);
}

const isIOS = isIOSDevice();

export function invalidateMetadataPluginsCache() {
  cachedSearchPlugins = null;
  // metadata_search.js 등 외부 모듈 캐시 무효화가 필요한 경우 트리거
  if (typeof window.invalidateSearchModalPluginsCache === 'function') {
    window.invalidateSearchModalPluginsCache();
  }
}
window.invalidateMetadataPluginsCache = invalidateMetadataPluginsCache;

function adjustMenuPosition(x, y) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu || bookMenu.style.display === 'none') return;
  positionMenuAtPoint(bookMenu, x, y, { zIndex: 20060 });
}

function clearLongPressTimer() {
  if (longPressTimer) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
}

function isBookContextMenuOpen() {
  return isFloatingMenuOpen('book-context-menu');
}

function hideBookContextMenu({ suppressMs = 0, clearTarget = true } = {}) {
  hideFloatingMenu('book-context-menu');
  if (clearTarget) currentTargetBook = null;
  menuOpenedByTouchUntil = 0;
  cancelPluginContextMenuLoad();
  clearPluginContextMenuItems();
  clearLongPressTimer();
  if (suppressMs > 0) {
    contextMenuSuppressUntil = Date.now() + suppressMs;
    dismissPointerGuardUntil = Date.now() + suppressMs;
  }
}

// iOS Safari: 메뉴가 보이는 동안 마지막으로 표시된 시각을 기록
let menuLastShownAt = 0;

function closeBookContextMenu() {
  hideBookContextMenu({ suppressMs: 0, clearTarget: true });
}

function hasActiveSearchPlugin() {
  return cachedSearchPlugins === null ? null : cachedSearchPlugins.some(p => p.enabled);
}

// menu_rules.js가 계산한 항목 상태를 DOM에 반영한다.
function applyBookMenuState(bookMenu, menuState) {
  const menuTitle = bookMenu.querySelector('.context-menu-title');
  if (menuTitle) menuTitle.textContent = menuState.title;

  Object.entries(menuState.items).forEach(([elementId, item]) => {
    const el = document.getElementById(elementId);
    if (!el) return;
    // Keep the stylesheet's grid layout when showing an item. Setting `block` here
    // overrides `.context-menu-item { display: grid; }` and shifts the row's label.
    if (item.visible !== undefined) el.style.display = item.visible ? '' : 'none';
    if (item.action) el.setAttribute('data-action', item.action);
    if (item.iconClass) {
      const icon = el.querySelector('i');
      if (icon) {
        icon.className = item.iconClass;
        icon.style.color = item.iconColor || '';
      }
    }
    const label = el.querySelector(item.setI18n ? 'span[data-i18n]' : 'span');
    if (!label) return;
    if (item.labelKey) {
      if (item.setI18n) label.dataset.i18n = item.labelKey;
      label.textContent = window.i18n?.t(item.labelKey) || item.labelFallback || label.textContent;
    } else if (item.labelText != null) {
      label.textContent = item.labelText;
    }
  });
}

export function showBookContextMenu(x, y, bookId, bookTitle, isVolumeDetail = false, context = {}) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu) return;

  if (Date.now() < contextMenuSuppressUntil) return;
  menuLastShownAt = Date.now();

  lastEventX = x;
  lastEventY = y;
  const selectedBooks = Array.isArray(context.selectedBooks) ? context.selectedBooks : [];
  const seriesName = String(context.seriesName || (isVolumeDetail ? state.detailSeriesName : '') || '').trim();
  currentTargetBook = { id: bookId, title: bookTitle, isVolumeDetail, ...context, selectedBooks, seriesName };

  applyBookMenuState(bookMenu, computeBookMenuState(currentTargetBook, {
    lazyScanAllowed: canRunLazyScanFromCurrentBookMenu(),
    diagnoseAllowed: canDiagnoseFromCurrentBookMenu(),
    listenable: canListen(String(context.fileFormat || '').toLowerCase()),
    ttsPregenEnabled: !!state.ttsPregenEnabled,
    isVideoLibrary: state.currentLibraryType === 'video',
    metaSearchAvailable: hasActiveSearchPlugin(),
  }));

  // 메타정보 검색 메뉴: 검색 플러그인 목록을 아직 모르면 비동기로 받아 표시 여부를 정한다
  const metaSearchEl = document.getElementById('ctx-search-meta-book');
  if (metaSearchEl && cachedSearchPlugins === null) {
    api.fetchMetadataPlugins().then(data => {
      if (data.success && Array.isArray(data.plugins)) {
        cachedSearchPlugins = data.plugins;
        metaSearchEl.style.display = hasActiveSearchPlugin() ? '' : 'none';
        // 메뉴의 높이가 변경될 수 있으므로 재조정 호출
        adjustMenuPosition(lastEventX, lastEventY);
      }
    }).catch(err => {
      console.error('[BookContextMenu] Failed to check search plugins:', err);
    });
  }

  // 임시 표시하여 실제 메뉴 크기 측정
  positionMenuAtPoint(bookMenu, x, y, { zIndex: 20060 });

  loadPluginContextMenuItems(currentTargetBook, {
    onItemClick: (pluginId, actionId) => triggerBookContextPluginAction(pluginId, actionId),
    onRendered: () => adjustMenuPosition(lastEventX, lastEventY),
  });
}

export function triggerBookContextPluginAction(pluginId, actionId) {
  return runBookContextPluginAction(currentTargetBook, pluginId, actionId);
}

const menuUi = {
  close: closeBookContextMenu,
  get point() { return { x: lastEventX, y: lastEventY }; },
};

function runBookMenuAction(action) {
  const run = BOOK_MENU_ACTIONS[action];
  return run ? run(currentTargetBook, menuUi) : undefined;
}

// 기존 전역/named export 호환 (ui.js, tab_media_library.js, 외부 플러그인 등이 부른다)
export const triggerScanSingleBookAction = () => runBookMenuAction('scan');
export const triggerLazyScanBookAction = () => runBookMenuAction('lazy-scan');
export const triggerSearchMetadataAction = () => runBookMenuAction('search-meta');
export const triggerAddToCollectionAction = () => runBookMenuAction('add-to-collection');
export const triggerAddSeriesToCollectionAction = () => runBookMenuAction('add-series-to-collection');
export const triggerPageTurnAction = () => runBookMenuAction('page-turn');
export const triggerTtsAction = () => runBookMenuAction('tts');
export const triggerTtsPregenAction = () => runBookMenuAction('tts-pregen');
export const triggerMarkAsUnreadAction = () => runBookMenuAction('mark-unread');
export const triggerMarkAsReadAction = () => runBookMenuAction('mark-read');
export { triggerSearchMetadataAction as triggerSearchAladinMetadataAction };

Object.assign(window, {
  triggerScanSingleBookAction,
  triggerLazyScanBookAction,
  triggerSearchMetadataAction,
  triggerSearchAladinMetadataAction: triggerSearchMetadataAction,
  triggerAddToCollectionAction,
  triggerAddSeriesToCollectionAction,
  triggerPageTurnAction,
  triggerTtsAction,
  triggerTtsPregenAction,
  triggerMarkAsUnreadAction,
  triggerMarkAsReadAction,
  triggerBookContextPluginAction,
  showBookContextMenu,
  closeBookContextMenu,
});

function resolveBookContextTarget(event) {
  if (!event || !event.target || typeof event.target.closest !== 'function') return null;

  const card = event.target.closest('.book-card, .vol-grid-card, .volume-card, .plugin-item-card');
  if (!card) return null;
  // 작가별 모음 카드는 여러 시리즈의 집계라 단일 책/시리즈 전제 컨텍스트 메뉴 액션이 성립하지 않음
  if (card.dataset?.isAuthorGroup === '1') return null;

  const rawId = card.getAttribute('data-book-id') || card.dataset?.bookId || card.dataset?.id || '';
  const parsedId = Number.parseInt(String(rawId), 10);
  if (!Number.isFinite(parsedId) || parsedId <= 0) return null;

  const title = (card.getAttribute('data-title') || card.dataset?.title || '').trim() || '도서';
  const isVolumeDetail = card.classList.contains('vol-grid-card') || card.classList.contains('volume-card');
  const markUnreadScope = card.dataset?.markUnreadScope || 'book';
  const seriesName = card.dataset?.seriesName || '';
  const rawLibraryId = card.dataset?.libraryId || '';
  const parsedLibraryId = Number.parseInt(rawLibraryId, 10);
  const libraryId = Number.isFinite(parsedLibraryId) ? parsedLibraryId : null;
  const coverAlign = card.dataset?.coverAlign || 'center';
  const fileFormat = (card.dataset?.fileFormat || '').toLowerCase();
  // 시리즈 집계 카드(여러 권을 대표)는 book_count > 1 - "커버 정렬"은 어느 권을 정렬할지
  // 모호해지므로 이 값으로 개별 권 카드인지 판별한다 (상세뷰 .vol-grid-card/.volume-card는
  // book_count 속성이 없어 기본값 1로 취급 - 애초에 개별 권이라 항상 명확함).
  const bookCount = parseInt(card.dataset?.bookCount, 10) || 1;
  // .book-card(ui.js)는 data-has-progress를 직접 갖고 있지만, 상세뷰의 .vol-grid-card/.volume-card는
  // data-pages-read/data-is-completed만 있으므로 그걸로 동일하게 계산한다.
  const hasProgress = card.dataset?.hasProgress !== undefined
    ? card.dataset.hasProgress === '1'
    : (card.dataset?.isCompleted === '1' || Number(card.dataset?.pagesRead || 0) > 0);
  return { id: parsedId, title, isVolumeDetail, markUnreadScope, seriesName, libraryId, coverAlign, bookCount, fileFormat, hasProgress };
}

// 카드별 개별 바인딩 누락/재렌더 타이밍 이슈가 있어도 우클릭 메뉴를 보장한다.
document.addEventListener('contextmenu', (event) => {
  const target = resolveBookContextTarget(event);
  if (!target) return;

  const card = event.target.closest('.book-card');
  const selected = getSelectedBookTargets();
  let selectedBooks = [];
  if (selected.length > 1 && card && isBookCardSelected(card)) {
    selectedBooks = selected;
  } else if (selected.length > 0 && (!card || !isBookCardSelected(card))) {
    clearBookSelection();
  }

  suppressBookCardClickUntil = Date.now() + 700;

  event.preventDefault();
  event.stopPropagation();
  if (typeof event.stopImmediatePropagation === 'function') {
    event.stopImmediatePropagation();
  }

  showBookContextMenu(event.clientX, event.clientY, target.id, target.title, target.isVolumeDetail, {
    markUnreadScope: target.markUnreadScope,
    seriesName: target.seriesName,
    libraryId: target.libraryId,
    coverAlign: target.coverAlign,
    bookCount: target.bookCount,
    fileFormat: target.fileFormat,
    hasProgress: target.hasProgress,
    selectedBooks,
  });
}, true);

// 우클릭 직후 브라우저/플랫폼별 합성 click으로 상세 열기(onclick)가 발동하는 케이스 차단
document.addEventListener('click', (event) => {
  if (Date.now() >= suppressBookCardClickUntil) return;
  const card = event && event.target && typeof event.target.closest === 'function'
    ? event.target.closest('.book-card, .vol-grid-card, .volume-card, .plugin-item-card')
    : null;
  if (!card) return;

  event.preventDefault();
  event.stopPropagation();
  if (typeof event.stopImmediatePropagation === 'function') {
    event.stopImmediatePropagation();
  }
}, true);

// 도서 우클릭 메뉴 클릭 이외 시 닫기 핸들러 추가
function shouldIgnoreBookMenuDismiss(event) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu || !event || !event.target) return false;
  return bookMenu.contains(event.target);
}

function dismissBookMenuOutside(event, suppressMs = 350) {
  // 롱터치로 메뉴를 연 직후의 동일 터치 종료/지연 클릭 이벤트는 무시합니다.
  if (Date.now() < menuOpenedByTouchUntil && event && (event.type === 'touchend' || event.type === 'click')) {
    return;
  }
  if (shouldIgnoreBookMenuDismiss(event)) return;
  const bookMenu = document.getElementById('book-context-menu');
  if (bookMenu && bookMenu.style.display !== 'none') {
    hideBookContextMenu({ suppressMs });
  }
}

function blockUnderlyingBookCardInteraction(event) {
  if (Date.now() < dismissPointerGuardUntil) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') {
        event.stopImmediatePropagation();
      }
    }
    return true;
  }
  return false;
}

document.addEventListener('pointerdown', (event) => {
  if (blockUnderlyingBookCardInteraction(event)) return;
  if (event.pointerType === 'mouse' && event.button !== 0) return;
  dismissBookMenuOutside(event, 500);
}, true);

// iOS Safari: touchstart 단계에서도 메뉴 외부 터치 시 suppress 설정
// (touchend보다 먼저 발생하므로 롱프레스 타이머 등록 전에 suppress 가드를 세울 수 있음)
if (isIOS) {
  document.addEventListener('touchstart', (event) => {
    if (!isBookContextMenuOpen()) return;
    if (shouldIgnoreBookMenuDismiss(event)) return;
    // 메뉴가 열린 상태에서 외부 터치 → 즉시 suppress 시작
    contextMenuSuppressUntil = Date.now() + 600;
    dismissPointerGuardUntil = Date.now() + 600;
  }, { passive: true });
}

document.addEventListener('touchend', (event) => {
  if (blockUnderlyingBookCardInteraction(event)) return;
  dismissBookMenuOutside(event, 600);
  // iOS Safari: touchend 이후 지연 click 이벤트 방지
}, { passive: false });

document.addEventListener('click', (event) => {
  if (blockUnderlyingBookCardInteraction(event)) return;
  dismissBookMenuOutside(event, 500);
}, true);

// 모바일 터치 기기용 롱 프레스 감지 헬퍼 함수
window.handleLongPressTouchStart = function(event, callback) {
  if (event.touches.length > 1) return;
  
  // iOS Safari: 메뉴가 열려 있거나 suppress 기간이면 롱프레스 타이머 등록 금지
  if (isBookContextMenuOpen()) {
    clearLongPressTimer();
    return;
  }
  if (Date.now() < contextMenuSuppressUntil) {
    clearLongPressTimer();
    return;
  }
  // iOS Safari: 메뉴가 최근 표시됐던 직후에도 추가 suppress (동일 터치 이벤트 여파 방지)
  if (isIOS && (Date.now() - menuLastShownAt < 700)) {
    clearLongPressTimer();
    return;
  }
  
  const touch = event.touches[0];
  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
  
  clearLongPressTimer();
  
  longPressTimer = setTimeout(() => {
    // 타이머 발화 시점에도 suppress 재확인 (iOS의 비동기 이벤트 딜레이 방어)
    if (Date.now() < contextMenuSuppressUntil) {
      longPressTimer = null;
      return;
    }
    if (typeof callback === 'function') {
      // 동일 롱터치의 touchend/click에 의한 즉시 닫힘 방지
      menuOpenedByTouchUntil = Date.now() + 900;
      // 기본 터치 홀드 효과 방지 (돋보기, 텍스트 선택 등 방어)
      if (event.cancelable) {
        event.preventDefault();
      }
      callback(touch.clientX, touch.clientY);
    }
    longPressTimer = null;
  }, 650); // 650ms 길게 누름 감지
};

window.handleLongPressTouchMove = function(event) {
  if (!longPressTimer || isBookContextMenuOpen()) return;
  const touch = event.touches[0];
  const diffX = Math.abs(touch.clientX - touchStartX);
  const diffY = Math.abs(touch.clientY - touchStartY);
  if (diffX > touchMoveThreshold || diffY > touchMoveThreshold) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
};

window.handleLongPressTouchEnd = function(event) {
  clearLongPressTimer();
};

const bookMenuEl = document.getElementById('book-context-menu');
if (bookMenuEl) {
  // iOS Safari: passive:false 로 전파 차단 가능하게 설정
  bookMenuEl.addEventListener('touchstart', (event) => {
    event.stopPropagation();
  }, { passive: false });
  bookMenuEl.addEventListener('touchend', (event) => {
    event.stopPropagation();
  }, { passive: false });
  bookMenuEl.addEventListener('pointerdown', (event) => {
    blockUnderlyingBookCardInteraction(event);
    event.stopPropagation();
  }, true);
  bookMenuEl.addEventListener('click', (event) => {
    blockUnderlyingBookCardInteraction(event);
    const item = event.target.closest('.context-menu-item');
    // "커버 정렬"은 여기서 끝나는 액션이 아니라 다른 서브메뉴(volume-cover-align-context-menu)를
    // 새로 여는 액션이라, 이 억제 타이머를 걸면 700ms 안에 이어지는 다음 카드의 메뉴 클릭이
    // dismissPointerGuardUntil에 막혀 씹혀버린다(서브메뉴가 안 뜨는 증상) - 제외한다.
    if (item && item.getAttribute('data-action') !== 'cover-align') {
      // 메뉴 항목 클릭 시 suppress를 충분히 길게 설정 (iOS 지연 이벤트 방어)
      setTimeout(() => {
        hideBookContextMenu({ suppressMs: 700, clearTarget: false });
      }, 0);
    }
  }, true);
}

if (!window.__bookContextActionBound) {
  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="book-context-action"], [data-role="book-context-close"]')
      : null;
    if (!target) return;

    event.preventDefault();
    const role = target.getAttribute('data-role');
    if (role === 'book-context-close') {
      closeBookContextMenu();
      return;
    }

    return runBookMenuAction(target.getAttribute('data-action'));
  }, true);
  window.__bookContextActionBound = true;
}
