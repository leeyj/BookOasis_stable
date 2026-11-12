// table_view/index.js – 관리자 테이블 뷰(시리즈 한 줄 = 표 한 행). 처음 표 모드를 켤 때 불러온다.
// 정렬·빈 값 필터·컬럼 선택·셀 편집·CSV 내보내기. 서버: /api/admin/series-table (api/routes/series_table_routes.py)
// 셀 값은 전부 textContent로 넣는다(메타 값은 사용자 입력이라 innerHTML 금지).
import { state } from '../state.js';
import { showToast } from '../view_manager.js';
import {
  COLUMN_DEFS, DEFAULT_SORT, VISIBLE_COLUMNS_STORAGE_KEY, BOOKS_LV_OPTIONS, PUBLICATION_STATUS_OPTIONS,
  getColumn, normalizeVisibleKeys, toggleVisibleKey, nextSort, normalizeMissingKeys, buildQuery, formatCellText,
} from './columns.js';
import { isTableModeActive } from './mode.js';
import { getBookCoverSrc, handleCoverError } from '../cover_fallback.js';

const PAGE_SIZE = 100;

const view = {
  rows: [],
  total: null,
  page: 0,
  hasMore: false,
  loading: false,
  serial: 0,          // 늦게 도착한 옛 응답을 버리기 위한 요청 번호
  sort: { ...DEFAULT_SORT },
  missing: [],
  visible: loadVisibleKeys(),
  editing: null,      // { td, row, col, input }
  openMenu: null,
  observer: null,
};

function t(key, fallback, vars) {
  const text = window.i18n ? window.i18n.t(key, vars) : '';
  return text && text !== key ? text : fallback;
}

function loadVisibleKeys() {
  let stored = null;
  try {
    stored = localStorage.getItem(VISIBLE_COLUMNS_STORAGE_KEY);
  } catch (e) {}
  return normalizeVisibleKeys(stored);
}

function saveVisibleKeys() {
  try {
    localStorage.setItem(VISIBLE_COLUMNS_STORAGE_KEY, JSON.stringify(view.visible));
  } catch (e) {}
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function icon(name) {
  const node = el('i', `lc ${name}`);
  node.setAttribute('aria-hidden', 'true');
  return node;
}

function columnLabel(col) {
  return t(col.labelKey, col.fallback);
}

function requestFilters() {
  return {
    type: state.currentLibraryType,
    libraryId: state.currentLibraryId,
    sort: view.sort,
    missing: view.missing,
    search: state.searchQuery || '',
    genres: state.filterGenres || [],
    tags: state.filterTags || [],
    filterMode: state.filterMode,
  };
}

function root() {
  return document.getElementById('books-table-view');
}

// ───────── 틀(도구 줄 + 표) ─────────

function ensureShell() {
  const container = root();
  if (!container) return null;
  if (container.dataset.ready === '1') return container;
  container.textContent = '';

  const bar = el('div', 'series-table-bar');
  bar.appendChild(el('div', 'series-table-status'));
  const actions = el('div', 'series-table-actions');
  actions.appendChild(menuButton('missing', 'lc-filter', t('table_view.missing_filter', '빈 값 필터')));
  actions.appendChild(menuButton('columns', 'lc-columns-3', t('table_view.columns', '컬럼')));
  const exportBtn = el('button', 'library-list-btn');
  exportBtn.type = 'button';
  exportBtn.dataset.act = 'export';
  exportBtn.title = t('table_view.export_title', '지금 조건에 맞는 전체 행을 CSV로 내려받기 (확인용 - 다시 가져오기는 지원하지 않습니다)');
  exportBtn.append(icon('lc-download'), el('span', '', 'CSV'));
  actions.appendChild(exportBtn);
  bar.appendChild(actions);

  // 수정 방법 안내: 몇 개는 셀에서, 많은 양은 kavita.yaml + 스캔. 셀을 고치면 잠기고 잠긴 시리즈엔 yaml이 안 들어간다
  const hint = el('p', 'series-table-hint', t('table_view.edit_hint',
    '셀을 고치면 그 시리즈가 잠기고, 잠긴 시리즈는 스캔이 메타를 덮어쓰지 않습니다(kavita.yaml 포함). 많은 시리즈를 한 번에 정리할 때는 시리즈 폴더에 kavita.yaml을 넣고 스캔하세요. 이미 잠긴 시리즈는 자물쇠를 먼저 풀어야 반영됩니다.'));

  const scroll = el('div', 'series-table-scroll');
  const table = el('table', 'series-table');
  table.append(el('thead'), el('tbody'));
  scroll.appendChild(table);

  const more = el('div', 'series-table-more');

  container.append(bar, hint, scroll, more);
  container.dataset.ready = '1';

  bar.addEventListener('click', onBarClick);
  table.querySelector('thead').addEventListener('click', onHeadClick);
  const tbody = table.querySelector('tbody');
  tbody.addEventListener('click', onBodyClick);
  tbody.addEventListener('keydown', onBodyKeydown);
  document.addEventListener('click', onDocumentClick);

  view.observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) loadNextPage();
  }, { rootMargin: '600px 0px' });
  view.observer.observe(more);
  return container;
}

function menuButton(name, iconName, label) {
  const wrap = el('div', 'series-table-menu-wrap');
  const btn = el('button', 'library-list-btn');
  btn.type = 'button';
  btn.dataset.act = name;
  btn.setAttribute('aria-haspopup', 'true');
  btn.setAttribute('aria-expanded', 'false');
  btn.append(icon(iconName), el('span', '', label), icon('lc-chevron-down library-list-btn-caret'));
  const menu = el('div', 'series-table-menu');
  menu.dataset.menu = name;
  menu.hidden = true;
  wrap.append(btn, menu);
  return wrap;
}

// ───────── 그리기 ─────────

function visibleColumns() {
  return view.visible.map(getColumn).filter(Boolean);
}

function renderHead() {
  const headRow = el('tr');
  visibleColumns().forEach((col) => {
    const th = el('th', `series-table-th col-${col.key}`);
    th.scope = 'col';
    if (col.sortable) {
      const btn = el('button', 'series-table-sort');
      btn.type = 'button';
      btn.dataset.sort = col.key;
      btn.appendChild(el('span', '', columnLabel(col)));
      if (view.sort.key === col.key) {
        btn.classList.add('active');
        btn.appendChild(icon(`lc-arrow-up series-table-sort-arrow${view.sort.dir === 'desc' ? ' is-desc' : ''}`));
        th.setAttribute('aria-sort', view.sort.dir === 'desc' ? 'descending' : 'ascending');
      }
      th.appendChild(btn);
    } else {
      th.textContent = columnLabel(col);
    }
    headRow.appendChild(th);
  });
  const thead = root().querySelector('thead');
  thead.textContent = '';
  thead.appendChild(headRow);
}

function selectLabel(col, value) {
  if (col.key === 'publication_status') {
    if (value === '') return '';
    return t(`detail.publication_status_${value}`, { 0: '연재', 1: '휴재', 2: '완결' }[value] || value);
  }
  return value;
}

function renderCell(col, row) {
  const td = el('td', `series-table-td col-${col.key}`);
  td.dataset.key = col.key;
  if (col.type === 'cover') {
    if (row.cover_image) {
      const img = el('img', 'series-table-cover');
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = '';
      // cover_image는 파일명(+?t=)이라 다른 화면과 같은 규칙으로 /covers/ URL을 만든다.
      img.addEventListener('error', () => handleCoverError(img, row.series_name || '', row.file_format || ''), { once: true });
      img.src = getBookCoverSrc({ coverImage: row.cover_image, title: row.series_name, format: row.file_format });
      td.appendChild(img);
    } else {
      td.appendChild(el('span', 'series-table-cover series-table-cover--empty'));
    }
    return td;
  }
  if (col.type === 'link') {
    const btn = el('button', 'series-table-link', row.series_name || t('table_view.no_series', '(시리즈 없음)'));
    btn.type = 'button';
    btn.dataset.open = '1';
    btn.title = row.series_name || '';
    td.appendChild(btn);
    return td;
  }
  if (col.type === 'longtext') {
    // 긴 글(설명)은 셀에 펼치지 않고 아이콘만: 있으면 밝게, 없으면 흐리게. 누르면 팝업에서 고친다
    const value = String(row[col.key] ?? '').trim();
    const btn = el('button', `series-table-longtext${value ? ' has-value' : ''}`);
    btn.type = 'button';
    btn.dataset.longtext = col.key;
    btn.title = value
      ? (value.length > 200 ? `${value.slice(0, 200)}…` : value)
      : t('table_view.summary_empty', '설명 없음');
    btn.setAttribute('aria-label', `${columnLabel(col)}: ${value ? t('table_view.summary_has', '있음') : t('table_view.summary_empty', '설명 없음')}`);
    btn.appendChild(icon('lc-file-text'));
    td.appendChild(btn);
    return td;
  }
  if (col.type === 'lock') {
    // 자물쇠 토글: 잠김 = 닫힌 자물쇠(강조), 풀림 = 열린 자물쇠(흐리게). 누르면 반대 상태로.
    const locked = !!row.metadata_locked;
    const btn = el('button', `series-table-lock${locked ? ' is-locked' : ''}`);
    btn.type = 'button';
    btn.dataset.lockToggle = '1';
    btn.setAttribute('aria-pressed', locked ? 'true' : 'false');
    btn.title = locked
      ? t('table_view.unlock_title', '잠금 해제 (다음 스캔부터 메타·kavita.yaml을 다시 반영)')
      : t('table_view.lock_title', '잠금 (스캔이 메타를 덮어쓰지 않게 - kavita.yaml도 반영되지 않음)');
    btn.setAttribute('aria-label', btn.title);
    btn.appendChild(icon(locked ? 'lc-lock' : 'lc-lock-open'));
    td.appendChild(btn);
    return td;
  }
  const text = col.type === 'select' ? selectLabel(col, String(row[col.key] ?? '')) : formatCellText(col, row);
  td.textContent = text;
  if (col.type !== 'number' && col.type !== 'date') td.title = text;
  if (col.editable && row.editable) {
    td.classList.add('is-editable');
    td.tabIndex = 0;
  }
  return td;
}

function renderRow(row, index) {
  const tr = el('tr', 'series-table-row');
  tr.dataset.index = String(index);
  visibleColumns().forEach((col) => tr.appendChild(renderCell(col, row)));
  return tr;
}

function renderBody(fromIndex = 0) {
  const tbody = root().querySelector('tbody');
  if (fromIndex === 0) tbody.textContent = '';
  const fragment = document.createDocumentFragment();
  for (let i = fromIndex; i < view.rows.length; i += 1) fragment.appendChild(renderRow(view.rows[i], i));
  tbody.appendChild(fragment);
}

function rerenderRow(index) {
  const tr = root().querySelector(`tbody tr[data-index="${index}"]`);
  if (tr) tr.replaceWith(renderRow(view.rows[index], index));
}

function renderStatus(message) {
  const container = root();
  const status = container.querySelector('.series-table-status');
  status.textContent = '';
  if (message) {
    status.textContent = message;
  } else if (view.total !== null) {
    status.appendChild(el('span', '', t('table_view.total', `${view.total.toLocaleString()}개 시리즈`, { n: view.total.toLocaleString() })));
  }
  view.missing.forEach((key) => {
    const chip = el('button', 'series-table-chip');
    chip.type = 'button';
    chip.dataset.clearMissing = key;
    chip.title = t('table_view.missing_chip_remove', '이 필터 끄기');
    chip.append(el('span', '', t('table_view.missing_chip', `빈 값: ${columnLabel(getColumn(key))}`, { name: columnLabel(getColumn(key)) })), icon('lc-x'));
    status.appendChild(chip);
  });

  // 목록 제목 옆 건수는 그리드용 문구(시리즈·권수)라 표 모드에서는 비운다 - 표 도구 줄에 건수가 있다
  const countSpan = document.getElementById('library-total-count');
  if (countSpan) countSpan.innerText = '';

  const more = container.querySelector('.series-table-more');
  more.textContent = '';
  if (view.loading) {
    more.appendChild(icon('lc-loader-circle lc-spin'));
  } else if (!view.rows.length && !message) {
    more.textContent = t('table_view.empty', '조건에 맞는 시리즈가 없습니다.');
  }
}

// ───────── 불러오기 ─────────

async function fetchPage(page) {
  const query = buildQuery({ ...requestFilters(), page, limit: PAGE_SIZE });
  const res = await fetch(`/api/admin/series-table?${query}&_=${Date.now()}`, { cache: 'no-store' });
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  return res.json();
}

// 표를 처음부터 다시 불러온다. 반환: 다시 그렸으면 true (편집 중이거나 표 모드가 아니면 false)
export async function reloadSeriesTable() {
  if (!isTableModeActive() || !ensureShell()) return false;
  // 스캔 완료 알림 등으로 들어온 자동 갱신이 입력 중인 셀을 날리지 않게 한다
  if (view.editing) return false;
  closeMenu();
  const serial = ++view.serial;
  view.loading = true;
  view.page = 0;
  view.hasMore = false;
  renderHead();
  renderStatus();
  try {
    const data = await fetchPage(1);
    if (serial !== view.serial) return false;
    if (!data.success) {
      view.rows = [];
      view.total = null;
      view.loading = false;
      renderBody();
      renderStatus(data.error || t('table_view.load_failed', '표를 불러오지 못했습니다.'));
      return false;
    }
    view.rows = data.rows || [];
    view.total = typeof data.total === 'number' ? data.total : null;
    view.page = 1;
    view.hasMore = !!data.has_more;
    view.loading = false;
    renderBody();
    renderStatus();
    return true;
  } catch (e) {
    if (serial !== view.serial) return false;
    view.loading = false;
    console.error('[Table-View] 불러오기 실패:', e);
    renderStatus(t('table_view.load_failed', '표를 불러오지 못했습니다.'));
    return false;
  }
}

async function loadNextPage() {
  if (!isTableModeActive() || view.loading || !view.hasMore) return;
  const serial = view.serial;
  view.loading = true;
  renderStatus();
  try {
    const data = await fetchPage(view.page + 1);
    if (serial !== view.serial) return;
    view.loading = false;
    if (!data.success) {
      view.hasMore = false;
      showToast(data.error || t('table_view.load_failed', '표를 불러오지 못했습니다.'), 'error');
      renderStatus();
      return;
    }
    const from = view.rows.length;
    view.rows = view.rows.concat(data.rows || []);
    view.page += 1;
    view.hasMore = !!data.has_more;
    renderBody(from);
    renderStatus();
  } catch (e) {
    if (serial !== view.serial) return;
    view.loading = false;
    view.hasMore = false;
    console.error('[Table-View] 다음 쪽 불러오기 실패:', e);
    renderStatus();
  }
}

// ───────── 도구 줄: 메뉴(빈 값 필터·컬럼), CSV ─────────

function closeMenu() {
  if (!view.openMenu) return;
  view.openMenu.hidden = true;
  view.openMenu.parentElement.querySelector('button')?.setAttribute('aria-expanded', 'false');
  view.openMenu = null;
}

function checkItem(labelText, checked, dataset) {
  const label = el('label', 'series-table-menu-item');
  const input = el('input');
  input.type = 'checkbox';
  input.checked = checked;
  Object.assign(input.dataset, dataset);
  label.append(input, el('span', '', labelText));
  return label;
}

function fillMenu(menu) {
  menu.textContent = '';
  if (menu.dataset.menu === 'missing') {
    menu.appendChild(el('div', 'series-table-menu-hint', t('table_view.missing_hint', '고른 항목이 모두 비어 있는 시리즈만 봅니다.')));
    COLUMN_DEFS.filter((col) => col.missing).forEach((col) => {
      menu.appendChild(checkItem(columnLabel(col), view.missing.includes(col.key), { missing: col.key }));
    });
  } else {
    COLUMN_DEFS.filter((col) => !col.fixed).forEach((col) => {
      menu.appendChild(checkItem(columnLabel(col), view.visible.includes(col.key), { column: col.key }));
    });
  }
}

function toggleMenu(button) {
  const menu = button.parentElement.querySelector('.series-table-menu');
  if (view.openMenu === menu) return closeMenu();
  closeMenu();
  fillMenu(menu);
  menu.hidden = false;
  button.setAttribute('aria-expanded', 'true');
  view.openMenu = menu;
}

function setMissing(keys) {
  view.missing = normalizeMissingKeys(keys);
  reloadSeriesTable();
}

function onBarClick(event) {
  const chip = event.target.closest('[data-clear-missing]');
  if (chip) return setMissing(view.missing.filter((key) => key !== chip.dataset.clearMissing));

  const input = event.target.closest('.series-table-menu input');
  if (input) {
    if (input.dataset.missing) {
      const keys = new Set(view.missing);
      if (input.checked) keys.add(input.dataset.missing);
      else keys.delete(input.dataset.missing);
      view.missing = normalizeMissingKeys([...keys]);
      // 메뉴는 열어 둔 채로 다시 불러온다 (여러 항목을 이어서 고를 수 있게)
      const menu = view.openMenu;
      view.openMenu = null;
      reloadSeriesTable();
      view.openMenu = menu;
    } else if (input.dataset.column) {
      view.visible = toggleVisibleKey(view.visible, input.dataset.column);
      saveVisibleKeys();
      commitEdit();
      renderHead();
      renderBody();
    }
    return undefined;
  }

  const button = event.target.closest('button[data-act]');
  if (!button) return undefined;
  if (button.dataset.act === 'export') {
    const query = buildQuery({ ...requestFilters(), columns: view.visible });
    // 첨부(Content-Disposition) 응답이라 화면은 그대로 있고 파일만 내려받는다
    window.location.href = `/api/admin/series-table/export?${query}`;
    return undefined;
  }
  return toggleMenu(button);
}

function onDocumentClick(event) {
  if (view.openMenu && !event.target.closest('.series-table-menu-wrap')) closeMenu();
}

function onHeadClick(event) {
  const btn = event.target.closest('[data-sort]');
  if (!btn) return;
  view.sort = nextSort(view.sort, btn.dataset.sort);
  reloadSeriesTable();
}

// ───────── 행 동작: 상세 열기, 잠금 해제, 셀 편집 ─────────

function rowOf(node) {
  const tr = node.closest('tr[data-index]');
  if (!tr) return null;
  const index = Number(tr.dataset.index);
  return { tr, index, row: view.rows[index] };
}

function onBodyClick(event) {
  const hit = rowOf(event.target);
  if (!hit || !hit.row) return;
  if (event.target.closest('[data-open]')) {
    if (typeof window.openBookDetail === 'function') {
      window.openBookDetail(event, hit.row.series_name, hit.row.library_id, hit.row.representative_book_id);
    }
    return;
  }
  if (event.target.closest('[data-lock-toggle]')) {
    toggleLock(hit.index);
    return;
  }
  const longtextBtn = event.target.closest('[data-longtext]');
  if (longtextBtn) {
    openLongtextPopover(longtextBtn, hit.index, getColumn(longtextBtn.dataset.longtext));
    return;
  }
  const td = event.target.closest('td.is-editable');
  if (td && (!view.editing || view.editing.td !== td)) startEdit(td, hit.index);
}

function onBodyKeydown(event) {
  if (view.editing) return; // 입력 중 키는 입력 상자가 처리한다
  const td = event.target.closest('td.is-editable');
  if (!td) return;
  if (event.key === 'Enter' || event.key === 'F2') {
    event.preventDefault();
    const hit = rowOf(td);
    if (hit) startEdit(td, hit.index);
  }
}

async function toggleLock(index) {
  const row = view.rows[index];
  if (!row || row.lockBusy) return; // 연타 방지
  const wasLocked = !!row.metadata_locked;
  const form = new FormData();
  form.append('type', state.currentLibraryType);
  form.append('series_name', row.series_name);
  form.append('library_id', row.library_id);
  if (!row.series_name) form.append('book_id', row.representative_book_id);
  // 먼저 화면에 반영하고, 실패하면 되돌린다
  row.lockBusy = true;
  row.metadata_locked = wasLocked ? 0 : 1;
  rerenderRow(index);
  try {
    const url = wasLocked ? '/api/media/unlock-metadata' : '/api/media/lock-metadata';
    const data = await (await fetch(url, { method: 'POST', body: form })).json();
    if (!data.success) throw new Error(data.error || '');
  } catch (e) {
    if (view.rows[index] === row) row.metadata_locked = wasLocked ? 1 : 0;
    const fallback = wasLocked
      ? t('table_view.unlock_failed', '잠금을 해제하지 못했습니다.')
      : t('table_view.lock_failed', '잠그지 못했습니다.');
    showToast(e.message || fallback, 'error');
  } finally {
    row.lockBusy = false;
    if (view.rows[index] === row && (!view.editing || view.editing.index !== index)) rerenderRow(index);
  }
}

// ── 긴 글(설명) 팝업 편집 ─────────────────────────────────────────────
// 표 위에 하나만 띄운다(position: fixed). 바깥 클릭·Esc·표 스크롤이면 닫히고, Ctrl/Cmd+Enter로 저장.
let popover = null; // { box, textarea, row, index, col, anchor }

function closeLongtextPopover() {
  if (!popover) return;
  const { box, anchor } = popover;
  popover = null;
  box.remove();
  document.removeEventListener('mousedown', onPopoverOutside, true);
  document.removeEventListener('keydown', onPopoverKeydown, true);
  window.removeEventListener('scroll', onPopoverScroll, true);
  window.removeEventListener('resize', closeLongtextPopover);
  if (anchor && anchor.isConnected) anchor.focus({ preventScroll: true });
}

function onPopoverOutside(event) {
  if (popover && !popover.box.contains(event.target) && event.target !== popover.anchor && !popover.anchor.contains(event.target)) {
    closeLongtextPopover();
  }
}

function onPopoverKeydown(event) {
  if (!popover) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    closeLongtextPopover();
  } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && popover.box.contains(event.target)) {
    event.preventDefault();
    saveLongtextPopover();
  }
}

function onPopoverScroll(event) {
  // 팝업 안(textarea) 스크롤은 무시, 표/페이지가 움직이면 기준 위치가 어긋나므로 닫는다
  if (popover && !popover.box.contains(event.target)) closeLongtextPopover();
}

function placePopover(box, anchor) {
  const rect = anchor.getBoundingClientRect();
  const gap = 6;
  const margin = 8;
  const width = box.offsetWidth;
  const height = box.offsetHeight;
  let left = rect.right - width;
  left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
  let top = rect.bottom + gap;
  if (top + height > window.innerHeight - margin) top = Math.max(margin, rect.top - gap - height);
  box.style.left = `${left}px`;
  box.style.top = `${top}px`;
}

function openLongtextPopover(anchor, index, col) {
  const row = view.rows[index];
  if (!row || !col) return;
  const sameTarget = popover && popover.anchor === anchor;
  closeLongtextPopover();
  if (sameTarget) return; // 같은 아이콘을 다시 누르면 닫기만
  if (view.editing) commitEdit();

  const box = el('div', 'series-table-popover');
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', `${row.series_name || ''} - ${columnLabel(col)}`);
  const head = el('div', 'series-table-popover-head');
  head.appendChild(el('strong', 'series-table-popover-title', columnLabel(col)));
  head.appendChild(el('span', 'series-table-popover-series', row.series_name || ''));
  box.appendChild(head);

  const textarea = el('textarea', 'series-table-popover-input');
  textarea.value = String(row[col.key] ?? '');
  textarea.rows = 8;
  textarea.placeholder = t('table_view.summary_placeholder', '설명을 입력하세요');
  const editable = !!row.editable;
  textarea.readOnly = !editable;
  box.appendChild(textarea);

  const foot = el('div', 'series-table-popover-foot');
  foot.appendChild(el('span', 'series-table-popover-hint', editable
    ? t('table_view.summary_hint', 'Ctrl+Enter 저장 · Esc 닫기')
    : t('table_view.summary_readonly', '시리즈명이 없는 행은 고칠 수 없습니다.')));
  const cancel = el('button', 'series-table-popover-btn', t('common.cancel', '취소'));
  cancel.type = 'button';
  cancel.addEventListener('click', closeLongtextPopover);
  foot.appendChild(cancel);
  if (editable) {
    const save = el('button', 'series-table-popover-btn is-primary', t('common.save', '저장'));
    save.type = 'button';
    save.addEventListener('click', saveLongtextPopover);
    foot.appendChild(save);
  }
  box.appendChild(foot);

  document.body.appendChild(box);
  placePopover(box, anchor);
  popover = { box, textarea, row, index, col, anchor };
  document.addEventListener('mousedown', onPopoverOutside, true);
  document.addEventListener('keydown', onPopoverKeydown, true);
  window.addEventListener('scroll', onPopoverScroll, true);
  window.addEventListener('resize', closeLongtextPopover);
  textarea.focus({ preventScroll: true });
}

async function saveLongtextPopover() {
  if (!popover || popover.saving) return;
  const current = popover;
  const { row, index, col, textarea, box } = current;
  const before = String(row[col.key] ?? '');
  if (textarea.value === before) {
    closeLongtextPopover();
    return;
  }
  current.saving = true;
  box.classList.add('is-saving');
  box.querySelectorAll('button, textarea').forEach((node) => { node.disabled = true; });
  const result = await saveCell(row, col, textarea.value);
  if (view.rows[index] !== row) { // 그사이 표를 다시 불러왔다
    if (popover === current) closeLongtextPopover();
    return;
  }
  if (result.ok) {
    row[col.key] = result.value;
    row.metadata_locked = 1;
    if (popover === current) closeLongtextPopover();
    if (!view.editing || view.editing.index !== index) rerenderRow(index);
  } else {
    current.saving = false;
    box.classList.remove('is-saving');
    box.querySelectorAll('button, textarea').forEach((node) => { node.disabled = false; });
    showToast(result.error || t('table_view.save_failed', '저장하지 못했습니다.'), 'error');
  }
}

function buildEditor(col, value) {
  if (col.type === 'select') {
    const select = el('select', 'series-table-input');
    const options = col.key === 'books_lv' ? BOOKS_LV_OPTIONS : PUBLICATION_STATUS_OPTIONS;
    // 스캐너가 넣은 값이 선택지에 없을 수 있다 - 지금 값은 잃지 않게 맨 위에 둔다
    const all = options.includes(value) ? options : [value, ...options];
    all.forEach((option) => {
      const node = el('option', '', option === '' ? t('table_view.option_unset', '(지정 안 함)') : selectLabel(col, option));
      node.value = option;
      select.appendChild(node);
    });
    select.value = value;
    return select;
  }
  const input = el('input', 'series-table-input');
  input.type = 'text';
  input.value = value;
  input.autocomplete = 'off';
  input.spellcheck = false;
  return input;
}

function startEdit(td, index) {
  commitEdit();
  const row = view.rows[index];
  const col = getColumn(td.dataset.key);
  if (!row || !col || !col.editable || !row.editable) return;
  const input = buildEditor(col, String(row[col.key] ?? ''));
  td.textContent = '';
  td.classList.add('is-editing');
  td.appendChild(input);
  view.editing = { td, index, col, input };
  input.focus();
  if (typeof input.select === 'function' && input.tagName === 'INPUT') input.select();

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit();
      td.focus();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      commitEdit();
      td.focus();
    } else if (event.key === 'Tab') {
      event.preventDefault();
      const next = neighborEditable(td, event.shiftKey ? -1 : 1);
      commitEdit();
      if (next) {
        const hit = rowOf(next.td);
        // commitEdit이 그 행을 다시 그렸으면 옛 td는 떨어져 나갔으니 위치로 다시 찾는다
        const target = hit && hit.tr.isConnected ? next.td : root().querySelector(`tbody tr[data-index="${next.index}"] td[data-key="${next.key}"]`);
        if (target) startEdit(target, next.index);
      }
    }
    event.stopPropagation();
  });
  // 다른 곳을 누르면 저장한다 (취소는 Esc)
  input.addEventListener('blur', () => {
    if (view.editing && view.editing.input === input) commitEdit();
  });
  if (input.tagName === 'SELECT') input.addEventListener('change', () => commitEdit());
}

function neighborEditable(td, step) {
  const cells = Array.from(root().querySelectorAll('tbody td.is-editable'));
  const target = cells[cells.indexOf(td) + step];
  if (!target) return null;
  const hit = rowOf(target);
  return hit ? { td: target, index: hit.index, key: target.dataset.key } : null;
}

function cancelEdit() {
  const editing = view.editing;
  if (!editing) return;
  view.editing = null;
  rerenderRow(editing.index);
}

function commitEdit() {
  const editing = view.editing;
  if (!editing) return;
  view.editing = null;
  const { index, col, input } = editing;
  const row = view.rows[index];
  const before = String(row[col.key] ?? '');
  const value = input.tagName === 'SELECT' ? input.value : input.value.replace(/\s+/g, ' ').trim();
  if (value === before) {
    rerenderRow(index);
    return;
  }
  // 먼저 화면에 반영하고, 실패하면 되돌린다
  row[col.key] = value;
  rerenderRow(index);
  root().querySelector(`tbody tr[data-index="${index}"] td[data-key="${col.key}"]`)?.classList.add('is-saving');
  saveCell(row, col, value).then((result) => {
    if (view.rows[index] !== row) return; // 그사이 표를 다시 불러왔다
    if (result.ok) {
      row[col.key] = result.value;
      row.metadata_locked = 1;
    } else {
      row[col.key] = before;
      showToast(result.error || t('table_view.save_failed', '저장하지 못했습니다.'), 'error');
    }
    if (!view.editing || view.editing.index !== index) rerenderRow(index);
  });
}

async function saveCell(row, col, value) {
  try {
    const res = await fetch('/api/admin/series-table/cell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: state.currentLibraryType,
        library_id: row.library_id,
        series_name: row.series_name,
        field: col.key,
        value,
      }),
    });
    const data = await res.json();
    if (data.success) return { ok: true, value: String(data.value ?? value) };
    return { ok: false, error: data.error };
  } catch (e) {
    console.error('[Table-View] 저장 실패:', e);
    return { ok: false, error: '' };
  }
}
