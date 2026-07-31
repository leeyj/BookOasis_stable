// index.js – 사이드바 카테고리 목록 로드 및 순서 드래그 앤 드롭 오케스트레이터
import { state } from '../state.js';
import * as api from '../api.js';
import { selectCategory } from '../tab_media_library.js';
import { bindSidebarContextMenu } from './context_menu.js';

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export async function loadLibraries() {
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
      
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      const addBtnHtml = isAdmin 
        ? `<button onclick="event.stopPropagation(); triggerAddLibrary();" style="background: none; border: none; color: #a855f7; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: background 0.2s;" onmouseenter="this.style.background='rgba(168, 85, 247, 0.15)'" onmouseleave="this.style.background='none'" title="${i18n.t('category.add_new_tooltip')}">
            <i class="fa-solid fa-plus"></i>
          </button>`
        : '';
      
      let html = `<li class="menu-item ${state.currentLibraryId === 'home' ? 'active' : ''}" data-type="system" id="category-home" data-id="home" onclick="selectCategory('home')" style="display: flex; justify-content: space-between; align-items: center; box-sizing: border-box;">
        <span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid fa-house"></i> ${i18n.t('category.home')}</span>
        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
          <button id="btn-pin-categories" onclick="event.stopPropagation(); window.toggleCategoryOrderPin();" style="background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s; ${pinBtnStyle}" title="${pinTitle}">
            <i class="fa-solid fa-thumbtack"></i>
          </button>
          ${addBtnHtml}
        </div>
      </li>`;

      html += `<li class="menu-item ${state.currentLibraryId === 'history' ? 'active' : ''}" data-type="system" id="category-history" data-id="history" onclick="selectCategory('history')"><i class="fa-solid fa-clock-rotate-left"></i> ${i18n.t('category.history')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" id="category-favorite" data-id="favorite" onclick="selectCategory('favorite')"><i class="fa-solid fa-star" style="color: #eab308;"></i> ${i18n.t('category.favorite')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'plugins' ? 'active' : ''}" data-type="system" id="category-plugins" data-id="plugins" onclick="selectCategory('plugins')"><i class="fa-solid fa-puzzle-piece" style="color: #38bdf8;"></i> ${i18n.t('category.plugins')}</li>`;
      if (state.showSidebarCategoryAll !== false) {
        html += `<li class="menu-item ${state.currentLibraryId === 'all' ? 'active' : ''}" data-type="system" id="category-all" data-id="all" onclick="selectCategory('all')"><i class="fa-solid fa-layer-group"></i> ${i18n.t('category.all')}</li>`;
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
          html += `<li class="menu-item ${isActive}" data-type="custom" data-id="${lib.id}" data-name="${safeName}" data-path="${safePath}" data-remote="${lib.is_remote || 0}" data-rclone-url="${safeRclone}" data-icon="${safeIcon}" data-color="${safeColor}" data-hide-cover="${hideCover}" ${draggableAttr} onclick="selectCategory('${lib.id}')"><i class="fa-solid ${safeIcon}" style="color: ${safeColor};"></i> ${safeName}</li>`;
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
              html += `<li class="menu-item ${isActive}" data-type="plugin" id="category-${catId}" data-id="${catId}" data-plugin-id="${cp.id}" onclick="selectCategory('${catId}')"><i class="${safeIcon}" style="color: #38bdf8;"></i> ${safeTitle}</li>`;
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
  const isAdmin = state.currentUser && state.currentUser.role === 'admin';
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
