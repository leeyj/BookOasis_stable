// 라이브러리 도서 카드 선택 상태와 Ctrl/Shift 다중 선택을 관리합니다.
import { state } from './state.js';

const selectedCards = new Map();
let selectionScope = '';
let selectionAnchor = null;
let toolbar = null;

function getScope() {
  return `${state.currentLibraryType || 'general'}:${state.currentLibraryId ?? ''}`;
}

function getSelectableCard(target) {
  const card = target && typeof target.closest === 'function'
    ? target.closest('.book-card')
    : null;
  return card && card.querySelector('[data-role="book-card-select-toggle"]')
    ? card
    : null;
}

function targetFromCard(card) {
  const id = Number.parseInt(card.dataset.bookId || '', 10);
  if (!Number.isFinite(id) || id <= 0) return null;

  const rawLibraryId = card.dataset.libraryId || '';
  const parsedLibraryId = Number.parseInt(rawLibraryId, 10);
  return {
    id,
    title: String(card.dataset.title || '도서'),
    markUnreadScope: card.dataset.markUnreadScope || 'book',
    seriesName: String(card.dataset.seriesName || '').trim(),
    libraryId: Number.isFinite(parsedLibraryId) ? parsedLibraryId : null,
    fileFormat: String(card.dataset.fileFormat || '').toLowerCase(),
    coverAlign: card.dataset.coverAlign || 'center',
    isVolumeDetail: false,
    selectionKey: `${getScope()}:${parsedLibraryId || ''}:${id}`,
  };
}

function setCardSelected(card, selected) {
  card.classList.toggle('book-card--selected', selected);
  const button = card.querySelector('[data-role="book-card-select-toggle"]');
  if (button) {
    button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    button.setAttribute('aria-label', selected ? '선택 해제' : '작품 선택');
  }
}

function ensureToolbar() {
  if (toolbar && toolbar.isConnected) return toolbar;

  toolbar = document.createElement('div');
  toolbar.id = 'book-selection-toolbar';
  toolbar.className = 'book-selection-toolbar';
  toolbar.setAttribute('role', 'status');
  toolbar.setAttribute('aria-live', 'polite');

  const summary = document.createElement('span');
  summary.className = 'book-selection-toolbar-summary';
  summary.dataset.role = 'book-selection-summary';

  const hint = document.createElement('span');
  hint.className = 'book-selection-toolbar-hint';
  hint.textContent = '선택한 작품을 우클릭해 일괄 작업';

  const clearButton = document.createElement('button');
  clearButton.type = 'button';
  clearButton.className = 'book-selection-clear';
  clearButton.dataset.role = 'book-selection-clear';
  clearButton.innerHTML = '<i class="fa-solid fa-xmark" aria-hidden="true"></i><span>선택 해제</span>';

  toolbar.append(summary, hint, clearButton);
  document.body.append(toolbar);
  return toolbar;
}

function updateToolbar() {
  const count = selectedCards.size;
  const element = ensureToolbar();
  element.hidden = count === 0;
  // 다중 선택 중에는 카드 정보 버튼 등 개별 카드 보조 버튼을 숨긴다 (CSS에서 이 클래스를 참조)
  document.body.classList.toggle('book-selection-active', count > 0);
  const summary = element.querySelector('[data-role="book-selection-summary"]');
  if (summary) summary.textContent = `${count}개 선택`;
}

function setSelected(card, selected) {
  const target = targetFromCard(card);
  if (!target) return;

  if (selected) {
    selectedCards.set(target.selectionKey, { ...target, card });
  } else {
    selectedCards.delete(target.selectionKey);
  }
  setCardSelected(card, selected);
  updateToolbar();
}

function ensureCurrentScope() {
  const scope = getScope();
  if (selectionScope && selectionScope !== scope) clearBookSelection();
  selectionScope = scope;
}

function selectRange(anchorCard, endCard) {
  const grid = endCard.closest('#books-list-container');
  if (!grid) return;
  const cards = Array.from(grid.querySelectorAll('.book-card'))
    .filter(card => card.querySelector('[data-role="book-card-select-toggle"]'));
  const start = cards.indexOf(anchorCard);
  const end = cards.indexOf(endCard);
  if (start < 0 || end < 0) {
    setSelected(endCard, true);
    return;
  }

  const first = Math.min(start, end);
  const last = Math.max(start, end);
  for (let index = first; index <= last; index += 1) setSelected(cards[index], true);
}

export function getSelectedBookTargets() {
  ensureCurrentScope();
  return Array.from(selectedCards.values()).map(({ card, ...target }) => target);
}

export function isBookCardSelected(card) {
  const target = card ? targetFromCard(card) : null;
  return !!target && selectedCards.has(target.selectionKey);
}

export function syncBookSelectionCard(card) {
  if (!card || !card.querySelector('[data-role="book-card-select-toggle"]')) return;
  const target = targetFromCard(card);
  setCardSelected(card, !!target && selectedCards.has(target.selectionKey));
}

export function clearBookSelection() {
  selectedCards.forEach(({ card }) => {
    if (card) setCardSelected(card, false);
  });
  selectedCards.clear();
  selectionAnchor = null;
  updateToolbar();
}

document.addEventListener('click', (event) => {
  const clearButton = event.target.closest?.('[data-role="book-selection-clear"]');
  if (clearButton) {
    event.preventDefault();
    clearBookSelection();
    return;
  }

  const selectionButton = event.target.closest?.('[data-role="book-card-select-toggle"]');
  if (selectionButton) {
    const card = getSelectableCard(selectionButton);
    if (!card) return;
    event.preventDefault();
    event.stopPropagation();
    ensureCurrentScope();
    const selected = isBookCardSelected(card);
    if (event.shiftKey && selectionAnchor) {
      selectRange(selectionAnchor, card);
    } else {
      setSelected(card, !selected);
      selectionAnchor = card;
    }
    return;
  }

  const card = getSelectableCard(event.target);
  if (!card || event.button !== 0) return;

  const usesMultiSelect = event.ctrlKey || event.metaKey || event.shiftKey;
  if (usesMultiSelect) {
    event.preventDefault();
    event.stopPropagation();
    ensureCurrentScope();
    if (event.shiftKey && selectionAnchor) {
      selectRange(selectionAnchor, card);
    } else {
      setSelected(card, !isBookCardSelected(card));
      selectionAnchor = card;
    }
    return;
  }

  if (selectedCards.size > 0) clearBookSelection();
}, true);

document.addEventListener('contextmenu', (event) => {
  const card = getSelectableCard(event.target);
  if (card && selectedCards.size > 0) ensureCurrentScope();
}, true);
