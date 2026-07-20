// sidebar_manager.js – 모바일/데스크톱 사이드바 토글 및 상태 유지 관리
let lastToggleTime = 0;
const MOBILE_BREAKPOINT = 1200;

function isMobileLayout() {
  return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
}

function getSidebarElements() {
  const content = document.getElementById('sidebar-collapsible-content');
  const btn = document.getElementById('btn-sidebar-toggle');
  const btnIcon = btn ? btn.querySelector('i') : null;
  return { content, btn, btnIcon };
}

function setSidebarMenuOpen(isOpen, options = {}) {
  const { resetScrollTop = false } = options;
  const { content, btn, btnIcon } = getSidebarElements();
  if (!content) return false;

  if (isOpen) {
    content.classList.add('show');
    content.hidden = false;
    if (resetScrollTop) {
      content.scrollTop = 0;
    }
    if (btnIcon) btnIcon.className = 'fa-solid fa-xmark';
    if (btn) btn.setAttribute('aria-expanded', 'true');
    content.dataset.open = '1';
    return true;
  }

  content.classList.remove('show');
  content.hidden = true;
  if (btnIcon) btnIcon.className = 'fa-solid fa-bars';
  if (btn) btn.setAttribute('aria-expanded', 'false');
  content.dataset.open = '0';
  return true;
}

export function toggleSidebarMenu() {
  const now = Date.now();
  if (now - lastToggleTime < 180) {
    return; // 고스트 클릭 차단
  }
  lastToggleTime = now;

  const { content } = getSidebarElements();
  if (!content) return;

  const isOpen = content.classList.contains('show');
  setSidebarMenuOpen(!isOpen, { resetScrollTop: !isOpen && isMobileLayout() });
}

export function closeSidebarMenuForMobile() {
  if (!isMobileLayout()) return;
  setSidebarMenuOpen(false);
}

export function syncSidebarMenuState() {
  const { content, btn, btnIcon } = getSidebarElements();
  if (!content || !btn) return;

  const isOpen = content.classList.contains('show');
  btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  if (btnIcon) btnIcon.className = isOpen ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
  content.dataset.open = isOpen ? '1' : '0';
  content.hidden = !isOpen;
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
  if (!sidebar || sidebar.dataset.mobileAutoCloseBound === '1') return;

  sidebar.dataset.mobileAutoCloseBound = '1';
  if (sidebar) {
    sidebar.addEventListener('click', (e) => {
      const menuItem = e.target.closest('.menu-item');
      if (menuItem && isMobileLayout()) {
        // 카테고리 전환 직후 재오픈이 즉시 되도록 쿨다운 타임스탬프는 건드리지 않음
        closeSidebarMenuForMobile();
      }
    });
  }
}

function initSidebarToggleButton() {
  const { btn } = getSidebarElements();
  if (!btn || btn.dataset.toggleBound === '1') return;

  btn.dataset.toggleBound = '1';
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    toggleSidebarMenu();
  });
}

function initSidebarCategorySync() {
  if (window.__sidebarCategorySyncBound) return;

  window.addEventListener('library:category-selected', () => {
    closeSidebarMenuForMobile();
    syncSidebarMenuState();
  });

  // 카테고리 목록이 innerHTML로 다시 렌더링된 뒤, 열린 상태라면 높이를 즉시 재측정
  window.addEventListener('library:categories-rendered', () => {
    syncSidebarMenuState();
  });

  window.__sidebarCategorySyncBound = true;
}

export function initSidebarInteractions() {
  initSidebarToggleButton();
  initSidebarAutoClose();
  initSidebarCategorySync();
  syncSidebarMenuState();
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
