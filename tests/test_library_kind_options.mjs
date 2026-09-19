import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/category/kind_options.js', import.meta.url), 'utf8');
const { buildKindOptionsHtml, buildKindListHtml, escapeHtml } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
);

const kinds = [
  { code: 'manga', name: '만화', is_builtin: 1 },
  { code: 'webtoon', name: '웹툰', is_builtin: 0 },
];

test('the select always starts with an unspecified option and selects it when no kind is set', () => {
  for (const selected of ['', 'unspecified', undefined]) {
    const html = buildKindOptionsHtml(kinds, selected);
    assert.ok(html.startsWith('<option value="" selected>미지정</option>'), `selected=${selected}`);
    assert.ok(!html.includes('value="manga" selected'));
  }
});

test('the stored kind is selected', () => {
  const html = buildKindOptionsHtml(kinds, 'webtoon');

  assert.ok(html.includes('<option value="webtoon" selected>웹툰</option>'));
  assert.ok(html.includes('<option value="">미지정</option>'));
});

test('a stored code that is not in the list is shown as-is so saving does not silently change it', () => {
  const html = buildKindOptionsHtml(kinds, 'imported_kind');

  assert.ok(html.includes('<option value="imported_kind" selected>imported_kind</option>'));
});

test('kind names are escaped before they reach innerHTML', () => {
  const html = buildKindOptionsHtml([{ code: 'x', name: '<img src=x onerror=alert(1)>"&' }], '');

  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;&quot;&amp;'));
  assert.equal(escapeHtml(null), '');
});

test('the management list hides the delete button for built-in kinds and labels them', () => {
  const html = buildKindListHtml(kinds, { builtin: '기본', remove: '삭제' });

  const rows = html.split('</li>').filter(Boolean);
  assert.ok(rows[0].includes('library-kind-badge'));
  assert.ok(!rows[0].includes('library-kind-delete'));
  assert.ok(rows[0].includes('library-kind-rename'));
  assert.ok(rows[1].includes('library-kind-delete'));
  assert.ok(!rows[1].includes('library-kind-badge'));
});

test('an empty list shows a placeholder row and list values are escaped', () => {
  assert.ok(buildKindListHtml([], { empty: '없음' }).includes('없음'));

  const html = buildKindListHtml([{ code: 'a"b', name: '<b>', is_builtin: 0 }]);
  assert.ok(!html.includes('<b>'));
  assert.ok(html.includes('data-kind-code="a&quot;b"'));
});
