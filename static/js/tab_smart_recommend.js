/* tab_smart_recommend.js - 최근 읽은 시리즈 기준 장르/태그 겹침 "스마트 추천" UI 렌더러 */
import { state } from './state.js';
import * as api from './api.js';
import { createBookCard } from './ui.js';
import { openBookDetail } from './modal.js';
import { getBookCoverSrc } from './cover_fallback.js';
import { buildRowNavButtonsHtml } from './scrollable_row_nav.js';

const RECENT_TAB_COUNT = 8;

let activeSeriesKey = null;

function seriesKey(item) {
  return `${item.library_id}::${item.series_name}`;
}

export async function renderSmartRecommendView() {
  const container = document.getElementById('books-list-container') || document.getElementById('media-library-grid');
  const indicator = document.getElementById('current-category-indicator');
  const countBadge = document.getElementById('library-total-count');
  const scrollSpinner = document.getElementById('infinite-scroll-spinner');
  if (scrollSpinner) scrollSpinner.style.display = 'none';

  if (indicator) indicator.innerText = i18n.t('smart_recommend.title');
  if (countBadge) countBadge.innerText = '';

  if (!container) return;
  container.innerHTML = `
    <div class="smart-rec-page">
      <div id="smart-rec-tabs" class="smart-rec-tabs-bar">
        <div class="smart-rec-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('smart_recommend.loading')}</div>
      </div>
      <div id="smart-rec-body"></div>
    </div>
  `;

  try {
    const data = await api.fetchReadingHistory(state.currentLibraryType || 'general');
    if (!data.success) {
      document.getElementById('smart-rec-tabs').innerHTML = `<div class="smart-rec-error">${i18n.t('smart_recommend.error', { error: data.error || '' })}</div>`;
      return;
    }

    const recentSeries = [];
    const seen = new Set();
    for (const item of (data.books || [])) {
      const key = seriesKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      recentSeries.push(item);
      if (recentSeries.length >= RECENT_TAB_COUNT) break;
    }

    if (recentSeries.length === 0) {
      document.getElementById('smart-rec-tabs').innerHTML = '';
      document.getElementById('smart-rec-body').innerHTML = `
        <div class="smart-rec-empty-state">
          <i class="fa-solid fa-wand-magic-sparkles smart-rec-empty-state-icon"></i>
          <h4 class="smart-rec-empty-state-title">${i18n.t('smart_recommend.no_history_title')}</h4>
          <p class="smart-rec-empty-state-desc">${i18n.t('smart_recommend.no_history_desc')}</p>
        </div>
      `;
      return;
    }

    activeSeriesKey = seriesKey(recentSeries[0]);
    renderTabs(recentSeries);
    await renderRecommendationsFor(recentSeries[0]);
  } catch (err) {
    document.getElementById('smart-rec-tabs').innerHTML = `<div class="smart-rec-error">${i18n.t('smart_recommend.error', { error: err.message })}</div>`;
  }
}

function renderTabs(recentSeries) {
  const tabsEl = document.getElementById('smart-rec-tabs');
  if (!tabsEl) return;

  tabsEl.innerHTML = recentSeries.map((item) => {
    const key = seriesKey(item);
    const isActive = key === activeSeriesKey;
    const title = item.series_alias || item.series_name || '';
    const cover = getBookCoverSrc({
      coverImage: item.cover_image,
      title,
      format: item.file_format,
      seed: item.id || item.representative_book_id || title
    });
    return `
      <button class="smart-rec-tab${isActive ? ' active' : ''}" data-key="${key}">
        <img src="${cover}" alt="${escapeHtml(title)}" data-title="${escapeHtml(title)}" data-format="${escapeHtml(item.file_format || '')}"
          onerror="window.handleCoverError(this)" class="smart-rec-tab-cover">
        <span class="smart-rec-tab-title">${escapeHtml(title)}</span>
      </button>
    `;
  }).join('');

  tabsEl.querySelectorAll('.smart-rec-tab').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const key = btn.getAttribute('data-key');
      if (key === activeSeriesKey) return;
      const target = recentSeries.find((item) => seriesKey(item) === key);
      if (!target) return;
      activeSeriesKey = key;
      renderTabs(recentSeries);
      await renderRecommendationsFor(target);
    });
  });
}

async function renderRecommendationsFor(seriesItem) {
  const bodyEl = document.getElementById('smart-rec-body');
  if (!bodyEl) return;
  bodyEl.innerHTML = `<div class="smart-rec-loading smart-rec-loading--centered"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('smart_recommend.loading')}</div>`;

  try {
    const data = await api.fetchSmartRecommendations(state.currentLibraryType || 'general', seriesItem.series_name, seriesItem.library_id);
    if (!data.success) {
      bodyEl.innerHTML = `<div class="smart-rec-error">${i18n.t('smart_recommend.error', { error: data.error || '' })}</div>`;
      return;
    }

    bodyEl.innerHTML = '';
    bodyEl.appendChild(buildSection('smart-rec-genre', i18n.t('smart_recommend.similar_genre'), 'fa-tags', data.genre || [], data.genre_is_fallback));
    bodyEl.appendChild(buildSection('smart-rec-tags', i18n.t('smart_recommend.similar_tags'), 'fa-hashtag', data.tags || [], data.tags_is_fallback));
  } catch (err) {
    bodyEl.innerHTML = `<div class="smart-rec-error">${i18n.t('smart_recommend.error', { error: err.message })}</div>`;
  }
}

function buildSection(rowId, title, iconClass, items, isFallback) {
  const section = document.createElement('div');
  section.className = 'smart-rec-section';

  const heading = document.createElement('div');
  heading.className = 'smart-rec-section-header';
  heading.innerHTML = `
    <h3 class="smart-rec-section-title">
      <i class="fa-solid ${iconClass}"></i> ${title}
      ${isFallback ? `<span class="smart-rec-fallback-note">${i18n.t('smart_recommend.fallback_note')}</span>` : ''}
    </h3>
    ${buildRowNavButtonsHtml(rowId, i18n.t('common.prev'), i18n.t('common.next'))}
  `;
  section.appendChild(heading);

  if (items.length === 0) {
    heading.querySelector('.section-nav-btns').classList.add('section-nav-btns--hidden');
    const empty = document.createElement('div');
    empty.className = 'smart-rec-section-empty';
    empty.textContent = i18n.t('smart_recommend.empty');
    section.appendChild(empty);
    return section;
  }

  const row = document.createElement('div');
  row.className = 'dashboard-row-container';
  row.id = rowId;

  items.forEach((item) => {
    const card = createBookCard({
      id: item.id,
      representative_book_id: item.id,
      series_name: item.series_name,
      cover_image: item.cover_image,
      file_format: item.file_format,
      library_id: item.library_id,
    }, {
      onPrimaryClick: (e) => openBookDetail(e, item.series_name, item.library_id ?? 'all', item.id, item.series_name),
    });
    row.appendChild(card);
  });

  section.appendChild(row);
  return section;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
