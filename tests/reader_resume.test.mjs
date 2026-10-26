// Run with: node --test tests/reader_resume.test.mjs
// Browser rendering is covered separately by the manual steps in reader_resume.md.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const root = new URL('../static/js/', import.meta.url);
const loader = await readFile(new URL('viewer/epub_loader.js', root), 'utf8');
const viewer = await readFile(new URL('viewer_txt.js', root), 'utf8');
const anchorSource = await readFile(new URL('viewer/txt_anchor_utils.js', root), 'utf8');
const selectors = vm.createContext({});
vm.runInContext(loader.slice(loader.indexOf('export function clampNumber'), loader.indexOf('export function syncActiveEpubToc')).replaceAll('export ', ''), selectors);
const pick = (session, initial = 50, count = 10) => selectors.pickEpubStartIndex(count, initial, session);

for (const [name, session, initial, expected] of [
  ['legacy zero index retains positive percentage fallback', { index: 0, percent: 18 }, 18, 2],
  ['nonzero chapter beats a conflicting percentage', { index: 3, percent: 90 }, 18, 3],
  ['legacy numeric string zero retains percentage fallback', { index: '0', percent: 50 }, 50, 5],
  ['first chapter with zero percent stays at zero', { index: 0, percent: 0 }, 50, 0],
  // Do not alter the legacy zero-index/percentage policy in a geometry/write fix.
  ['existing index clamping stays unchanged', { index: 10, percent: 50 }, 0, 9],
  ['legacy fractional index handling stays unchanged', { index: 1.5, percent: 50 }, 0, 1.5],
  ['existing negative index clamping stays unchanged', { index: -1 }, 50, 0],
  ['absent session retains initial progress', null, 50, 5],
  ['percentage fallback still clamps to the book', { percent: 200 }, 0, 9],
]) {
  test(name, () => assert.equal(pick(session, initial), expected));
}
test('empty and one-chapter books stay at zero', () => {
  assert.equal(pick({ index: 3, percent: 100 }, 100, 0), 0);
  assert.equal(pick({ index: 0, percent: 100 }, 100, 1), 0);
});

const anchors = await import('data:text/javascript;base64,' + Buffer.from(anchorSource).toString('base64'));
function restoreFixture({ mode = 'scroll', queryRect = true, paragraphOffset = 100 } = {}) {
  const paragraph = {
    children: [], tagName: 'P', textContent: 'prefix saved sentence suffix', offsetTop: paragraphOffset,
    getBoundingClientRect: () => ({ top: 1100, left: 100, width: 1 }),
    getClientRects: () => [{ top: 1100, left: 100, width: 1 }],
  };
  // The text Range is lower inside the paragraph than its bounding rectangle.
  globalThis.NodeFilter = { SHOW_TEXT: 4 };
  const textNode = { nodeValue: paragraph.textContent };
  globalThis.document = {
    createTreeWalker: () => { let done = false; return { nextNode: () => done ? null : (done = true, textNode) }; },
    createRange: () => ({ setStart() {}, setEnd() {}, getClientRects: () => queryRect ? [{ top: 1300, left: 900, width: 1 }] : [] }),
  };
  const wrapper = {
    scrollTop: 200, scrollLeft: 0, clientWidth: 800, scrollWidth: 4000,
    getBoundingClientRect: () => ({ top: 100, left: 100 }),
  };
  const restored = anchors.restoreTxtAnchorInfoByMode({
    anchorInfo: { chunkIdx: 1, anchorText: 'saved sentence' },
    scrollWrapper: wrapper, contentArea: { querySelector: () => ({ querySelectorAll: () => [paragraph] }) },
    storage: { getItem: () => mode }, currentChunkIdx: 1, getPageAdvanceWidth: () => 800,
    isEpub: true, fullText: '', txtChunks: [], stripHtml: s => s,
  });
  return { restored, wrapper };
}
test('scroll restore uses sentence geometry including container scroll', () => {
  const { restored, wrapper } = restoreFixture();
  assert.equal(restored, true);
  assert.equal(wrapper.scrollTop, 1370);
});
test('scroll restore falls back to paragraph geometry if no text Range is available', () => {
  assert.equal(restoreFixture({ queryRect: false }).wrapper.scrollTop, 1170);
});
test('page-mode sentence geometry remains unchanged', () => {
  assert.equal(restoreFixture({ mode: 'page' }).wrapper.scrollLeft, 800);
});

function progressContext(format = 'epub') {
  const writes = [], reads = [], events = {};
  const area = { querySelectorAll: () => [], scrollLeft: 0, scrollTop: 0 };
  const storage = new Map([['viewer_last_pos_1', JSON.stringify({ savedAt: 1234 })]]);
  const noop = () => {};
  const ctx = vm.createContext({
    state: { currentViewerFormat: format, activeBookId: 1 },
    document: { getElementById: () => area, addEventListener: (type, cb) => { events[type] = cb; } },
    localStorage: { getItem: k => storage.get(k) ?? 'page', setItem: (k, v) => storage.set(k, v) },
    persistProgress: (...args) => writes.push(args), saveProgress: (...args) => writes.push(args),
    noteReadActivity: () => reads.push(true), rememberStableTxtPageAnchor: noop,
    heldTxtAnchorInfo: () => null, getTxtAnchorInfo: () => ({ chunkIdx: 0, anchorText: 'saved sentence' }),
    currentChunkIdx: 0, txtChunks: ['synthetic chapter'], formatTxtToHtml: s => s,
    renderTxtChunkView: () => true, i18n: { t: s => s },
    applyAnnotationsToAllRenderedChunks: noop, applyDynamicParagraphStyles: noop,
    applyTxtImageMaxHeight: noop, applyTxtTwoPageTrailingSpacer: noop,
    hydrateEpubChapterWindow: noop, scheduleVisibleEpubPlaceholderRecovery: noop,
    updateTxtSeekBar: noop, syncActiveEpubToc: noop, setTimeout: noop,
  });
  const flag = viewer.match(/let epubAwaitingUserInput = false;/)?.[0];
  const wrapperStart = viewer.indexOf('function saveProgress(');
  if (flag && wrapperStart >= 0) {
    vm.runInContext(flag + '\n' + viewer.slice(wrapperStart, viewer.indexOf('\n}', wrapperStart) + 2) + '\nepubAwaitingUserInput = true;', ctx);
  }
  const holdStart = viewer.indexOf('let txtRestoreHold = null;');
  const holdEnd = viewer.indexOf('// 이 기기에 저장된 세부 위치', holdStart);
  vm.runInContext(viewer.slice(holdStart, holdEnd), ctx);
  const renderStart = viewer.indexOf('function renderCurrentChunk(');
  vm.runInContext(viewer.slice(renderStart, viewer.indexOf('\nfunction applyDynamicParagraphStyles()', renderStart)), ctx);
  const saveStart = viewer.indexOf('export function saveDetailPosition()');
  vm.runInContext(viewer.slice(saveStart, viewer.indexOf('\nexport function applyTxtSettings(', saveStart)).replace('export ', ''), ctx);
  return { ctx, writes, reads, events, storage };
}
test('initial EPUB render does not schedule progress before user input', () => {
  const { ctx, writes } = progressContext();
  vm.runInContext('renderCurrentChunk(true);', ctx);
  assert.equal(writes.length, 0);
});
test('EPUB detail restoration neither reports reading nor advances local freshness', () => {
  const { ctx, reads, storage } = progressContext();
  vm.runInContext('saveDetailPosition();', ctx);
  assert.equal(reads.length, 0);
  assert.equal(JSON.parse(storage.get('viewer_last_pos_1')).savedAt, 1234);
});
test('new browser restore does not invent a fresh local reading timestamp', () => {
  const { ctx, storage } = progressContext();
  storage.delete('viewer_last_pos_1');
  vm.runInContext('saveDetailPosition();', ctx);
  assert.equal(JSON.parse(storage.get('viewer_last_pos_1')).savedAt, 0);
});
test('trusted reading input releases EPUB progress protection', () => {
  const { ctx, writes, reads, events } = progressContext();
  events.wheel({ isTrusted: true });
  vm.runInContext('renderCurrentChunk(); saveDetailPosition();', ctx);
  assert.equal(writes.length, 1);
  assert.equal(reads.length, 1);
});
test('clicking Close is not a reading action', () => {
  const { ctx, writes, reads, events } = progressContext();
  events.pointerdown({ isTrusted: true, target: { closest: () => ({}) } });
  vm.runInContext('renderCurrentChunk(true); saveDetailPosition();', ctx);
  assert.equal(writes.length, 0);
  assert.equal(reads.length, 0);
});
test('Escape does not turn a restored viewport into reading', () => {
  const { ctx, writes, events } = progressContext();
  events.keydown({ isTrusted: true, key: 'Escape' });
  vm.runInContext('renderCurrentChunk(true);', ctx);
  assert.equal(writes.length, 0);
});
test('synthetic input does not turn restoration into reading', () => {
  const { ctx, writes, events } = progressContext();
  events.keydown({ isTrusted: false });
  vm.runInContext('renderCurrentChunk(true);', ctx);
  assert.equal(writes.length, 0);
});
test('first-ever EPUB opens retain their existing history write', () => {
  const { ctx, writes } = progressContext();
  Object.assign(ctx, { ttsTarget: null, readLocalTxtPosition: () => null, serverEpubSession: null, initialPageIdx: 0, bookId: 1 });
  const decision = viewer.match(/epubAwaitingUserInput = !!\([\s\S]*?\);/);
  if (decision) vm.runInContext(decision[0], ctx);
  vm.runInContext('renderCurrentChunk(true);', ctx);
  assert.equal(writes.length, 1);
});
for (const [name, values] of [
  ['server saved position', { serverEpubSession: { updatedAt: '2026-01-01 00:00:00' } }],
  ['local saved position', { readLocalTxtPosition: () => ({ chunkIdx: 1, savedAt: 1234 }) }],
  ['read or listen sync target', { ttsTarget: { kind: 'read', chunkIdx: 1 } }],
  ['legacy nonzero progress', { initialPageIdx: 50 }],
]) {
  test(`restoring ${name} remains quiet`, () => {
    const { ctx, writes } = progressContext();
    Object.assign(ctx, { ttsTarget: null, readLocalTxtPosition: () => null, serverEpubSession: null, initialPageIdx: 0, bookId: 1 }, values);
    const decision = viewer.match(/epubAwaitingUserInput = !!\([\s\S]*?\);/);
    if (decision) vm.runInContext(decision[0], ctx);
    vm.runInContext('renderCurrentChunk(true);', ctx);
    assert.equal(writes.length, 0);
  });
}
test('TXT progress is not blocked by EPUB restore protection', () => {
  const { ctx, writes } = progressContext('txt');
  vm.runInContext('renderCurrentChunk(true);', ctx);
  assert.equal(writes.length, 1);
});
