// context_menu.js – 카테고리 사이드바 우클릭 및 모바일 롱터치 컨텍스트 메뉴
import { state } from '../state.js';
import { bindFloatingMenuOutsideClose, hideAllContextMenus, positionMenuAtPoint } from '../context_menu_manager.js';
import {
  triggerAddLibrary,
  triggerEditLibrary,
  triggerDeleteLibrary,
  triggerScanLibrary,
  triggerScanLibraryCovers,
  triggerCancelScanLibrary
} from './crud_controller.js';

export let currentTargetLibrary = null; // 우클릭 대상 저장
let suppressSidebarClickUntil = 0;

function isCurrentUserAdmin() {
  const user = state.currentUser || window.currentUser || {};
  return String(user.role || '').trim().toLowerCase() === 'admin';
}

function configureCategoryContextMenu(type) {
  const isSystem = type === 'system';
  const isGroup = type === 'group';
  document.getElementById('ctx-edit-category').style.display = isSystem ? 'none' : 'block';
  document.getElementById('ctx-delete-category').style.display = isSystem ? 'none' : 'block';
  document.getElementById('ctx-scan-category').style.display = (isSystem || isGroup) ? 'none' : 'block';
  ['ctx-force-scan-category', 'ctx-scan-covers-category', 'ctx-cancel-scan-category'].forEach((id) => {
    const element = document.getElementById(id);
    if (element) element.style.display = (isSystem || isGroup) ? 'none' : 'block';
  });
}

export function setCurrentTargetLibrary(val) {
  currentTargetLibrary = val;
}

export function bindSidebarContextMenu() {
  const sidebar = document.querySelector('.library-sidebar');
  const contextMenu = document.getElementById('library-context-menu');

  if (!sidebar || sidebar.dataset.sidebarContextBound === '1') {
    return;
  }
  sidebar.dataset.sidebarContextBound = '1';

  if (sidebar) {
    // 우클릭 직후 발생하는 click/onClick 전파로 카테고리 전환이 일어나는 것을 차단
    // 단, "더 보기 / 접기" 버튼은 차단 대상에서 제외
    sidebar.addEventListener('click', (e) => {
      if (Date.now() < suppressSidebarClickUntil) {
        if (e.target && typeof e.target.closest === 'function') {
          const moreBtn = e.target.closest('[data-role="sidebar-show-more"]');
          if (moreBtn) return; // 더 보기 버튼은 차단하지 않음
        }
        e.preventDefault();
        e.stopPropagation();
        if (typeof e.stopImmediatePropagation === 'function') {
          e.stopImmediatePropagation();
        }
      }
    }, true);

    sidebar.addEventListener('contextmenu', (e) => {
      const isAdmin = isCurrentUserAdmin();
      const menuItem = e.target.closest('.menu-item');
      if (!isAdmin) {
        return;
      }
      if (menuItem && menuItem.dataset.type === 'plugin') {
        // 플러그인 카테고리는 실제 카테고리가 아니므로 컨텍스트 메뉴를 띄우지 않음
        e.preventDefault();
        return;
      }

      suppressSidebarClickUntil = Date.now() + 700;
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') {
        e.stopImmediatePropagation();
      }

      if (menuItem) {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;
        
        currentTargetLibrary = { id, name, type };

        configureCategoryContextMenu(type);
      } else {
        currentTargetLibrary = null;
        document.getElementById('ctx-edit-category').style.display = 'none';
        document.getElementById('ctx-delete-category').style.display = 'none';
        document.getElementById('ctx-scan-category').style.display = 'none';
        if (document.getElementById('ctx-force-scan-category')) {
          document.getElementById('ctx-force-scan-category').style.display = 'none';
        }
        if (document.getElementById('ctx-scan-covers-category')) {
          document.getElementById('ctx-scan-covers-category').style.display = 'none';
        }
        if (document.getElementById('ctx-cancel-scan-category')) {
          document.getElementById('ctx-cancel-scan-category').style.display = 'none';
        }
      }

      showContextMenu(e.clientX, e.clientY);
    });

    sidebar.addEventListener('touchstart', (e) => {
      const isAdmin = isCurrentUserAdmin();
      if (!isAdmin) return;

      const menuItem = e.target.closest('.menu-item');
      if (menuItem && menuItem.dataset.type !== 'plugin') {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;

        if (typeof window.handleLongPressTouchStart === 'function') {
          window.handleLongPressTouchStart(e, (x, y) => {
            suppressSidebarClickUntil = Date.now() + 900;
            currentTargetLibrary = { id, name, type };

            configureCategoryContextMenu(type);
            showContextMenu(x, y);
          });
        }
      }
    }, { passive: true });

    sidebar.addEventListener('touchmove', (e) => {
      if (typeof window.handleLongPressTouchMove === 'function') {
        window.handleLongPressTouchMove(e);
      }
    }, { passive: true });

    sidebar.addEventListener('touchend', (e) => {
      if (typeof window.handleLongPressTouchEnd === 'function') {
        window.handleLongPressTouchEnd(e);
      }
    });

    sidebar.addEventListener('touchcancel', (e) => {
      if (typeof window.handleLongPressTouchEnd === 'function') {
        window.handleLongPressTouchEnd(e);
      }
    });
  }

  // 문서 클릭 시 컨텍스트 메뉴 닫기 (중복 바인딩 방지)
  bindFloatingMenuOutsideClose(contextMenu, {
    eventTypes: ['click'],
    capture: true,
    shouldIgnoreEvent: () => Date.now() < suppressSidebarClickUntil,
  });

  if (!window.__libraryContextActionBound) {
    document.addEventListener('click', (event) => {
      const actionEl = event && event.target && typeof event.target.closest === 'function'
        ? event.target.closest('[data-role="library-context-action"]')
        : null;
      if (!actionEl) return;

      event.preventDefault();
      hideAllContextMenus();
      const action = actionEl.getAttribute('data-action');
      if (action === 'scan') return triggerScanLibrary ? triggerScanLibrary(false) : window.triggerScanLibrary?.(false);
      if (action === 'force-scan') return triggerScanLibrary ? triggerScanLibrary(true) : window.triggerScanLibrary?.(true);
      if (action === 'scan-covers') return triggerScanLibraryCovers ? triggerScanLibraryCovers() : window.triggerScanLibraryCovers?.();
      if (action === 'cancel-scan') return triggerCancelScanLibrary ? triggerCancelScanLibrary() : window.triggerCancelScanLibrary?.();
      if (action === 'add') return triggerAddLibrary ? triggerAddLibrary() : window.triggerAddLibrary?.();
      if (action === 'edit') return triggerEditLibrary ? triggerEditLibrary() : window.triggerEditLibrary?.();
      if (action === 'delete') return triggerDeleteLibrary ? triggerDeleteLibrary() : window.triggerDeleteLibrary?.();
    }, true);
    window.__libraryContextActionBound = true;
  }
}

export function showContextMenu(x, y) {
  positionMenuAtPoint('library-context-menu', x, y, { zIndex: 20050 });
}
