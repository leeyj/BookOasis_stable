import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
}

const { makeAnchor, findAnchorOffset, resolveOffset, chunkStarts, offsetToChunk, pickOtherDeviceReadTarget } = await load('../static/js/viewer/text_position_utils.js');
const { chunkText } = await load('../static/js/viewer/txt_text_utils.js');
const { segmentForTts, splitForTts, pieceAtOffset, htmlToText, listenProgress } = await load('../static/js/tts/tts_core.js');

const NOVEL = Array.from({ length: 400 }, (_, i) => (i % 3 === 0
  ? `"${i}번째 대사다. 정말이야?"`
  : `그는 ${i}번째 문단에서 천천히 걸음을 옮겼다. 바람이 불었다.`)).join('\n');

// ---- anchors ----

test('an anchor is ~30 meaningful characters with whitespace collapsed', () => {
  const text = '앞부분\n\n   그는   문을\n열었다. 바람이 불었다. 누구지? 아무도 없었다.';
  const anchor = makeAnchor(text, 3);
  assert.equal(anchor, '그는 문을 열었다. 바람이 불었다. 누구지? 아무도 없');
  assert.equal(anchor.length, 30);
  assert.equal(makeAnchor(text, 10_000), '');
});

test('anchors match across different whitespace and line breaks (EPUB viewer vs TTS text)', () => {
  const viewerText = '제1장그는 문을 열었다.바람이 불었다.'; // stripHtml이 블록 사이를 붙인 경우
  const ttsText = '제1장\n그는 문을 열었다.\n바람이 불었다.';
  const anchor = makeAnchor(viewerText, 3);
  const found = findAnchorOffset(ttsText, anchor, 0);
  assert.equal(found, ttsText.indexOf('그는'));
});

test('a repeated phrase resolves to the occurrence nearest the approximate offset', () => {
  const text = 'A. 같은 문장이 반복된다. B. '.repeat(50);
  const anchor = '같은 문장이 반복된다';
  const approx = text.length * 0.6;
  const found = findAnchorOffset(text, anchor, approx);
  const all = [...text.matchAll(/같은 문장이 반복된다/g)].map((m) => m.index);
  const nearest = all.reduce((a, b) => (Math.abs(b - approx) < Math.abs(a - approx) ? b : a));
  assert.equal(found, nearest);
});

test('missing or too-short anchors fall back to the offset ratio', () => {
  const text = 'x'.repeat(1000);
  assert.equal(findAnchorOffset(text, '없는 문구입니다', 10), null);
  assert.equal(findAnchorOffset(text, 'xx', 10), null);
  // 다른 길이의 텍스트 기준 위치(50%)는 비율로 옮겨진다
  assert.equal(resolveOffset(text, { char_offset: 200, text_len: 400, anchor: '없는 문구입니다' }), 500);
  assert.equal(resolveOffset(text, null), 0);
  assert.equal(resolveOffset('', { char_offset: 5, text_len: 10 }), 0);
  assert.equal(resolveOffset(text, { char_offset: 5000, text_len: 0 }), 1000);
});

test('regex metacharacters in anchors are matched literally', () => {
  const text = '앞 (정말?) [확인] $100 + 50% ... 뒤';
  const at = text.indexOf('(정말?)');
  assert.equal(findAnchorOffset(text, '(정말?) [확인] $100 + 50%', 0), at);
});

// ---- TXT chunk mapping (must agree with the viewer's chunkText) ----

test('offsetToChunk agrees with the viewer chunk boundaries', () => {
  const chunks = chunkText(NOVEL, 4000);
  assert.ok(chunks.length >= 3);
  const starts = chunkStarts(chunks);
  assert.equal(starts[0], 0);
  for (let i = 0; i < chunks.length; i++) {
    assert.equal(NOVEL.slice(starts[i], starts[i] + chunks[i].length), chunks[i]);
    assert.deepEqual(offsetToChunk(chunks, starts[i]), { chunkIdx: i, inChunk: 0 });
    assert.deepEqual(offsetToChunk(chunks, starts[i] + 7), { chunkIdx: i, inChunk: 7 });
  }
  assert.equal(offsetToChunk(chunks, NOVEL.length + 99).chunkIdx, chunks.length - 1);
  assert.deepEqual(offsetToChunk([], 10), { chunkIdx: 0, inChunk: 0 });
});

// ---- TTS segments carry original offsets ----

test('each TTS segment start points at its text in the original string', () => {
  const text = '  첫 줄입니다.\r\n\r\n  둘째 줄. 셋째!\n\t넷째 줄은 조금 더 길게 써서 합쳐지는지 본다.\n***\n끝.';
  const segments = segmentForTts(text, 20);
  assert.deepEqual(segments.map((s) => s.text), splitForTts(text, 20));
  for (const s of segments) {
    const firstWord = s.text.split(' ')[0];
    assert.ok(text.startsWith(firstWord, s.start), `segment "${s.text}" start ${s.start}`);
  }
});

test('segment starts are exact for long sentences split without punctuation', () => {
  const text = Array.from({ length: 80 }, (_, i) => `단어${i}`).join(' ');
  for (const s of segmentForTts(text, 50)) assert.ok(text.startsWith(s.text.split(' ')[0], s.start));
  const solid = '다'.repeat(95);
  assert.deepEqual(segmentForTts(solid, 40).map((s) => s.start), [0, 40, 80]);
});

test('pieceAtOffset finds the segment containing an offset', () => {
  const segments = segmentForTts(NOVEL, 120);
  assert.equal(pieceAtOffset(segments, 0), 0);
  for (const i of [1, 17, segments.length - 1]) {
    assert.equal(pieceAtOffset(segments, segments[i].start), i);
    assert.equal(pieceAtOffset(segments, segments[i].start + 3), i);
  }
  assert.equal(pieceAtOffset([], 50), 0);
});

// ---- round trips: read -> listen -> read ----

test('a TXT reading position maps to the TTS piece that contains it and back to the same chunk', () => {
  const chunks = chunkText(NOVEL, 4000);
  const starts = chunkStarts(chunks);
  // 뷰어가 2번째 청크 중간을 읽는 중
  const readOffset = starts[1] + 1234;
  const pos = { char_offset: readOffset, text_len: NOVEL.length, anchor: makeAnchor(NOVEL, readOffset) };
  const segments = segmentForTts(NOVEL, 120);
  const piece = pieceAtOffset(segments, resolveOffset(NOVEL, pos));
  assert.ok(segments[piece].start <= readOffset && readOffset - segments[piece].start < 200);
  // 그 조각에서 듣기 위치를 저장하고 뷰어로 돌아가면 같은 청크
  const listenOffset = segments[piece].start;
  const back = offsetToChunk(chunks, resolveOffset(NOVEL, {
    char_offset: listenOffset, text_len: NOVEL.length, anchor: makeAnchor(NOVEL, listenOffset),
  }));
  assert.equal(back.chunkIdx, 1);
  assert.ok(Math.abs(starts[1] + back.inChunk - readOffset) < 200); // 몇 줄 이내
});

test('an EPUB position survives the viewer/TTS text difference within a few lines', () => {
  const html = Array.from({ length: 60 }, (_, i) => `<p>${i}번째 문단의 내용이다. 그는 말했다.</p>`).join('');
  const ttsText = htmlToText(html);
  const viewerText = html.replace(/<[^>]+>/g, ''); // stripHtml 흉내: 블록 사이 공백 없음
  const viewerOffset = viewerText.indexOf('37번째');
  const pos = { char_offset: viewerOffset, text_len: viewerText.length, anchor: makeAnchor(viewerText, viewerOffset) };
  const resolved = resolveOffset(ttsText, pos);
  assert.equal(resolved, ttsText.indexOf('37번째'));
});

// ---- 들은 위치 → 뷰어 읽기 진행도 ----

test('TXT listen progress uses the same 4000-char pages as the viewer', () => {
  const chunks = chunkText(NOVEL, 4000);
  const starts = chunkStarts(chunks);
  assert.ok(chunks.length > 2, 'fixture should span several viewer pages');
  const segs = segmentForTts(NOVEL, 120);
  for (const seg of [segs[0], segs[Math.floor(segs.length / 2)], segs.at(-1)]) {
    const p = listenProgress('txt', { offset: seg.start, txtChunkStarts: starts });
    assert.equal(p.page_idx, offsetToChunk(chunks, seg.start).chunkIdx);
    assert.equal(p.total_pages, chunks.length);
    assert.equal(p.epub_session, undefined);
  }
  // 끝까지 들으면 본문 끝 기준으로 보고 → 마지막 페이지 → 서버가 완독(95% 이상)으로 기록한다.
  // (마지막 조각의 시작 위치는 마지막 페이지 앞일 수 있어 그걸로는 완독이 안 된다)
  assert.equal(listenProgress('txt', { offset: NOVEL.length, txtChunkStarts: starts }).page_idx, chunks.length - 1);
});

test('EPUB listen progress is the chapter index, like the viewer', () => {
  assert.deepEqual(listenProgress('epub', { chapter: 4, chapterCount: 14 }), { page_idx: 4, total_pages: 14, epub_session: { index: 4 } });
  assert.equal(listenProgress('epub', { chapter: 20, chapterCount: 14 }).page_idx, 13);
  assert.equal(listenProgress('epub', { chapter: 0, chapterCount: 0 }), null);
  assert.equal(listenProgress('txt', { offset: 10, txtChunkStarts: [] }), null);
});

test('pickOtherDeviceReadTarget: 다른 기기에서 더 최근에 읽었을 때만 그 위치를 따른다', () => {
  const read = { chapter_idx: 2, char_offset: 900, text_len: 5000, anchor: '빈선예도 그녀의 아우라를 느꼈는지', updated_ms: 1_000_000 };
  const state = (extra = {}) => ({ latest: 'read', read, clockOffsetMs: 0, ...extra });
  const local = (extra = {}) => ({ chunkIdx: 2, anchorText: '그녀를 누구라고 설명해야 하나?', savedAt: 900_000, ...extra });

  // 다른 기기가 더 최근 (서버 시각 1,000,000 > 이 기기 900,000 + 5초)
  assert.equal(pickOtherDeviceReadTarget(state(), local()), read);
  // 이 기기가 닫을 때 보낸 자기 보고: 저장 시각과 거의 같음 → 무시
  assert.equal(pickOtherDeviceReadTarget(state(), local({ savedAt: 998_000 })), null);
  // 이 기기가 더 최근
  assert.equal(pickOtherDeviceReadTarget(state(), local({ savedAt: 1_200_000 })), null);
  // 같은 문장(공백 차이 무시) → 이동/알림 없음
  assert.equal(pickOtherDeviceReadTarget(state(), local({ anchorText: '빈선예도 그녀의  아우라를 느꼈는지', savedAt: 1 })), null);
  // 이 기기 시계가 서버보다 2분 늦음: 이 기기 저장(900,000)은 서버 시계로 1,020,000 → 서버 읽기(1,000,000)가 더 오래됨
  assert.equal(pickOtherDeviceReadTarget(state({ clockOffsetMs: 120_000 }), local()), null);
  // 새 기기/저장소 삭제(로컬 없음), 구버전 로컬(savedAt 없음) → 문장이 다르면 따른다
  assert.equal(pickOtherDeviceReadTarget(state(), null), read);
  assert.equal(pickOtherDeviceReadTarget(state(), local({ savedAt: undefined })), read);
  // 듣기 위치가 더 최근이거나(listen) 세밀한 위치가 없으면(legacy/null) 관여하지 않는다
  assert.equal(pickOtherDeviceReadTarget(state({ latest: 'listen' }), null), null);
  assert.equal(pickOtherDeviceReadTarget(state({ latest: 'legacy' }), null), null);
  assert.equal(pickOtherDeviceReadTarget(null, null), null);
  assert.equal(pickOtherDeviceReadTarget(state({ read: { ...read, anchor: '' } }), null), null);
});
