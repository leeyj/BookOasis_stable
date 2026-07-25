function getSystemCategoryLabel(id) {
  if (!window.i18n || typeof window.i18n.t !== 'function') return String(id || '');
  if (id === 'home') return window.i18n.t('header.title') || '도서 보관함';
  if (id === 'history') return window.i18n.t('category.history') || '최근 읽은 도서';
  if (id === 'favorite') return window.i18n.t('category.favorite') || '즐겨찾기';
  if (id === 'plugins') return window.i18n.t('category.plugins') || '플러그인 데스크';
  if (id === 'all') return window.i18n.t('category.all') || '전체 도서 목록';
  if (id === 'settings') return window.i18n.t('sidebar.settings') || '환경설정';
  return String(id || '');
}

export function updateCurrentCategoryIndicator(id, activeItem = null) {
  const indicator = document.getElementById('current-category-indicator');
  if (!indicator) return;

  const resolvedItem = activeItem || Array.from(document.querySelectorAll('#sidebar-categories .menu-item'))
    .find(item => String(item.dataset.id) === String(id));

  let label = '';
  if (resolvedItem && resolvedItem.dataset.type === 'custom') {
    label = String(resolvedItem.dataset.name || '').trim();
  }
  if (!label && ['home', 'history', 'favorite', 'plugins', 'all', 'settings'].includes(String(id))) {
    label = getSystemCategoryLabel(id);
  }
  if (!label && resolvedItem) {
    label = String(resolvedItem.textContent || '').replace(/\s+/g, ' ').trim();
  }
  if (!label) label = String(id || '');

  indicator.textContent = label;
  indicator.title = label;
}