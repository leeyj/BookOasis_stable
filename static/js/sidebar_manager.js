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

// 예전엔 모바일 햄버거 버튼이 CSS position:fixed로 화면에 고정돼 있었고, 핀치줌 시
// visualViewport를 추적해 위치를 맞추는 JS가 있었다. 그 방식이 오히려 흔들림/사라짐
// 등 새 버그를 반복 유발해(2026-08-17) BookOasis 로고 옆 일반 문서 흐름으로 되돌렸다
// (static/css/mobile.css의 .btn-sidebar-toggle 주석 참고). 더 이상 JS로 위치를 추적할
// 필요가 없어져 관련 코드(syncMobileToggleViewportPosition 등)를 전부 제거했다.

// iOS Safari는 화면 잠금 해제 후 백그라운드 상태에서 이미 그려져 있던 콘텐츠를 즉시
// 다시 페인트하지 않는 경우가 있다(알려진 WebKit 리페인트 버그, 커뮤니티 리포트:
// 잠금 해제 시 상단 헤더(로고+햄버거)가 안 나타남). transform을 살짝 건드렸다 되돌리는
// 것만으로 강제 리페인트를 유도할 수 있다. (버튼이 더 이상 fixed가 아니어도 이 리페인트
// 버그 자체는 fixed 여부와 무관하게 발생할 수 있어 유지한다.)
function forceIosHeaderRepaint() {
  const header = document.querySelector('.sidebar-header-wrapper');
  const sidebar = document.querySelector('.library-sidebar');
  [header, sidebar].forEach((el) => {
    if (!el) return;
    // 어떤 종류의 WebKit 리페인트 누락인지 확신할 수 없어(컴포지팅 레이어 문제인지,
    // 순수 페인트 누락인지) transform과 opacity 두 가지 강제 리페인트 트릭을 함께
    // 건다 - 실제 로그로 확인된 증상은 "계산된 display는 정상인데 화면엔 안 그려짐"
    // 이라, 레이아웃(reflow)이 아니라 페인트 단계의 문제로 보고 opacity를 추가했다.
    const prevOpacity = el.style.opacity;
    el.style.webkitTransform = 'translateZ(0)';
    el.style.opacity = '0.999';
    window.requestAnimationFrame(() => {
      el.style.webkitTransform = '';
      el.style.opacity = prevOpacity;
    });
  });
}

// 실제 원인 확정(2026-08-17, 원격 로그로 확인): 헤더가 "안 그려진" 게 아니라 화면 위로
// 스크롤되어 가려진 것이었다(headerRect.top이 -30~-59까지 나감). html/body가
// overflow:hidden이라도 iOS Safari는 키보드 표시/숨김, 주소창 접힘 등으로 여전히 창을
// 스크롤시킬 수 있다. tab_media_library.js::recoverTopCategoryUiAfterBack()에 뒤로가기
// 전용으로 이미 있던 스크롤 복구 로직과 동일한 원리를 탭 전환/포그라운드 복귀 등
// 다른 트리거 경로에도 적용한다.
function resetScrollIfHeaderHidden() {
  const header = document.querySelector('.sidebar-header-wrapper');
  if (!header || !isMobileLayout()) return;
  const rect = header.getBoundingClientRect();
  if (rect.bottom <= 0 || rect.top < -4) {
    // y=0 대신 y=1로 스크롤: iOS Safari는 스크롤 위치가 정확히 0일 때 주소창을
    // 완전히 펼치며 페이지 콘텐츠 위에 겹쳐 그리는 버그가 있다. 1px만 남겨두면
    // 주소창이 겹치지 않으면서도 사실상 맨 위와 동일하게 보인다.
    window.scrollTo(0, 1);
    const mainContent = document.querySelector('.library-main-content');
    if (mainContent) mainContent.scrollTop = 0;
  }
}

function initSidebarViewportRecovery() {
  if (window.__sidebarViewportRecoveryBound) return;

  const mediaQuery = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
  const recover = () => {
    scheduleSidebarResponsiveSync();
    forceIosHeaderRepaint();
    resetScrollIfHeaderHidden();
  };

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
  // 최초 로드 시에도(백그라운드 복귀 경로와 무관하게) 계산된 display 값과 실제 화면에
  // 그려지는 것이 어긋나는 iOS WebKit 리페인트 버그가 재현됐다(로그상 display는 전부
  // 정상인데 화면엔 안 보임). 1회 보정으로 안 될 수 있어(실측: 300ms 1회 시도로도
  // 재현됨) 여러 시점에 반복 시도한다.
  syncSidebarResponsiveControls();
  resetScrollIfHeaderHidden();
  [100, 300, 800, 1500].forEach((delay) => {
    window.setTimeout(() => {
      forceIosHeaderRepaint();
      resetScrollIfHeaderHidden();
    }, delay);
  });
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
