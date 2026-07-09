// book_context_menu.js – 도서 우클릭 단독 스캔 컨텍스트 메뉴 제어 모듈
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail } from './modal.js';
import { loadBooksList, loadReadingHistory } from './book_list.js';
import { loadDashboardData } from './dashboard.js';

let currentTargetBook = null;
let contextMenuSuppressUntil = 0;
let dismissPointerGuardUntil = 0;
let longPressTimer = null;
let touchStartX = 0;
let touchStartY = 0;
const touchMoveThreshold = 10;
let contextMenuLoadSeq = 0;

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
}

async function loadPluginContextMenuItems() {
  if (!currentTargetBook || !currentTargetBook.id) {
    clearPluginContextMenuItems();
    return;
  }

  const seq = ++contextMenuLoadSeq;
  console.log('[BookContextMenu] loading plugin items', {
    seq,
    bookId: currentTargetBook.id,
    title: currentTargetBook.title,
    isVolumeDetail: currentTargetBook.isVolumeDetail,
    libraryId: state.currentLibraryId,
  });
  try {
    const payload = buildCurrentContextPayload();
    console.log('[BookContextMenu] request payload', payload);
    const res = await api.fetchBookContextMenuPluginItems(state.currentLibraryType, payload);
    if (seq !== contextMenuLoadSeq) return;

    console.log('[BookContextMenu] response', res);
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
  const bookMenu = document.getElementById('book-context-menu');
  return !!bookMenu && bookMenu.style.display !== 'none';
}

function hideBookContextMenu({ suppressMs = 0, clearTarget = true } = {}) {
  const bookMenu = document.getElementById('book-context-menu');
  if (bookMenu) bookMenu.style.display = 'none';
  if (clearTarget) currentTargetBook = null;
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

export function showBookContextMenu(x, y, bookId, bookTitle, isVolumeDetail = false) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu) return;

  if (Date.now() < contextMenuSuppressUntil) return;
  menuLastShownAt = Date.now();
  
  currentTargetBook = { id: bookId, title: bookTitle, isVolumeDetail };
  
  // 임시 표시하여 실제 메뉴 크기 측정
  bookMenu.style.display = 'block';
  const menuHeight = bookMenu.offsetHeight || 180;
  const menuWidth = bookMenu.offsetWidth || 160;
  
  // 뷰포트 경계 검사 및 위치 보정
  let targetX = x + window.scrollX;
  let targetY = y + window.scrollY;
  
  if (y + menuHeight > window.innerHeight) {
    targetY = (y - menuHeight) + window.scrollY;
    // 음수가 되지 않도록 최소 한계 보정
    if (targetY < window.scrollY) targetY = window.scrollY;
  }
  
  if (x + menuWidth > window.innerWidth) {
    targetX = (x - menuWidth) + window.scrollX;
    if (targetX < window.scrollX) targetX = window.scrollX;
  }
  
  bookMenu.style.left = `${targetX}px`;
  bookMenu.style.top = `${targetY}px`;
  
  // 다른 메뉴 닫기
  const libMenu = document.getElementById('library-context-menu');
  if (libMenu) libMenu.style.display = 'none';

  loadPluginContextMenuItems();
}

export async function triggerBookContextPluginAction(pluginId, actionId) {
  if (!pluginId || !actionId) return;
  if (!currentTargetBook || !currentTargetBook.id) return;

  let pendingPopup = null;
  try {
    pendingPopup = window.open('', '_blank');
    if (pendingPopup) {
      pendingPopup.document.write('<!doctype html><title>네이버 도서 검색 중...</title><p>검색 페이지를 여는 중입니다.</p>');
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

export async function triggerMarkAsUnreadAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title } = currentTargetBook;

  import('./view_manager.js').then(async (vm) => {
    try {
      const res = await api.markBookAsUnread(state.currentLibraryType, id);
      if (res.success) {
        vm.showToast(`"${title}" 도서가 읽지 않은 상태(0%)로 변경되었습니다.`, 'success');
        
        // 화면 리프레시: 현재 위치한 탭/뷰에 맞추어 라이브 리로드 실행
        if (state.currentLibraryId === 'home') {
          loadDashboardData();
        } else if (state.currentLibraryId === 'history') {
          loadReadingHistory();
        } else {
          // 상세 뷰 혹은 일반 도서 목록 새로고침
          const detailModal = document.getElementById('book-detail-modal');
          if (detailModal && detailModal.style.display === 'flex') {
            const seriesName = document.querySelector('.detail-title-text')?.textContent || '';
            if (seriesName) {
              openBookDetail(null, seriesName, state.currentLibraryId);
            }
          }
          loadBooksList();
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

// 도서 우클릭 메뉴 클릭 이외 시 닫기 핸들러 추가
function shouldIgnoreBookMenuDismiss(event) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu || !event || !event.target) return false;
  return bookMenu.contains(event.target);
}

function dismissBookMenuOutside(event, suppressMs = 350) {
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
document.addEventListener('touchstart', (event) => {
  if (!isBookContextMenuOpen()) return;
  if (shouldIgnoreBookMenuDismiss(event)) return;
  // 메뉴가 열린 상태에서 외부 터치 → 즉시 suppress 시작
  contextMenuSuppressUntil = Date.now() + 600;
  dismissPointerGuardUntil = Date.now() + 600;
}, { passive: true });

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
  if (Date.now() - menuLastShownAt < 700) {
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
    if (item) {
      // 메뉴 항목 클릭 시 suppress를 충분히 길게 설정 (iOS 지연 이벤트 방어)
      setTimeout(() => {
        hideBookContextMenu({ suppressMs: 700, clearTarget: false });
      }, 0);
    }
  }, true);
}
