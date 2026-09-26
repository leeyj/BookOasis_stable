// text_position_utils.js - 읽기(뷰어)와 듣기(TTS) 위치를 서로 옮기기 위한 순수 함수.
// 위치는 (글자 오프셋, 기준 텍스트 길이, 앵커 문구)로 주고받는다. 받는 쪽은 자기 텍스트에서
// 앵커를 찾아 맞추고, 못 찾으면 오프셋/길이 비율로 근사한다 (몇 줄 오차는 허용 — 2026-09-24 결정).
// EPUB은 뷰어(stripHtml)와 TTS(htmlToText)의 공백/줄바꿈 처리가 달라, 앵커 비교는 공백을 전부 무시한다.

export const ANCHOR_CHARS = 30;

const MIN_LINE_ANCHOR = 8;

// 오프셋 위치부터 공백을 정리한 약 30자. 공백만 있는 구간이면 뒤로 넘어가 의미 있는 글자부터 잡는다.
// 줄(=뷰어의 <p> 한 개) 안에 충분한 글자가 있으면 줄 끝에서 멈춘다 — 뷰어의 앵커 복원
// (restoreTxtAnchorInfoByMode)이 문단 요소 단위로 먼저 찾기 때문에 두 문단에 걸친 앵커는 덜 정확하다.
export function makeAnchor(text, offset, length = ANCHOR_CHARS) {
  const source = String(text || '');
  let start = Math.max(0, Math.min(Number(offset) || 0, source.length));
  while (start < source.length && /\s/.test(source[start])) start++;
  const window = source.slice(start, start + length * 4);
  const lineEnd = window.indexOf('\n');
  if (lineEnd >= 0) {
    const line = window.slice(0, lineEnd).replace(/\s+/g, ' ').trim();
    if (line.length >= MIN_LINE_ANCHOR) return line.slice(0, length);
  }
  return window.replace(/\s+/g, ' ').trim().slice(0, length);
}

function escapeRegExp(ch) {
  return ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 앵커를 공백 무시로 찾아 approxOffset에 가장 가까운 시작 위치를 돌려준다 (없으면 null).
// 같은 문구가 여러 번 나오는 경우(반복 대사 등)를 위해 가장 가까운 것을 고른다.
export function findAnchorOffset(text, anchor, approxOffset = 0) {
  const chars = Array.from(String(anchor || '').replace(/\s+/g, ''));
  if (chars.length < 4) return null; // 너무 짧으면 엉뚱한 곳에 맞을 확률이 높다
  const pattern = new RegExp(chars.map(escapeRegExp).join('\\s*'), 'gu');
  const source = String(text || '');
  let best = null;
  let m;
  while ((m = pattern.exec(source)) !== null) {
    if (best === null || Math.abs(m.index - approxOffset) < Math.abs(best - approxOffset)) best = m.index;
    if (m.index > approxOffset && best !== null && m.index - approxOffset > Math.abs(best - approxOffset)) break;
  }
  return best;
}

// 저장된 위치 {char_offset, text_len, anchor}를 지금 가진 text 기준 오프셋으로 바꾼다.
export function resolveOffset(text, pos) {
  const length = String(text || '').length;
  if (!pos || !length) return 0;
  const offset = Math.max(0, Number(pos.char_offset) || 0);
  const basis = Number(pos.text_len) || 0;
  const approx = basis > 0 ? Math.round((offset / basis) * length) : offset;
  const found = findAnchorOffset(text, pos.anchor, Math.min(approx, length));
  return Math.max(0, Math.min(length, found ?? approx));
}

// 뷰어 chunkText(text, 4000) 결과의 각 청크 시작 오프셋
export function chunkStarts(chunks) {
  const starts = [];
  let acc = 0;
  for (const chunk of chunks || []) {
    starts.push(acc);
    acc += String(chunk).length;
  }
  return starts;
}

export function offsetToChunk(chunks, offset) {
  const starts = chunkStarts(chunks);
  if (!starts.length) return { chunkIdx: 0, inChunk: 0 };
  let lo = 0, hi = starts.length - 1;
  const target = Math.max(0, Number(offset) || 0);
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= target) lo = mid; else hi = mid - 1;
  }
  return { chunkIdx: lo, inChunk: target - starts[lo] };
}
