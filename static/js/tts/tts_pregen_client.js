// tts_pregen_client.js - 듣기 서버 미리 만들기 요청 (듣기 화면과 도서 메뉴가 같이 쓴다).
// 책 전체를 듣기 화면과 똑같은 규칙(segmentForTts → speakableText)으로 조각내고 조각 키를 붙여 서버에 보낸다.
// 규칙이 조금이라도 다르면 키가 안 맞아 미리 만든 음성을 못 쓰므로, 조각내는 코드는 여기 한 곳에만 둔다.
import { htmlToText, segmentForTts, speakableText, pieceKey, pieceAtOffset, MIN_ALONE_CHARS, MAX_PIECE_CHARS } from './tts_core.js';
import { resolveOffset } from '../viewer/text_position_utils.js';

// 듣기 화면의 기본 설정 (tts_player.js settings와 같아야 한다)
export const DEFAULT_LISTEN_SETTINGS = { voice: 'F1', steps: 4, speed: 1.05 };

// 한자→한국식 음 변환표. 한 번만 받고, 쓰는 쪽은 끝날 때까지 기다린다 (키에 변환 결과가 들어간다)
let hanjaPromise = null;
let hanjaReadings = null;
export function loadHanjaReadings() {
  if (!hanjaPromise) {
    hanjaPromise = (async () => {
      try {
        const res = await fetch('/static/lib/hanja/readings-v1.json');
        if (res.ok) hanjaReadings = await res.json();
      } catch (e) { hanjaReadings = null; }
      return hanjaReadings;
    })();
  }
  return hanjaPromise;
}

async function getJson(url) {
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

const q = (dbType, bookId) => `db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}`;

export async function fetchEpubChapterText(dbType, bookId, idx) {
  const ch = await getJson(`/api/media/epub/chapter?${q(dbType, bookId)}&chapter_idx=${idx}`);
  return htmlToText(ch.content);
}

// 그림·제목 한 줄뿐인 EPUB 항목 — 재생 때도 건너뛴다 (tts_player.js loadText)
export function isFillerSegments(segments) {
  return !segments.length || (segments.length === 1 && segments[0].text.length < MIN_ALONE_CHARS);
}

// 이 책을 이 사용자가 마지막으로 들은 설정(없으면 기본값)과, 마지막으로 읽거나 들은 위치
export async function savedListenState(dbType, bookId) {
  const settings = { ...DEFAULT_LISTEN_SETTINGS };
  try {
    const data = await getJson(`/api/media/tts/position?${q(dbType, bookId)}&_ts=${Date.now()}`);
    const st = data?.state || {};
    const saved = st.settings || {};
    if (saved.voice) settings.voice = saved.voice;
    if ([4, 8].includes(Number(saved.steps))) settings.steps = Number(saved.steps);
    if (saved.speed) settings.speed = Number(saved.speed);
    const pos = st.latest === 'read' ? st.read : st.latest === 'listen' ? st.listen : null;
    return { settings, position: pos ? { chapter: pos.chapter_idx || 0, pos } : null };
  } catch (e) {
    return { settings, position: null };
  }
}

// 책 전체 조각 목록 [{chapter, text}]. format/chapterCount/txtText를 알면 넘겨서 다시 받지 않게 한다.
// startAt: {chapter, piece}(듣기 화면의 현재 조각) 또는 {chapter, pos}(서버에 저장된 읽기·듣기 위치). 그 조각의 전체 목록 번호를 startIndex로 돌려준다.
export async function collectBookPieces({ dbType, bookId, format = null, chapterCount = null, txtText = null, onProgress = null, startAt = null }) {
  const readings = await loadHanjaReadings();
  let fmt = format;
  if (!fmt) {
    const info = await getJson(`/api/media/books/${encodeURIComponent(bookId)}/reader-info?type=${encodeURIComponent(dbType)}`);
    if (!info.success) throw new Error(info.error || 'book info failed');
    fmt = String(info.book.file_format || '').toLowerCase();
  }
  const out = [];
  let startIndex = 0;
  const add = (chapter, segments, text) => {
    if (startAt && chapter === startAt.chapter) {
      const local = startAt.pos ? pieceAtOffset(segments, resolveOffset(text, startAt.pos)) : (startAt.piece || 0);
      startIndex = out.length + Math.min(Math.max(0, local), Math.max(0, segments.length - 1));
    }
    for (const seg of segments) out.push({ chapter, text: speakableText(seg.text, readings) });
  };
  if (fmt === 'epub') {
    let count = chapterCount;
    if (count === null) count = (await getJson(`/api/media/epub/meta?${q(dbType, bookId)}`)).total_chapters || 0;
    for (let idx = 0; idx < count; idx++) {
      onProgress?.(idx + 1, count);
      const text = await fetchEpubChapterText(dbType, bookId, idx);
      const segments = segmentForTts(text, MAX_PIECE_CHARS);
      if (!isFillerSegments(segments)) add(idx, segments, text);
    }
  } else if (fmt === 'txt' || fmt === 'text') {
    let text = txtText;
    if (text === null) {
      const res = await fetch(`/api/media/txt?${q(dbType, bookId)}`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error(`txt: HTTP ${res.status}`);
      text = await res.text();
    }
    add(0, segmentForTts(text, MAX_PIECE_CHARS), text);
  } else {
    throw new Error(`unsupported format: ${fmt}`);
  }
  return { pieces: out, startIndex };
}

// 조각에 키를 붙여 요청한다. 성공하면 서버 응답({created, job})을 돌려준다.
export async function submitPregen({ dbType, bookId, settings, onProgress = null, ...bookHints }) {
  if (!globalThis.crypto?.subtle) throw new Error('https required');
  const conf = { voice: settings.voice, steps: Number(settings.steps), speed: Number(settings.speed) };
  const { pieces: all, startIndex } = await collectBookPieces({ dbType, bookId, onProgress, ...bookHints });
  if (!all.length) throw new Error('no text');
  // 듣던 곳부터 먼저 만들게 목록을 돌린다(서버는 받은 순서대로 만든다). 이어 듣기가 조금 앞에서 시작하므로 두 조각 앞부터.
  const from = Math.max(0, startIndex - 2);
  const pieces = from ? all.slice(from).concat(all.slice(0, from)) : all;
  const keyed = await Promise.all(pieces.map(async (p) => ({ ...p, key: await pieceKey(p.text, conf) })));
  const res = await fetch('/api/media/tts/pregen', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ db_type: dbType, book_id: Number(bookId), ...conf, pieces: keyed }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
  return { ...data, pieceCount: keyed.length, startIndex: from };
}
