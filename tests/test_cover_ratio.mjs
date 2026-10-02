import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/utils/cover_ratio.js', import.meta.url), 'utf8');
const { resolveCoverAspectRatio, coverRatioAttr, normalizeCoverAspectRatio } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
);

test('music categories in the audiobook session are always square', () => {
  assert.equal(resolveCoverAspectRatio({ contentKind: 'music', coverAspectRatio: '16:9' }, 'audiobook'), '1:1');
  assert.equal(resolveCoverAspectRatio({ contentKind: 'music', coverAspectRatio: '4:3' }, 'audiobook'), '1:1');
});

test('other categories follow their own setting, including the new square option', () => {
  assert.equal(resolveCoverAspectRatio({ contentKind: 'unspecified', coverAspectRatio: '1:1' }, 'audiobook'), '1:1');
  assert.equal(resolveCoverAspectRatio({ contentKind: 'manga', coverAspectRatio: '16:9' }, 'general'), '16:9');
  assert.equal(resolveCoverAspectRatio({ contentKind: 'music', coverAspectRatio: '4:3' }, 'general'), '4:3');
  assert.equal(resolveCoverAspectRatio(undefined, 'audiobook'), '4:3');
});

test('unknown ratios fall back to the default and map to card attributes', () => {
  assert.equal(normalizeCoverAspectRatio('21:9'), '4:3');
  assert.equal(coverRatioAttr('1:1'), '1-1');
  assert.equal(coverRatioAttr('16:9'), '16-9');
  assert.equal(coverRatioAttr(undefined), '4-3');
});
