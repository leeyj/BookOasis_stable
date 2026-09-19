import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const helperSource = await readFile(new URL('../static/js/book_list_refresh_state.js', import.meta.url), 'utf8');
const helperUrl = `data:text/javascript;base64,${Buffer.from(helperSource).toString('base64')}`;
const { BookListRefreshState, getLoadedPageRange } = await import(helperUrl);

test('a scan invalidation makes the rendered list stale until a later request succeeds', () => {
  const refreshState = new BookListRefreshState();
  const listKey = 'general:12';
  const originalRequest = refreshState.beginRequest(listKey);

  refreshState.invalidate(listKey);
  refreshState.markLoaded(listKey, originalRequest);
  assert.equal(refreshState.isStale(listKey), true);

  const refreshRequest = refreshState.beginRequest(listKey);
  refreshState.markLoaded(listKey, refreshRequest);
  assert.equal(refreshState.isStale(listKey), false);
});

test('an older response cannot mark a newer invalidation as loaded', () => {
  const refreshState = new BookListRefreshState();
  const listKey = 'adult:4';
  const firstRequest = refreshState.beginRequest(listKey);
  refreshState.invalidate(listKey);
  const secondRequest = refreshState.beginRequest(listKey);
  refreshState.invalidate(listKey);

  refreshState.markLoaded(listKey, secondRequest);
  assert.equal(refreshState.isStale(listKey), true);

  const newestRequest = refreshState.beginRequest(listKey);
  refreshState.markLoaded(listKey, newestRequest);
  assert.equal(refreshState.isStale(listKey), false);
  assert.equal(firstRequest, 0);
});

test('refresh state for one library does not make another library stale', () => {
  const refreshState = new BookListRefreshState();
  refreshState.invalidate('general:12');

  assert.equal(refreshState.isStale('general:12'), true);
  assert.equal(refreshState.isStale('general:13'), false);
});

test('loaded page range covers the visible list when restoring after refresh', () => {
  assert.deepEqual(getLoadedPageRange(1, 6, true), { firstPage: 1, lastPage: 5 });
  assert.deepEqual(getLoadedPageRange(4, 4, false), { firstPage: 4, lastPage: 4 });
  assert.deepEqual(getLoadedPageRange(0, 0, false), { firstPage: 1, lastPage: 1 });
});
