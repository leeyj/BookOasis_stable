// notification_cards.js – 알림센터 문제 카드 펼침/조치 (관리자 전용 항목에만 나타난다)
// 카드 → 시리즈 줄 → 도서 목록. 재스캔은 기존 스캔 API를 그대로 쓴다.
// 목록은 2초 폴링마다 다시 그려지므로 펼친 상태와 불러온 줄/도서를 여기서 기억했다가 restore()로 되살린다.
import {
  cardActionButtons,
  escapeActivityText,
  itemRescanAction,
  problemLineText,
  tr,
} from './notification_render.js';
import { openBookDiagnosis } from './book_diagnosis.js';

const ITEM_PAGE = 30;
const expanded = new Map(); // group_key(또는 multi id) → { loading, lines, hasMore, error, series: Map }

function attr(value) {
  return escapeActivityText(value).replace(/"/g, '&quot;');
}

function actionLabel(action) {
  const keys = {
    rescan_all: ['problems.action.rescan_all', '모두 재스캔'],
    rescan_series: ['problems.action.rescan_series', '시리즈 재스캔'],
    rescan_path: ['problems.action.rescan', '재스캔'],
    rescan_book: ['problems.action.rescan', '재스캔'],
    rescan_library: ['problems.action.rescan', '재스캔'],
    confirm_trash: ['problems.action.confirm_trash', '확인 후 휴지통으로'],
    resolve: ['problems.action.resolve', '해결됨'],
    diagnose: ['problems.action.diagnose', '진단'],
    plugin_action: ['problems.action.plugin_action', '실행'],
    mute: ['problems.action.mute', '알고 있음'],
    more: ['problems.action.more', '더 보기'],
  };
  const [key, fallback] = keys[action] || [action, action];
  return tr(key, {}, fallback);
}

function button(action, data, extraClass = '', label = '') {
  const dataAttrs = Object.entries(data || {})
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => ` data-${k}="${attr(v)}"`).join('');
  return `<button type="button" class="notify-card-btn${extraClass}" data-notify-action="${action}"${dataAttrs}>${escapeActivityText(label || actionLabel(action))}</button>`;
}

// 플러그인 조치 버튼: 문구는 플러그인이 준 action_label, 없으면 '실행'
function pluginActionButton(card, pluginAction, target = {}) {
  return button('plugin_action', {
    'plugin-id': pluginAction.plugin_id || card.plugin?.id, 'action-id': pluginAction.action_id,
    'db-type': card.db_type, 'group-key': card.group_key, 'problem-code': card.plugin?.code || '',
    'target-type': target.target_type, 'target-id': target.target_id, 'book-id': target.book_id,
  }, '', pluginAction.label || pluginAction.action_label || '');
}

function cardContext(itemEl) {
  try {
    return JSON.parse(itemEl.getAttribute('data-card') || 'null');
  } catch (_err) {
    return null;
  }
}

// ---- 렌더 ----

function seriesItemsHtml(card, line, state) {
  if (!state) return '';
  if (state.loading && !state.items) return `<div class="notify-card-note">${escapeActivityText(tr('common.loading', {}, '불러오는 중...'))}</div>`;
  const rows = (state.items || []).map(item => {
    let action = itemRescanAction(item);
    // 같은 폴더 재스캔이면 위 [시리즈 재스캔]과 같은 일이라 권마다 반복해 두지 않는다
    if (action === 'rescan_path' && item.scan_path === line.scan_path) action = null;
    const label = item.title || item.file_name || item.target_path || item.target_id;
    const btn = action ? button(action, {
      'library-id': card.library_id, 'db-type': card.db_type, 'scan-path': item.scan_path, 'book-id': item.book_id,
    }) : '';
    const diagnose = item.book_id && ['general', 'adult'].includes(card.db_type)
      ? button('diagnose', { 'db-type': card.db_type, 'book-id': item.book_id, title: label }) : '';
    // 사용자 신고: 뷰어가 보낸 오류 문구를 이름 아래 한 줄로
    const noteText = item.code === 'user_report' ? item.message : item.detail;
    const note = noteText ? `<span class="notify-card-book-note">${escapeActivityText(noteText)}</span>` : '';
    const plugin = item.plugin_action ? pluginActionButton(card, item.plugin_action, item) : '';
    return `<li class="notify-card-book"><span class="notify-card-book-name" title="${attr(item.target_path || '')}">${escapeActivityText(label)}${note}</span>${btn}${plugin}${diagnose}</li>`;
  }).join('');
  const more = state.items && state.items.length < state.total
    ? button('more', { 'group-key': card.group_key, 'series-key': line.series_key || '' }, ' is-link') : '';
  return `<ul class="notify-card-books">${rows}</ul>${more}`;
}

function lineHtml(card, line, entry) {
  const seriesState = line.series_key ? entry.series.get(line.series_key) : null;
  const buttons = [];
  if (line.target_type === 'book') {
    if (line.scan_path != null && Number(line.open_count) > 1) {
      buttons.push(button('rescan_series', { 'library-id': card.library_id, 'db-type': card.db_type, 'scan-path': line.scan_path }));
    } else if (Number(line.open_count) === 1) {
      const pseudo = { code: card.code, scan_path: line.scan_path, book_id: /^\d+$/.test(String(line.single_target_id || '')) ? line.single_target_id : null };
      const action = itemRescanAction(pseudo);
      if (action) buttons.push(button(action, { 'library-id': card.library_id, 'db-type': card.db_type, 'scan-path': pseudo.scan_path, 'book-id': pseudo.book_id }));
      if (pseudo.book_id && ['general', 'adult'].includes(card.db_type)) {
        buttons.push(button('diagnose', { 'db-type': card.db_type, 'book-id': pseudo.book_id, title: line.series_name || '' }));
      }
    }
  }
  const toggle = line.series_key
    ? `<button type="button" class="notify-card-line-toggle" data-notify-action="toggle_series" data-group-key="${attr(card.group_key)}" data-series-key="${attr(line.series_key)}" aria-expanded="${seriesState ? 'true' : 'false'}"><i class="fa-solid fa-chevron-${seriesState ? 'down' : 'right'}" aria-hidden="true"></i>${escapeActivityText(problemLineText(line))}</button>`
    : `<span class="notify-card-line-text">${escapeActivityText(problemLineText(line))}</span>`;
  return `<li class="notify-card-line"><div class="notify-card-line-head">${toggle}${buttons.join('')}</div>${seriesItemsHtml(card, line, seriesState)}</li>`;
}

function bodyHtml(card, actions, entry) {
  const top = cardActionButtons(card, actions)
    .map(action => (action === 'plugin_action'
      ? pluginActionButton(card, { plugin_id: card.plugin.id, action_id: card.plugin.action_id, label: card.plugin.action_label })
      : button(action, { 'group-key': card.group_key, 'library-id': card.library_id, 'db-type': card.db_type, count: card.open_count })))
    .join('');
  let lines = '';
  if (entry.error) lines = `<div class="notify-card-note is-error">${escapeActivityText(entry.error)}</div>`;
  else if (entry.loading && !entry.lines) lines = `<div class="notify-card-note">${escapeActivityText(tr('common.loading', {}, '불러오는 중...'))}</div>`;
  else lines = `<ul class="notify-card-lines">${(entry.lines || []).map(line => lineHtml(card, line, entry)).join('')}</ul>`;
  return `<div class="notify-card-body">${top ? `<div class="notify-card-actions">${top}</div>` : ''}${lines}</div>`;
}

// 여러 카테고리가 함께 끊긴 경우: 카테고리마다 한 줄 + [재스캔]
function multiBodyHtml(cards) {
  const rows = (cards || []).map(card => `<li class="notify-card-line"><div class="notify-card-line-head"><span class="notify-card-line-text">${escapeActivityText(card.library || `#${card.library_id}`)}</span>${button('rescan_library', { 'library-id': card.library_id, 'db-type': card.db_type })}</div></li>`).join('');
  return `<div class="notify-card-body"><ul class="notify-card-lines">${rows}</ul></div>`;
}

function renderInto(itemEl) {
  const key = itemEl.getAttribute('data-expand-key');
  const entry = expanded.get(key);
  itemEl.querySelector('.notify-card-body')?.remove();
  itemEl.classList.toggle('is-expanded', Boolean(entry));
  const toggle = itemEl.querySelector('[data-notify-action="toggle_card"]');
  if (toggle) toggle.setAttribute('aria-expanded', entry ? 'true' : 'false');
  if (!entry) return;
  const ctx = cardContext(itemEl);
  const html = ctx?.multi ? multiBodyHtml(ctx.cards) : bodyHtml(ctx.card, ctx.actions, entry);
  itemEl.insertAdjacentHTML('beforeend', html);
}

export function restoreCardExpansions(list) {
  const present = new Set();
  list.querySelectorAll('[data-expand-key]').forEach(el => {
    present.add(el.getAttribute('data-expand-key'));
    if (expanded.has(el.getAttribute('data-expand-key'))) renderInto(el);
  });
  // 해결돼서 사라진 카드의 펼침 상태는 버린다
  [...expanded.keys()].forEach(key => { if (!present.has(key)) expanded.delete(key); });
}

// ---- 데이터 ----

async function getJson(url, options) {
  const res = await fetch(url, options);
  let data = {};
  try { data = await res.json(); } catch (_err) { data = {}; }
  if (!res.ok || data.success === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function loadLines(itemEl, key, groupKey) {
  const entry = expanded.get(key);
  entry.loading = true;
  renderInto(itemEl);
  try {
    const data = await getJson(`/api/problems/card?group_key=${encodeURIComponent(groupKey)}&limit=50`);
    entry.lines = data.lines || [];
    entry.hasMore = Boolean(data.has_more);
  } catch (err) {
    entry.error = err.message;
  }
  entry.loading = false;
  const current = document.querySelector(`[data-expand-key="${CSS.escape(key)}"]`);
  if (current && expanded.get(key) === entry) renderInto(current);
}

async function loadSeriesItems(groupKey, seriesKey, append) {
  const entry = expanded.get(groupKey);
  if (!entry) return;
  const state = entry.series.get(seriesKey) || { items: null, total: 0 };
  entry.series.set(seriesKey, state);
  state.loading = true;
  const offset = append && state.items ? state.items.length : 0;
  const rerender = () => {
    const el = document.querySelector(`[data-expand-key="${CSS.escape(groupKey)}"]`);
    if (el) renderInto(el);
  };
  rerender();
  try {
    const data = await getJson(`/api/problems/card/items?group_key=${encodeURIComponent(groupKey)}&series_key=${encodeURIComponent(seriesKey)}&offset=${offset}&limit=${ITEM_PAGE}`);
    state.items = (append && state.items ? state.items : []).concat(data.items || []);
    state.total = data.total || 0;
  } catch (err) {
    state.items = state.items || [];
    if (typeof window.showToast === 'function') window.showToast(err.message, 'error');
  }
  state.loading = false;
  rerender();
}

// ---- 조치 ----

function toast(message, type = 'success') {
  if (typeof window.showToast === 'function') window.showToast(message, type);
}

function failed(err) {
  toast(tr('problems.action.failed', { error: err.message }, `처리하지 못했습니다: ${err.message}`), 'error');
}

async function runAction(btn, refresh) {
  const action = btn.getAttribute('data-notify-action');
  const d = btn.dataset;
  const form = fields => {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    return { method: 'POST', body: fd };
  };
  const json = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  btn.disabled = true;
  try {
    if (action === 'rescan_all' || action === 'rescan_library') {
      await getJson(`/api/media/libraries/${encodeURIComponent(d.libraryId)}/scan`, form({ type: d.dbType || 'general' }));
      toast(tr('problems.action.queued', {}, '재스캔을 등록했습니다.'));
    } else if (action === 'rescan_series' || action === 'rescan_path') {
      await getJson(`/api/media/libraries/${encodeURIComponent(d.libraryId)}/scan-path`, form({ type: d.dbType || 'general', path: d.scanPath || '' }));
      toast(tr('problems.action.done', {}, '처리했습니다.'));
    } else if (action === 'rescan_book') {
      await getJson('/api/media/books/scan-batch', json({ type: d.dbType || 'general', book_ids: [Number(d.bookId)], scope: 'book' }));
      toast(tr('problems.action.queued', {}, '재스캔을 등록했습니다.'));
    } else if (action === 'confirm_trash') {
      const prompt = tr('problems.action.confirm_trash_prompt', { count: Number(d.count || 0).toLocaleString() }, `아직 파일이 없는 ${d.count}권을 휴지통으로 옮길까요?`);
      if (!window.confirm(prompt)) return;
      await getJson('/api/problems/card/confirm-trash', json({ group_key: d.groupKey }));
      expanded.delete(d.groupKey);
      toast(tr('problems.action.done', {}, '처리했습니다.'));
    } else if (action === 'resolve') {
      await getJson('/api/problems/card/resolve', json({ group_key: d.groupKey }));
      expanded.delete(d.groupKey);
      toast(tr('problems.action.done', {}, '처리했습니다.'));
    } else if (action === 'plugin_action') {
      // 플러그인 문제 카드 조치 = 기존 도서 컨텍스트 메뉴 액션 RPC (새 API 없음, 6단계 계약)
      const context = { source: 'problem_card', group_key: d.groupKey, problem_code: d.problemCode };
      if (d.targetType) context.target_type = d.targetType;
      if (d.targetId) context.target_id = d.targetId;
      if (d.bookId) context.book_id = Number(d.bookId);
      const result = await getJson('/api/media/context-menu/book/plugins/action', json({
        type: d.dbType || 'general', plugin_id: d.pluginId, action_id: d.actionId, context,
      }));
      // 도서 메뉴 플러그인 액션과 같은 규칙: open_url이 오면 새 탭으로 연다 (OAuth 재연결 등)
      if (result.open_url) window.open(result.open_url, '_blank', 'noopener');
      toast(result.message || tr('problems.action.done', {}, '처리했습니다.'));
    } else if (action === 'diagnose') {
      openBookDiagnosis(d.dbType || 'general', Number(d.bookId), d.title || '');
      return;
    } else if (action === 'mute') {
      await getJson('/api/problems/card/mute', json({ group_key: d.groupKey }));
      expanded.delete(d.groupKey);
    }
    refresh?.();
  } catch (err) {
    failed(err);
  } finally {
    btn.disabled = false;
  }
}

export function initNotificationCards(list, { refresh } = {}) {
  if (!list || list.dataset.cardsBound === '1') return;
  list.dataset.cardsBound = '1';
  list.addEventListener('click', event => {
    const btn = event.target.closest('[data-notify-action]');
    if (!btn || !list.contains(btn)) return;
    event.stopPropagation();
    const action = btn.getAttribute('data-notify-action');
    if (action === 'toggle_card') {
      const itemEl = btn.closest('[data-expand-key]');
      const key = itemEl.getAttribute('data-expand-key');
      if (expanded.has(key)) {
        expanded.delete(key);
        renderInto(itemEl);
        return;
      }
      const ctx = cardContext(itemEl);
      expanded.set(key, { loading: false, lines: null, hasMore: false, error: null, series: new Map() });
      if (ctx?.multi) renderInto(itemEl);
      else loadLines(itemEl, key, ctx.card.group_key);
    } else if (action === 'toggle_series') {
      const entry = expanded.get(btn.dataset.groupKey);
      if (!entry) return;
      if (entry.series.has(btn.dataset.seriesKey)) {
        entry.series.delete(btn.dataset.seriesKey);
        const el = btn.closest('[data-expand-key]');
        if (el) renderInto(el);
      } else {
        loadSeriesItems(btn.dataset.groupKey, btn.dataset.seriesKey, false);
      }
    } else if (action === 'more') {
      loadSeriesItems(btn.dataset.groupKey, btn.dataset.seriesKey, true);
    } else {
      runAction(btn, refresh);
    }
  });
}
