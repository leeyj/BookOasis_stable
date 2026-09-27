// tts_core.js - 브라우저 TTS(듣기 화면 /listen, 테스트 페이지 /experimental/tts)의 순수 로직.
// ORT/DOM에 의존하지 않아 node:test로 바로 검증할 수 있게 분리했다 (tests/test_tts_core.mjs).

// 모델 가중치는 재배포하지 않고 브라우저가 Hugging Face에서 직접 받는다 (OpenRAIL-M).
// pip supertonic 1.3.1이 검증한 리비전으로 고정해 저장소가 바뀌어도 결과가 달라지지 않게 한다.
export const MODEL_REPO = 'Supertone/supertonic-3';
export const MODEL_REVISION = '724fb5abbf5502583fb520898d45929e62f02c0b';
export const MODEL_BASE = `https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REVISION}`;
// HF 직접 다운로드가 막힐 때 쓰는 같은 출처 경로 (api/routes/tts_routes.py, onnx만 제공)
export const MODEL_FALLBACK_BASE = '/tts/model';
export const ONNX_MODELS = ['duration_predictor', 'text_encoder', 'vector_estimator', 'vocoder'];
export const VOICES = ['F1', 'F2', 'F3', 'F4', 'F5', 'M1', 'M2', 'M3', 'M4', 'M5'];

// 서버 미리 만들기 조각 키 — 합성 입력 전체의 sha256. services/tts_engine.py piece_key()와 같은 입력·같은 결과여야 한다
// (숫자는 JS 기본 표기: 1.0 → "1"). text는 speakableText()까지 거친 실제 합성 입력.
export async function pieceKey(text, { voice, steps, speed }) {
  const raw = `${MODEL_REVISION}|${voice}|${steps}|${speed}|${text}`;
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

export function modelUrl(path) {
  return `${MODEL_BASE}/${String(path).replace(/^\/+/, '')}`;
}

// ---- 텍스트 준비 ----

const NAMED_ENTITIES = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', hellip: '…', middot: '·',
  ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’', mdash: '—', ndash: '–',
};

function decodeEntities(text) {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, body) => {
    if (body[0] === '#') {
      const code = body[1] === 'x' || body[1] === 'X' ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
      try { return String.fromCodePoint(code); } catch (e) { return whole; }
    }
    const named = NAMED_ENTITIES[body.toLowerCase()];
    return named === undefined ? whole : named;
  });
}

const BLOCK_TAG = /<\/?(?:p|div|h[1-6]|li|ul|ol|br|tr|table|blockquote|section|article|header|footer|figure|figcaption|hr|pre|dd|dt)\b[^>]*>/gi;

// EPUB 챕터 API(/api/media/epub/chapter)는 정제된 HTML을 주므로 읽을 텍스트만 남긴다.
// 루비 주석(<rt>)은 본문을 두 번 읽게 되므로 버린다.
export function htmlToText(html) {
  if (!html) return '';
  const stripped = String(html)
    .replace(/<(script|style|head|rt|rp)\b[^>]*>[\s\S]*?<\/\1>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(BLOCK_TAG, '\n')
    .replace(/<[^>]*>/g, '');
  return decodeEntities(stripped)
    .split('\n')
    .map((line) => line.replace(/[ \t 　]+/g, ' ').trim())
    .filter(Boolean)
    .join('\n');
}

// 문장 끝(마침표류 + 닫는 따옴표/괄호) 뒤 공백에서만 자른다 — "3.14" 같은 숫자는 보존된다.
const SENTENCE_BREAK = /(?<=[.?!。？！…]+["'”’」』)\]]*)\s+/u;
const SPEAKABLE = /[\p{L}\p{N}]/u;

// 문장 하나를 maxLen 이하로 자르고, 각 조각의 원문 시작 위치(base 기준)를 함께 돌려준다.
function splitLong(sentence, base, maxLen) {
  const out = [];
  let rest = sentence;
  let pos = base;
  while (rest.length > maxLen) {
    // maxLen 안쪽에서 가장 뒤에 있는 쉼표 → 공백 순으로 끊을 자리를 찾고, 없으면 강제로 자른다
    const inside = rest.slice(0, maxLen);
    const comma = Math.max(inside.lastIndexOf(','), inside.lastIndexOf('，'), inside.lastIndexOf('、'));
    let cut = comma > maxLen / 3 ? comma + 1 : rest.slice(0, maxLen + 1).lastIndexOf(' ');
    if (cut <= 0) cut = maxLen;
    out.push({ text: rest.slice(0, cut).trim(), start: pos });
    const remainder = rest.slice(cut);
    pos += cut + (remainder.length - remainder.trimStart().length);
    rest = remainder.trim();
  }
  if (rest) out.push({ text: rest, start: pos });
  return out;
}

const SENTENCE_BREAK_G = new RegExp(SENTENCE_BREAK.source, 'gu');

function splitSentences(para, base) {
  const out = [];
  let last = 0;
  SENTENCE_BREAK_G.lastIndex = 0;
  let m;
  while ((m = SENTENCE_BREAK_G.exec(para)) !== null) {
    out.push({ text: para.slice(last, m.index), start: base + last });
    last = m.index + m[0].length;
  }
  out.push({ text: para.slice(last), start: base + last });
  return out;
}

// 합성 단위로 자르고 각 조각의 원문 시작 오프셋(start)을 함께 돌려준다 — 듣던 위치를 조각 번호가 아닌
// 글자 위치로 저장해 분할 방식이 바뀌어도, 뷰어 읽기 위치와도 맞출 수 있게 하기 위함.
// 줄 하나를 문단으로 보고 문장 단위로 나눈 뒤, 짧은 문장은 문단을 넘어서라도 maxLen까지 묶는다.
// 웹소설은 한 줄 대사가 많아 문단마다 끊으면 조각이 평균 3초 남짓이 되고, 화면이 꺼진 상태에서
// 오디오를 3초마다 갈아 끼우면 그만큼 끊길 기회가 늘어난다 (실측 2026-09-24).
// 글자/숫자가 하나도 없는 조각(장면 전환용 "***" 등)은 버린다.
// 엔진(Supertonic 3)은 아주 짧은 텍스트를 단독으로 합성하면 글자를 빼먹거나 무음을 낸다 — 단독 약 60% 실패,
// 같은 구절을 긴 문장과 함께 넣으면 0% (공식 Python 레퍼런스도 동일, docs/bug/20260926_bugfix_tts_short_sentence_repro.md).
// 그래서 이보다 짧은 조각은 혼자 보내지 않는다.
export const MIN_ALONE_CHARS = 15;
// 듣기 화면의 조각 최대 길이. 서버 미리 만들기도 같은 값으로 조각내야 키가 맞는다
export const MAX_PIECE_CHARS = 120;

export function segmentForTts(text, maxLen = 120, minAlone = MIN_ALONE_CHARS) {
  const source = String(text || '');
  const pieces = [];
  let buf = null;
  const lineRe = /[^\r\n]+/g;
  let line;
  while ((line = lineRe.exec(source)) !== null) {
    const raw = line[0];
    const lead = raw.length - raw.trimStart().length;
    const para = raw.trim();
    if (!para || !SPEAKABLE.test(para)) continue;
    const sentences = splitSentences(para, line.index + lead)
      .flatMap((s) => splitLong(s.text.trimEnd(), s.start, maxLen));
    for (const s of sentences) {
      if (!s.text) continue;
      // 짧은 조각은 maxLen을 넘더라도 다음 문장과 묶는다 (넘어도 MIN_ALONE_CHARS 미만만큼이라 짧다)
      if (buf && buf.text.length + 1 + s.text.length > maxLen && buf.text.length >= minAlone) { pieces.push(buf); buf = { ...s }; }
      else if (buf) buf.text = `${buf.text} ${s.text}`;
      else buf = { ...s };
    }
  }
  // 챕터 끝에 남은 짧은 조각은 앞 조각에 붙인다
  if (buf && buf.text.length < minAlone && pieces.length) pieces[pieces.length - 1].text += ` ${buf.text}`;
  else if (buf) pieces.push(buf);
  return pieces.filter((p) => SPEAKABLE.test(p.text));
}

// 한글 뒤 괄호로 병기한 한자("마종(魔鐘)")는 한글과 같은 말을 한 번 더 읽게 되므로 합성 직전에 뺀다.
// 화면 표시와 오프셋은 원문 그대로 두기 위해 segmentForTts가 아니라 합성할 문자열에만 적용한다.
// 괄호 없이 단독으로 쓴 한자는 그 자체가 뜻이라 남긴다. 다 빼서 빈 문자열이 되면 원문을 읽는다.
const HANJA_GLOSS = /\s*[(（]\s*\p{Script=Han}[\p{Script=Han}\s·・,、]*[)）]/gu;

// ---- 한자 → 한국식 음 ----
// 괄호 병기 없이 한자만 쓴 단어(무협지의 "運命", "奇人總師")를 엔진이 중국어·일본어처럼 읽으므로 합성 직전에 한글 음으로 바꾼다.
// 화면 표시는 원문 그대로. 변환표는 Unicode Unihan kHangul의 교육용 표준 음(static/lib/hanja/readings-v1.json,
// tools/hanja/build_hanja_readings.py) — 두음법칙 전 형태(女→녀)라 아래 규칙으로 보정한다.
const HAN_RUN = /[\u3400-\u9FFF\uF900-\uFAFF]+/gu;
// 글자 하나씩 바꾸면 틀리는 단어 (음이 여럿인 글자). 두음법칙·렬/률·不 규칙보다 우선한다.
export const HANJA_WORDS = {
  音樂: '음악', 樂器: '악기', 樂曲: '악곡', 聲樂: '성악', 國樂: '국악', 器樂: '기악', 樂山樂水: '요산요수',
  復活: '부활', 復興: '부흥', 復舊: '복구',
  自轉車: '자전거', 車馬: '거마', 行列: '항렬', 洞察: '통찰', 洞窟: '동굴', 一切: '일체', 便所: '변소', 便紙: '편지',
  更新: '갱신', 謁見: '알현', 容易: '용이', 難易: '난이', 交易: '교역', 貿易: '무역', 相殺: '상쇄', 遊說: '유세',
  省略: '생략', 反省: '반성', 布施: '보시', 茶: '차', 茶菓: '다과', 宅: '댁', 金氏: '김씨', 數: '수',
  十月: '시월', 六月: '유월', 初八日: '초파일', 菩提: '보리', 菩薩: '보살', 道場: '도량', 刺客: '자객', 尸: '시',
};
const HANJA_WORD_MAX = 4;
const HANJA_SUFFIXES = new Set(['者', '的', '化', '性', '家', '界', '式']);

// 한글 음절 분해/조립 (초성 19 · 중성 21 · 종성 28)
const S_BASE = 0xAC00;
const splitSyl = (s) => { const n = s.charCodeAt(0) - S_BASE; return n < 0 || n > 11171 ? null : [Math.floor(n / 588), Math.floor((n % 588) / 28), n % 28]; };
const joinSyl = (l, v, t) => String.fromCharCode(S_BASE + l * 588 + v * 28 + t);
const L_NIEUN = 2, L_RIEUL = 5, L_IEUNG = 11, L_DIGEUT = 3, L_JIEUT = 12;
const T_NONE = 0, T_NIEUN = 4;
const Y_VOWELS = new Set([2, 3, 6, 7, 12, 17, 20]); // ㅑㅒㅕㅖㅛㅠㅣ

// 두음법칙: 단어 첫머리의 ㄴ(ㅕㅛㅠㅣ 앞)·ㄹ(ㅑㅕㅖㅛㅠㅣ 앞)은 ㅇ, 그 밖의 ㄹ은 ㄴ (女→여, 流→유, 老→노, 樂→낙)
function initialLaw(syl) {
  const p = splitSyl(syl);
  if (!p) return syl;
  const [l, v, t] = p;
  if (l === L_NIEUN && Y_VOWELS.has(v) && v !== 2 && v !== 3) return joinSyl(L_IEUNG, v, t);
  if (l === L_RIEUL) return joinSyl(Y_VOWELS.has(v) ? L_IEUNG : L_NIEUN, v, t);
  return syl;
}

function convertRun(run, readings, wordInitial) {
  const chars = [...run];
  const out = [];   // 음절
  const fixed = []; // 예외 단어에서 온 음절은 규칙을 적용하지 않는다
  for (let i = 0; i < chars.length;) {
    let matched = false;
    for (let len = Math.min(HANJA_WORD_MAX, chars.length - i); len >= 1; len--) {
      const w = chars.slice(i, i + len).join('');
      if (HANJA_WORDS[w]) { for (const syl of HANJA_WORDS[w]) { out.push(syl); fixed.push(true); } i += len; matched = true; break; }
    }
    if (matched) continue;
    out.push(readings[chars[i]] || chars[i]);
    fixed.push(false);
    i++;
  }
  for (let k = 0; k < out.length; k++) {
    if (fixed[k]) continue;
    const src = chars.length === out.length ? chars[k] : null;
    // 不: ㄷ·ㅈ 앞에서 부 (不動→부동, 不正→부정)
    if (src === '不' && out[k] === '불') {
      const next = out[k + 1] && splitSyl(out[k + 1]);
      if (next && (next[0] === L_DIGEUT || next[0] === L_JIEUT)) out[k] = '부';
    }
    // 六: 十·百·千·萬 뒤에서는 육 (十六→십육, 三十六→삼십육), 그 밖은 륙 (五六→오륙)
    if (src === '六' && k > 0 && '十百千萬'.includes(chars[k - 1])) out[k] = '육';
    // 렬·률: 모음이나 ㄴ 받침 뒤에서 열·율 (規律→규율, 分裂→분열)
    if (k > 0 && (out[k] === '렬' || out[k] === '률')) {
      const prev = splitSyl(out[k - 1]);
      if (prev && (prev[2] === T_NONE || prev[2] === T_NIEUN)) out[k] = out[k] === '렬' ? '열' : '율';
    }
  }
  if (wordInitial && out.length && !fixed[0]) out[0] = initialLaw(out[0]);
  // 짝수 길이(4·6·8자) 한자어는 대개 2자 단어의 합성(梅花+路傍, 華山+論劍) — 뒤쪽 단어 첫머리에도 두음법칙
  // (작가 병기 3,907건 대조로 확인, 2026-09-26)
  // 단, 者·的 같은 접미사로 끝나면 (唯神論)+者 구조라 적용하지 않는다 (唯神論者→유신론자)
  if (out.length >= 4 && out.length % 2 === 0 && !HANJA_SUFFIXES.has(chars[chars.length - 1])) {
    for (let k = 2; k < out.length; k += 2) if (!fixed[k]) out[k] = initialLaw(out[k]);
  }
  return out.join('');
}

// readings: { 한자: 한글 음 } (없으면 그대로 돌려준다)
export function hanjaToHangul(text, readings) {
  const src = String(text || '');
  if (!readings) return src;
  return src.replace(HAN_RUN, (run, offset) => {
    // 앞 글자가 한글이면 단어 중간 (예: "대大韓" 같은 드문 섞어 쓰기) — 두음법칙을 적용하지 않는다
    const before = src[offset - 1] || '';
    const wordInitial = !/[가-힣]/.test(before);
    return convertRun(run, readings, wordInitial);
  });
}

// 엔진 글자표(unicode_indexer)에 없어 -1로 들어가는 기호 — 섞이면 그 조각이 튄다(재현 25%). 공백으로 바꾼다.
// 엔진이 스스로 치환하는 글자(— – ☆♡♥ [] 등)는 빼고, 리비전 724fb5a 글자표로 확인한 목록.
const UNMAPPED_SYMBOLS = /[♪♫♬♩★✦✧◆◇■□▲▽♤♠♧♣♢♦☞☜✔✖✕✓❤♂♀☀☁☂☎♨〃∴∵≒≠≤≥〔〕［］━│┃┌┐└┘▶◀↑⇒⇔]/gu;
// 엔진은 NFKD로 …를 ...로 풀어서 ……는 점 6개가 된다. 점 4개 이상은 짧은 문장에서 특히 잘 빠진다(재현 18회 중 15회).
const LONG_ELLIPSIS = /(?:…|‥|\.{3,})+/g;

// hanjaReadings: 한자→한글 변환표(선택). 병기 한자를 먼저 빼고 남은 한자만 한국식 음으로 바꾼다.
export function speakableText(text, hanjaReadings = null) {
  const src = String(text || '');
  const out = hanjaToHangul(src.replace(HANJA_GLOSS, ''), hanjaReadings)
    .replace(UNMAPPED_SYMBOLS, ' ')
    .replace(LONG_ELLIPSIS, '...')
    .replace(/ {2,}/g, ' ')
    .trim();
  return SPEAKABLE.test(out) ? out : src;
}

// 합성 결과가 거의 무음인가: 20ms 프레임 RMS로 소리가 난 길이를 재서 엔진이 예측한 길이의 15% 미만이면 무음으로 본다.
// 짧은 발화는 원래 앞뒤 무음 비중이 커서(실측 정상 중앙값 약 30%) 기준을 낮게 잡았다.
export function isNearSilent(wav, sampleRate, predSec, minRatio = 0.15) {
  const frame = Math.floor(sampleRate * 0.02);
  const n = frame > 0 ? Math.floor((wav?.length || 0) / frame) : 0;
  if (!n || !(predSec > 0)) return false;
  const rms = new Array(n);
  let max = 0;
  for (let f = 0; f < n; f++) {
    let sum = 0;
    for (let k = f * frame; k < (f + 1) * frame; k++) sum += wav[k] * wav[k];
    rms[f] = Math.sqrt(sum / frame);
    if (rms[f] > max) max = rms[f];
  }
  const thr = Math.max(0.01, 0.05 * max);
  const voicedSec = rms.filter((v) => v > thr).length * 0.02;
  return voicedSec / predSec < minRatio;
}

// 들은 위치를 뷰어의 읽기 진행도(/api/media/progress) 단위로 바꾼다 — 목록의 진행 막대·완독·최근 읽은 도서가
// 듣기로도 움직이게. 뷰어와 같은 규칙: TXT는 4000자 페이지(chunkText) 번호, EPUB은 챕터 번호.
// 진행도는 뷰어처럼 "마지막 위치"라서 앞부분을 다시 들으면 내려간다.
// txtChunkStarts: chunkStarts(chunkText(text, 4000)) — 뷰어 모듈이라 호출하는 쪽에서 넘긴다.
export function listenProgress(format, { chapter = 0, chapterCount = 0, offset = 0, txtChunkStarts = [] } = {}) {
  if (format === 'epub') {
    if (!(chapterCount > 0)) return null;
    const idx = Math.max(0, Math.min(chapterCount - 1, chapter));
    return { page_idx: idx, total_pages: chapterCount, epub_session: { index: idx } };
  }
  if (!txtChunkStarts.length) return null;
  let lo = 0, hi = txtChunkStarts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (txtChunkStarts[mid] <= offset) lo = mid; else hi = mid - 1;
  }
  return { page_idx: lo, total_pages: txtChunkStarts.length };
}

export function splitForTts(text, maxLen = 120, minAlone = MIN_ALONE_CHARS) {
  return segmentForTts(text, maxLen, minAlone).map((p) => p.text);
}

// 플레이어 화면용: 원문을 줄(문단)마다 [from, to) 구간으로 나누고 각 구간이 속한 조각 번호(seg)를 붙인다.
// 조각은 문단을 넘어 묶이기도 하므로 한 조각이 여러 문단에 걸칠 수 있고, 한 문단에 여러 조각이 있을 수 있다.
// 읽지 않는 줄(장면 전환 "***" 등)은 seg -1.
export function paragraphRuns(text, segments) {
  const source = String(text || '');
  const starts = (segments || []).map((s) => s.start);
  const out = [];
  const lineRe = /[^\r\n]+/g;
  let line;
  let k = -1; // start <= 현재 위치인 마지막 조각
  while ((line = lineRe.exec(source)) !== null) {
    const raw = line[0];
    const from = line.index + (raw.length - raw.trimStart().length);
    const to = line.index + raw.trimEnd().length;
    if (from >= to) continue;
    if (!SPEAKABLE.test(raw)) { out.push([{ from, to, seg: -1 }]); continue; }
    while (k + 1 < starts.length && starts[k + 1] <= from) k++;
    const runs = [];
    let pos = from;
    while (k + 1 < starts.length && starts[k + 1] < to) {
      if (starts[k + 1] > pos) runs.push({ from: pos, to: starts[k + 1], seg: k });
      pos = starts[k + 1];
      k++;
    }
    runs.push({ from: pos, to, seg: k });
    out.push(runs);
  }
  return out;
}

// offset이 속한 조각 번호 (start <= offset인 마지막 조각)
export function pieceAtOffset(segments, offset) {
  if (!segments || !segments.length) return 0;
  let lo = 0, hi = segments.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (segments[mid].start <= offset) lo = mid; else hi = mid - 1;
  }
  return lo;
}

// ---- 모델 다운로드 (Cache API + Range 이어받기) ----

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function totalFromHeaders(res, offset) {
  const range = res.headers.get('content-range');
  if (range) {
    const m = /\/(\d+)\s*$/.exec(range);
    if (m) return Number(m[1]);
  }
  const len = Number(res.headers.get('content-length'));
  return Number.isFinite(len) && len > 0 ? len + offset : null;
}

class HttpError extends Error {
  constructor(url, status) { super(`${url}: HTTP ${status}`); this.status = status; }
}

// 400MB급 모델을 인터넷으로 받다 끊기는 경우(측정 때 3건)를 위해, 받은 만큼 유지하고
// Range 요청으로 나머지만 이어 받는다. 서버가 Range를 무시하고 200을 주면 처음부터 다시 받는다.
// fallbackUrl: fetch() 자체가 거부되면(HF CDN 리다이렉트의 CORS 차단 등) 한 번 그쪽으로 넘어가
// 받은 위치부터 계속 받는다. 캐시 키는 항상 url이라 어느 쪽에서 받았든 기존 캐시가 그대로 맞는다.
export async function resumableFetch(url, {
  fetchImpl = globalThis.fetch?.bind(globalThis),
  fallbackUrl = null,
  cache = null,
  onProgress = null,
  retries = 5,
  baseDelayMs = 800,
  sleep = defaultSleep,
} = {}) {
  if (cache) {
    try {
      const hit = await cache.match(url);
      if (hit) {
        const buffer = await hit.arrayBuffer();
        onProgress?.({ received: buffer.byteLength, total: buffer.byteLength, fromCache: true });
        return { buffer, fromCache: true, attempts: 0 };
      }
    } catch (e) { /* 캐시가 깨졌으면 네트워크로 */ }
  }

  let parts = [];
  let received = 0;
  let total = null;
  let failures = 0;
  let attempts = 0;
  let source = url;
  for (;;) {
    attempts++;
    try {
      const headers = received > 0 ? { Range: `bytes=${received}-` } : {};
      let res;
      try {
        res = await fetchImpl(source, { headers });
      } catch (e) {
        if (!fallbackUrl || source === fallbackUrl) throw e;
        source = fallbackUrl;
        attempts--;
        continue;
      }
      if (received > 0 && res.status === 200) { parts = []; received = 0; }
      else if (!res.ok) throw new HttpError(source, res.status);
      total = totalFromHeaders(res, received) ?? total;
      const reader = res.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parts.push(value);
        received += value.byteLength;
        onProgress?.({ received, total, fromCache: false });
      }
      if (total !== null && received < total) throw new Error(`${source}: 응답이 ${received}/${total}바이트에서 끝남`);
      break;
    } catch (e) {
      // 4xx는 다시 받아도 같으므로 바로 실패 (429만 예외)
      if (e instanceof HttpError && e.status < 500 && e.status !== 429) throw e;
      failures++;
      if (failures > retries) throw e;
      await sleep(baseDelayMs * 2 ** (failures - 1));
    }
  }

  const bytes = new Uint8Array(received);
  let off = 0;
  for (const p of parts) { bytes.set(p, off); off += p.byteLength; }
  if (cache) {
    try { await cache.put(url, new Response(bytes.slice())); } catch (e) { /* 저장 공간 부족 등은 무시 */ }
  }
  return { buffer: bytes.buffer, fromCache: false, attempts, fromFallback: source !== url };
}

// ---- 듣던 위치 ----

export function positionKey(dbType, bookId, chapter = 0) {
  return `bo-tts:${dbType}:${bookId}:${chapter}`;
}

export function lastChapterKey(dbType, bookId) {
  return `bo-tts:${dbType}:${bookId}:last`;
}

// localStorage는 사생활 보호 모드 등에서 예외를 던질 수 있어 항상 감싼다.
export function loadPosition(storage, key, total = null) {
  try {
    const raw = storage?.getItem(key);
    if (raw === null || raw === undefined) return 0;
    const piece = Number(JSON.parse(raw)?.piece);
    if (!Number.isInteger(piece) || piece < 0) return 0;
    return total !== null && piece >= total ? 0 : piece;
  } catch (e) {
    return 0;
  }
}

// 조각 안 재생 위치(초)까지 복원한다. 멈춘 지점 그대로가 아니라 rewindSec만큼 앞에서 시작해
// 문맥을 다시 잡게 하고, 조각 번호가 무효(텍스트 변경 등)면 위치도 버린다.
export function loadResume(storage, key, total = null, rewindSec = 2.5) {
  const piece = loadPosition(storage, key, total);
  let offset = 0;
  try {
    const saved = JSON.parse(storage?.getItem(key) ?? 'null');
    const raw = Number(saved?.offset);
    if (saved && Number(saved.piece) === piece && Number.isFinite(raw) && raw > 0) offset = Math.max(0, raw - rewindSec);
  } catch (e) { offset = 0; }
  return { piece, offset };
}

export function savePosition(storage, key, piece, extra = {}) {
  try {
    storage?.setItem(key, JSON.stringify({ piece, ...extra, savedAt: Date.now() }));
    return true;
  } catch (e) {
    return false;
  }
}

// ---- 앞서 생성하기 ----

// 화면이 꺼져도 생성은 계속되지만(측정 확인), 챕터 전체를 WAV로 쌓으면 메모리가 커진다
// (24kHz 16bit 모노 ≈ 48KB/초). 재생 위치보다 targetSec만큼만 앞서 만들어 둔다.
export class AheadPlanner {
  constructor({ targetSec = 300, maxPieces = 60 } = {}) {
    this.targetSec = targetSec;
    this.maxPieces = maxPieces;
    this.pending = new Map(); // piece index -> audioSec (생성됐지만 아직 재생이 끝나지 않음)
  }

  get bufferedSec() {
    let sum = 0;
    for (const sec of this.pending.values()) sum += sec;
    return sum;
  }

  onGenerated(index, audioSec) { this.pending.set(index, audioSec); }

  onPlayed(index) { this.pending.delete(index); }

  reset() { this.pending.clear(); }

  shouldGenerate() {
    return this.bufferedSec < this.targetSec && this.pending.size < this.maxPieces;
  }
}
