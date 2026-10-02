import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// 실제 언어팩으로 번역을 확인한다 (static/js/i18n.js의 t()와 같은 규칙).
const ko = JSON.parse(await readFile(new URL('../static/i18n/ko.json', import.meta.url), 'utf8'));
const en = JSON.parse(await readFile(new URL('../static/i18n/en.json', import.meta.url), 'utf8'));
function makeI18n(dictionary) {
  return {
    t(key, variables = {}, fallback = null) {
      if (typeof variables === 'string') { fallback = variables; variables = {}; }
      let value = dictionary;
      for (const k of key.split('.')) {
        if (value && value[k] !== undefined) value = value[k];
        else return fallback || key;
      }
      if (typeof value !== 'string') return fallback || key;
      let result = value;
      for (const [vKey, vVal] of Object.entries(variables)) result = result.replace(new RegExp(`{${vKey}}`, 'g'), vVal);
      return result;
    },
  };
}
globalThis.i18n = makeI18n(ko);
globalThis.window = globalThis;

const render = await import(new URL('../static/js/notification_render.js', import.meta.url));

const historyItem = {
  id: 'scan:history:1', track_key: 'scan:library_scan_general_80', kind: 'recent', tone: 'new', source: 'scan',
  title: '리디(GDS,소설)', title_key: null, title_vars: {},
  detail: [
    { key: 'notify.scan.status.completed', vars: { task: { key: 'notify.scan.task.library_scan' } } },
    { key: 'notify.scan.new_books', vars: { count: 3 } },
    { key: 'notify.scan.failed_books', vars: { count: 1 } },
  ],
  raw_detail: '', updated_at: new Date().toISOString(), read: false,
};

test('scan completion reads as one line with counts', () => {
  assert.equal(render.notificationDetail(historyItem), '카테고리 스캔 완료 · 새 도서 3권 · 실패 1권');
  assert.equal(render.notificationTitle(historyItem), '리디(GDS,소설)');
});

test('unknown task types fall back to the group default text', () => {
  const item = { detail: [{ key: 'notify.scan.running.something_new', vars: {} }] };
  assert.equal(render.notificationDetail(item), '백그라운드 작업 진행 중');
  const status = { detail: [{ key: 'notify.scan.status.failed', vars: { task: { key: 'notify.scan.task.nope' } } }] };
  assert.equal(render.notificationDetail(status), '백그라운드 작업 실패');
});

test('title keys, library prefix and adult suffix', () => {
  assert.equal(render.notificationTitle({ title_key: 'notify.scan.selected_books', title_vars: { count: 3, library: '만화' } }), '만화 · 선택 도서 3권');
  assert.equal(render.notificationTitle({ title_key: 'notify.scan.whole_system', title_vars: {} }), '전체 시스템');
  assert.equal(render.notificationTitle({ title: '책', adult: true }), '책 (성인)');
});

test('raw detail is appended untranslated and html is escaped', () => {
  const item = { ...historyItem, title: '<b>x</b>', raw_detail: '도서 파일 10/20 (50%)', detail: [] };
  const html = render.notificationItemHtml(item);
  assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;'));
  assert.ok(!html.includes('<b>x</b>'));
  assert.ok(html.includes('도서 파일 10/20 (50%)'));
});

test('item html carries tone class, label and unread marker', () => {
  const html = render.notificationItemHtml(historyItem);
  assert.ok(html.includes('notify-tone-new'));
  assert.ok(html.includes('is-unread'));
  assert.ok(html.includes('notify-unread-dot'));
  assert.ok(html.includes('>신규<') || html.includes('</span>신규'));
  const pending = render.notificationItemHtml({ kind: 'running', tone: 'running', progress: { pending: true }, detail: [] });
  assert.ok(pending.includes('notify-tone-pending') && pending.includes('fa-clock'));
});

test('summary priorities: action > running > unread > recent > idle', () => {
  const problem = { kind: 'problem', severity: 'action_required', read: true };
  const running = { kind: 'running', read: true };
  const recentUnread = { kind: 'recent', read: false };
  const recentRead = { kind: 'recent', read: true };
  assert.equal(render.summarizeNotifications([problem, running]).text, '조치 필요 1건');
  assert.equal(render.summarizeNotifications([running, recentUnread]).text, '진행 중 1건');
  assert.equal(render.summarizeNotifications([recentUnread, recentRead]).text, '새 알림 1건');
  assert.equal(render.summarizeNotifications([recentRead]).text, '최근 1건');
  const idle = render.summarizeNotifications([]);
  assert.equal(idle.text, '대기 중');
  assert.ok(idle.isEmpty && !idle.isRunning && !idle.hasWarning);
  // 참고(notice) 문제는 빨간 점을 켜지 않는다
  assert.equal(render.summarizeNotifications([{ kind: 'problem', severity: 'notice' }]).hasWarning, false);
});

test('finished-while-watching only fires for items seen running before', () => {
  const runningItem = { kind: 'running', track_key: 'scan:k' };
  const first = render.finishedWhileWatching([runningItem], null);
  assert.deepEqual(first.finished, []);
  const done = { kind: 'recent', id: 'scan:history:9', track_key: 'scan:k' };
  const other = { kind: 'recent', id: 'scan:history:8', track_key: 'scan:other' };
  const second = render.finishedWhileWatching([done, other], first.runningKeys);
  assert.deepEqual(second.finished.map(i => i.id), ['scan:history:9']);
  // 첫 폴링(페이지를 막 연 상태)에 이미 끝나 있던 항목은 알리지 않는다
  assert.deepEqual(render.finishedWhileWatching([done], null).finished, []);
});

test('english pack has every notify key used by the korean pack', () => {
  const flat = (obj, prefix = '') => Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? flat(v, `${prefix}${k}.`) : [`${prefix}${k}`]);
  const missing = flat(ko.notify, 'notify.').filter(key => makeI18n(en).t(key) === key);
  assert.deepEqual(missing, []);
});

test('running items show translated elapsed time', () => {
  const html = render.notificationItemHtml({ kind: 'running', tone: 'running', source: 'scan', progress: { elapsed_seconds: 3725 }, detail: [] });
  assert.ok(html.includes('1시간 2분'));
});

test('problem line text: all / some / unknown total / whole category', () => {
  assert.equal(render.problemLineText({ target_type: 'book', series_name: '원피스', open_count: 110, series_total: 110 }), '원피스 — 110권 전체');
  assert.equal(render.problemLineText({ target_type: 'book', series_name: '나루토', open_count: 12, series_total: 72 }), '나루토 — 72권 중 12권');
  assert.equal(render.problemLineText({ target_type: 'book', series_name: '', open_count: 2 }), '(시리즈 없음) — 2권');
  assert.equal(render.problemLineText({ target_type: 'library' }), '카테고리 전체');
});

test('per-book rescan: missing files rescan the folder, broken files rescan the book', () => {
  assert.equal(render.itemRescanAction({ code: 'file_missing', scan_path: 'S', book_id: 3 }), 'rescan_path');
  assert.equal(render.itemRescanAction({ code: 'mass_missing', scan_path: null, book_id: 3 }), null);
  assert.equal(render.itemRescanAction({ code: 'file_corrupt', book_id: 3, scan_path: 'S' }), 'rescan_book');
  assert.equal(render.itemRescanAction({ code: 'unknown', book_id: null, scan_path: 'S' }), 'rescan_path');
});

test('card buttons: rescan needs a category, confirm only when offered', () => {
  const card = { group_key: 'mass_missing|general|80', library_id: 80 };
  assert.deepEqual(render.cardActionButtons(card, ['rescan', 'confirm_trash']), ['rescan_all', 'confirm_trash', 'mute']);
  assert.deepEqual(render.cardActionButtons({ group_key: 'x|general|-', library_id: null }, ['rescan']), ['mute']);
});

test('problem items are expandable and carry card context', () => {
  const html = render.notificationItemHtml({
    kind: 'problem', tone: 'error', severity: 'action_required', title_key: 'problems.code.mass_missing.title', detail: [],
    card: { group_key: 'mass_missing|general|80', library_id: 80, db_type: 'general', code: 'mass_missing' }, actions: ['rescan', 'confirm_trash'],
  });
  assert.ok(html.includes('data-expand-key="mass_missing|general|80"'));
  assert.ok(html.includes('data-notify-action="toggle_card"'));
  assert.ok(html.includes('&quot;confirm_trash&quot;'));
  const plain = render.notificationItemHtml({ kind: 'recent', tone: 'done', detail: [] });
  assert.ok(!plain.includes('data-expand-key'));
});

test('clear button counts finished items and notice cards only', () => {
  const items = [
    { kind: 'running', id: 'r' },
    { kind: 'recent', id: 'a' },
    { kind: 'problem', severity: 'action_required', card: { group_key: 'remote_unavailable|general|80' } },
    { kind: 'problem', severity: 'action_required', id: 'system:warning:w' },
    { kind: 'problem', severity: 'notice', card: { group_key: 'file_corrupt|general|80' } },
  ];
  assert.equal(render.clearableCount(items), 2);
  assert.equal(render.clearableCount([{ kind: 'running' }]), 0);
  assert.equal(render.clearableCount(null), 0);
});

const diag = await import(new URL('../static/js/diagnosis_render.js', import.meta.url));

test('diagnosis renders checklist, conclusion tone and actions (escaped)', () => {
  const result = {
    book: { id: 3, title: '<b>원피스</b>', library: '만화', file_path: '/lib/원피스/3.zip' },
    checks: [
      { id: 'db', status: 'ok', key: 'diagnose.check.db.ok', vars: {} },
      { id: 'remote', status: 'ok', key: 'diagnose.check.remote.ok', vars: {} },
      { id: 'file', status: 'fail', key: 'diagnose.check.file.missing', vars: { path: '/lib/원피스/3.zip' } },
    ],
    conclusion: { key: 'diagnose.result.file_moved', vars: {} },
    actions: [{ id: 'rescan_path', library_id: 80, scan_path: '원피스' }],
    problems: [],
  };
  const html = diag.diagnosisHtml(result);
  assert.match(html, /&lt;b&gt;원피스&lt;\/b&gt;/);
  assert.match(html, /파일 없음 — \/lib\/원피스\/3.zip/);
  assert.match(html, /diagnose-conclusion notify-tone-error/);
  assert.match(html, /data-diagnose-action="rescan_path"[^>]*data-scan-path="원피스"/);
  assert.match(html, />폴더 재스캔</);
  assert.equal(diag.diagnosisTone({ checks: [{ status: 'ok' }], problems: [] }), 'done');
  assert.equal(diag.diagnosisTone({ checks: [{ status: 'warn' }] }), 'notice');
});

test('user report cards offer [resolved]; english pack covers diagnose and problems keys', () => {
  assert.deepEqual(render.cardActionButtons({ group_key: 'user_report|general|80' }, ['resolve']), ['resolve', 'mute']);
  const flat = (obj, prefix = '') => Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? flat(v, `${prefix}${k}.`) : [`${prefix}${k}`]);
  const keys = [...flat(ko.diagnose, 'diagnose.'), ...flat(ko.problems, 'problems.')];
  assert.deepEqual(keys.filter(key => makeI18n(en).t(key) === key), []);
});

test('plugin cards: action button only when the plugin gave one, system line text', () => {
  const card = { group_key: 'plugin:sample_mood|token_expired|-', plugin: { id: 'sample_mood', action_id: 'reauth' } };
  assert.deepEqual(render.cardActionButtons(card, ['plugin_action']), ['plugin_action', 'mute']);
  assert.deepEqual(render.cardActionButtons({ ...card, plugin: { id: 'sample_mood' } }, ['plugin_action']), ['mute']);
  assert.equal(render.problemLineText({ target_type: 'system', open_count: 1 }), '공통 (특정 도서와 무관)');
  const html = render.notificationItemHtml({ id: 'problem:x', kind: 'problem', tone: 'notice', source: 'plugin', title: '샘플 무드 · 한도 초과', detail: [], card: card, actions: ['plugin_action'] });
  assert.match(html, /fa-puzzle-piece/);
});
