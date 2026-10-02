import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/audio_player_modules/track_cover.js', import.meta.url), 'utf8');
const { getTrackCoverImage } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('music mode shows the cover of the song being played', () => {
  const meta = { is_music: true, cover_image: '/album' };
  assert.equal(getTrackCoverImage(meta, { cover_image: '/track/7' }), '/track/7');
  assert.equal(getTrackCoverImage(meta, {}), '/album');
  assert.equal(getTrackCoverImage(meta, null), '/album');
});

test('audiobooks keep the book cover', () => {
  assert.equal(getTrackCoverImage({ cover_image: '/book' }, { cover_image: '/track/1' }), '/book');
  assert.equal(getTrackCoverImage(null, null), '');
});
