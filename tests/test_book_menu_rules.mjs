import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/book_menu/menu_rules.js', import.meta.url), 'utf8');
const { computeBookMenuState, getBookScanScope, getLazyScanSeriesTarget, isDiagnoseAllowed, isLazyScanAllowed } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
);

const seriesCard = { markUnreadScope: 'series', seriesName: 'S', libraryId: 3, bookCount: 5, fileFormat: 'zip', hasProgress: true };
const volumeCard = { isVolumeDetail: true, markUnreadScope: 'book', seriesName: 'S', libraryId: 3, fileFormat: 'epub', hasProgress: false };
const multi = (books) => ({ ...books[0], selectedBooks: books });

test('scan scope and label follow series card / volume / multi selection', () => {
  assert.equal(getBookScanScope(seriesCard), 'series');
  assert.equal(getBookScanScope(volumeCard), 'book');
  assert.equal(computeBookMenuState(seriesCard).items['ctx-scan-book'].labelKey, 'context_menu.scan_series_now');
  assert.equal(computeBookMenuState(volumeCard).items['ctx-scan-book'].labelKey, 'context_menu.scan_book_now');
  const allSeries = multi([seriesCard, { ...seriesCard, seriesName: 'T' }]);
  assert.equal(computeBookMenuState(allSeries).items['ctx-scan-book'].labelKey, 'context_menu.scan_selected_series_now');
  const mixed = multi([seriesCard, volumeCard]);
  assert.equal(computeBookMenuState(mixed).items['ctx-scan-book'].labelKey, 'context_menu.scan_selected_now');
});

test('title shows the selection count only for multi selection', () => {
  assert.equal(computeBookMenuState(seriesCard).title, '도서 메뉴');
  assert.equal(computeBookMenuState(multi([seriesCard, volumeCard])).title, '도서 메뉴 (2개 선택)');
});

test('lazy scan: admin only for general/adult/audiobook, series label only for a single series card', () => {
  assert.equal(isLazyScanAllowed({ role: 'admin' }, 'general'), true);
  assert.equal(isLazyScanAllowed({ role: 'Admin ' }, 'ADULT'), true);
  assert.equal(isLazyScanAllowed({ role: 'admin' }, 'video'), false);
  assert.equal(isLazyScanAllowed({ role: 'user' }, 'general'), false);
  assert.deepEqual(getLazyScanSeriesTarget(seriesCard), { libraryId: 3, seriesName: 'S' });
  assert.equal(getLazyScanSeriesTarget({ ...seriesCard, libraryId: null }), null);

  const hidden = computeBookMenuState(seriesCard, { lazyScanAllowed: false }).items['ctx-lazy-scan-book'];
  assert.equal(hidden.visible, false);
  const single = computeBookMenuState(seriesCard, { lazyScanAllowed: true }).items['ctx-lazy-scan-book'];
  assert.equal(single.visible, true);
  assert.equal(single.labelKey, 'context_menu.lazy_scan_series');
  const many = computeBookMenuState(multi([seriesCard, seriesCard]), { lazyScanAllowed: true }).items['ctx-lazy-scan-book'];
  assert.equal(many.labelKey, 'context_menu.lazy_scan_book');
});

test('page turn only for single zip/cbz; listen/pregen only for single listenable formats', () => {
  assert.equal(computeBookMenuState(seriesCard).items['ctx-page-turn-book'].visible, true);
  assert.equal(computeBookMenuState({ ...seriesCard, fileFormat: 'CBZ' }).items['ctx-page-turn-book'].visible, true);
  assert.equal(computeBookMenuState(volumeCard).items['ctx-page-turn-book'].visible, false);
  assert.equal(computeBookMenuState(multi([seriesCard, seriesCard])).items['ctx-page-turn-book'].visible, false);

  const env = { listenable: true, ttsPregenEnabled: false };
  assert.equal(computeBookMenuState(volumeCard, env).items['ctx-tts-book'].visible, true);
  assert.equal(computeBookMenuState(volumeCard, env).items['ctx-tts-pregen-book'].visible, false);
  assert.equal(computeBookMenuState(volumeCard, { ...env, ttsPregenEnabled: true }).items['ctx-tts-pregen-book'].visible, true);
  assert.equal(computeBookMenuState(volumeCard, { listenable: false, ttsPregenEnabled: true }).items['ctx-tts-pregen-book'].visible, false);
  assert.equal(computeBookMenuState(multi([volumeCard, volumeCard]), { ...env, ttsPregenEnabled: true }).items['ctx-tts-book'].visible, false);
});

test('add series to collection needs a series name (all of them for multi selection)', () => {
  assert.equal(computeBookMenuState(seriesCard).items['ctx-add-series-to-collection'].visible, true);
  assert.equal(computeBookMenuState({ ...seriesCard, seriesName: ' ' }).items['ctx-add-series-to-collection'].visible, false);
  assert.equal(computeBookMenuState(multi([seriesCard, { ...seriesCard, seriesName: '' }])).items['ctx-add-series-to-collection'].visible, false);
  assert.equal(computeBookMenuState(multi([seriesCard, seriesCard])).items['ctx-add-series-to-collection'].visible, true);
});

test('cover align: volume detail, single-book cards, or multi selection of single books only', () => {
  assert.equal(computeBookMenuState(volumeCard).items['ctx-cover-align-book'].visible, true);
  assert.equal(computeBookMenuState(seriesCard).items['ctx-cover-align-book'].visible, false);
  assert.equal(computeBookMenuState({ ...seriesCard, bookCount: 1 }).items['ctx-cover-align-book'].visible, true);
  assert.equal(computeBookMenuState({ ...seriesCard, bookCount: 0 }).items['ctx-cover-align-book'].visible, true);

  const singles = multi([{ ...seriesCard, bookCount: 1 }, { ...seriesCard, bookCount: 1 }]);
  const bulk = computeBookMenuState(singles).items['ctx-cover-align-book'];
  assert.equal(bulk.visible, true);
  assert.equal(bulk.labelText, '선택한 2개 커버 정렬 (이중 스캔본용)');
  assert.equal(computeBookMenuState(multi([seriesCard, { ...seriesCard, bookCount: 1 }])).items['ctx-cover-align-book'].visible, false);
});

test('read toggle: mark-read only for a single unread non-video target', () => {
  const read = computeBookMenuState(volumeCard).items['ctx-unread-book'];
  assert.equal(read.action, 'mark-read');
  assert.equal(read.labelKey, 'context_menu.mark_as_read');
  assert.equal(computeBookMenuState({ ...seriesCard, hasProgress: false }).items['ctx-unread-book'].labelKey, 'context_menu.mark_series_as_read');

  assert.equal(computeBookMenuState(volumeCard, { isVideoLibrary: true }).items['ctx-unread-book'].action, 'mark-unread');
  assert.equal(computeBookMenuState(seriesCard).items['ctx-unread-book'].labelKey, 'context_menu.mark_series_as_unread');
  assert.equal(computeBookMenuState({ ...volumeCard, hasProgress: undefined }).items['ctx-unread-book'].action, 'mark-unread');

  const many = computeBookMenuState(multi([volumeCard, volumeCard])).items['ctx-unread-book'];
  assert.equal(many.action, 'mark-unread');
  assert.equal(many.labelText, '선택한 2개 작품을 읽지 않은 상태로 변경 (0%)');
});

test('metadata search visibility is left alone until the plugin list is known', () => {
  assert.equal(computeBookMenuState(seriesCard, { metaSearchAvailable: null }).items['ctx-search-meta-book'].visible, undefined);
  assert.equal(computeBookMenuState(seriesCard, { metaSearchAvailable: true }).items['ctx-search-meta-book'].visible, true);
  assert.equal(computeBookMenuState(seriesCard, { metaSearchAvailable: false }).items['ctx-search-meta-book'].visible, false);
});

test('diagnose: admin + general/adult only, single book (volume or 1-book card), never multi', () => {
  assert.equal(isDiagnoseAllowed({ role: 'admin' }, 'general'), true);
  assert.equal(isDiagnoseAllowed({ role: 'admin' }, 'adult'), true);
  assert.equal(isDiagnoseAllowed({ role: 'admin' }, 'audiobook'), false);
  assert.equal(isDiagnoseAllowed({ role: 'user' }, 'general'), false);
  const env = { diagnoseAllowed: true };
  assert.equal(computeBookMenuState(volumeCard, env).items['ctx-diagnose-book'].visible, true);
  assert.equal(computeBookMenuState({ ...seriesCard, bookCount: 1 }, env).items['ctx-diagnose-book'].visible, true);
  assert.equal(computeBookMenuState(seriesCard, env).items['ctx-diagnose-book'].visible, false);
  assert.equal(computeBookMenuState(multi([volumeCard, volumeCard]), env).items['ctx-diagnose-book'].visible, false);
  assert.equal(computeBookMenuState(volumeCard, {}).items['ctx-diagnose-book'].visible, false);
});
