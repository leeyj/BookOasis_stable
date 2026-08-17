// sidebar_manager.js – 모바일/데스크톱 사이드바 토글 및 상태 유지 관리
let lastToggleTime = 0;
const MOBILE_BREAKPOINT = 1200;

function isMobileLayout() {
  return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
}

function getSidebarElements() {
  const content = document.getElementById('sidebar-collapsible-content');
  const btn = document.getElementById('btn-sidebar-toggle');
  const desktopBtn = document.getElementById('btn-sidebar-toggle-desktop');
  const brandHome = document.querySelector('[data-role="mobile-brand-home"]');
  const btnIcon = btn ? btn.querySelector('i') : null;
  return { content, btn, desktopBtn, brandHome, btnIcon };
}

export function syncSidebarResponsiveControls() {
  const { btn, desktopBtn, brandHome } = getSidebarElements();
  const mobile = isMobileLayout();

  if (btn) {
    btn.style.setProperty('display', mobile ? 'block' : 'none', 'important');
  }
  if (desktopBtn) {
    desktopBtn.style.setProperty('display', mobile ? 'none' : 'flex', 'important');
  }
  if (brandHome) {
    if (mobile) {
      brandHome.setAttribute('role', 'button');
      brandHome.setAttribute('tabindex', '0');
      brandHome.setAttribute('aria-label', 'BookOasis 홈으로 이동');
    } else {
      brandHome.removeAttribute('role');
      brandHome.removeAttribute('tabindex');
      brandHome.removeAttribute('aria-label');
    }
  }
}

function scheduleSidebarResponsiveSync() {
  syncSidebarResponsiveControls();
  window.requestAnimationFrame(syncSidebarResponsiveControls);
  window.setTimeout(syncSidebarResponsiveControls, 250);
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

// 모바일 햄버거 버튼은 CSS에서 position:fixed(layout viewport 기준)로 고정돼 있다.
// 핀치 확대(pinch-zoom) 시 실제로 보이는 visual viewport는 좁아지고 이동하지만, fixed
// 요소의 좌표는 layout viewport 기준 그대로 남아 화면 밖으로 밀려날 수 있다. html/body가
// overflow:hidden이라 사용자가 스크롤로 되찾을 수도 없다 (커뮤니티 리포트, Pixel 7 2배
// 확대 시 412px 뷰포트가 206px로 좁아지며 버튼이 완전히 이탈하는 것으로 재현됨).
// visualViewport의 resize/scroll 이벤트로 실제 보이는 영역 기준으로 위치를 보정한다.
let mobileToggleOriginalTopPx = null;
let mobileToggleOriginalRightPx = null;

function syncMobileToggleViewportPosition() {
  const viewport = window.visualViewport;
  const { btn } = getSidebarElements();
  if (!viewport || !btn || !isMobileLayout()) return;
  if (getComputedStyle(btn).display === 'none') return;

  // CSS가 정의한 원래 top/right 여백(safe-area 포함)을 최초 1회만 읽어서 기준값으로 삼는다 -
  // 이후 인라인 스타일로 덮어써도 CSS 원본 디자인의 여백 자체는 그대로 유지된다.
  if (mobileToggleOriginalTopPx === null) {
    btn.style.top = '';
    btn.style.right = '';
    const rect = btn.getBoundingClientRect();
    mobileToggleOriginalTopPx = rect.top;
    mobileToggleOriginalRightPx = window.innerWidth - rect.right;
  }

  const btnWidth = btn.offsetWidth || 0;
  btn.style.right = 'auto';
  btn.style.left = `${viewport.offsetLeft + viewport.width - btnWidth - mobileToggleOriginalRightPx}px`;
  btn.style.top = `${viewport.offsetTop + mobileToggleOriginalTopPx}px`;
}

function initMobileToggleViewportSync() {
  if (window.__mobileToggleViewportSyncBound) return;
  const viewport = window.visualViewport;
  if (!viewport) return;

  viewport.addEventListener('resize', syncMobileToggleViewportPosition);
  viewport.addEventListener('scroll', syncMobileToggleViewportPosition);
  window.addEventListener('orientationchange', syncMobileToggleViewportPosition);

  window.__mobileToggleViewportSyncBound = true;
}

function initSidebarViewportRecovery() {
  if (window.__sidebarViewportRecoveryBound) return;

  const mediaQuery = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
  const recover = () => scheduleSidebarResponsiveSync();

  window.addEventListener('pageshow', recover);
  window.addEventListener('focus', recover);
  window.addEventListener('resize', recover);
  window.addEventListener('orientationchange', recover);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') recover();
  });
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', recover);
  } else if (typeof mediaQuery.addListener === 'function') {
    mediaQuery.addListener(recover);
  }

  window.__sidebarViewportRecoveryBound = true;
}

export function initSidebarInteractions() {
  initSidebarToggleButton();
  initSidebarAutoClose();
  initSidebarCategorySync();
  initSidebarViewportRecovery();
  initMobileToggleViewportSync();
  syncSidebarResponsiveControls();
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
