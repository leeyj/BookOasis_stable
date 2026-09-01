// account_menu.js – 상단 헤더의 계정 아이콘 팝오버(사용자명/로그아웃) 개폐 제어
// scan_activity_status.js의 팝오버 패턴을 그대로 재사용한다.

function setAccountMenuOpen(open) {
  const button = document.getElementById('btn-account-menu');
  const popover = document.getElementById('account-menu-popover');
  if (!button || !popover) return;
  popover.hidden = !open;
  button.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function initAccountMenuPopover() {
  const button = document.getElementById('btn-account-menu');
  const popover = document.getElementById('account-menu-popover');
  if (!button || !popover || button.dataset.bound === '1') return;
  button.dataset.bound = '1';

  button.addEventListener('click', event => {
    event.stopPropagation();
    setAccountMenuOpen(popover.hidden);
  });
  popover.addEventListener('click', event => event.stopPropagation());
  document.addEventListener('click', () => setAccountMenuOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setAccountMenuOpen(false);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAccountMenuPopover);
} else {
  initAccountMenuPopover();
}
