// sidebar_manager.js – 모바일/데스크톱 사이드바 토글 및 상태 유지 관리
export function toggleSidebarMenu() {
  const content = document.getElementById('sidebar-collapsible-content');
  const btnIcon = document.querySelector('#btn-sidebar-toggle i');
  if (!content) return;

  if (content.classList.contains('show')) {
    content.classList.remove('show');
    if (btnIcon) btnIcon.className = 'fa-solid fa-bars';
  } else {
    content.classList.add('show');
    if (btnIcon) btnIcon.className = 'fa-solid fa-xmark';
  }
}

export function toggleDesktopSidebar() {
  const sidebar = document.querySelector('.library-sidebar');
  if (sidebar) {
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    localStorage.setItem('desktopSidebarCollapsed', isCollapsed ? 'true' : 'false');
  }
}

// 모바일 해상도(1200px 이하) 카테고리 클릭 시 사이드바 자동 닫기 처리 등록
export function initSidebarAutoClose() {
  const sidebar = document.querySelector('.library-sidebar');
  if (sidebar) {
    sidebar.addEventListener('click', (e) => {
      const menuItem = e.target.closest('.menu-item');
      if (menuItem && window.innerWidth <= 1200) {
        const content = document.getElementById('sidebar-collapsible-content');
        const btnIcon = document.querySelector('#btn-sidebar-toggle i');
        if (content && content.classList.contains('show')) {
          content.classList.remove('show');
          if (btnIcon) btnIcon.className = 'fa-solid fa-bars';
        }
      }
    });
  }
}

// 데스크톱 사이드바 초기 접힘 상태 로컬스토리지 기반 복원
export function restoreDesktopSidebarState() {
  if (window.innerWidth > 1200) {
    const isCollapsed = localStorage.getItem('desktopSidebarCollapsed') === 'true';
    const sidebar = document.querySelector('.library-sidebar');
    if (isCollapsed && sidebar) {
      sidebar.classList.add('collapsed');
    }
  }
}

// HTML 인라인 onclick 등과의 하위 호환성을 위해 window 전역 공간 노출
window.toggleSidebarMenu = toggleSidebarMenu;
window.toggleDesktopSidebar = toggleDesktopSidebar;
