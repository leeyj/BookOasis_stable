import test from 'node:test';
import assert from 'node:assert/strict';

// 파일 URL로 불러와야 모듈 안의 상대 import(tts_core.js, text_position_utils.js)가 풀린다
const { submitPregen, DEFAULT_LISTEN_SETTINGS } = await import(new URL('../static/js/tts/tts_pregen_client.js', import.meta.url));
const { pieceKey, segmentForTts, MAX_PIECE_CHARS } = await import(new URL('../static/js/tts/tts_core.js', import.meta.url));

const TXT = Array.from({ length: 12 }, (_, i) => `${i + 1}번째 문장은 테스트용으로 충분히 길게 쓴 문장입니다. 그래서 조각이 따로 나뉩니다.`).join('\n');

function mockFetch() {
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), opts });
    const json = (body) => ({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) });
    if (String(url).includes('/static/lib/hanja/')) return { ok: false, status: 404 };
    if (String(url).startsWith('/api/media/txt')) return { ok: true, status: 200, text: async () => TXT };
    if (String(url) === '/api/media/tts/pregen') return json({ success: true, created: true, job: { id: 1 } });
    throw new Error(`unexpected fetch ${url}`);
  };
  return calls;
}

test('default listen quality is normal (4)', () => {
  assert.equal(DEFAULT_LISTEN_SETTINGS.steps, 4);
});

test('pieces are sent starting two pieces before the listening position, with matching keys', async () => {
  const calls = mockFetch();
  const settings = { voice: 'F1', steps: 4, speed: 1.05 };
  const total = segmentForTts(TXT, MAX_PIECE_CHARS).length;
  assert.ok(total >= 6, `need several pieces, got ${total}`);
  const data = await submitPregen({ dbType: 'general', bookId: 3, settings, format: 'txt', startAt: { chapter: 0, piece: 5 } });
  assert.equal(data.startIndex, 3);
  const body = JSON.parse(calls.find((c) => c.url === '/api/media/tts/pregen').opts.body);
  assert.equal(body.pieces.length, total);
  const expectedOrder = segmentForTts(TXT, MAX_PIECE_CHARS).map((s) => s.text);
  const rotated = expectedOrder.slice(3).concat(expectedOrder.slice(0, 3));
  assert.deepEqual(body.pieces.map((p) => p.text), rotated);
  for (const p of body.pieces) assert.equal(p.key, await pieceKey(p.text, settings));
});

test('without a position the book is sent from the beginning', async () => {
  const calls = mockFetch();
  const data = await submitPregen({ dbType: 'general', bookId: 3, settings: { voice: 'F1', steps: 4, speed: 1.05 }, format: 'txt' });
  assert.equal(data.startIndex, 0);
  const body = JSON.parse(calls.find((c) => c.url === '/api/media/tts/pregen').opts.body);
  assert.equal(body.pieces[0].text, segmentForTts(TXT, MAX_PIECE_CHARS)[0].text);
});
