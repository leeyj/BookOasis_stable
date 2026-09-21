// card_info_menu.js – 그리드 카드 좌측 하단 "..." 버튼(관리자 전용) 클릭 시 뜨는 작은 정보 메뉴
// (도서 경로 / 카테고리 / 추가일 / 포맷). 목록 응답에는 이 값들을 싣지 않고, 클릭할 때 한 건만 조회한다.
import { state } from './state.js';
import { fetchCardInfo } from './api.js';

const MENU_ID = 'card-info-menu';
let requestToken = 0;
let openButton = null;

function t(key, params) {
  const text = window.i18n ? window.i18n.t(key, params) : key;
  return text;
}

export function closeCardInfoMenu() {
  requestToken += 1;
  openButton = null;
  document.getElementById(MENU_ID)?.remove();
  document.removeEventListener('pointerdown', onOutsidePointerDown, true);
  document.removeEventListener('keydown', onKeydown, true);
  window.removeEventListener('scroll', closeCardInfoMenu, true);
  window.removeEventListener('resize', closeCardInfoMenu);
}

function onOutsidePointerDown(event) {
  const menu = document.getElementById(MENU_ID);
  if (menu && !menu.contains(event.target) && !event.target.closest?.('[data-role="card-info-toggle"]')) {
    closeCardInfoMenu();
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') closeCardInfoMenu();
}

function resolveCategoryLabel(libraryId) {
  const item = Array.from(document.querySelectorAll('#sidebar-categories .menu-item[data-category-id]'))
    .find((el) => String(el.dataset.categoryId) === String(libraryId));
  if (!item) return '';
  const name = item.dataset.name || '';
  const code = item.dataset.contentKind || '';
  const kind = (state.libraryKinds || []).find((k) => String(k.code) === String(code));
  const kindLabel = kind ? kind.name : (code && code !== 'unspecified' ? code : t('card_info.unspecified'));
  return `${name} · ${kindLabel}`;
}

function formatLabel(formats) {
  const list = (formats || []).map((f) => String(f).toUpperCase());
  if (list.length <= 1) return list[0] || '-';
  return t('card_info.formats_more', { first: list[0], count: list.length - 1 });
}

function addedLabel(value) {
  const text = String(value || '');
  return text ? text.slice(0, 10) : '-';
}

function fillRows(menu, info, libraryId) {
  const rows = [
    ['card_info.path', info.physical_path || '-'],
    ['card_info.category', resolveCategoryLabel(libraryId) || '-'],
    ['card_info.added', addedLabel(info.added_at)],
    ['card_info.format', formatLabel(info.formats)],
  ];
  const dl = document.createElement('dl');
  rows.forEach(([labelKey, value]) => {
    const dt = document.createElement('dt');
    dt.textContent = t(labelKey);
    const dd = document.createElement('dd');
    dd.textContent = value;
    dl.append(dt, dd);
  });
  menu.replaceChildren(dl);
}

function positionMenu(menu, button) {
  const rect = button.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  const margin = 8;
  let left = rect.left;
  let top = rect.top - menuRect.height - 6;
  if (top < margin) top = rect.bottom + 6;
  left = Math.max(margin, Math.min(left, window.innerWidth - menuRect.width - margin));
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}

export async function toggleCardInfoMenu(button) {
  if (openButton === button) {
    closeCardInfoMenu();
    return;
  }
  closeCardInfoMenu();

  const card = button.closest('.book-card');
  if (!card) return;
  const token = ++requestToken;
  openButton = button;

  const menu = document.createElement('div');
  menu.id = MENU_ID;
  menu.className = 'card-info-menu';
  menu.textContent = t('card_info.loading');
  document.body.appendChild(menu);
  positionMenu(menu, button);
  document.addEventListener('pointerdown', onOutsidePointerDown, true);
  document.addEventListener('keydown', onKeydown, true);
  window.addEventListener('scroll', closeCardInfoMenu, true);
  window.addEventListener('resize', closeCardInfoMenu);

  const isSeries = card.dataset.markUnreadScope === 'series' && card.dataset.seriesName;
  const libraryId = card.dataset.libraryId || '';
  try {
    const data = await fetchCardInfo({
      type: state.currentLibraryType,
      bookId: card.dataset.bookId,
      seriesName: isSeries ? card.dataset.seriesName : '',
      libraryId: isSeries ? libraryId : '',
    });
    if (token !== requestToken) return;
    if (!data || !data.success) throw new Error((data && data.error) || 'card-info failed');
    fillRows(menu, data, libraryId);
    positionMenu(menu, button);
  } catch (e) {
    if (token !== requestToken) return;
    console.error('[CardInfo] 조회 실패:', e);
    menu.textContent = t('card_info.load_fail');
  }
}
