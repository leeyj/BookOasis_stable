// context_menu.js – 카테고리 사이드바 우클릭 및 모바일 롱터치 컨텍스트 메뉴
import { state } from '../state.js';

export let currentTargetLibrary = null; // 우클릭 대상 저장

export function setCurrentTargetLibrary(val) {
  currentTargetLibrary = val;
}

export function bindSidebarContextMenu() {
  const sidebar = document.querySelector('.library-sidebar');
  const contextMenu = document.getElementById('library-context-menu');

  if (sidebar) {
    sidebar.addEventListener('contextmenu', (e) => {
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      if (!isAdmin) return;
      
      e.preventDefault();
      
      const menuItem = e.target.closest('.menu-item');
      if (menuItem) {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;
        
        currentTargetLibrary = { id, name, type };

        if (type === 'system') {
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
        } else {
          document.getElementById('ctx-edit-category').style.display = 'block';
          document.getElementById('ctx-delete-category').style.display = 'block';
          document.getElementById('ctx-scan-category').style.display = 'block';
          if (document.getElementById('ctx-force-scan-category')) {
            document.getElementById('ctx-force-scan-category').style.display = 'block';
          }
          if (document.getElementById('ctx-scan-covers-category')) {
            document.getElementById('ctx-scan-covers-category').style.display = 'block';
          }
          if (document.getElementById('ctx-cancel-scan-category')) {
            document.getElementById('ctx-cancel-scan-category').style.display = 'block';
          }
        }
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
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      if (!isAdmin) return;

      const menuItem = e.target.closest('.menu-item');
      if (menuItem) {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;
        
        if (typeof window.handleLongPressTouchStart === 'function') {
          window.handleLongPressTouchStart(e, (x, y) => {
            currentTargetLibrary = { id, name, type };

            if (type === 'system') {
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
            } else {
              document.getElementById('ctx-edit-category').style.display = 'block';
              document.getElementById('ctx-delete-category').style.display = 'block';
              document.getElementById('ctx-scan-category').style.display = 'block';
              if (document.getElementById('ctx-force-scan-category')) {
                document.getElementById('ctx-force-scan-category').style.display = 'block';
              }
              if (document.getElementById('ctx-scan-covers-category')) {
                document.getElementById('ctx-scan-covers-category').style.display = 'block';
              }
              if (document.getElementById('ctx-cancel-scan-category')) {
                document.getElementById('ctx-cancel-scan-category').style.display = 'block';
              }
            }
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

  // 문서 클릭 시 컨텍스트 메뉴 닫기
  document.addEventListener('click', () => {
    if (contextMenu) contextMenu.style.display = 'none';
  });
}

export function showContextMenu(x, y) {
  const contextMenu = document.getElementById('library-context-menu');
  if (!contextMenu) return;
  
  // 임시 표시하여 높이 측정
  contextMenu.style.display = 'block';
  const menuHeight = contextMenu.offsetHeight || 180;
  const menuWidth = contextMenu.offsetWidth || 160;
  
  // 뷰포트 경계 검사 및 조정
  let targetY = y + window.scrollY;
  let targetX = x + window.scrollX;
  
  if (y + menuHeight > window.innerHeight) {
    targetY = (y - menuHeight) + window.scrollY;
    // 음수가 되지 않도록 최소 한계 보정
    if (targetY < window.scrollY) targetY = window.scrollY;
  }
  
  if (x + menuWidth > window.innerWidth) {
    targetX = (x - menuWidth) + window.scrollX;
  }
  
  contextMenu.style.left = `${targetX}px`;
  contextMenu.style.top = `${targetY}px`;
}
