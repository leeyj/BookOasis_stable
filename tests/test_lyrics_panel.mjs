import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/audio_player_modules/lyrics_panel.js', import.meta.url), 'utf8');
const { findActiveLyricIndex } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('the active lyric line is the last one whose time has passed', () => {
  const lines = [{ t: 1 }, { t: 5 }, { t: 9 }];
  assert.equal(findActiveLyricIndex(lines, 0.5), -1);
  assert.equal(findActiveLyricIndex(lines, 1), 0);
  assert.equal(findActiveLyricIndex(lines, 7.2), 1);
  assert.equal(findActiveLyricIndex(lines, 120), 2);
  assert.equal(findActiveLyricIndex([], 3), -1);
});
