// book_context_menu.js – 도서 우클릭 단독 스캔 컨텍스트 메뉴 제어 모듈
import { state } from './state.js';
import * as api from './api.js?v=20260809-unread-series-v3';
import { openBookDetail } from './modal.js';
import { loadBooksList, loadReadingHistory } from './book_list.js?v=20260809-unread-series-v3';
import { loadDashboardData } from './dashboard.js?v=20260809-unread-series-v3';
import { hideFloatingMenu, isFloatingMenuOpen, positionMenuAtPoint } from './context_menu_manager.js';

let currentTargetBook = null;
let contextMenuSuppressUntil = 0;
let dismissPointerGuardUntil = 0;
let longPressTimer = null;
let touchStartX = 0;
let touchStartY = 0;
const touchMoveThreshold = 10;
let contextMenuLoadSeq = 0;
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

function getPluginAccentColor(pluginId) {
  const text = String(pluginId || 'plugin');
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 72% 60%)`;
}

function buildCurrentContextPayload() {
  if (!currentTargetBook) return {};
  return {
    book_id: currentTargetBook.id,
    book_title: currentTargetBook.title,
    is_volume_detail: !!currentTargetBook.isVolumeDetail,
    library_id: state.currentLibraryId,
  };
}

function clearPluginContextMenuItems() {
  const bookMenu = document.getElementById('book-context-menu');
  const listEl = bookMenu ? bookMenu.querySelector('.context-menu-list') : null;
  if (!listEl) return;
  listEl.querySelectorAll('.plugin-context-menu-item, .plugin-context-menu-group-title, .plugin-context-menu-separator').forEach((el) => el.remove());
}

function renderPluginContextMenuItems(items) {
  const bookMenu = document.getElementById('book-context-menu');
  const listEl = bookMenu ? bookMenu.querySelector('.context-menu-list') : null;
  if (!listEl) return;

  clearPluginContextMenuItems();

  if (!Array.isArray(items) || items.length === 0) return;

  const closeItem = listEl.querySelector('.context-menu-close-item');
  const groups = new Map();
  items.forEach((item) => {
    const pluginId = String(item.plugin_id || '').trim();
    if (!pluginId) return;
    const pluginName = String(item.plugin_name || pluginId).trim();
    if (!groups.has(pluginId)) {
      groups.set(pluginId, { pluginId, pluginName, items: [] });
    }
    groups.get(pluginId).items.push(item);
  });

  const groupList = Array.from(groups.values());
  groupList.forEach((group, groupIdx) => {
    const accentColor = getPluginAccentColor(group.pluginId);

    if (groupIdx > 0) {
      const sep = document.createElement('li');
      sep.className = 'plugin-context-menu-separator';
      if (closeItem) listEl.insertBefore(sep, closeItem);
      else listEl.appendChild(sep);
    }

    const titleEl = document.createElement('li');
    titleEl.className = 'plugin-context-menu-group-title';
    titleEl.style.setProperty('--plugin-accent', accentColor);
    titleEl.textContent = group.pluginName;
    if (closeItem) listEl.insertBefore(titleEl, closeItem);
    else listEl.appendChild(titleEl);

    group.items.forEach((item) => {
      const pluginId = String(item.plugin_id || '').trim();
      const actionId = String(item.id || '').trim();
      const label = String(item.label || '').trim();
      const iconClass = String(item.icon || 'fa-solid fa-puzzle-piece').trim();
      if (!pluginId || !actionId || !label) return;

      const li = document.createElement('li');
      li.className = 'context-menu-item plugin-context-menu-item';
      li.dataset.pluginId = pluginId;
      li.dataset.actionId = actionId;
      li.style.setProperty('--plugin-accent', accentColor);
      li.innerHTML = `<i class="${iconClass} plugin-context-menu-icon"></i> <span class="plugin-context-menu-label">${label}</span>`;
      li.addEventListener('click', () => {
        triggerBookContextPluginAction(pluginId, actionId);
      });

      if (closeItem) {
        listEl.insertBefore(li, closeItem);
      } else {
        listEl.appendChild(li);
      }
    });
  });

  // 플러그인 항목 렌더링 후 동적으로 확장된 메뉴 높이를 기반으로 위치 재보정
  adjustMenuPosition(lastEventX, lastEventY);
}

function adjustMenuPosition(x, y) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu || bookMenu.style.display === 'none') return;
  positionMenuAtPoint(bookMenu, x, y, { zIndex: 20060 });
}

async function loadPluginContextMenuItems() {
  if (!currentTargetBook || !currentTargetBook.id) {
    clearPluginContextMenuItems();
    return;
  }

  const seq = ++contextMenuLoadSeq;
  try {
    const payload = buildCurrentContextPayload();
    const res = await api.fetchBookContextMenuPluginItems(state.currentLibraryType, payload);
    if (seq !== contextMenuLoadSeq) return;

    if (res && res.success) {
      renderPluginContextMenuItems(res.items || []);
      return;
    }

    clearPluginContextMenuItems();
  } catch (err) {
    console.error('컨텍스트 메뉴 플러그인 항목 조회 실패:', err);
    if (seq === contextMenuLoadSeq) {
      clearPluginContextMenuItems();
    }
  }
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
  contextMenuLoadSeq += 1;
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

export function showBookContextMenu(x, y, bookId, bookTitle, isVolumeDetail = false, context = {}) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu) return;

  if (Date.now() < contextMenuSuppressUntil) return;
  menuLastShownAt = Date.now();
  
  lastEventX = x;
  lastEventY = y;
  const seriesName = String(context.seriesName || (isVolumeDetail ? state.detailSeriesName : '') || '').trim();
  currentTargetBook = { id: bookId, title: bookTitle, isVolumeDetail, ...context, seriesName };

  // "페이지 넘김으로 보기(실험적)"는 이미지 기반 만화(zip/cbz)에서만 의미가 있음
  const pageTurnItem = document.getElementById('ctx-page-turn-book');
  if (pageTurnItem) {
    const fmt = String(context.fileFormat || '').toLowerCase();
    pageTurnItem.style.display = (fmt === 'zip' || fmt === 'cbz') ? '' : 'none';
  }

  const addSeriesItem = document.getElementById('ctx-add-series-to-collection');
  if (addSeriesItem) {
    addSeriesItem.style.display = seriesName ? '' : 'none';
  }

  // "커버 정렬"은 개별 권(볼륨) 카드에서만 의미가 있음 (시리즈 카드는 어느 권을 정렬할지 모호함)
  const coverAlignItem = document.getElementById('ctx-cover-align-book');
  if (coverAlignItem) {
    coverAlignItem.style.display = isVolumeDetail ? '' : 'none';
  }

  const unreadLabel = document.querySelector('#ctx-unread-book span');
  if (unreadLabel) {
    unreadLabel.textContent = context.markUnreadScope === 'series'
      ? (window.i18n?.t('context_menu.mark_series_as_unread') || '이 시리즈 전체를 읽지 않은 상태로 변경 (0%)')
      : (window.i18n?.t('context_menu.mark_as_unread') || '읽지 않은 상태로 변경 (0%)');
  }
  
  // 메타정보 검색 메뉴의 플러그인 활성 상태 동적 검사
  const metaSearchEl = document.getElementById('ctx-search-meta-book');
  if (metaSearchEl) {
    if (cachedSearchPlugins === null) {
      // 1. 아직 로드되지 않은 경우 비동기 로드 시도
      api.fetchMetadataPlugins().then(data => {
        if (data.success && Array.isArray(data.plugins)) {
          cachedSearchPlugins = data.plugins;
          const hasActive = cachedSearchPlugins.some(p => p.enabled);
          metaSearchEl.style.display = hasActive ? 'block' : 'none';
          // 메뉴의 높이가 변경될 수 있으므로 재조정 호출
          adjustMenuPosition(lastEventX, lastEventY);
        }
      }).catch(err => {
        console.error('[BookContextMenu] Failed to check search plugins:', err);
      });
    } else {
      // 2. 캐시된 목록 기준 판단
      const hasActive = cachedSearchPlugins.some(p => p.enabled);
      metaSearchEl.style.display = hasActive ? 'block' : 'none';
    }
  }

  // 임시 표시하여 실제 메뉴 크기 측정
  positionMenuAtPoint(bookMenu, x, y, { zIndex: 20060 });
  
  loadPluginContextMenuItems();
}

export async function triggerBookContextPluginAction(pluginId, actionId) {
  if (!pluginId || !actionId) return;
  if (!currentTargetBook || !currentTargetBook.id) return;

  let pendingPopup = null;
  try {
    // 팝업 차단을 피하려면 비동기 응답을 기다리기 전, 사용자 클릭 시점에 미리 창을 열어둬야
    // 한다(open_url이 있는 플러그인 액션 전용 placeholder — 없는 액션이면 아래에서 바로 닫음).
    pendingPopup = window.open('', '_blank');
    if (pendingPopup) {
      pendingPopup.document.write('<!doctype html><title>작업 처리 중...</title><p>플러그인 작업을 처리하는 중입니다.</p>');
      pendingPopup.document.close();
    }

    const payload = buildCurrentContextPayload();
    console.log('[BookContextMenu] run plugin action', {
      pluginId,
      actionId,
      payload,
    });
    const res = await api.runBookContextMenuPluginAction(
      state.currentLibraryType,
      pluginId,
      actionId,
      payload
    );

    console.log('[BookContextMenu] action response', res);

    const vm = await import('./view_manager.js');
    if (!res || !res.success) {
      if (pendingPopup) {
        pendingPopup.close();
      }
      vm.showToast(res && res.error ? res.error : '플러그인 작업 실행에 실패했습니다.', 'error');
      return;
    }

    if (res.open_url) {
      if (pendingPopup) {
        pendingPopup.location.href = res.open_url;
      } else {
        window.open(res.open_url, '_blank');
      }
    } else if (pendingPopup) {
      // 액션이 성공했지만 이동할 URL이 없는 경우(YAML 저장 등) 미리 열어둔
      // 플레이스홀더 팝업을 그대로 두면 about:blank(정확히는 "검색 중..." 문구)로 남는다.
      pendingPopup.close();
    }

    if (res.message) {
      vm.showToast(res.message, 'success');
    }
  } catch (err) {
    if (pendingPopup) {
      pendingPopup.close();
    }
    console.error('플러그인 컨텍스트 메뉴 액션 실행 실패:', err);
    const vm = await import('./view_manager.js');
    vm.showToast('플러그인 작업 실행 중 오류가 발생했습니다.', 'error');
  }
}

export function triggerPageTurnAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const url = '/experimental/page-turn?book_id=' + encodeURIComponent(currentTargetBook.id) +
    '&db_type=' + encodeURIComponent(state.currentLibraryType || 'general') + '&format=comic';
  window.open(url, '_blank');
  closeBookContextMenu();
}
window.triggerPageTurnAction = triggerPageTurnAction;

export async function triggerScanSingleBookAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title, isVolumeDetail } = currentTargetBook;
  
  import('./view_manager.js').then(async (vm) => {
    vm.showToast(`"${title}" 스캔 중...`, 'info');
    try {
      const res = await api.scanSingleBook(state.currentLibraryType, id);
      if (res.success) {
        vm.showToast(res.message, 'success');
        
        const newCoverName = res.cover_image;
        if (!newCoverName) return;

        // 캐시 버스팅을 위한 URL 타임스탬프 생성
        const cacheBustedCoverUrl = `/covers/${newCoverName}?t=${Date.now()}`;

        if (isVolumeDetail) {
          // 상세 뷰: 해당 volume-card의 img 갱신
          // oncontextmenu 식에 b.id 값을 인자로 보냈음
          const volCards = document.querySelectorAll('.volume-card');
          volCards.forEach(card => {
            // 인라인 oncontextmenu 식 문자열 분석 혹은 innerHTML 내 openReader 호출 등으로 매칭 탐색
            if (card.outerHTML.includes(`openReader(${id},`) || card.outerHTML.includes(`showBookContextMenu(event.clientX, event.clientY, ${id},`)) {
              const img = card.querySelector('.volume-thumb');
              if (img) {
                img.src = cacheBustedCoverUrl;
                console.log(`[CacheBusting] 상세 뷰 단행본 표지 교체 성공 (ID: ${id})`);
              }
            }
          });
        } else {
          // 그리드 뷰: data-book-id 기반으로 매칭되는 카드 찾기
          const targetCard = document.querySelector(`.book-card[data-book-id="${id}"]`);
          if (targetCard) {
            const img = targetCard.querySelector('.book-card-cover img');
            if (img) {
              img.src = cacheBustedCoverUrl;
              console.log(`[CacheBusting] 그리드 뷰 책 표지 교체 성공 (ID: ${id})`);
            }
          }
        }
      } else {
        vm.showToast(`스캔 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('단일 도서 스캔 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

window.triggerScanSingleBookAction = triggerScanSingleBookAction;

export function triggerSearchMetadataAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title } = currentTargetBook;
  
  if (typeof window.openMetadataSearchModal === 'function') {
    window.openMetadataSearchModal(id, title);
  } else if (typeof window.openAladinSearchModal === 'function') {
    window.openAladinSearchModal(id, title);
  } else {
    console.error('[Global Trigger ERROR] window.openMetadataSearchModal 함수가 바인딩되지 않았습니다.');
  }
}
window.triggerSearchMetadataAction = triggerSearchMetadataAction;
window.triggerSearchAladinMetadataAction = triggerSearchMetadataAction;

function removeUnreadTargetCards({ id, isSeriesScope, seriesName, libraryId }) {
  if (state.currentLibraryId !== 'home' && state.currentLibraryId !== 'history') return;

  const historyContainer = state.currentLibraryId === 'home'
    ? document.getElementById('dashboard-history-row')
    : document.getElementById('books-list-container');
  if (!historyContainer) return;

  historyContainer.querySelectorAll('.book-card').forEach((card) => {
    const sameBook = String(card.dataset.bookId || '') === String(id);
    const sameSeries = isSeriesScope
      && String(card.dataset.seriesName || '') === String(seriesName || '')
      && String(card.dataset.libraryId || '') === String(libraryId ?? '');
    if (sameBook || sameSeries) card.remove();
  });
}

export async function triggerMarkAsUnreadAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title, markUnreadScope, seriesName, libraryId } = currentTargetBook;
  const isSeriesScope = markUnreadScope === 'series';

  import('./view_manager.js').then(async (vm) => {
    try {
      const res = await api.markBookAsUnread(state.currentLibraryType, id, {
        scope: isSeriesScope ? 'series' : 'book',
        seriesName,
        libraryId,
      });
      if (res.success) {
        const targetLabel = isSeriesScope ? '시리즈 전체가' : '도서가';
        vm.showToast(`"${title}" ${targetLabel} 읽지 않은 상태(0%)로 변경되었습니다.`, 'success');
        removeUnreadTargetCards({ id, isSeriesScope, seriesName, libraryId });
        closeBookContextMenu();
        
        // 화면 리프레시: 현재 위치한 탭/뷰에 맞추어 라이브 리로드 실행
        if (state.currentLibraryId === 'home') {
          await loadDashboardData();
        } else if (state.currentLibraryId === 'history') {
          await loadReadingHistory();
        } else {
          // 상세 뷰 혹은 일반 도서 목록 새로고침
          // (구 모달 구조 시절의 #book-detail-modal / .detail-title-text 참조는 지금의
          // #book-detail-view / state.detailSeriesName 구조로 바뀐 뒤 갱신되지 않아 죽은
          // 참조로 남아있었음 — 상세 화면에서 읽지 않음 처리해도 진행률 표시가 새로고침
          // 안 되던 원인)
          const detailView = document.getElementById('book-detail-view');
          const isDetailViewOpen = !!detailView && detailView.style.display !== 'none';
          if (isDetailViewOpen) {
            const currentSeriesName = String(state.detailSeriesName || '').trim();
            if (currentSeriesName) {
              openBookDetail(null, currentSeriesName, libraryId || state.currentLibraryId);
            }
          } else {
            await loadBooksList();
          }
        }
      } else {
        vm.showToast(`변경 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('도서 읽지않음 처리 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

window.triggerMarkAsUnreadAction = triggerMarkAsUnreadAction;
window.triggerBookContextPluginAction = triggerBookContextPluginAction;
export { triggerSearchMetadataAction as triggerSearchAladinMetadataAction };

window.showBookContextMenu = showBookContextMenu;
window.closeBookContextMenu = closeBookContextMenu;

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
  return { id: parsedId, title, isVolumeDetail, markUnreadScope, seriesName, libraryId, coverAlign, fileFormat };
}

// 카드별 개별 바인딩 누락/재렌더 타이밍 이슈가 있어도 우클릭 메뉴를 보장한다.
document.addEventListener('contextmenu', (event) => {
  const target = resolveBookContextTarget(event);
  if (!target) return;

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
    fileFormat: target.fileFormat,
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

export function triggerAddToCollectionAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title } = currentTargetBook;
  import('./tab_collections.js').then((colls) => {
    colls.openAddToCollectionModal({ book_id: id, title: title });
  });
}
window.triggerAddToCollectionAction = triggerAddToCollectionAction;

export function triggerAddSeriesToCollectionAction() {
  if (!currentTargetBook) return;
  const seriesName = String(currentTargetBook.seriesName || '').trim();
  if (!seriesName) return;
  import('./tab_collections.js').then((colls) => {
    colls.openAddToCollectionModal({ series_name: seriesName, title: seriesName });
  });
}
window.triggerAddSeriesToCollectionAction = triggerAddSeriesToCollectionAction;

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

    const action = target.getAttribute('data-action');
    if (action === 'scan') return window.triggerScanSingleBookAction?.();
    if (action === 'search-meta') return window.triggerSearchMetadataAction?.();
    if (action === 'add-to-collection') return window.triggerAddToCollectionAction?.();
    if (action === 'add-series-to-collection') return window.triggerAddSeriesToCollectionAction?.();
    if (action === 'page-turn') return window.triggerPageTurnAction?.();
    if (action === 'mark-unread') return window.triggerMarkAsUnreadAction?.();
    if (action === 'cover-align') {
      const bookId = currentTargetBook?.id;
      const coverAlign = currentTargetBook?.coverAlign;
      closeBookContextMenu();
      return window.showVolumeCoverAlignContextMenu?.(lastEventX, lastEventY, bookId, coverAlign);
    }
  }, true);
  window.__bookContextActionBound = true;
}
