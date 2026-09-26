import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../static/js/tts/tts_core.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const {
  MODEL_BASE, modelUrl, htmlToText, splitForTts, resumableFetch, speakableText, segmentForTts, paragraphRuns, MIN_ALONE_CHARS, isNearSilent, hanjaToHangul,
  positionKey, lastChapterKey, loadPosition, loadResume, savePosition, AheadPlanner,
} = await import(moduleUrl);

const noSpace = (s) => s.replace(/\s+/g, '');

// ---- splitForTts ----

test('korean sentences are split and short ones merged within a paragraph', () => {
  const text = '그는 문을 열었다. 바람이 불었다! 누구지? 아무도 없었다.';
  assert.deepEqual(splitForTts(text, 20, 0), ['그는 문을 열었다. 바람이 불었다!', '누구지? 아무도 없었다.']);
  assert.deepEqual(splitForTts(text, 200), [text]);
});

test('short lines are merged across paragraphs up to maxLen and blank lines are ignored', () => {
  const text = '첫 문단입니다.\r\n\r\n\n두 번째 문단입니다.\n세 번째.';
  assert.deepEqual(splitForTts(text, 200), ['첫 문단입니다. 두 번째 문단입니다. 세 번째.']);
  assert.deepEqual(splitForTts(text, 20, 0), ['첫 문단입니다. 두 번째 문단입니다.', '세 번째.']);
});

test('web-novel style one-line dialogue yields pieces near maxLen, not one per line', () => {
  const lines = Array.from({ length: 40 }, (_, i) => (i % 2 ? `"그래, ${i}번째 대답이다."` : `그가 ${i}번째로 말했다.`));
  const pieces = splitForTts(lines.join('\n'), 120);
  assert.ok(pieces.length <= 8, `too many pieces: ${pieces.length}`);
  for (const p of pieces.slice(0, -1)) assert.ok(p.length > 80 && p.length <= 120, `piece length ${p.length}`);
});

test('closing quotes stay attached to their sentence', () => {
  const text = '"정말이야?" 그녀가 물었다. “응.” 나는 답했다… 그리고 웃었다.';
  const pieces = splitForTts(text, 10, 0);
  assert.deepEqual(pieces, ['"정말이야?"', '그녀가 물었다.', '“응.”', '나는 답했다…', '그리고 웃었다.']);
});

test('decimal numbers are not treated as sentence ends', () => {
  assert.deepEqual(splitForTts('원주율은 3.14 정도다. 끝.', 15, 0), ['원주율은 3.14 정도다.', '끝.']);
});

test('a long sentence without punctuation is cut under maxLen without losing characters', () => {
  const words = Array.from({ length: 60 }, (_, i) => `단어${i}`);
  const text = words.join(' ');
  const pieces = splitForTts(text, 50);
  assert.ok(pieces.length > 1);
  for (const p of pieces) assert.ok(p.length <= 50, `piece too long: ${p.length}`);
  assert.equal(noSpace(pieces.join('')), noSpace(text));
});

test('a long sentence prefers a comma break and a spaceless run is hard-cut', () => {
  const withComma = '가'.repeat(30) + ', ' + '나'.repeat(30);
  assert.deepEqual(splitForTts(withComma, 40), ['가'.repeat(30) + ',', '나'.repeat(30)]);
  const solid = '다'.repeat(95);
  const pieces = splitForTts(solid, 40);
  assert.deepEqual(pieces.map((p) => p.length), [40, 40, 15]);
});

test('pieces without letters or numbers (scene breaks) are dropped', () => {
  assert.deepEqual(splitForTts('끝이었다.\n***\n- - -\n새 장.', 100), ['끝이었다. 새 장.']);
  assert.deepEqual(splitForTts('', 100), []);
  assert.deepEqual(splitForTts(null, 100), []);
});

test('every non-space character of a realistic passage survives splitting', () => {
  const text = [
    '"대사부님, 오셨습니까?" 청명이 고개를 숙였다.',
    '',
    '장문인은 대답 대신 긴 한숨을 내쉬었다. 화산의 봄은 늘 늦게 왔고, 올해도 예외는 아니었다. 매화가 필 무렵이면 산문 앞 돌계단에는 이끼가 두껍게 앉았다.',
    '그래서 뭐?',
  ].join('\n');
  const pieces = splitForTts(text, 60);
  for (const p of pieces) assert.ok(p.length <= 60);
  assert.equal(noSpace(pieces.join('')), noSpace(text));
});

// ---- htmlToText ----

test('epub chapter html becomes one line per block', () => {
  const html = '<h2>제1장</h2><p>첫 줄<br/>둘째 줄</p><div><p>  공백   정리 </p></div><p></p>';
  assert.equal(htmlToText(html), '제1장\n첫 줄\n둘째 줄\n공백 정리');
});

test('entities are decoded and script, style, ruby annotations are dropped', () => {
  const html = '<style>p{}</style><script>alert(1)</script><p>A&amp;B &lt;i&gt; &#54620;&#xAE00; &hellip;&nbsp;끝</p>'
    + '<p><ruby>漢<rt>한</rt></ruby>字</p><!-- note -->';
  assert.equal(htmlToText(html), 'A&B <i> 한글 … 끝\n漢字');
  assert.equal(htmlToText(''), '');
  assert.equal(htmlToText('&unknown; &#xZZ;'), '&unknown; &#xZZ;');
});

// ---- resumableFetch ----

function bytesOf(n, seed = 7) {
  return Uint8Array.from({ length: n }, (_, i) => (i * seed) % 251);
}

function streamResponse(bytes, { status = 200, failAfter = null, headers = {}, chunk = 64 } = {}) {
  let sent = 0;
  const body = new ReadableStream({
    pull(controller) {
      if (failAfter !== null && sent >= failAfter) { controller.error(new TypeError('network error')); return; }
      if (sent >= bytes.length) { controller.close(); return; }
      const end = Math.min(bytes.length, sent + chunk, failAfter ?? Infinity);
      controller.enqueue(bytes.slice(sent, end));
      sent = end;
    },
  });
  return new Response(body, { status, headers });
}

// Range를 지원하는 가짜 서버. failOnce[n]이면 n번째 요청을 중간에 끊는다.
function rangeServer(full, { failAt = {}, ignoreRange = false } = {}) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    const range = init.headers?.Range ?? null;
    calls.push(range);
    const n = calls.length;
    const m = range && !ignoreRange ? /bytes=(\d+)-/.exec(range) : null;
    const start = m ? Number(m[1]) : 0;
    const slice = full.slice(start);
    const headers = m
      ? { 'content-length': String(slice.length), 'content-range': `bytes ${start}-${full.length - 1}/${full.length}` }
      : { 'content-length': String(full.length) };
    return streamResponse(slice, { status: m ? 206 : 200, headers, failAfter: failAt[n] ?? null });
  };
  return { fetchImpl, calls };
}

const fastRetry = { sleep: async () => {}, baseDelayMs: 1 };

test('a dropped download resumes with a Range request and yields identical bytes', async () => {
  const full = bytesOf(1000);
  const { fetchImpl, calls } = rangeServer(full, { failAt: { 1: 300, 2: 200 } });
  const progress = [];
  const { buffer, fromCache } = await resumableFetch('https://x/model.onnx', {
    fetchImpl, onProgress: (p) => progress.push(p), ...fastRetry,
  });
  assert.equal(fromCache, false);
  assert.deepEqual(new Uint8Array(buffer), full);
  assert.deepEqual(calls, [null, 'bytes=300-', 'bytes=500-']);
  assert.equal(progress.at(-1).received, 1000);
  assert.equal(progress.at(-1).total, 1000);
});

test('a server that ignores Range restarts from zero instead of corrupting the file', async () => {
  const full = bytesOf(500, 13);
  const { fetchImpl, calls } = rangeServer(full, { failAt: { 1: 256 }, ignoreRange: true });
  const { buffer } = await resumableFetch('https://x/a', { fetchImpl, ...fastRetry });
  assert.deepEqual(new Uint8Array(buffer), full);
  assert.equal(calls.length, 2);
});

test('a body that ends early (short of content-length) is retried', async () => {
  const full = bytesOf(400);
  let call = 0;
  const fetchImpl = async (url, init = {}) => {
    call++;
    if (call === 1) return new Response(full.slice(0, 100), { status: 200, headers: { 'content-length': '400' } });
    const start = Number(/bytes=(\d+)-/.exec(init.headers.Range)[1]);
    return new Response(full.slice(start), { status: 206, headers: { 'content-range': `bytes ${start}-399/400` } });
  };
  const { buffer, attempts } = await resumableFetch('https://x/b', { fetchImpl, ...fastRetry });
  assert.deepEqual(new Uint8Array(buffer), full);
  assert.equal(attempts, 2);
});

test('a cache hit skips the network and a fresh download is stored', async () => {
  const store = new Map();
  const cache = {
    match: async (url) => (store.has(url) ? new Response(store.get(url)) : undefined),
    put: async (url, res) => { store.set(url, new Uint8Array(await res.arrayBuffer())); },
  };
  const full = bytesOf(300);
  const { fetchImpl, calls } = rangeServer(full);
  const first = await resumableFetch('https://x/c', { fetchImpl, cache, ...fastRetry });
  assert.equal(first.fromCache, false);
  assert.deepEqual(store.get('https://x/c'), full);

  const second = await resumableFetch('https://x/c', { fetchImpl, cache, ...fastRetry });
  assert.equal(second.fromCache, true);
  assert.deepEqual(new Uint8Array(second.buffer), full);
  assert.equal(calls.length, 1);
});

test('gives up after the retry budget and does not retry a 404', async () => {
  const full = bytesOf(100);
  const { fetchImpl, calls } = rangeServer(full, { failAt: { 1: 0, 2: 0, 3: 0, 4: 0 } });
  await assert.rejects(resumableFetch('https://x/d', { fetchImpl, retries: 2, ...fastRetry }), /network error/);
  assert.equal(calls.length, 3);

  let notFoundCalls = 0;
  const notFound = async () => { notFoundCalls++; return new Response('nope', { status: 404 }); };
  await assert.rejects(resumableFetch('https://x/e', { fetchImpl: notFound, ...fastRetry }), /HTTP 404/);
  assert.equal(notFoundCalls, 1);
});

test('backoff doubles between failures', async () => {
  const waits = [];
  const full = bytesOf(50);
  const { fetchImpl } = rangeServer(full, { failAt: { 1: 0, 2: 0, 3: 0 } });
  await resumableFetch('https://x/f', { fetchImpl, baseDelayMs: 100, sleep: async (ms) => { waits.push(ms); } });
  assert.deepEqual(waits, [100, 200, 400]);
});

// ---- model urls / positions ----

test('model urls are pinned to a revision', () => {
  assert.match(MODEL_BASE, /\/resolve\/[0-9a-f]{40}$/);
  assert.equal(modelUrl('/onnx/vocoder.onnx'), `${MODEL_BASE}/onnx/vocoder.onnx`);
});

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)) };
}

test('listening position round-trips per book and chapter', () => {
  const storage = memoryStorage();
  const key = positionKey('general', 42, 3);
  assert.equal(key, 'bo-tts:general:42:3');
  assert.notEqual(key, positionKey('adult', 42, 3));
  assert.equal(lastChapterKey('general', 42), 'bo-tts:general:42:last');
  assert.equal(loadPosition(storage, key), 0);
  assert.equal(savePosition(storage, key, 17, { total: 90 }), true);
  assert.equal(loadPosition(storage, key), 17);
  assert.equal(loadPosition(storage, key, 90), 17);
  // 텍스트가 바뀌어 조각 수가 줄면 처음부터
  assert.equal(loadPosition(storage, key, 10), 0);
});

test('resume restores the in-piece offset with a small rewind', () => {
  const storage = memoryStorage();
  const key = positionKey('general', 7, 0);
  assert.deepEqual(loadResume(storage, key, 100), { piece: 0, offset: 0 });
  savePosition(storage, key, 12, { offset: 9.3 });
  assert.deepEqual(loadResume(storage, key, 100), { piece: 12, offset: 9.3 - 2.5 });
  savePosition(storage, key, 12, { offset: 1.2 });
  assert.deepEqual(loadResume(storage, key, 100), { piece: 12, offset: 0 });
  // 조각 시작 시 저장(offset 없음)은 조각 처음부터
  savePosition(storage, key, 13);
  assert.deepEqual(loadResume(storage, key, 100), { piece: 13, offset: 0 });
  // 조각 번호가 무효가 되면 위치도 버린다
  savePosition(storage, key, 50, { offset: 8 });
  assert.deepEqual(loadResume(storage, key, 20), { piece: 0, offset: 0 });
  savePosition(storage, key, 3, { offset: 'x' });
  assert.deepEqual(loadResume(storage, key, 20), { piece: 3, offset: 0 });
  const throwing = { getItem() { throw new Error('denied'); } };
  assert.deepEqual(loadResume(throwing, key, 20), { piece: 0, offset: 0 });
});

test('broken or unavailable storage never throws', () => {
  const throwing = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('quota'); } };
  assert.equal(loadPosition(throwing, 'k'), 0);
  assert.equal(savePosition(throwing, 'k', 3), false);
  assert.equal(loadPosition(null, 'k'), 0);
  const garbage = memoryStorage();
  garbage.setItem('k', '{not json');
  assert.equal(loadPosition(garbage, 'k'), 0);
  garbage.setItem('k', JSON.stringify({ piece: -4 }));
  assert.equal(loadPosition(garbage, 'k'), 0);
});

// ---- AheadPlanner ----

test('generation pauses once the buffer target is reached and resumes as audio plays', () => {
  const planner = new AheadPlanner({ targetSec: 30, maxPieces: 10 });
  assert.equal(planner.shouldGenerate(), true);
  planner.onGenerated(0, 15);
  planner.onGenerated(1, 14);
  assert.equal(planner.shouldGenerate(), true);
  planner.onGenerated(2, 12);
  assert.equal(planner.bufferedSec, 41);
  assert.equal(planner.shouldGenerate(), false);
  planner.onPlayed(0);
  assert.equal(planner.shouldGenerate(), true);
  planner.reset();
  assert.equal(planner.bufferedSec, 0);
});

test('the piece cap applies even when pieces are very short', () => {
  const planner = new AheadPlanner({ targetSec: 1000, maxPieces: 3 });
  for (let i = 0; i < 3; i++) planner.onGenerated(i, 1);
  assert.equal(planner.shouldGenerate(), false);
});

test('a rejected fetch (CORS) switches to fallbackUrl once, resuming, and caches under the primary url', async () => {
  const full = bytesOf(600);
  const store = new Map();
  const cache = {
    match: async (u) => (store.has(u) ? new Response(store.get(u)) : undefined),
    put: async (u, res) => { store.set(u, new Uint8Array(await res.arrayBuffer())); },
  };
  const server = rangeServer(full);
  const urls = [];
  let primaryCalls = 0;
  const fetchImpl = async (u, init) => {
    urls.push(u);
    if (u === 'https://hf/m.onnx') {
      primaryCalls++;
      if (primaryCalls === 1) return streamResponse(full, { headers: { 'content-length': '600' }, failAfter: 200 });
      throw new TypeError('Failed to fetch');
    }
    return server.fetchImpl(u, init);
  };
  const { buffer, attempts, fromFallback } = await resumableFetch('https://hf/m.onnx', {
    fetchImpl, cache, fallbackUrl: '/fb/m.onnx', ...fastRetry,
  });
  assert.deepEqual(new Uint8Array(buffer), full);
  assert.equal(fromFallback, true);
  assert.equal(attempts, 2);
  assert.deepEqual(urls, ['https://hf/m.onnx', 'https://hf/m.onnx', '/fb/m.onnx']);
  assert.deepEqual(server.calls, ['bytes=200-']);
  assert.deepEqual(store.get('https://hf/m.onnx'), full);
});

test('without fallbackUrl a rejected fetch is retried on the same url', async () => {
  let calls = 0;
  const fetchImpl = async () => { calls++; throw new TypeError('Failed to fetch'); };
  await assert.rejects(resumableFetch('https://hf/x', { fetchImpl, retries: 1, ...fastRetry }), /Failed to fetch/);
  assert.equal(calls, 2);
});

test('hanja glosses in parentheses are dropped before synthesis', () => {
  assert.equal(
    speakableText('-마종(魔鐘)은 너 혈황종(血皇宗)에게 천하(天下)를 줄 것이나, 또한 네 영혼(靈魂)을 천 가닥 만 가닥으로 찢어 발기리라!'),
    '-마종은 너 혈황종에게 천하를 줄 것이나, 또한 네 영혼을 천 가닥 만 가닥으로 찢어 발기리라!',
  );
  assert.equal(speakableText('검(劍 · 刀)과 창（槍）'), '검과 창');
  assert.equal(speakableText('그는 (웃으며) 말했다 (2024)'), '그는 (웃으며) 말했다 (2024)');
  assert.equal(speakableText('天下無敵'), '天下無敵');
  assert.equal(speakableText('(天下)'), '(天下)');
});

test('paragraphRuns maps every readable character of the text to the piece that speaks it', () => {
  const text = '첫 문장이다. 둘째 문장이다.\n\n***\n짧은 줄\n  들여쓴 문단의 아주 긴 문장, 쉼표 뒤에서 잘릴 수 있다.';
  const segments = segmentForTts(text, 20);
  const paras = paragraphRuns(text, segments);
  assert.equal(paras.length, 4);
  assert.deepEqual(paras[1], [{ from: text.indexOf('***'), to: text.indexOf('***') + 3, seg: -1 }]);
  // 각 조각의 시작 위치에서 새 구간이 시작하고, 구간을 이으면 문단 원문이 그대로 나온다
  const runs = paras.flat();
  for (let i = 0; i < segments.length; i++) {
    assert.ok(runs.some((r) => r.seg === i && r.from === segments[i].start), `piece ${i} starts a run`);
  }
  for (const p of paras) {
    const joined = p.map((r) => text.slice(r.from, r.to)).join('');
    assert.equal(joined, text.slice(p[0].from, p.at(-1).to));
  }
  // 구간의 조각 번호는 줄어들지 않는다
  const segs = runs.filter((r) => r.seg >= 0).map((r) => r.seg);
  assert.deepEqual(segs, [...segs].sort((a, b) => a - b));
  assert.equal(segs.at(-1), segments.length - 1);
});

test('paragraphRuns handles empty input', () => {
  assert.deepEqual(paragraphRuns('', []), []);
  assert.deepEqual(paragraphRuns('***', []), [[{ from: 0, to: 3, seg: -1 }]]);
});

// ---- 짧은 조각은 혼자 보내지 않는다 (엔진이 짧은 단독 텍스트를 빼먹음 — docs/bug/20260926_bugfix_tts_short_sentence_repro.md) ----

test('a short title before a long paragraph is merged into it even past maxLen', () => {
  const para = '가'.repeat(110) + '다.';
  const text = `화산파 천재검귀 6권\n${para}`;
  const segs = segmentForTts(text, 120);
  assert.equal(segs.length, 1);
  assert.equal(segs[0].text, `화산파 천재검귀 6권 ${para}`);
  assert.equal(segs[0].start, 0);
  assert.ok(segs[0].text.length <= 120 + MIN_ALONE_CHARS);
});

test('a short line left between two long ones joins the next piece', () => {
  const long = '나'.repeat(113) + '다.'; // 앞 조각에 붙이면 120자를 넘는 길이
  const pieces = splitForTts(`${long}\n아....그건\n${long}`, 120);
  assert.deepEqual(pieces, [long, `아....그건 ${long}`]);
});

test('a short line at the end of a chapter joins the previous piece', () => {
  const long = '라'.repeat(110) + '다.';
  const pieces = splitForTts(`${long}\n끝.`, 120);
  assert.deepEqual(pieces, [`${long} 끝.`]);
});

test('a chapter that is only a short line is still read', () => {
  assert.deepEqual(splitForTts('후기', 120), ['후기']);
});

test('no piece shorter than MIN_ALONE_CHARS is produced when neighbours exist', () => {
  const lines = Array.from({ length: 50 }, (_, i) => (i % 3 === 0 ? '응.' : '그는 오래도록 창밖을 바라보며 아무 말도 하지 않았다. 바람이 불었다.'.repeat(1 + (i % 2))));
  const pieces = splitForTts(lines.join('\n'), 120);
  assert.ok(pieces.length > 1);
  for (const p of pieces) assert.ok(p.length >= MIN_ALONE_CHARS, `short piece: ${p}`);
});

test('symbols missing from the engine table are dropped and long ellipses shortened', () => {
  assert.equal(speakableText('노래를 불렀다♪ 별이 빛난다★'), '노래를 불렀다 별이 빛난다');
  assert.equal(speakableText('〔알림〕 ▶ 시작'), '알림 시작');
  assert.equal(speakableText('아....그건'), '아...그건');
  assert.equal(speakableText('아……그건 말이야.'), '아...그건 말이야.');
  assert.equal(speakableText('그건... 아니야.'), '그건... 아니야.');
  assert.equal(speakableText('원주율은 3.14다.'), '원주율은 3.14다.');
  assert.equal(speakableText('♪'), '♪');
});

test('isNearSilent flags an almost silent clip but not normal or short speech', () => {
  const sr = 1000;
  const tone = (sec, amp) => Array.from({ length: Math.round(sec * sr) }, (_, i) => amp * Math.sin(i / 3));
  const silence = (sec) => new Array(Math.round(sec * sr)).fill(0);
  assert.equal(isNearSilent(silence(1.5), sr, 1.5), true);
  assert.equal(isNearSilent([...silence(1.4), ...tone(0.1, 0.3)], sr, 1.5), true);   // 7%
  assert.equal(isNearSilent([...silence(0.9), ...tone(0.45, 0.3), ...silence(0.15)], sr, 1.5), false); // 30%
  assert.equal(isNearSilent(tone(3, 0.3), sr, 3), false);
  assert.equal(isNearSilent([], sr, 1), false);
  assert.equal(isNearSilent(tone(1, 0.3), sr, 0), false);
});

// ---- 한자 → 한국식 음 (static/lib/hanja/readings-v1.json) ----

const HANJA = JSON.parse(await readFile(new URL('../static/lib/hanja/readings-v1.json', import.meta.url), 'utf8'));

test('standalone hanja words are read with Korean readings', () => {
  const cases = {
    運命: '운명', 人間萬事塞翁之馬: '인간만사새옹지마', 奇人總師: '기인총사', 華山派: '화산파', 天下第一: '천하제일',
    // 두음법칙: 단어 첫머리
    女人: '여인', 流星: '유성', 老人: '노인', 樂園: '낙원', 來日: '내일', 良心: '양심', 李氏: '이씨',
    // 단어 안쪽은 그대로, 짝수 길이 합성어의 뒤 단어 첫머리는 두음법칙
    男女: '남녀', 法律: '법률', 男女老少: '남녀노소', 砂上樓閣: '사상누각', 華山論劍: '화산논검',
    // 접미사로 끝나면 (X論)+者 구조
    唯神論者: '유신론자', 運命的: '운명적',
    // 렬·률, 不, 六, 음이 여럿인 글자
    規律: '규율', 分裂: '분열', 不動: '부동', 不正: '부정', 不幸: '불행', 十六: '십육', 三十六: '삼십육', 五六: '오륙',
    音樂: '음악', 馬車: '마차', 自轉車: '자전거', 赤狼: '적랑', 全裸: '전라',
  };
  for (const [hanja, hangul] of Object.entries(cases)) assert.equal(hanjaToHangul(hanja, HANJA), hangul, hanja);
});

test('hanja conversion keeps particles and only runs on hanja', () => {
  assert.equal(hanjaToHangul('그 塔이 完成 직전 무너질 運命이었다', HANJA), '그 탑이 완성 직전 무너질 운명이었다');
  assert.equal(hanjaToHangul('運命', null), '運命');
  assert.equal(hanjaToHangul('䞿', HANJA), '䞿'); // 표에 없는 희귀자는 그대로
});

test('speakableText drops glosses first, then converts the remaining hanja', () => {
  assert.equal(speakableText('서막(序幕) 그 塔이 運命이었다', HANJA), '서막 그 탑이 운명이었다');
  assert.equal(speakableText('서막(序幕) 그 塔이', null), '서막 그 塔이');
});
