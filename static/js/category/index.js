// index.js – 사이드바 카테고리 목록 로드 및 순서 드래그 앤 드롭 오케스트레이터
import { state } from '../state.js';
import * as api from '../api.js';
import { selectCategory } from '../tab_media_library.js';
import { updateCurrentCategoryIndicator } from '../category_indicator.js';
import { bindSidebarContextMenu } from './context_menu.js';
import { triggerAddLibrary, triggerAddLibraryGroup } from './crud_controller.js';

// 고정 포함 전체 15개 이상부터 "더 보기" 버튼 노출
const SIDEBAR_MORE_THRESHOLD = 15;

function getLegacyCustomOrderStorageKey(libraryType) {
  return `libraries_order_${libraryType}`;
}

function getMixedOrderStorageKey(libraryType) {
  return `libraries_order_mixed_${libraryType}`;
}

function getMovableCategoryItems(sidebar) {
  if (!sidebar) return [];
  return Array.from(sidebar.children).filter((el) => el.matches('li[data-type="custom"], li[data-type="plugin"]'));
}

function getMovableCategoryToken(el) {
  if (!el || !el.dataset) return '';
  const type = String(el.dataset.type || '').trim();
  if (type === 'plugin') {
    const pluginId = String(el.dataset.pluginId || '').trim();
    if (!pluginId) return '';
    return `plugin:${pluginId}`;
  }

  const customId = String(el.dataset.id || '').trim();
  if (!customId) return '';
  return `custom:${customId}`;
}

function applySavedMixedOrder(sidebar) {
  if (!sidebar) return;

  let savedOrder = [];
  try {
    savedOrder = JSON.parse(localStorage.getItem(getMixedOrderStorageKey(state.currentLibraryType)) || '[]');
  } catch (_) {
    savedOrder = [];
  }
  if (!Array.isArray(savedOrder) || savedOrder.length === 0) return;

  const movableItems = getMovableCategoryItems(sidebar);
  if (movableItems.length === 0) return;

  const itemByToken = new Map();
  movableItems.forEach((el) => {
    const token = getMovableCategoryToken(el);
    if (token) itemByToken.set(token, el);
  });

  const ordered = [];
  savedOrder.forEach((token) => {
    if (itemByToken.has(token)) {
      ordered.push(itemByToken.get(token));
      itemByToken.delete(token);
    }
  });

  if (itemByToken.size > 0) {
    // 신규 항목은 현재 렌더 순서(custom -> plugin fallback)를 유지
    movableItems.forEach((el) => {
      const token = getMovableCategoryToken(el);
      if (token && itemByToken.has(token)) {
        ordered.push(el);
        itemByToken.delete(token);
      }
    });
  }

  const systemItems = Array.from(sidebar.querySelectorAll('li[data-type="system"]'));
  if (systemItems.length === 0) return;

  ordered.forEach((el) => el.remove());
  const groupItems = Array.from(sidebar.children).filter((el) => el.matches('li[data-library-group-id]'));
  let insertAfterEl = groupItems[groupItems.length - 1] || systemItems[systemItems.length - 1];
  ordered.forEach((el) => {
    insertAfterEl.after(el);
    insertAfterEl = el;
  });
}

function isCurrentUserAdmin() {
  const user = state.currentUser || window.currentUser || {};
  return String(user.role || '').trim().toLowerCase() === 'admin';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderLibraryItem(lib, isPinned) {
  const isActive = String(state.currentLibraryId) === String(lib.id) ? 'active' : '';
  const draggableAttr = !isPinned ? 'draggable="true"' : '';
  const safeName = escapeHtml(lib.name || '');
  const safePath = escapeHtml(lib.physical_path || '');
  const safeRclone = escapeHtml(lib.rclone_rc_url || '');
  const safeIcon = escapeHtml(lib.icon || 'fa-book');
  const safeColor = escapeHtml(lib.color || '#94a3b8');
  const hideCover = Number(lib.hide_cover || 0) ? 1 : 0;
  const groupId = lib.group_id == null ? '' : String(lib.group_id);
  const safeGdriveCopyRemote = escapeHtml(lib.gdrive_copy_remote || '');
  const safeGdriveCopyDestPath = escapeHtml(lib.gdrive_copy_dest_path || '');
  return `<li class="menu-item ${isActive}" data-type="custom" data-role="sidebar-category-dynamic" data-id="${lib.id}" data-category-id="${lib.id}" data-name="${safeName}" data-path="${safePath}" data-remote="${lib.is_remote || 0}" data-rclone-url="${safeRclone}" data-icon="${safeIcon}" data-color="${safeColor}" data-hide-cover="${hideCover}" data-group-id="${groupId}" data-gdrive-copy-remote="${safeGdriveCopyRemote}" data-gdrive-copy-dest-path="${safeGdriveCopyDestPath}" ${draggableAttr} style="display: flex; align-items: center; justify-content: space-between;"><span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid ${safeIcon}" style="color: ${safeColor};"></i> ${safeName}</span><i class="fa-solid fa-circle-notch fa-spin category-scan-spinner" style="display:none; color:#c084fc; font-size:0.75rem; margin-left:auto;" title="스캔 진행 중"></i></li>`;
}

function renderPluginItem(cp) {
  const catId = cp.category_id;
  const isActive = String(state.currentLibraryId) === String(catId) ? 'active' : '';
  const safeTitle = escapeHtml(cp.title || cp.name);
  const safeIcon = escapeHtml(cp.icon || 'fa-puzzle-piece');
  return `<li class="menu-item ${isActive}" data-type="plugin" data-role="sidebar-category-dynamic" id="category-${catId}" data-id="${catId}" data-category-id="${catId}" data-plugin-id="${cp.id}"><i class="${safeIcon}" style="color: #38bdf8;"></i> ${safeTitle}</li>`;
}

function getGroupCollapsedStorageKey(groupId) {
  return `library_group_collapsed_${state.currentLibraryType}_${groupId}`;
}

/**
 * Plex 스타일 사이드바 "더 보기" 제어
 * - 총 카테고리 항목 수 >= SIDEBAR_MORE_THRESHOLD 일 때 (THRESHOLD-1)번째 항목 이후를 접어서 보여줌
 * - 활성 카테고리가 숨겨지는 영역에 있으면 자동 전개
 * - localStorage(sidebar_more_expanded)로 상태 기억
 */
export function applySidebarShowMore(sidebar, currentLibraryId) {
  if (!sidebar) return;

  // 기존 "더 보기" / "접기" 버튼 제거
  sidebar.querySelectorAll('[data-role="sidebar-show-more"]').forEach(el => el.remove());

  if (sidebar.querySelector('[data-type="group"]')) {
    sidebar.querySelectorAll('li[data-role="sidebar-category-dynamic"]').forEach(item => item.style.removeProperty('display'));
    return;
  }

  const items = Array.from(sidebar.querySelectorAll('li[data-role="sidebar-category-dynamic"]'));
  const total = items.length;

  if (total < SIDEBAR_MORE_THRESHOLD) {
    // 15개 미만이면 모두 노출하고 종료
    items.forEach(item => { item.style.display = ''; });
    return;
  }

  const savedExpanded = localStorage.getItem('sidebar_more_expanded') === 'true';

  // 활성 카테고리가 숨겨질 영역에 있으면 자동 전개
  const activeItem = currentLibraryId
    ? sidebar.querySelector(`[data-category-id="${currentLibraryId}"]`)
    : null;
  const activeIdx = activeItem ? items.indexOf(activeItem) : -1;
  const forceExpand = activeIdx >= SIDEBAR_MORE_THRESHOLD - 1;

  const expanded = savedExpanded || forceExpand;
  const visibleCount = SIDEBAR_MORE_THRESHOLD - 1; // 14개까지 노출

  items.forEach((item, idx) => {
    if (idx >= visibleCount && !expanded) {
      item.style.display = 'none';
    } else {
      // style.display를 완전히 제거하면 HTML의 인라인 style="display: flex"가 자연스럽게 복원됨
      item.style.removeProperty('display');
    }
  });

  // "더 보기" / "접기" 버튼 생성
  // data-type="system"을 부여하여 Sortable.js filter에 걸리도록 하여 드래그 간섭 방지
  const moreBtn = document.createElement('li');
  moreBtn.className = 'menu-item sidebar-more-btn';
  moreBtn.dataset.role = 'sidebar-show-more';
  moreBtn.dataset.type = 'system';  // Sortable filter 제외 등록
  const hiddenCount = total - visibleCount;
  if (expanded) {
    moreBtn.innerHTML = `<i class="fa-solid fa-chevron-up"></i> <span>접기</span>`;
    sidebar.appendChild(moreBtn);
  } else {
    moreBtn.innerHTML = `<span>더 보기 (${hiddenCount})</span> <i class="fa-solid fa-chevron-right"></i>`;
    // visibleCount - 1번째 항목 바로 뒤에 삽입
    const insertAfter = items[visibleCount - 1];
    if (insertAfter && insertAfter.parentNode) {
      insertAfter.after(moreBtn);
    } else {
      sidebar.appendChild(moreBtn);
    }
  }
}

function initDynamicSidebarDelegation() {
  if (window.__dynamicSidebarDelegationBound) return;
  console.log('[Category-Delegation] initDynamicSidebarDelegation() 바인딩 완료');

  document.addEventListener('click', (event) => {
    const rawTarget = event && event.target && typeof event.target.closest === 'function' ? event.target : null;
    if (!rawTarget) return;

    const addBtn = rawTarget.closest('[data-role="sidebar-add-library"]');
    if (addBtn) {
      console.log('[Category-Delegation] + (카테고리 추가) 버튼 감지됨:', addBtn, 'rawTarget:', rawTarget);
      event.preventDefault();
      event.stopPropagation();
      if (typeof triggerAddLibrary === 'function') {
        console.log('[Category-Delegation] triggerAddLibrary() 모듈 함수 직접 호출');
        triggerAddLibrary();
      } else if (typeof window.triggerAddLibrary === 'function') {
        console.log('[Category-Delegation] window.triggerAddLibrary() 전역 함수 호출');
        window.triggerAddLibrary();
      } else {
        console.error('[Category-Delegation] Error: triggerAddLibrary 함수를 찾을 수 없습니다!');
      }
      return;
    }

    const addGdriveCopyBtn = rawTarget.closest('[data-role="sidebar-add-gdrive-copy"]');
    if (addGdriveCopyBtn) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof window.triggerAddGdriveCopy === 'function') {
        window.triggerAddGdriveCopy();
      }
      return;
    }

    const addGroupBtn = rawTarget.closest('[data-role="sidebar-add-library-group"]');
    if (addGroupBtn) {
      event.preventDefault();
      event.stopPropagation();
      triggerAddLibraryGroup();
      return;
    }

    const groupToggle = rawTarget.closest('[data-role="sidebar-group-toggle"]');
    if (groupToggle) {
      event.preventDefault();
      event.stopPropagation();
      const groupId = groupToggle.dataset.id;
      const groupContainer = groupToggle.closest('[data-library-group-id]');
      const isCollapsed = groupContainer?.classList.toggle('collapsed') || false;
      groupToggle.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
      localStorage.setItem(getGroupCollapsedStorageKey(groupId), isCollapsed ? 'true' : 'false');
      return;
    }

    const pinBtn = rawTarget.closest('[data-role="sidebar-pin-categories"]');
    if (pinBtn) {
      console.log('[Category-Delegation] 핀 고정 버튼 감지됨:', pinBtn);
      event.preventDefault();
      event.stopPropagation();
      toggleCategoryOrderPin();
      return;
    }

    // 더 보기 / 접기 버튼 클릭 처리
    const moreBtn = rawTarget.closest('[data-role="sidebar-show-more"]');
    if (moreBtn) {
      event.preventDefault();
      event.stopPropagation();
      const isExpanded = localStorage.getItem('sidebar_more_expanded') === 'true';
      localStorage.setItem('sidebar_more_expanded', isExpanded ? 'false' : 'true');
      const sidebarEl = document.getElementById('sidebar-categories');
      applySidebarShowMore(sidebarEl, state.currentLibraryId);
      return;
    }

    const dynamicItem = rawTarget.closest('[data-role="sidebar-category-dynamic"]');
    if (dynamicItem) {
      const catId = dynamicItem.getAttribute('data-category-id') || dynamicItem.getAttribute('data-id') || 'home';
      console.log('[Category-Delegation] 동적 카테고리 항목 클릭 감지됨:', catId, dynamicItem);
      event.preventDefault();
      event.stopPropagation();
      selectCategory(catId);
      return;
    }
  }, true);

  window.__dynamicSidebarDelegationBound = true;
}

export async function loadLibraries() {
  initDynamicSidebarDelegation();
  window.loadLibraries = loadLibraries;
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;
  try {
    const data = await api.fetchLibraries(state.currentLibraryType);
    if (data.success) {
      state.libraryGroups = Array.isArray(data.groups) ? data.groups : [];
      const isPinned = localStorage.getItem('category_order_pinned') !== 'false';
      const pinBtnStyle = isPinned 
        ? "color: #a855f7; transform: none;" 
        : "color: #94a3b8; transform: rotate(45deg);";
      const pinTitle = isPinned ? i18n.t('category.pin_pinned') : i18n.t('category.pin_unpinned');
      
      const isAdmin = isCurrentUserAdmin();
      const addBtnHtml = isAdmin 
        ? `<button data-role="sidebar-add-library" style="background: none; border: none; color: #a855f7; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px;" title="${i18n.t('category.add_new_tooltip')}">
            <i class="fa-solid fa-plus"></i>
          </button>`
        : '';
      const addGroupBtnHtml = isAdmin
        ? `<button data-role="sidebar-add-library-group" style="background: none; border: none; color: #a855f7; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px;" title="그룹 추가">
            <i class="fa-solid fa-folder-plus"></i>
          </button>`
        : '';
      const addGdriveCopyBtnHtml = (isAdmin && window.DEVELOP_MODE)
        ? `<button data-role="sidebar-add-gdrive-copy" style="background: none; border: none; color: #60a5fa; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px;" title="Drive에서 복사해오기 (실험적)">
            <i class="fa-brands fa-google-drive"></i>
          </button>`
        : '';
      
      const tHome = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.home', 'Home') : 'Home';
      const tHistory = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.history', '최근 읽은 도서') : '최근 읽은 도서';
      const tFavorite = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.favorite', '즐겨찾기') : '즐겨찾기';
      const tCollection = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.collection', '컬렉션') : '컬렉션';
      const tSmartRec = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.smart_recommend', '스마트 추천') : '스마트 추천';
      const tPlugins = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.plugins', '플러그인') : '플러그인';
      const tAll = (window.i18n && typeof window.i18n.t === 'function') ? window.i18n.t('category.all', '전체보기') : '전체보기';

      let html = `<li class="menu-item ${state.currentLibraryId === 'home' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-home" data-id="home" data-category-id="home" style="display: flex; justify-content: space-between; align-items: center; box-sizing: border-box;">
        <span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid fa-house"></i> ${tHome}</span>
        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
          <button id="btn-pin-categories" data-role="sidebar-pin-categories" style="background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; ${pinBtnStyle}" title="${pinTitle}">
            <i class="fa-solid fa-thumbtack"></i>
          </button>
          ${addGroupBtnHtml}
          ${addBtnHtml}
          ${addGdriveCopyBtnHtml}
        </div>
      </li>`;

      html += `<li class="menu-item ${state.currentLibraryId === 'history' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-history" data-id="history" data-category-id="history"><i class="fa-solid fa-clock-rotate-left"></i> ${tHistory}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-favorite" data-id="favorite" data-category-id="favorite"><i class="fa-solid fa-star" style="color: #eab308;"></i> ${tFavorite}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'collection' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-collection" data-id="collection" data-category-id="collection"><i class="fa-solid fa-bookmark" style="color: #a855f7;"></i> ${tCollection}</li>`;
      if (state.smartRecommendEnabled !== false) {
        html += `<li class="menu-item ${state.currentLibraryId === 'smart_rec' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-smart-rec" data-id="smart_rec" data-category-id="smart_rec"><i class="fa-solid fa-wand-magic-sparkles" style="color: #34d399;"></i> ${tSmartRec}</li>`;
      }
      html += `<li class="menu-item ${state.currentLibraryId === 'plugins' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-plugins" data-id="plugins" data-category-id="plugins"><i class="fa-solid fa-puzzle-piece" style="color: #38bdf8;"></i> ${tPlugins}</li>`;
      if (state.showSidebarCategoryAll !== false) {
        html += `<li class="menu-item ${state.currentLibraryId === 'all' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-all" data-id="all" data-category-id="all"><i class="fa-solid fa-layer-group"></i> ${tAll}</li>`;
      }
      
      if (data.libraries && data.libraries.length > 0) {
        const hasServerOrder = data.libraries.some((lib) => Number(lib.sort_order || 0) > 0);
        const savedOrderStr = localStorage.getItem(getLegacyCustomOrderStorageKey(state.currentLibraryType));
        if (!hasServerOrder && savedOrderStr) {
          try {
            const savedOrder = JSON.parse(savedOrderStr);
            data.libraries.sort((a, b) => {
              let idxA = savedOrder.indexOf(String(a.id));
              let idxB = savedOrder.indexOf(String(b.id));
              if (idxA === -1) idxA = 9999;
              if (idxB === -1) idxB = 9999;
              return idxA - idxB;
            });
          } catch(e) {
            console.error('Error parsing library order:', e);
          }
        }
      }

      const librariesByGroup = new Map();
      (data.libraries || []).forEach((lib) => {
        const groupKey = lib.group_id == null ? '' : String(lib.group_id);
        if (!librariesByGroup.has(groupKey)) librariesByGroup.set(groupKey, []);
        librariesByGroup.get(groupKey).push(lib);
      });

      // 동적 카테고리 레벨 플러그인 탭 조회 (그룹 렌더링보다 먼저 수행해야 그룹 내부에 배치 가능)
      let categoryPlugins = [];
      try {
        const catPluginRes = await fetch(`/api/media/category-plugins?type=${state.currentLibraryType}`);
        if (catPluginRes.ok) {
          const catPluginData = await catPluginRes.json();
          if (catPluginData.success && Array.isArray(catPluginData.category_plugins)) {
            categoryPlugins = catPluginData.category_plugins;
          }
        }
      } catch (e) {
        console.warn('[Category] Failed to fetch category plugins:', e);
      }

      const validGroupIds = new Set(state.libraryGroups.map((g) => String(g.id)));
      const pluginsByGroup = new Map();
      const ungroupedPlugins = [];
      categoryPlugins.forEach((cp) => {
        const groupKey = cp.group_id == null ? '' : String(cp.group_id);
        if (groupKey && validGroupIds.has(groupKey)) {
          if (!pluginsByGroup.has(groupKey)) pluginsByGroup.set(groupKey, []);
          pluginsByGroup.get(groupKey).push(cp);
        } else {
          ungroupedPlugins.push(cp);
        }
      });

      state.libraryGroups.forEach((group) => {
        const groupId = String(group.id);
        const groupLibraries = librariesByGroup.get(groupId) || [];
        const groupPlugins = pluginsByGroup.get(groupId) || [];
        if (!isAdmin && groupLibraries.length === 0 && groupPlugins.length === 0) return;
        const containsActive = groupLibraries.some((lib) => String(lib.id) === String(state.currentLibraryId))
          || groupPlugins.some((cp) => String(cp.category_id) === String(state.currentLibraryId));
        const isCollapsed = !containsActive && localStorage.getItem(getGroupCollapsedStorageKey(groupId)) === 'true';
        const safeGroupName = escapeHtml(group.name || '');
        const safeGroupIcon = escapeHtml(group.icon || 'fa-folder');
        const safeGroupColor = escapeHtml(group.color || '#a855f7');
        html += `<li class="sidebar-library-group${isCollapsed ? ' collapsed' : ''}" data-type="group-container" data-library-group-id="${groupId}">
          <button type="button" class="menu-item sidebar-group-header" data-type="group" data-role="sidebar-group-toggle" data-id="${groupId}" data-name="${safeGroupName}" aria-expanded="${isCollapsed ? 'false' : 'true'}">
            <span><i class="fa-solid fa-chevron-down sidebar-group-chevron"></i><i class="fa-solid ${safeGroupIcon}" style="color:${safeGroupColor};"></i>${safeGroupName}</span>
            <small>${groupLibraries.length + groupPlugins.length}</small>
          </button>
          <ul class="sidebar-library-group-items" data-group-id="${groupId}">${groupLibraries.map((lib) => renderLibraryItem(lib, isPinned)).join('')}${groupPlugins.map((cp) => renderPluginItem(cp)).join('')}</ul>
        </li>`;
        librariesByGroup.delete(groupId);
        pluginsByGroup.delete(groupId);
      });

      (librariesByGroup.get('') || []).forEach((lib) => {
        html += renderLibraryItem(lib, isPinned);
      });

      ungroupedPlugins.forEach((cp) => {
        html += renderPluginItem(cp);
      });

      sidebar.innerHTML = html;
      applySavedMixedOrder(sidebar);
      const activeItem = document.getElementById(`category-${state.currentLibraryId}`) || sidebar.querySelector(`[data-id="${state.currentLibraryId}"]`);
      state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
      updateCurrentCategoryIndicator(state.currentLibraryId, activeItem);
      bindSidebarContextMenu();
      bindDragAndDropEvents(!isPinned);
      // Sortable.js 초기화 이후에 "더 보기" 버튼 삽입해야 Sortable의 내부 상태와 충돌 없이 정상 동작함
      applySidebarShowMore(sidebar, state.currentLibraryId);

      window.dispatchEvent(new CustomEvent('library:categories-rendered', {
        detail: {
          libraryType: state.currentLibraryType,
          currentLibraryId: state.currentLibraryId
        }
      }));
    }
  } catch (e) {
    console.error('라이브러리 목록 로드 실패:', e);
  }
}

export function toggleCategoryOrderPin() {
  const isPinned = localStorage.getItem('category_order_pinned') !== 'false';
  localStorage.setItem('category_order_pinned', isPinned ? 'false' : 'true');
  loadLibraries();
}

export function bindDragAndDropEvents(isEnabled) {
  const isAdmin = isCurrentUserAdmin();
  if (!isAdmin) {
    isEnabled = false;
  }
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;

  (sidebar._categorySortables || []).forEach((sortable) => sortable.destroy());
  sidebar._categorySortables = [];

  if (!isEnabled) return;

  if (typeof Sortable !== 'undefined') {
    const persistOnEnd = async (event) => {
      saveNewOrder();
      const draggedType = event.item?.dataset?.type;
      if (draggedType === 'custom') {
        await persistLibraryPositions(sidebar);
      } else if (draggedType === 'plugin') {
        await persistPluginGroupPositions(sidebar);
      } else if (draggedType === 'group-container') {
        await persistGroupPositions(sidebar);
      }
    };
    const allowCategoryMove = (event) => {
      const groupContainer = event.related?.closest?.('[data-library-group-id]');
      if (groupContainer?.classList.contains('collapsed')) {
        groupContainer.classList.remove('collapsed');
        const toggle = groupContainer.querySelector('[data-role="sidebar-group-toggle"]');
        toggle?.setAttribute('aria-expanded', 'true');
        localStorage.setItem(getGroupCollapsedStorageKey(groupContainer.dataset.libraryGroupId), 'false');
      }
      const targetIsGroup = event.to?.matches?.('.sidebar-library-group-items');
      const draggedType = event.dragged?.dataset?.type;
      if (draggedType === 'group-container') {
        // 그룹 자체는 다른 그룹 내부(하위 목록)로 들어갈 수 없음
        return !targetIsGroup;
      }
      return !(targetIsGroup && draggedType !== 'custom' && draggedType !== 'plugin');
    };

    sidebar._categorySortables.push(new Sortable(sidebar, {
      animation: 150,
      group: {name: 'library-categories', pull: true, put: true},
      draggable: 'li[data-type="custom"], li[data-type="plugin"], li[data-type="group-container"]',
      filter: 'li[data-type="system"]',
      preventOnFilter: false,
      onMove: allowCategoryMove,
      onEnd: persistOnEnd
    }));

    sidebar.querySelectorAll('.sidebar-library-group-items').forEach((groupList) => {
      sidebar._categorySortables.push(new Sortable(groupList, {
        animation: 150,
        group: {name: 'library-categories', pull: true, put: true},
        draggable: 'li[data-type="custom"], li[data-type="plugin"]',
        emptyInsertThreshold: 18,
        onMove: allowCategoryMove,
        onEnd: persistOnEnd
      }));
    });
  }
}

async function persistLibraryPositions(sidebar) {
  const items = Array.from(sidebar.querySelectorAll('li[data-type="custom"]')).map((element) => {
    const groupContainer = element.closest('[data-library-group-id]');
    const groupId = groupContainer?.dataset?.libraryGroupId || null;
    element.dataset.groupId = groupId || '';
    return {id: element.dataset.id, group_id: groupId};
  });

  try {
    const result = await api.moveLibraries(items, state.currentLibraryType);
    if (!result.success) throw new Error(result.error || '카테고리 위치를 저장하지 못했습니다.');
    await loadLibraries();
  } catch (error) {
    alert(error.message || '카테고리 위치를 저장하지 못했습니다.');
    await loadLibraries();
  }
}

async function persistGroupPositions(sidebar) {
  const items = Array.from(sidebar.querySelectorAll(':scope > li[data-type="group-container"]')).map((element) => ({
    id: element.dataset.libraryGroupId
  }));

  try {
    const result = await api.moveLibraryGroups(items, state.currentLibraryType);
    if (!result.success) throw new Error(result.error || '그룹 순서를 저장하지 못했습니다.');
    await loadLibraries();
  } catch (error) {
    alert(error.message || '그룹 순서를 저장하지 못했습니다.');
    await loadLibraries();
  }
}

async function persistPluginGroupPositions(sidebar) {
  const items = Array.from(sidebar.querySelectorAll('li[data-type="plugin"]')).map((element) => {
    const groupContainer = element.closest('[data-library-group-id]');
    const groupId = groupContainer?.dataset?.libraryGroupId || null;
    return {plugin_id: element.dataset.pluginId, group_id: groupId};
  });

  try {
    const result = await api.assignPluginGroups(items, state.currentLibraryType);
    if (!result.success) throw new Error(result.error || '플러그인 그룹 위치를 저장하지 못했습니다.');
    await loadLibraries();
  } catch (error) {
    alert(error.message || '플러그인 그룹 위치를 저장하지 못했습니다.');
    await loadLibraries();
  }
}

export function saveNewOrder() {
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;

  const customItems = Array.from(sidebar.children).filter((el) => el.matches('li[data-type="custom"]'));
  const legacyCustomOrder = Array.from(customItems).map(el => String(el.dataset.id));
  localStorage.setItem(getLegacyCustomOrderStorageKey(state.currentLibraryType), JSON.stringify(legacyCustomOrder));

  const movableItems = getMovableCategoryItems(sidebar);
  const mixedOrder = movableItems
    .map((el) => getMovableCategoryToken(el))
    .filter((token) => !!token);
  localStorage.setItem(getMixedOrderStorageKey(state.currentLibraryType), JSON.stringify(mixedOrder));
}
