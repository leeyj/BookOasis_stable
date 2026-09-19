import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/search_navigation.js', import.meta.url), 'utf8');
const { resolveSearchNavigation } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

const resolve = (overrides) => resolveSearchNavigation({
  query: '원피스',
  rawQuery: '원피스',
  libraryId: '24',
  detailVisible: false,
  ...overrides,
});

test('an empty query never navigates', () => {
  assert.equal(resolve({ query: '', rawQuery: '' }), null);
  assert.equal(resolve({ query: '   ', detailVisible: true }), null);
});

test('home and history searches go to the all-library results and remember where they came from', () => {
  for (const libraryId of ['home', 'history']) {
    const navigation = resolve({ libraryId });
    assert.equal(navigation.categoryId, 'all');
    assert.deepEqual(navigation.options, {
      preserveSearch: true, searchNavigationFrom: libraryId, searchQuery: '원피스',
    });
  }
});

test('a regular library list keeps filtering in place', () => {
  assert.equal(resolve({ libraryId: '24' }), null);
  assert.equal(resolve({ libraryId: 'all' }), null);
});

test('searching while a series detail is open goes to the results of the current library and keeps the detail in history', () => {
  const navigation = resolve({ libraryId: '24', detailVisible: true });

  assert.equal(navigation.categoryId, '24');
  assert.deepEqual(navigation.options, {
    preserveSearch: true, searchNavigation: true, searchQuery: '원피스',
  });
});

test('a detail opened from home has no list to search in, so it searches everything', () => {
  const navigation = resolve({ libraryId: 'home', detailVisible: true });

  assert.equal(navigation.categoryId, 'all');
  assert.equal(navigation.options.searchNavigation, true);
});
