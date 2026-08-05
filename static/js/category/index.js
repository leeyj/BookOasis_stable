// index.js – 사이드바 카테고리 목록 로드 및 순서 드래그 앤 드롭 오케스트레이터
import { state } from '../state.js';
import * as api from '../api.js';
import { selectCategory } from '../tab_media_library.js';
import { bindSidebarContextMenu } from './context_menu.js';
import { triggerAddLibrary } from './crud_controller.js';

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

    const pinBtn = rawTarget.closest('[data-role="sidebar-pin-categories"]');
    if (pinBtn) {
      console.log('[Category-Delegation] 핀 고정 버튼 감지됨:', pinBtn);
      event.preventDefault();
      event.stopPropagation();
      toggleCategoryOrderPin();
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
      
      let html = `<li class="menu-item ${state.currentLibraryId === 'home' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-home" data-id="home" data-category-id="home" style="display: flex; justify-content: space-between; align-items: center; box-sizing: border-box;">
        <span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid fa-house"></i> ${i18n.t('category.home')}</span>
        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
          <button id="btn-pin-categories" data-role="sidebar-pin-categories" style="background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; ${pinBtnStyle}" title="${pinTitle}">
            <i class="fa-solid fa-thumbtack"></i>
          </button>
          ${addBtnHtml}
        </div>
      </li>`;

      html += `<li class="menu-item ${state.currentLibraryId === 'history' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-history" data-id="history" data-category-id="history"><i class="fa-solid fa-clock-rotate-left"></i> ${i18n.t('category.history')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-favorite" data-id="favorite" data-category-id="favorite"><i class="fa-solid fa-star" style="color: #eab308;"></i> ${i18n.t('category.favorite')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'plugins' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-plugins" data-id="plugins" data-category-id="plugins"><i class="fa-solid fa-puzzle-piece" style="color: #38bdf8;"></i> ${i18n.t('category.plugins')}</li>`;
      if (state.showSidebarCategoryAll !== false) {
        html += `<li class="menu-item ${state.currentLibraryId === 'all' ? 'active' : ''}" data-type="system" data-role="sidebar-category-dynamic" id="category-all" data-id="all" data-category-id="all"><i class="fa-solid fa-layer-group"></i> ${i18n.t('category.all')}</li>`;
      }
      
      if (data.libraries && data.libraries.length > 0) {
        const savedOrderStr = localStorage.getItem(`libraries_order_${state.currentLibraryType}`);
        if (savedOrderStr) {
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

        data.libraries.forEach(lib => {
          const isActive = String(state.currentLibraryId) === String(lib.id) ? 'active' : '';
          const draggableAttr = !isPinned ? 'draggable="true"' : '';
          const safeName    = escapeHtml(lib.name || '');
          const safePath    = escapeHtml(lib.physical_path || '');
          const safeRclone  = escapeHtml(lib.rclone_rc_url || '');
          const safeIcon    = escapeHtml(lib.icon || 'fa-book');
          const safeColor   = escapeHtml(lib.color || '#94a3b8');
          const hideCover = Number(lib.hide_cover || 0) ? 1 : 0;
          html += `<li class="menu-item ${isActive}" data-type="custom" data-role="sidebar-category-dynamic" data-id="${lib.id}" data-category-id="${lib.id}" data-name="${safeName}" data-path="${safePath}" data-remote="${lib.is_remote || 0}" data-rclone-url="${safeRclone}" data-icon="${safeIcon}" data-color="${safeColor}" data-hide-cover="${hideCover}" ${draggableAttr} style="display: flex; align-items: center; justify-content: space-between;"><span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid ${safeIcon}" style="color: ${safeColor};"></i> ${safeName}</span><i class="fa-solid fa-circle-notch fa-spin category-scan-spinner" style="display:none; color:#c084fc; font-size:0.75rem; margin-left:auto;" title="스캔 진행 중"></i></li>`;
        });
      }

      // 동적 카테고리 레벨 플러그인 탭 주입
      try {
        const catPluginRes = await fetch(`/api/media/category-plugins?type=${state.currentLibraryType}`);
        if (catPluginRes.ok) {
          const catPluginData = await catPluginRes.json();
          if (catPluginData.success && catPluginData.category_plugins && catPluginData.category_plugins.length > 0) {
            catPluginData.category_plugins.forEach(cp => {
              const catId = cp.category_id;
              const isActive = String(state.currentLibraryId) === String(catId) ? 'active' : '';
              const safeTitle = escapeHtml(cp.title || cp.name);
              const safeIcon = escapeHtml(cp.icon || 'fa-puzzle-piece');
              html += `<li class="menu-item ${isActive}" data-type="plugin" data-role="sidebar-category-dynamic" id="category-${catId}" data-id="${catId}" data-category-id="${catId}" data-plugin-id="${cp.id}"><i class="${safeIcon}" style="color: #38bdf8;"></i> ${safeTitle}</li>`;
            });
          }
        }
      } catch (e) {
        console.warn('[Category] Failed to fetch category plugins:', e);
      }

      sidebar.innerHTML = html;
      const activeItem = document.getElementById(`category-${state.currentLibraryId}`) || sidebar.querySelector(`[data-id="${state.currentLibraryId}"]`);
      state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
      bindSidebarContextMenu();
      bindDragAndDropEvents(!isPinned);

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

  if (sidebar._sortable) {
    sidebar._sortable.destroy();
    sidebar._sortable = null;
  }

  if (!isEnabled) return;

  if (typeof Sortable !== 'undefined') {
    sidebar._sortable = new Sortable(sidebar, {
      animation: 150,
      draggable: 'li[data-type="custom"]',
      filter: 'li[data-type="system"]',
      preventOnFilter: false,
      onEnd: function () {
        saveNewOrder();
      }
    });
  }
}

export function saveNewOrder() {
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;
  const customItems = sidebar.querySelectorAll('li[data-type="custom"]');
  const order = Array.from(customItems).map(el => String(el.dataset.id));
  localStorage.setItem(`libraries_order_${state.currentLibraryType}`, JSON.stringify(order));
}
