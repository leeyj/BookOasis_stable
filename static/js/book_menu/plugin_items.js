// book_menu/plugin_items.js – 도서 컨텍스트 메뉴의 플러그인 항목 조회/렌더/실행.
// 메뉴의 열림/닫힘과 현재 대상 도서는 book_context_menu.js가 갖고, 여기엔 대상을 인자로 넘긴다.
import { state } from '../state.js';
import * as api from '../api.js';

let loadSeq = 0;

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

function buildContextPayload(target) {
  if (!target) return {};
  return {
    book_id: target.id,
    book_title: target.title,
    is_volume_detail: !!target.isVolumeDetail,
    library_id: state.currentLibraryId,
  };
}

function getMenuList() {
  const bookMenu = document.getElementById('book-context-menu');
  return bookMenu ? bookMenu.querySelector('.context-menu-list') : null;
}

export function clearPluginContextMenuItems() {
  const listEl = getMenuList();
  if (!listEl) return;
  listEl.querySelectorAll('.plugin-context-menu-item, .plugin-context-menu-group-title, .plugin-context-menu-separator').forEach((el) => el.remove());
}

// 진행 중인 항목 조회 결과를 버린다 (메뉴가 닫히거나 다른 도서로 다시 열린 경우).
export function cancelPluginContextMenuLoad() {
  loadSeq += 1;
}

function renderPluginContextMenuItems(items, { onItemClick, onRendered }) {
  const listEl = getMenuList();
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
        onItemClick(pluginId, actionId);
      });

      if (closeItem) {
        listEl.insertBefore(li, closeItem);
      } else {
        listEl.appendChild(li);
      }
    });
  });

  // 플러그인 항목 렌더링 후 동적으로 확장된 메뉴 높이를 기반으로 위치 재보정
  onRendered?.();
}

// 도서별 최근 조회 결과. 같은 도서 메뉴를 다시 열 때 서버 응답을 기다리지 않고 바로 그린다.
// (항목이 도서마다 다를 수 있어(예: 독후감 유무) 도서 단위로만 재사용하고, 열 때마다 뒤에서 다시 확인한다.)
const ITEMS_CACHE_LIMIT = 100;
const itemsCache = new Map();

function getCacheKey(target) {
  return `${state.currentLibraryType}:${target.id}:${target.isVolumeDetail ? 1 : 0}`;
}

function rememberItems(key, items) {
  itemsCache.delete(key);
  itemsCache.set(key, items);
  if (itemsCache.size > ITEMS_CACHE_LIMIT) {
    itemsCache.delete(itemsCache.keys().next().value);
  }
}

function isPluginTarget(target) {
  return !!(target && target.id && !(target.selectedBooks?.length > 1));
}

// 메뉴를 띄우기 전에 플러그인 항목을 그린다. 이미 그렸거나(캐시) 더 기다릴 필요가 없으면
// 반환된 ready가 resolve된다 — 호출부는 ready 이후에 메뉴를 보여 주면 항목이 한 번에 뜬다.
// ready는 최대 waitMs까지만 기다리며, 그 뒤에 도착한 응답은 기존처럼 열린 메뉴에 덧붙인다.
export function loadPluginContextMenuItems(target, { onItemClick, onRendered, waitMs = 250 }) {
  if (!isPluginTarget(target)) {
    clearPluginContextMenuItems();
    return { ready: Promise.resolve() };
  }

  const seq = ++loadSeq;
  const key = getCacheKey(target);
  const cached = itemsCache.get(key);
  let renderedSignature = null;

  if (cached) {
    renderPluginContextMenuItems(cached, { onItemClick });
    renderedSignature = JSON.stringify(cached);
  } else {
    clearPluginContextMenuItems();
  }

  const fetchPromise = (async () => {
    try {
      const payload = buildContextPayload(target);
      const res = await api.fetchBookContextMenuPluginItems(state.currentLibraryType, payload);
      if (seq !== loadSeq) return;

      if (res && res.success) {
        const items = res.items || [];
        rememberItems(key, items);
        if (JSON.stringify(items) !== renderedSignature) {
          renderPluginContextMenuItems(items, { onItemClick, onRendered });
        }
        return;
      }

      clearPluginContextMenuItems();
      onRendered?.();
    } catch (err) {
      console.error('컨텍스트 메뉴 플러그인 항목 조회 실패:', err);
      if (seq === loadSeq) {
        clearPluginContextMenuItems();
        onRendered?.();
      }
    }
  })();

  if (cached) return { ready: Promise.resolve() };
  return {
    ready: Promise.race([
      fetchPromise,
      new Promise((resolve) => setTimeout(resolve, waitMs)),
    ]),
  };
}

export async function runBookContextPluginAction(target, pluginId, actionId) {
  if (!pluginId || !actionId) return;
  if (!target || !target.id) return;

  let pendingPopup = null;
  try {
    // 팝업 차단을 피하려면 비동기 응답을 기다리기 전, 사용자 클릭 시점에 미리 창을 열어둬야
    // 한다(open_url이 있는 플러그인 액션 전용 placeholder — 없는 액션이면 아래에서 바로 닫음).
    pendingPopup = window.open('', '_blank');
    if (pendingPopup) {
      pendingPopup.document.write('<!doctype html><title>작업 처리 중...</title><p>플러그인 작업을 처리하는 중입니다.</p>');
      pendingPopup.document.close();
    }

    const payload = buildContextPayload(target);
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

    const vm = await import('../view_manager.js');
    if (!res || !res.success) {
      if (pendingPopup) {
        pendingPopup.close();
      }
      vm.showToast(res && res.error ? res.error : '플러그인 작업 실행에 실패했습니다.', 'error');
      return;
    }

    if (res.open_category) {
      // 외부 새 탭이 아니라 앱 내부의 카테고리 플러그인 풀페이지로 바로 이동하는 경우
      // (예: 'plugin_<plugin_id>'). 미리 열어둔 placeholder 팝업은 필요 없으므로 닫는다.
      if (pendingPopup) {
        pendingPopup.close();
      }
      const tml = await import('../tab_media_library.js');
      tml.selectCategory(res.open_category);
    } else if (res.open_url) {
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
    const vm = await import('../view_manager.js');
    vm.showToast('플러그인 작업 실행 중 오류가 발생했습니다.', 'error');
  }
}
