// category_info_popover.js – 헤더 햄버거 옆 "..." 버튼: 현재 선택된 카테고리의
// ID/이름/등록 경로/시리즈 수/도서 권수를 보여주는 팝오버 (마우스 오버 또는 클릭으로 개폐)
import { escapeHtml } from './utils/html.js';
import { state } from './state.js';
import { fetchBooksTotals } from './api.js';

const HOVER_OPEN_DELAY = 200;
const HOVER_CLOSE_DELAY = 250;

let popoverEl = null;
let hoverOpenTimer = null;
let hoverCloseTimer = null;
let requestSerial = 0;

function getTriggerButtons() {
  return [document.getElementById('btn-category-info')].filter(Boolean);
}

function getActiveCategoryElement() {
  const targetId = String(state.currentLibraryId || '');
  // data-category-id만 본다 (data-id 폴백 금지) - 그룹 폴더 토글 버튼도 .menu-item이고
  // data-id에 그룹 ID를 갖고 있어서, 그 ID가 우연히 현재 카테고리 ID와 같으면(서로 다른
  // 테이블의 독립적인 auto-increment라 언제든 충돌 가능) 그룹 헤더가 잘못 매칭돼
  // "그룹명+배지숫자"가 카테고리 이름인 것처럼 표시되는 버그가 있었다.
  return Array.from(document.querySelectorAll('#sidebar-categories .menu-item[data-category-id]'))
    .find((item) => String(item.dataset.categoryId || '') === targetId) || null;
}

function ensurePopoverEl() {
  if (popoverEl) return popoverEl;
  popoverEl = document.createElement('div');
  popoverEl.id = 'category-info-popover';
  popoverEl.className = 'category-info-popover';
  popoverEl.hidden = true;
  popoverEl.addEventListener('mouseenter', cancelHoverClose);
  popoverEl.addEventListener('mouseleave', scheduleHoverClose);
  document.body.appendChild(popoverEl);
  return popoverEl;
}

function bookCountLabel() {
  if (state.currentLibraryType === 'audiobook') return i18n.t('book_list.info_track_count');
  if (state.currentLibraryType === 'video') return i18n.t('book_list.info_episode_count');
  return i18n.t('book_list.info_book_count');
}

function renderPopoverContent(item) {
  const popover = ensurePopoverEl();
  const isCustomCategory = !!(item && item.dataset.type === 'custom');

  if (!isCustomCategory) {
    const label = item ? String(item.textContent || '').replace(/\s+/g, ' ').trim() : '';
    popover.innerHTML = `
      <div class="category-info-popover-title"><i class="lc lc-info"></i> ${escapeHtml(label || i18n.t('book_list.category_info_title'))}</div>
      <div class="category-info-popover-empty">${i18n.t('book_list.info_none')}</div>
    `;
    return;
  }

  const id = item.dataset.id || '';
  const name = item.dataset.name || '';
  const path = item.dataset.path || '';
  popover.innerHTML = `
    <div class="category-info-popover-title"><i class="${window.boIcon(escapeHtml(item.dataset.icon || 'fa-book'))}" style="color: ${escapeHtml(item.dataset.color || 'var(--app-accent)')};"></i> ${escapeHtml(name)}</div>
    <dl style="margin: 0;">
      <div class="category-info-popover-row"><dt>ID</dt><dd>${escapeHtml(id)}</dd></div>
      <div class="category-info-popover-row"><dt>${i18n.t('book_list.info_name')}</dt><dd>${escapeHtml(name)}</dd></div>
      <div class="category-info-popover-row"><dt>${i18n.t('book_list.info_path')}</dt><dd>${escapeHtml(path)}</dd></div>
      <div class="category-info-popover-row"><dt>${i18n.t('book_list.info_series_count')}</dt><dd data-role="category-info-series-count">${i18n.t('tv.loading')}</dd></div>
      <div class="category-info-popover-row"><dt>${escapeHtml(bookCountLabel())}</dt><dd data-role="category-info-book-count">${i18n.t('tv.loading')}</dd></div>
    </dl>
  `;

  const mySerial = ++requestSerial;
  fetchBooksTotals({ type: state.currentLibraryType, libraryId: id })
    .then((data) => {
      if (mySerial !== requestSerial || popover.hidden) return;
      const seriesEl = popover.querySelector('[data-role="category-info-series-count"]');
      const bookEl = popover.querySelector('[data-role="category-info-book-count"]');
      if (data && data.success) {
        if (seriesEl) seriesEl.textContent = Number(data.total_series_count || 0).toLocaleString();
        if (bookEl) bookEl.textContent = Number(data.total_book_count || 0).toLocaleString();
      } else {
        if (seriesEl) seriesEl.textContent = '-';
        if (bookEl) bookEl.textContent = '-';
      }
    })
    .catch(() => {
      if (mySerial !== requestSerial || popover.hidden) return;
      const seriesEl = popover.querySelector('[data-role="category-info-series-count"]');
      const bookEl = popover.querySelector('[data-role="category-info-book-count"]');
      if (seriesEl) seriesEl.textContent = '-';
      if (bookEl) bookEl.textContent = '-';
    });
}

function positionPopover(triggerBtn) {
  const popover = ensurePopoverEl();
  const rect = triggerBtn.getBoundingClientRect();
  const margin = 8;
  popover.style.visibility = 'hidden';
  popover.hidden = false;
  const popoverWidth = popover.offsetWidth;
  let left = rect.left;
  if (left + popoverWidth > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - margin - popoverWidth);
  }
  popover.style.top = `${Math.round(rect.bottom + 8)}px`;
  popover.style.left = `${Math.round(left)}px`;
  popover.style.visibility = '';
}

function openPopover(triggerBtn) {
  cancelHoverClose();
  const item = getActiveCategoryElement();
  renderPopoverContent(item);
  positionPopover(triggerBtn);
  getTriggerButtons().forEach((btn) => btn.setAttribute('aria-expanded', String(btn === triggerBtn)));
}

function closePopover() {
  if (!popoverEl || popoverEl.hidden) return;
  popoverEl.hidden = true;
  getTriggerButtons().forEach((btn) => btn.setAttribute('aria-expanded', 'false'));
}

function cancelHoverClose() {
  if (hoverCloseTimer) {
    clearTimeout(hoverCloseTimer);
    hoverCloseTimer = null;
  }
}

function scheduleHoverClose() {
  cancelHoverClose();
  hoverCloseTimer = setTimeout(closePopover, HOVER_CLOSE_DELAY);
}

function cancelHoverOpen() {
  if (hoverOpenTimer) {
    clearTimeout(hoverOpenTimer);
    hoverOpenTimer = null;
  }
}

function bindTrigger(btn) {
  if (!btn || btn.dataset.categoryInfoBound === '1') return;
  btn.dataset.categoryInfoBound = '1';

  btn.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    cancelHoverOpen();
    const isOpen = popoverEl && !popoverEl.hidden && btn.getAttribute('aria-expanded') === 'true';
    if (isOpen) {
      closePopover();
    } else {
      openPopover(btn);
    }
  });

  btn.addEventListener('mouseenter', () => {
    cancelHoverClose();
    cancelHoverOpen();
    hoverOpenTimer = setTimeout(() => openPopover(btn), HOVER_OPEN_DELAY);
  });

  btn.addEventListener('mouseleave', () => {
    cancelHoverOpen();
    scheduleHoverClose();
  });
}

function initCategoryInfoPopover() {
  getTriggerButtons().forEach(bindTrigger);
  document.addEventListener('click', (event) => {
    if (popoverEl && !popoverEl.hidden && !popoverEl.contains(event.target) && !getTriggerButtons().some((btn) => btn.contains(event.target))) {
      closePopover();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closePopover();
  });
  window.addEventListener('library:category-selected', closePopover);
  window.addEventListener('resize', closePopover);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCategoryInfoPopover);
} else {
  initCategoryInfoPopover();
}
