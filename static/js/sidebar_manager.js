// sidebar_manager.js – 모바일/데스크톱 사이드바 토글 및 상태 유지 관리
let lastToggleTime = 0;
let mobileNavigationToken = 0;
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
    btn.style.setProperty('display', mobile ? 'flex' : 'none', 'important');
  }
  if (desktopBtn) {
    desktopBtn.style.setProperty('display', mobile ? 'none' : 'flex', 'important');
  }
  if (brandHome) {
    brandHome.setAttribute('role', 'button');
    brandHome.setAttribute('tabindex', '0');
    brandHome.setAttribute('aria-label', 'BookOasis 홈으로 이동');
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
      const scroller = content.querySelector('.sidebar-drawer-scroll');
      content.scrollTop = 0;
      if (scroller) scroller.scrollTop = 0;
    }
    if (btnIcon) btnIcon.className = 'fa-solid fa-xmark';
    if (btn) btn.setAttribute('aria-expanded', 'true');
    content.dataset.open = '1';
    syncDrawerChromeState(true);
    return true;
  }

  content.classList.remove('show');
  content.hidden = true;
  if (btnIcon) btnIcon.className = 'fa-solid fa-bars';
  if (btn) btn.setAttribute('aria-expanded', 'false');
  content.dataset.open = '0';
  syncDrawerChromeState(false);
  clearSidebarMenuSearch();
  return true;
}

// 모바일 드로어의 부가 상태: 백드롭 표시용 body 클래스 + 닫힌 드로어는 inert로 포커스/스크린리더 차단.
// 데스크톱에선 #sidebar-collapsible-content가 그냥 사이드바 본문이라 inert를 걸면 안 된다.
function syncDrawerChromeState(isOpen) {
  const { content } = getSidebarElements();
  const mobile = isMobileLayout();
  if (document.body) document.body.classList.toggle('sidebar-drawer-open', Boolean(isOpen && mobile));
  if (content) content.inert = mobile && !isOpen;
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

// 모바일에서 메뉴 항목을 누르면 데이터 조회나 기존 목록 정리보다 먼저 메뉴를 닫는다.
// category/index.js의 동적 메뉴 delegation은 캡처 단계에서 이벤트 전파를 중단하므로 위의
// sidebar 버블 리스너(initSidebarAutoClose)가 실행되지 않고, 홈/기록 이동은 selectCategory()가
// 진행률 저장을 await한 뒤에야 끝의 닫기 이벤트에 도달한다. 또 같은 이벤트 작업 안에서 바로
// 무거운 화면 전환을 시작하면 메뉴 닫힘이 다음 페인트까지 보이지 않아 메뉴가 멈춘 것처럼
// 느껴진다. 한 프레임을 양보한 뒤 가장 최근 이동 요청만 실행한다(연속 탭 시 앞선 요청은 취소).
export function runAfterMobileSidebarClose(callback) {
  if (typeof callback !== 'function') return;
  if (!isMobileLayout()) {
    callback();
    return;
  }

  const token = ++mobileNavigationToken;
  closeSidebarMenuForMobile();
  window.requestAnimationFrame(() => {
    window.setTimeout(() => {
      if (token !== mobileNavigationToken) return;
      callback();
    }, 0);
  });
}

export function syncSidebarMenuState() {
  const { content, btn, btnIcon } = getSidebarElements();
  if (!content || !btn) return;

  const isOpen = content.classList.contains('show');
  btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  if (btnIcon) btnIcon.className = isOpen ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
  content.dataset.open = isOpen ? '1' : '0';
  content.hidden = !isOpen;
  syncDrawerChromeState(isOpen);
}

// category/index.js가 그리는 항목들은 라벨이 <span>으로 감싸여 있지 않고 아이콘 뒤에 맨
// 텍스트로 붙어있는 경우가 많다(정적 HTML 마크업과 다름). 그래서 querySelector('span')만으론
// 라벨을 못 얻는 항목이 많아, 아이콘/버튼/배지 등 텍스트가 아닌 요소를 다 걷어낸 나머지
// 텍스트를 라벨로 취급한다.
function extractMenuItemLabel(item) {
  const clone = item.cloneNode(true);
  clone.querySelectorAll('i, button, small, div').forEach((el) => el.remove());
  return clone.textContent.replace(/\s+/g, ' ').trim();
}

// 접힘(아이콘 전용) 모드에서는 텍스트 라벨이 사라지므로, 남은 아이콘에 네이티브 title
// 툴팁으로 라벨을 대신 붙여준다. 펼침 상태에서는 라벨이 이미 보이니 title은 제거한다
// (그대로 두면 마우스오버 시 텍스트와 중복되는 브라우저 기본 툴팁이 뜬다).
function syncCollapsedSidebarTooltips(sidebar) {
  if (!sidebar) return;
  const isCollapsed = sidebar.classList.contains('collapsed');
  const items = sidebar.querySelectorAll('.menu-item, .sidebar-group-header, .sidebar-more-btn');
  items.forEach((item) => {
    if (!isCollapsed) {
      item.removeAttribute('title');
      return;
    }
    if (!item.dataset.fullLabel) {
      const label = extractMenuItemLabel(item);
      if (label) item.dataset.fullLabel = label;
    }
    if (item.dataset.fullLabel) item.setAttribute('title', item.dataset.fullLabel);
  });
}

export function toggleDesktopSidebar() {
  const sidebar = document.querySelector('.library-sidebar');
  if (sidebar) {
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    localStorage.setItem('desktopSidebarCollapsed', isCollapsed ? 'true' : 'false');
    syncCollapsedSidebarTooltips(sidebar);
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
    // 새로 그려진 항목들(플러그인 카테고리 등)에도 접힘 모드면 title 툴팁을 다시 채워준다
    syncCollapsedSidebarTooltips(document.querySelector('.library-sidebar'));
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
// 화면 맨 위에 실제로 보이는 헤더: 모바일은 로고 앱바(.sidebar-header-wrapper)를 숨기고 검색 헤더 카드(.library-header)가
// 앱바 역할을 하므로(2026-10-01) 레이아웃별로 대상을 고른다.
function getVisibleTopHeader() {
  return document.querySelector(isMobileLayout() ? '.library-header' : '.sidebar-header-wrapper');
}

function forceIosHeaderRepaint() {
  const header = getVisibleTopHeader();
  // 모바일에선 .library-sidebar 안에 position:fixed 드로어가 있어, 사이드바에 transform/opacity를 거는
  // 순간 드로어가 사이드바 기준으로 배치되거나 본문보다 아래 층에 깔린다. 모바일 앱바는 header 자체라
  // header만 다시 그려도 충분하므로 사이드바는 데스크톱에서만 건드린다.
  const sidebar = isMobileLayout() ? null : document.querySelector('.library-sidebar');
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
  if (!isMobileLayout()) return;
  const header = getVisibleTopHeader();
  const mainContent = document.querySelector('.library-main-content');
  // .sidebar-header-wrapper(로고/햄버거)는 .library-sidebar 안에 있어 실제 스크롤
  // 컨테이너인 .library-main-content 내부 스크롤과는 무관하다 - 그래서 이 rect
  // 조건만으로는 안드로이드 Chrome에서 검색창(.library-header 첫 줄)이
  // .library-main-content.scrollTop이 0이 아닌 채로 시작해 화면 밖으로 밀리는
  // 케이스를 못 잡는다(로고는 제자리인데 검색창만 가려짐). 그래서 scrollTop을
  // 별도로 항상 확인해 되돌린다.
  if (mainContent && mainContent.scrollTop !== 0) {
    mainContent.scrollTop = 0;
  }
  if (!header) return;
  const rect = header.getBoundingClientRect();
  if (!rect.width && !rect.height) return; // display:none이면 rect가 전부 0이라 "화면 밖"으로 오판
  if (rect.bottom <= 0 || rect.top < -4) {
    // y=0 대신 y=1로 스크롤: iOS Safari는 스크롤 위치가 정확히 0일 때 주소창을
    // 완전히 펼치며 페이지 콘텐츠 위에 겹쳐 그리는 버그가 있다. 1px만 남겨두면
    // 주소창이 겹치지 않으면서도 사실상 맨 위와 동일하게 보인다.
    window.scrollTo(0, 1);
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
  // 모바일↔데스크톱 전환 시 열려 있던 드로어 상태(body 클래스/inert)를 새 레이아웃 기준으로 다시 맞춘다
  const onLayoutChange = () => {
    syncMobilePopoverHost();
    if (!isMobileLayout()) setSidebarMenuOpen(false);
    else syncSidebarMenuState();
    recover();
  };

  window.addEventListener('pageshow', recover);
  window.addEventListener('focus', recover);
  window.addEventListener('resize', recover);
  window.addEventListener('orientationchange', recover);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') recover();
  });
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', onLayoutChange);
  } else if (typeof mediaQuery.addListener === 'function') {
    mediaQuery.addListener(onLayoutChange);
  }

  window.__sidebarViewportRecoveryBound = true;
}

// 모바일 드로어의 백드롭/닫기 버튼/Esc, 하단 푸터(스캔 활동·환경설정·계정) 버튼 바인딩.
// 푸터 버튼은 원래 헤더 버튼을 대신 눌러주는 프록시라 각 기능의 기존 로직을 그대로 쓴다.
function initSidebarDrawerChrome() {
  if (window.__sidebarDrawerChromeBound) return;
  window.__sidebarDrawerChromeBound = true;

  const backdrop = document.querySelector('[data-role="sidebar-drawer-backdrop"]');
  if (backdrop) backdrop.addEventListener('click', () => closeSidebarMenuForMobile());

  const closeBtn = document.querySelector('[data-role="sidebar-drawer-close"]');
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeSidebarMenuForMobile();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || !document.body.classList.contains('sidebar-drawer-open')) return;
    closeSidebarMenuForMobile();
  });

  document.querySelectorAll('[data-role="drawer-proxy"]').forEach((proxy) => {
    proxy.addEventListener('click', (e) => {
      e.preventDefault();
      // 이 클릭이 document까지 버블링되면 account_menu.js/scan_activity_status.js의 "바깥 클릭 시 닫기"
      // 리스너가 방금 연 팝오버를 바로 닫아버린다
      e.stopPropagation();
      const target = document.getElementById(proxy.dataset.target || '');
      if (!target) return;
      runAfterMobileSidebarClose(() => target.click());
    });
  });

  initSidebarMenuSearch();
}

function normalizeSearchText(value) {
  return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

// 드로어 상단 "메뉴 / 보관함 검색": 라벨 부분일치로 항목을 거른다. 그룹 안의 카테고리가 매치되면
// 그 그룹은 접혀 있어도 임시로 펼쳐 보여주고, 그룹 이름이 매치되면 하위 항목을 모두 보여준다.
function applySidebarMenuSearch() {
  const input = document.querySelector('[data-role="sidebar-menu-search"]');
  const list = document.getElementById('sidebar-categories');
  const { content } = getSidebarElements();
  if (!input || !list) return;

  const query = normalizeSearchText(input.value);
  const matches = (el) => !query || normalizeSearchText(extractMenuItemLabel(el)).includes(query);
  if (content) content.classList.toggle('is-menu-searching', Boolean(query));

  Array.from(list.children).forEach((li) => {
    if (li.matches('.sidebar-library-group')) {
      const header = li.querySelector('.sidebar-group-header');
      const groupHit = Boolean(query) && Boolean(header) && matches(header);
      let childHit = false;
      li.querySelectorAll('.sidebar-library-group-items > li').forEach((child) => {
        const hit = !query || groupHit || matches(child);
        child.classList.toggle('search-hidden', !hit);
        if (query && hit) childHit = true;
      });
      li.classList.toggle('search-hidden', Boolean(query) && !groupHit && !childHit);
      li.classList.toggle('search-expanded', Boolean(query) && (groupHit || childHit));
      return;
    }
    if (li.matches('.sidebar-section-label, .sidebar-more-btn')) return; // CSS가 검색 중 숨김
    li.classList.toggle('search-hidden', !matches(li));
  });
}

function clearSidebarMenuSearch() {
  const input = document.querySelector('[data-role="sidebar-menu-search"]');
  if (!input || !input.value) return;
  input.value = '';
  applySidebarMenuSearch();
}

function initSidebarMenuSearch() {
  const input = document.querySelector('[data-role="sidebar-menu-search"]');
  if (!input) return;
  input.addEventListener('input', applySidebarMenuSearch);
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    input.blur(); // 모바일 키보드만 내리고 결과는 그대로 둔다
  });
  // 세션 전환 등으로 목록이 다시 그려지면 현재 검색어를 다시 적용
  window.addEventListener('library:categories-rendered', applySidebarMenuSearch);
}

// 스캔 활동/계정 팝오버는 원래 .library-header 안의 버튼 옆에 있는데, 모바일은 그 헤더를 기본으로 숨기므로
// (display:none) 드로어 푸터에서 열어도 팝오버째 안 보였다. 모바일에선 두 팝오버를 body 바로 아래로 옮겨
// 하단 시트(mobile.css, position:fixed)로 띄우고, 데스크톱으로 돌아가면 원래 자리(버튼 옆 드롭다운)로 되돌린다.
// 스타일은 전부 클래스 기준이고 JS는 id로 찾으므로 위치만 바뀌어도 동작은 같다.
const RELOCATED_POPOVER_IDS = ['scan-activity-popover', 'account-menu-popover'];
const popoverHomes = new Map();

function syncMobilePopoverHost() {
  if (!document.body) return;
  const mobile = isMobileLayout();
  RELOCATED_POPOVER_IDS.forEach((id) => {
    const popover = document.getElementById(id);
    if (!popover) return;
    if (!popoverHomes.has(id)) popoverHomes.set(id, popover.parentElement);
    const home = popoverHomes.get(id);
    const host = mobile ? document.body : home;
    if (host && popover.parentElement !== host) host.appendChild(popover);
  });
}

// 모바일 헤더의 세션 선택 버튼 → 세션 전환 팝업(2열 그리드). 헤더 세션탭(#library-type-toggle-group)은 모바일에서
// 숨겨 두고 원본으로만 쓰며, 라벨/노출/활성 상태를 버튼과 팝업에 복제한다(i18n·권한별 노출을 따로 두지 않기 위함).
// 팝업 항목은 같은 data-role="library-type-toggle"이라 tab_media_library.js의 기존 위임 핸들러가 세션을 바꾼다.
function initMobileSessionMenu() {
  const trigger = document.getElementById('btn-mobile-session-select');
  const menu = document.getElementById('mobile-session-menu');
  const group = document.getElementById('library-type-toggle-group');
  if (!trigger || !menu || !group || menu.dataset.bound === '1') return;
  menu.dataset.bound = '1';
  const triggerLabel = trigger.querySelector('.mobile-session-select-label');

  const close = () => {
    if (menu.hidden) return;
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
  };
  const open = () => {
    // 팝업은 헤더 카드 폭에 맞춰 세션 버튼 바로 아래에 띄운다
    const header = trigger.closest('.library-header');
    const anchor = (header || trigger).getBoundingClientRect();
    const rect = trigger.getBoundingClientRect();
    menu.style.top = `${Math.round(rect.bottom + 6)}px`;
    menu.style.left = `${Math.round(anchor.left)}px`;
    menu.style.width = `${Math.round(anchor.width)}px`;
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
  };

  const sync = () => {
    const sources = Array.from(group.querySelectorAll('[data-role="library-type-toggle"]'));
    if (menu.children.length !== sources.length) {
      menu.replaceChildren(...sources.map((src) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mobile-session-menu-item';
        btn.setAttribute('data-role', 'library-type-toggle');
        btn.setAttribute('data-library-type', src.getAttribute('data-library-type') || 'general');
        return btn;
      }));
    }
    let visibleCount = 0;
    let activeLabel = '';
    sources.forEach((src, i) => {
      const btn = menu.children[i];
      const label = src.textContent.replace(/\s+/g, ' ').trim();
      if (btn.textContent !== label) btn.textContent = label;
      const visible = src.style.display !== 'none';
      btn.hidden = !visible;
      if (visible) visibleCount += 1;
      const active = src.classList.contains('active');
      if (active) activeLabel = label;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    if (triggerLabel && triggerLabel.textContent !== activeLabel) triggerLabel.textContent = activeLabel;
    // 세션이 하나뿐이면 고를 게 없으므로 버튼째 숨긴다
    trigger.hidden = group.style.display === 'none' || visibleCount < 2;
    if (trigger.hidden) close();
  };

  trigger.addEventListener('click', (e) => {
    e.preventDefault();
    if (menu.hidden) open(); else close();
  });
  // 항목 선택(기존 위임 핸들러가 세션 전환)이나 바깥 탭이면 팝업만 닫는다
  document.addEventListener('click', (e) => {
    if (menu.hidden) return;
    const target = e.target && typeof e.target.closest === 'function' ? e.target : null;
    if (target && target.closest('#btn-mobile-session-select')) return;
    window.requestAnimationFrame(close);
  }, true);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });
  window.addEventListener('resize', close);
  window.addEventListener('scroll', close, true);

  sync();
  new MutationObserver(sync).observe(group, {
    subtree: true, attributes: true, attributeFilter: ['class', 'style'], characterData: true, childList: true,
  });
}

export function initSidebarInteractions() {
  initSidebarToggleButton();
  initSidebarAutoClose();
  initSidebarCategorySync();
  initSidebarViewportRecovery();
  initSidebarDrawerChrome();
  initMobileSessionMenu();
  syncMobilePopoverHost();
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
      syncCollapsedSidebarTooltips(sidebar);
    }
  }
}

// HTML 인라인 onclick 등과의 하위 호환성을 위해 window 전역 공간 노출
window.toggleSidebarMenu = toggleSidebarMenu;
window.toggleDesktopSidebar = toggleDesktopSidebar;
