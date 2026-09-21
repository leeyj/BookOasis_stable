/* search_overlay.js - Enter 검색 오버레이: 제목 / 주제 / 회차 세 갈래를 가로 행으로 보여준다 */
import { state } from './state.js';
import { fetchSearchOverlay } from './api.js';
import { buildSeriesGridCard } from './ui.js';
import { buildRowNavButtonsHtml } from './scrollable_row_nav.js';

const OVERLAY_ID = 'search-overlay';
let requestToken = 0;

const SECTIONS = [
  { key: 'series', icon: 'fa-book', titleKey: 'search_overlay.section_series' },
  { key: 'topic', icon: 'fa-tags', titleKey: 'search_overlay.section_topic' },
  { key: 'episode', icon: 'fa-list-ol', titleKey: 'search_overlay.section_episode' },
];

function t(key, params) {
  return window.i18n ? window.i18n.t(key, params) : key;
}

export function closeSearchOverlay() {
  requestToken += 1;
  document.getElementById(OVERLAY_ID)?.remove();
  document.removeEventListener('keydown', onOverlayKeydown, true);
}

function onOverlayKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    closeSearchOverlay();
  }
}

function buildSection(section, items, query) {
  const wrap = document.createElement('section');
  wrap.className = 'search-overlay-section';
  const rowId = `search-overlay-row-${section.key}`;

  const heading = document.createElement('div');
  heading.className = 'search-overlay-section-head';
  heading.innerHTML = `
    <h3 class="search-overlay-section-title"><i class="fa-solid ${section.icon}"></i>
      <span data-role="title"></span> <span class="search-overlay-count"></span></h3>
    ${items.length ? buildRowNavButtonsHtml(rowId, t('common.prev'), t('common.next')) : ''}
  `;
  heading.querySelector('[data-role="title"]').textContent = `${t(section.titleKey)} : ${query}`;
  heading.querySelector('.search-overlay-count').textContent = items.length ? `(${items.length})` : '';
  wrap.appendChild(heading);

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'search-overlay-empty';
    empty.textContent = t('search_overlay.empty');
    wrap.appendChild(empty);
    return wrap;
  }

  const row = document.createElement('div');
  row.className = 'dashboard-row-container';
  row.id = rowId;
  items.forEach((item) => row.appendChild(buildSeriesGridCard(item)));
  wrap.appendChild(row);
  return wrap;
}

export async function openSearchOverlay(rawQuery) {
  const query = String(rawQuery || '').trim();
  if (!query) return;

  closeSearchOverlay();
  const token = ++requestToken;

  const overlay = document.createElement('div');
  overlay.id = OVERLAY_ID;
  overlay.className = 'search-overlay';
  overlay.innerHTML = `
    <div class="search-overlay-panel" role="dialog" aria-modal="true">
      <div class="search-overlay-header">
        <h2 class="search-overlay-title"><i class="fa-solid fa-magnifying-glass"></i> <span data-role="search-overlay-query"></span></h2>
        <button type="button" class="search-overlay-close" data-role="search-overlay-close" aria-label="close">&times;</button>
      </div>
      <div class="search-overlay-body" data-role="search-overlay-body">
        <div class="loading-spinner loading-spinner--compact">${t('search_overlay.loading')}</div>
      </div>
    </div>
  `;
  overlay.querySelector('[data-role="search-overlay-query"]').textContent = query;
  document.body.appendChild(overlay);
  document.addEventListener('keydown', onOverlayKeydown, true);

  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.closest('[data-role="search-overlay-close"]')) {
      closeSearchOverlay();
      return;
    }
    // 카드를 눌러 상세로 이동하면 오버레이도 닫는다 (카드 자체 핸들러가 먼저 돌도록 한 틱 뒤에 닫음)
    if (event.target.closest('.book-card')) setTimeout(closeSearchOverlay, 0);
  });

  const body = overlay.querySelector('[data-role="search-overlay-body"]');
  try {
    const libraryId = ['home', 'history', 'favorite'].includes(String(state.currentLibraryId))
      ? 'all' : state.currentLibraryId;
    const data = await fetchSearchOverlay({ type: state.currentLibraryType, libraryId, query });
    if (token !== requestToken) return;
    if (!data || !data.success) throw new Error((data && data.error) || 'search failed');
    body.innerHTML = '';
    SECTIONS.forEach((section) => {
      // 오디오북/영상에는 주제(장르/태그) 검색이 없으므로 행 자체를 숨긴다
      if (section.key === 'topic' && !['general', 'adult'].includes(state.currentLibraryType)) return;
      body.appendChild(buildSection(section, data[section.key] || [], query));
    });
  } catch (e) {
    if (token !== requestToken) return;
    console.error('[SearchOverlay] 검색 실패:', e);
    body.innerHTML = `<div class="loading-spinner loading-spinner--compact">${t('search_overlay.load_fail')}</div>`;
  }
}

window.openSearchOverlay = openSearchOverlay;
window.closeSearchOverlay = closeSearchOverlay;
