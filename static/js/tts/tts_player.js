// tts_player.js - 듣기 화면(/listen).
// 본문 전체를 스크롤로 보여 주고 지금 읽는 조각을 강조한다. 페이지 모드는 없다.
// 생성/재생 엔진(생성 대기열 + AheadPlanner, <audio> 하나로 src 교체, 예상 밖 일시정지 자동 재개,
// mediaSession, 조각 안 오프셋 이어 듣기, 위치 서버 동기화)은 실폰에서 검증된 실험 페이지
// (templates/experimental_tts.html)와 같은 동작을 그대로 옮겼다. 진단 정보는 LOG 오버레이로 뺐다.
// 화면 문구는 i18n(static/i18n/*.json의 tts.*)으로, LOG 오버레이의 진단 로그는 개발용이라 한국어 그대로 둔다.
import { ort, loadCfgs, loadTextProcessor, loadVoiceStyle, TextToSpeech, writeWavFile } from '/static/lib/supertonic/st_helper.js';
import {
  MODEL_BASE, MODEL_FALLBACK_BASE, MODEL_REVISION, ONNX_MODELS, VOICES, modelUrl, htmlToText, segmentForTts, pieceAtOffset,
  resumableFetch, speakableText, paragraphRuns, isNearSilent, MIN_ALONE_CHARS, listenProgress, positionKey, lastChapterKey, loadResume, savePosition, AheadPlanner,
} from '/static/js/tts/tts_core.js';
import { makeAnchor, resolveOffset, chunkStarts } from '/static/js/viewer/text_position_utils.js';
import { chunkText } from '/static/js/viewer/txt_text_utils.js';

const $ = (id) => document.getElementById(id);
const t = (key, vars = {}) => window.i18n?.t(`tts.${key}`, vars) ?? key;
const params = new URLSearchParams(location.search);
const bookId = params.get('book_id');
// 도서 메뉴/상세/뷰어의 "듣기"로 열면 autoplay=1 — 준비되는 대로 바로 재생을 시도한다.
// 새로고침 때 다시 자동재생되지 않도록 주소에서는 지운다.
let autoplayWanted = params.get('autoplay') === '1';
if (autoplayWanted) {
  params.delete('autoplay');
  try { history.replaceState(null, '', `${location.pathname}?${params}`); } catch (e) { /* 무시 */ }
}
const dbType = params.get('db_type') || 'general';
const CACHE_NAME = `bo-tts-supertonic3-${MODEL_REVISION.slice(0, 8)}`;
const TOTAL_MODEL_BYTES = 398_000_000;
const MAX_PIECE_CHARS = 120;
const SPEEDS = [0.9, 1.05, 1.2, 1.4];
const STEPS = [[2, 'quality_fast'], [4, 'quality_normal'], [8, 'quality_best']];
const FONT_SIZES = [16, 18, 19, 21, 24];
const THEMES = [['dark', 'theme_dark'], ['light', 'theme_light'], ['sepia', 'theme_sepia']];
const UI_KEY = 'bo-tts-player-ui';
const PARAS_PER_BLOCK = 60;
const storage = (() => { try { return window.localStorage; } catch (e) { return null; } })();
const t0 = performance.now();

// ---- 로그 (LOG 오버레이) ----
function log(msg) {
  const line = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${msg}`;
  const el = $('log');
  el.textContent += line + '\n';
  if (!$('devOverlay').hidden) el.scrollTop = 1e9;
}
function kv(el, obj) {
  el.replaceChildren(...Object.entries(obj).flatMap(([k, v]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    return [dt, dd];
  }));
}
let toastTimer = null;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg; el.hidden = false; el.style.opacity = '1';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.opacity = '0'; setTimeout(() => { el.hidden = true; }, 300); }, 2600);
}

// ---- 화면 설정 (기기별) ----
const ui = (() => {
  const d = { fontSize: 19, theme: 'dark', follow: true };
  try { return { ...d, ...JSON.parse(storage?.getItem(UI_KEY) || '{}') }; } catch (e) { return d; }
})();
function saveUi() { try { storage?.setItem(UI_KEY, JSON.stringify(ui)); } catch (e) { /* 무시 */ } }
function applyUi() {
  document.documentElement.dataset.theme = ui.theme;
  document.documentElement.style.setProperty('--font-size', `${ui.fontSize}px`);
  document.querySelector('meta[name=theme-color]').content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  $('followToggle').checked = ui.follow;
}

// ---- 상태 ----
const book = { title: '', format: '', chapters: [], chapter: 0 };
const planner = new AheadPlanner({ targetSec: 300, maxPieces: 60 });
const S = {
  tts: null, style: null, styleVoice: null,
  pieces: [], cur: 0, genNext: 0, clips: new Map(),
  token: 0, active: false, waiting: false, stallStart: null, stalls: 0, playedInRun: false, userPaused: false, resumeTries: 0, pendingOffset: 0,
  text: '', segments: [], sync: null, syncApplied: false,
  genSec: 0, audioSec: 0, loading: false,
};
const settings = { voice: 'F1', steps: 8, speed: 1.05 };
let wake = null;
const wakeGenerator = () => { if (wake) { const w = wake; wake = null; w(); } };

// 같은 ORT 세션에 추론이 겹치지 않도록 한 번에 하나씩만 돌린다 (위치 이동 직후 이전 루프가 아직 끝나지 않았을 때)
let inferChain = Promise.resolve();
function inferExclusive(fn) {
  const run = inferChain.then(fn, fn);
  inferChain = run.catch(() => {});
  return run;
}

// ---- 환경 ----
async function detectEnv() {
  let webgpu = '없음';
  if (navigator.gpu) {
    try {
      const a = await navigator.gpu.requestAdapter();
      webgpu = a ? `있음${a.info?.vendor ? ` (${a.info.vendor} ${a.info.architecture || ''})` : ''}` : '어댑터 없음';
    } catch (e) { webgpu = '오류: ' + e.message; }
  }
  const threads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1;
  ort.env.wasm.wasmPaths = '/tts/ort/';
  ort.env.wasm.numThreads = threads;
  if (!self.isSecureContext) $('insecure').hidden = false;
  kv($('env'), {
    'HTTPS': self.isSecureContext ? '예' : '아니오',
    '교차 출처 격리': self.crossOriginIsolated ? `예 (WASM ${threads}스레드)` : '아니오 (WASM 1스레드)',
    'WebGPU': webgpu,
    '모델 캐시': 'caches' in self ? '사용 가능' : '불가',
  });
  return webgpu.startsWith('있음');
}

// ---- 도서 ----
async function getJson(url) {
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

async function loadBookInfo() {
  const info = await getJson(`/api/media/books/${encodeURIComponent(bookId)}/reader-info?type=${encodeURIComponent(dbType)}`);
  if (!info.success) throw new Error(info.error || t('book_info_failed'));
  book.title = info.book.title;
  book.format = String(info.book.file_format || '').toLowerCase();
  $('bookTitle').textContent = book.title;
  document.title = `${t('page_title')} · ${book.title}`;
  if (book.format === 'epub') {
    const meta = await getJson(`/api/media/epub/meta?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}`);
    const titles = new Map();
    for (const t of meta.toc || []) if (!titles.has(t.chapter_idx)) titles.set(t.chapter_idx, t.title);
    book.chapters = Array.from({ length: meta.total_chapters || 0 }, (_, i) => titles.get(i) || t('chapter_fallback', { n: i + 1 }));
    $('chapterBtn').hidden = false; $('chapterBtn').disabled = false; $('autoNextField').hidden = false;
    let last = 0;
    try { last = Number(storage?.getItem(lastChapterKey(dbType, bookId))) || 0; } catch (e) { last = 0; }
    const synced = syncChapter();
    if (synced !== null) last = synced;
    book.chapter = Math.min(Math.max(0, last), Math.max(0, book.chapters.length - 1));
  } else if (book.format !== 'txt') {
    throw new Error(t('only_txt_epub', { format: book.format.toUpperCase() }));
  }
}

async function fetchChapterText(idx) {
  const ch = await getJson(`/api/media/epub/chapter?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}&chapter_idx=${idx}`);
  return htmlToText(ch.content);
}

async function loadText() {
  let text;
  let segments;
  if (book.format === 'epub') {
    // 표지·삽화처럼 그림만 있는 항목(앞쪽에 여러 장 이어지는 경우가 많다)은 읽을 글자가 없으므로
    // 글자가 있는 다음 항목까지 건너뛴다. 뒤로는 가지 않는다. 제목 한 줄뿐인 속표지("화산파 천재검귀 6권")도 같이 건너뛴다 —
    // 앞뒤로 묶을 문장이 없어 엔진이 단독으로 받게 되는데, 짧은 단독 텍스트는 잘 빠지거나 튄다.
    const isFiller = (segs) => !segs.length || (segs.length === 1 && segs[0].text.length < MIN_ALONE_CHARS);
    const from = book.chapter;
    text = await fetchChapterText(book.chapter);
    segments = segmentForTts(text, MAX_PIECE_CHARS);
    while (isFiller(segments) && book.chapter + 1 < book.chapters.length) {
      book.chapter++;
      text = await fetchChapterText(book.chapter);
      segments = segmentForTts(text, MAX_PIECE_CHARS);
    }
    if (book.chapter !== from && !isFiller(segments)) {
      log(`${from + 1}~${book.chapter}번째 항목은 그림이나 제목만 있어 건너뜀`);
      toast(t('skipped_images'));
      S.syncApplied = true; // 동기화 위치는 건너뛴 항목 기준이라 새 항목에는 맞지 않는다
      try { storage?.setItem(lastChapterKey(dbType, bookId), String(book.chapter)); } catch (e) { /* 무시 */ }
    }
    $('chapterName').textContent = `${book.chapter + 1}. ${book.chapters[book.chapter] || ''}`;
  } else {
    const res = await fetch(`/api/media/txt?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}`, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(t('text_failed', { status: res.status }));
    text = await res.text();
    segments = segmentForTts(text, MAX_PIECE_CHARS);
  }
  S.text = text;
  S.segments = segments;
  S.pieces = S.segments.map((s) => s.text);
  const resume = loadResume(storage, positionKey(dbType, bookId, book.chapter), S.pieces.length);
  S.cur = resume.piece;
  S.pendingOffset = resume.offset;
  const synced = syncStartPiece(text);
  if (synced) {
    if (synced.piece !== S.cur) S.pendingOffset = 0;
    S.cur = synced.piece;
    if (synced.notice) toast(t(synced.notice));
  }
  $('seek').max = String(Math.max(0, S.pieces.length - 1));
  const at = S.cur || S.pendingOffset ? `, ${S.cur + 1}번째 조각 ${S.pendingOffset.toFixed(1)}초부터` : '';
  log(`본문 ${text.length.toLocaleString()}자 → ${S.pieces.length.toLocaleString()}조각${at}${synced ? ` (${synced.source})` : ''}`);
  renderText();
  renderNow({ instant: true });
  updateControls();
}

function updateControls() {
  for (const id of ['playBtn', 'prevBtn', 'nextBtn', 'seek']) $(id).disabled = !S.tts || !S.pieces.length;
}

// ---- 읽기↔듣기 위치 동기화 (/api/media/tts/position) ----
function syncChapter() {
  const st = S.sync;
  if (!st || S.syncApplied || book.format !== 'epub') return null;
  if (st.latest === 'read') return st.read.chapter_idx;
  if (st.latest === 'listen') return st.listen.chapter_idx;
  if (st.latest === 'legacy' && st.legacy.epub_index !== null && st.legacy.epub_index !== undefined) return st.legacy.epub_index;
  return null;
}

function syncStartPiece(text) {
  const st = S.sync;
  if (!st || S.syncApplied || !S.segments.length) return null;
  S.syncApplied = true;
  if (st.latest === 'read') {
    return { piece: pieceAtOffset(S.segments, resolveOffset(text, st.read)), notice: 'started_at_read', source: '읽던 위치' };
  }
  if (st.latest === 'listen') {
    return { piece: pieceAtOffset(S.segments, resolveOffset(text, st.listen)), source: '듣던 위치' };
  }
  if (st.latest === 'legacy' && book.format === 'txt' && st.legacy.pages_read > 0) {
    const starts = chunkStarts(chunkText(text, 4000));
    const offset = starts[Math.min(starts.length - 1, st.legacy.pages_read - 1)] || 0;
    return { piece: pieceAtOffset(S.segments, offset), notice: 'started_at_read', source: '읽던 페이지' };
  }
  return null;
}

async function fetchSync() {
  try {
    const res = await fetch(`/api/media/tts/position?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}&_ts=${Date.now()}`, { cache: 'no-store' });
    const data = res.ok ? await res.json() : null;
    S.sync = data && data.success ? data.state : null;
  } catch (e) { S.sync = null; }
  const saved = S.sync && S.sync.settings;
  if (saved) {
    // 다른 기기에서 쓰던 음성 설정을 이어받는다
    if (saved.voice && VOICES.includes(saved.voice)) settings.voice = saved.voice;
    if (saved.steps) settings.steps = Number(saved.steps);
    if (saved.speed) settings.speed = Number(saved.speed);
  }
}

// 듣기 위치 서버 저장: 조각이 바뀔 때(10초 간격 제한) + 일시정지/화면 이탈 시 즉시
let lastListenReport = 0;
function reportListen(force = false, useBeacon = false, atEnd = false) {
  if (!S.segments || !S.segments.length || !S.playedInRun) return;
  const now = Date.now();
  if (!force && now - lastListenReport < 10_000) return;
  lastListenReport = now;
  const seg = S.segments[S.cur];
  if (!seg) return;
  const body = JSON.stringify({
    db_type: dbType, book_id: Number(bookId), kind: 'listen',
    chapter_idx: book.format === 'epub' ? book.chapter : 0,
    char_offset: seg.start, text_len: S.text.length, anchor: makeAnchor(S.text, seg.start),
    voice: settings.voice, steps: settings.steps, speed: settings.speed,
  });
  // 뷰어의 읽기 진행도도 같이 올린다 (목록 진행 막대·완독·최근 읽은 도서)
  const progress = listenProgress(book.format, {
    // 끝까지 들었으면 본문 끝 기준 — 마지막 조각은 마지막 페이지 앞에서 시작할 수 있어 완독 처리가 안 됐다
    chapter: book.chapter, chapterCount: book.chapters.length, offset: atEnd ? S.text.length : seg.start,
    txtChunkStarts: book.format === 'epub' ? [] : txtChunkStarts(),
  });
  // 떠날 때(beacon)는 서버 버퍼를 거치지 않고 바로 저장 — BookOasis 창이 곧바로 다시 읽어 간다
  const progressBody = progress && JSON.stringify({ db_type: dbType, book_id: Number(bookId), ...progress, ...(useBeacon ? { flush_immediately: true } : {}) });
  try {
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon('/api/media/tts/position', new Blob([body], { type: 'application/json' }));
      if (progressBody) { navigator.sendBeacon('/api/media/progress', new Blob([progressBody], { type: 'application/json' })); notifyProgress(); }
      return;
    }
    fetch('/api/media/tts/position', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
    if (progressBody) fetch('/api/media/progress', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: progressBody, keepalive: true }).then(notifyProgress, () => {});
  } catch (e) { /* 동기화 실패는 재생에 영향 없음 */ }
}

// 읽기 진행도를 저장했다고 BookOasis 창에 알린다 → 목록/상세/홈이 새로고침 없이 갱신된다 (static/js/tts_progress_listener.js)
const progressChannel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('bookoasis-tts-progress') : null;
function notifyProgress() {
  try { progressChannel?.postMessage({ db_type: dbType, book_id: Number(bookId) }); } catch (e) { /* 무시 */ }
}

// TXT 뷰어의 4000자 페이지 시작 위치 (본문이 바뀔 때만 다시 계산)
let txtStartsCache = { text: null, starts: [] };
function txtChunkStarts() {
  if (txtStartsCache.text !== S.text) txtStartsCache = { text: S.text, starts: chunkStarts(chunkText(S.text, 4000)) };
  return txtStartsCache.starts;
}

// ---- 모델 ----
async function modelCached() {
  if (!('caches' in self)) return false;
  try {
    const cache = await caches.open(CACHE_NAME);
    const hits = await Promise.all(ONNX_MODELS.map((m) => cache.match(modelUrl(`onnx/${m}.onnx`))));
    return hits.every(Boolean);
  } catch (e) {
    return false;
  }
}

// 한자→한국식 음 변환표 (약 100KB, /static/lib는 오래 캐시된다). 못 받으면 한자를 그대로 넘긴다.
let hanjaReadings = null;
async function loadHanjaReadings() {
  try {
    const res = await fetch('/static/lib/hanja/readings-v1.json');
    if (res.ok) hanjaReadings = await res.json();
  } catch (e) { log('한자 변환표를 받지 못함 — 한자는 그대로 읽습니다'); }
}

async function loadModel(hasWebGpu, cached) {
  if (!hanjaReadings) loadHanjaReadings();
  if (S.loading || S.tts) return;
  S.loading = true;
  $('modelCard').hidden = false;
  $('loadBtn').hidden = true;
  $('mcTitle').textContent = t(cached ? 'model_opening' : 'model_downloading');
  $('mcSub').textContent = t(cached ? 'model_opening_sub' : 'model_downloading_sub');
  renderStatus();
  let cache = null;
  if ('caches' in self) { try { cache = await caches.open(CACHE_NAME); } catch (e) { cache = null; } }
  const received = new Map();
  let fromCacheAll = true;
  const td = performance.now();
  try {
    const bufs = [];
    for (const m of ONNX_MODELS) {
      log(`${m}.onnx 받는 중`);
      const { buffer, fromCache, attempts, fromFallback } = await resumableFetch(modelUrl(`onnx/${m}.onnx`), {
        cache,
        fallbackUrl: `${MODEL_FALLBACK_BASE}/onnx/${m}.onnx`,
        onProgress: ({ received: got }) => {
          received.set(m, got);
          const sum = [...received.values()].reduce((a, b) => a + b, 0);
          const ratio = Math.min(1, sum / TOTAL_MODEL_BYTES);
          $('dlBar').style.transform = `scaleX(${ratio})`;
          if (!cached) $('mcSub').textContent = t('model_progress', { got: Math.round(sum / 1e6), total: Math.round(TOTAL_MODEL_BYTES / 1e6) });
        },
      });
      fromCacheAll = fromCacheAll && fromCache;
      if (attempts > 1) log(`${m}.onnx: 끊겨서 ${attempts - 1}번 이어 받음`);
      if (fromFallback) log(`${m}.onnx: HF 직접 다운로드가 막혀 서버에서 받음`);
      bufs.push(buffer);
    }
    const dlSec = (performance.now() - td) / 1000;
    $('mcSub').textContent = t('model_preparing');
    const want = $('backend').value;
    const eps = want === 'auto' ? (hasWebGpu ? ['webgpu', 'wasm'] : ['wasm']) : [want];
    let sessions = null, used = null;
    const ts = performance.now();
    for (const ep of eps) {
      try {
        sessions = [];
        for (let i = 0; i < ONNX_MODELS.length; i++) {
          sessions.push(await ort.InferenceSession.create(new Uint8Array(bufs[i]), { executionProviders: [ep], graphOptimizationLevel: 'all' }));
        }
        used = ep; break;
      } catch (e) { log(`${ep} 세션 실패: ${e.message}`); }
    }
    if (!used) throw new Error('모든 백엔드에서 세션 생성 실패');
    const onnxDir = `${MODEL_BASE}/onnx`;
    S.tts = new TextToSpeech(await loadCfgs(onnxDir), await loadTextProcessor(onnxDir), ...sessions);
    kv($('loadInfo'), {
      '백엔드': used.toUpperCase(),
      '다운로드': fromCacheAll ? `브라우저 캐시에서 ${dlSec.toFixed(1)}초` : `${dlSec.toFixed(1)}초`,
      '세션 준비': `${((performance.now() - ts) / 1000).toFixed(1)}초`,
    });
    log(`모델 준비 완료 (${used})`);
    $('modelCard').hidden = true;
    updateControls();
    if (autoplayWanted) setTimeout(startAutoplay, 0);
  } catch (e) {
    log('모델 로드 실패: ' + e.message);
    $('mcTitle').textContent = t('model_failed');
    $('mcSub').textContent = e.message;
    $('loadBtn').textContent = t('model_retry');
    $('loadBtn').hidden = false;
  } finally {
    S.loading = false;
    renderStatus();
    renderPlayBtn();
  }
}

async function ensureStyle() {
  const voice = settings.voice;
  if (S.styleVoice !== voice) {
    S.style = await loadVoiceStyle([modelUrl(`voice_styles/${voice}.json`)]);
    S.styleVoice = voice;
  }
  return S.style;
}

// ---- 생성 + 재생 ----
const player = $('player');

function releaseClip(i) {
  const clip = S.clips.get(i);
  if (clip) { URL.revokeObjectURL(clip.url); S.clips.delete(i); }
  planner.onPlayed(i);
}

function clearClips() {
  for (const i of [...S.clips.keys()]) releaseClip(i);
  planner.reset();
}

async function generatorLoop(token) {
  while (S.active && token === S.token) {
    if (S.genNext >= S.pieces.length) return;
    if (!planner.shouldGenerate()) { await new Promise((r) => { wake = r; }); continue; }
    const i = S.genNext;
    const style = await ensureStyle();
    const { steps, speed } = settings;
    const ts = performance.now();
    let result;
    try {
      const input = speakableText(S.pieces[i], hanjaReadings);
      result = await inferExclusive(() => S.tts._infer([input], ['ko'], style, steps, speed));
      // 엔진이 가끔 거의 무음을 낸다 — 초기 노이즈가 랜덤이라 다시 만들면 대부분 정상 (한 번만)
      if (token === S.token && isNearSilent(result.wav, S.tts.sampleRate, result.duration[0])) {
        log(`${i + 1}번째 조각이 거의 무음 — 다시 생성`);
        result = await inferExclusive(() => S.tts._infer([input], ['ko'], style, steps, speed));
      }
    } catch (e) {
      log(`${i + 1}번째 조각 생성 실패: ${e.message} — 건너뜀`);
      S.genNext = i + 1; continue;
    }
    if (token !== S.token) return; // 그 사이 위치가 바뀌었으면 버린다
    const genSec = (performance.now() - ts) / 1000;
    const pad = new Array(Math.floor(0.25 * S.tts.sampleRate)).fill(0);
    const wav = result.wav.concat(pad);
    const audioSec = wav.length / S.tts.sampleRate;
    S.clips.set(i, { url: URL.createObjectURL(new Blob([writeWavFile(wav, S.tts.sampleRate)], { type: 'audio/wav' })), audioSec });
    planner.onGenerated(i, audioSec);
    S.genSec += genSec; S.audioSec += audioSec;
    S.genNext = i + 1;
    renderStats();
    if (document.hidden || i < 3) log(`생성 #${i + 1} ${genSec.toFixed(1)}초${document.hidden ? ' (화면 꺼짐 중)' : ''}`);
    if (S.waiting && S.cur === i) playCurrent();
  }
}

function playCurrent() {
  const clip = S.clips.get(S.cur);
  renderNow();
  // 이어 듣기 위치를 아직 못 틀었으면 그 위치를 유지해 둔다 (대기 중 새로고침 대비)
  savePosition(storage, positionKey(dbType, bookId, book.chapter), S.cur,
    S.pendingOffset ? { total: S.pieces.length, offset: S.pendingOffset + 2.5 } : { total: S.pieces.length });
  if (!clip) {
    S.waiting = true;
    if (S.stallStart === null) S.stallStart = performance.now();
    renderStatus(); renderPlayBtn();
    return;
  }
  // 재생 시작/위치 이동 직후의 첫 대기는 끊김이 아니라 준비 시간이므로 세지 않는다
  if (S.waiting && S.stallStart !== null && S.playedInRun) {
    S.stalls++;
    log(`끊김 ${((performance.now() - S.stallStart) / 1000).toFixed(1)}초 후 재개`);
  }
  S.waiting = false; S.stallStart = null; S.playedInRun = true; S.resumeTries = 0;
  S.listened = true;
  reportListen();
  player.dataset.prime = '0';
  player.src = clip.url;
  const offset = S.pendingOffset;
  S.pendingOffset = 0;
  if (offset > 0 && offset < clip.audioSec - 0.5) {
    player.addEventListener('loadedmetadata', () => { player.currentTime = offset; }, { once: true });
    log(`${S.cur + 1}번째 조각 ${offset.toFixed(1)}초부터 재생`);
  }
  player.play().catch((e) => log(`재생 실패 #${S.cur + 1}: ${e.name} ${e.message}`));
  renderStatus(); renderPlayBtn();
}

// 위치 이동/설정 변경: 만들어 둔 오디오를 버리고 i번째부터 다시 생성한다
function restartAt(i, keepOffset = false) {
  if (!keepOffset) S.pendingOffset = 0; // 사용자가 위치/설정을 바꾸면 조각 처음부터
  S.token++;
  wakeGenerator();
  if (S.active && player.dataset.prime !== '1') player.pause();
  clearClips();
  S.cur = Math.max(0, Math.min(i, S.pieces.length - 1));
  S.genNext = S.cur;
  S.waiting = false; S.stallStart = null; S.playedInRun = false;
  if (!S.active) { renderNow(); return; }
  if (!S.pieces.length) { onFinished(); return; } // 표지뿐인 EPUB 항목 등
  generatorLoop(S.token);
  playCurrent();
}

function primeAudio() {
  // 첫 재생은 버튼 클릭(사용자 제스처) 안에서 열어 두어야 이후 자동 재생이 허용된다
  player.dataset.prime = '1';
  player.src = URL.createObjectURL(new Blob([writeWavFile(new Array(2400).fill(0), 24000)], { type: 'audio/wav' }));
  const p = player.play();
  p.catch(() => {});
  return p;
}

// 자동 시작: 브라우저 자동재생 정책상 이 페이지에서 사용자가 누른 적이 없으면 소리 재생이 막힌다
// (누른 곳은 원래 화면이라 새 페이지로 넘어오지 않는다). 막히면 되돌리고 화면 전체 "탭해서 듣기"를 띄운다.
// 홈 화면에 추가(PWA)했거나 미디어 재생 이력이 많으면 브라우저가 허용하기도 한다.
async function startAutoplay() {
  autoplayWanted = false;
  if (!S.tts || S.active || !S.pieces.length) return;
  togglePlay();
  try {
    await S.primePromise;
  } catch (e) {
    log(`자동 재생이 막힘 (${e.name}) — 탭해서 듣기 표시`);
    S.active = false; S.token++; wakeGenerator(); clearClips(); S.waiting = false;
    player.pause();
    renderPlayBtn(); renderStatus();
    $('tapStart').hidden = false;
  }
}
$('tapStart').onclick = () => {
  $('tapStart').hidden = true;
  if (!S.active) togglePlay();
};

function togglePlay() {
  if (!S.tts) return;
  if (!S.active) {
    S.active = true;
    S.userPaused = false;
    S.primePromise = primeAudio();
    setMediaSession();
    follow(true, false);
    restartAt(S.cur, true);
  } else if (isPausedByUser() && !S.waiting) {
    S.userPaused = false;
    S.resumeTries = 0;
    player.play().catch((e) => log('재생 실패: ' + e.message));
  } else {
    // 생성 대기 중에 누르면 멈춘다 (다시 누르면 그 자리에서 이어서)
    S.userPaused = true;
    if (S.waiting) { S.active = false; S.token++; wakeGenerator(); clearClips(); S.waiting = false; }
    player.pause();
  }
  renderPlayBtn(); renderStatus();
}

player.addEventListener('ended', () => {
  if (player.dataset.prime === '1') { player.dataset.prime = '0'; if (!S.waiting) playCurrent(); return; }
  releaseClip(S.cur);
  wakeGenerator();
  if (S.cur + 1 < S.pieces.length) { S.cur++; playCurrent(); return; }
  onFinished();
});

function onFinished() {
  reportListen(true, false, true); // 끝까지 들은 위치를 바로 저장 → 진행도 100%, 완독
  savePosition(storage, positionKey(dbType, bookId, book.chapter), 0, { total: S.pieces.length, finished: true });
  if (book.format === 'epub' && $('autoNext').checked && book.chapter + 1 < book.chapters.length) {
    log('챕터 끝 — 다음 챕터로');
    changeChapter(book.chapter + 1, true);
  } else {
    // 책 끝: 뒤에 읽을 글자 없는 항목(판권·뒤표지)만 남아 마지막 챕터까지 못 가도 완독으로 기록한다
    if (S.listened && (book.format !== 'epub' || book.chapter + 1 >= book.chapters.length)) reportBookEnd();
    S.active = false; log('끝까지 읽었습니다'); toast(t('finished'));
    renderPlayBtn(); renderStatus();
  }
}

function reportBookEnd() {
  const progress = book.format === 'epub'
    ? listenProgress('epub', { chapter: book.chapters.length - 1, chapterCount: book.chapters.length })
    : listenProgress('txt', { offset: S.text.length, txtChunkStarts: txtChunkStarts() });
  if (!progress) return;
  fetch('/api/media/progress', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
    body: JSON.stringify({ db_type: dbType, book_id: Number(bookId), ...progress, flush_immediately: true }),
  }).then(notifyProgress, () => {});
}
for (const ev of ['play', 'pause', 'playing']) player.addEventListener(ev, () => { renderPlayBtn(); renderStatus(); });

// 화면이 꺼진 동안 조각을 갈아 끼운 직후 OS/브라우저가 재생을 멈추는 경우가 있다
// (삼성 인터넷, #17 재생 0.1초 뒤 pause — 2026-09-24 실측). 사용자가 멈춘 게 아니면 다시 튼다.
player.addEventListener('pause', () => {
  if (player.dataset.prime === '1' || player.ended || !S.active || S.userPaused || S.waiting) return;
  const clip = S.clips.get(S.cur);
  if (!clip || player.src !== clip.url) return; // 위치 이동 중
  if (S.resumeTries >= 3) { log(`자동 재개 포기 #${S.cur + 1}`); return; }
  S.resumeTries++;
  setTimeout(() => {
    if (!player.paused || S.userPaused || !S.active) return;
    log(`예상 밖 일시정지 → 자동 재개 시도 ${S.resumeTries} #${S.cur + 1}${document.hidden ? ' (화면 꺼짐)' : ''}`);
    player.play().catch((e) => log(`자동 재개 실패: ${e.name} ${e.message}`));
  }, 300);
});
player.addEventListener('playing', () => { S.userPaused = false; });

// 조각 안 재생 위치까지 저장한다 — 일시정지 순간, 화면을 떠날 때, 재생 중 3초마다.
function saveOffset() {
  if (player.dataset.prime === '1' || player.ended || !S.pieces.length) return;
  const clip = S.clips.get(S.cur);
  if (!clip || player.src !== clip.url) return;
  savePosition(storage, positionKey(dbType, bookId, book.chapter), S.cur, { total: S.pieces.length, offset: player.currentTime });
}
let lastOffsetSave = 0;
player.addEventListener('pause', saveOffset);
player.addEventListener('timeupdate', () => {
  const now = performance.now();
  if (now - lastOffsetSave > 3000) { lastOffsetSave = now; saveOffset(); }
});
window.addEventListener('pagehide', () => { saveOffset(); reportListen(true, true); });
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { saveOffset(); reportListen(true, true); log('화면 꺼짐/백그라운드'); return; }
  log('화면 다시 보임');
  renderNow({ instant: true }); // 꺼져 있는 동안은 강조/스크롤을 건너뛰었다
});
player.addEventListener('pause', () => { if (S.userPaused) reportListen(true); });

// ---- 진단 ----
for (const ev of ['ended', 'playing', 'pause', 'waiting', 'stalled', 'error']) {
  player.addEventListener(ev, () => {
    if (player.dataset.prime === '1') return;
    if (ev === 'playing' && !document.hidden) return;
    const err = ev === 'error' && player.error ? ` code=${player.error.code}` : '';
    log(`[audio] ${ev} #${S.cur + 1} @${player.currentTime.toFixed(1)}s${document.hidden ? ' (화면 꺼짐)' : ''}${err}`);
  });
}
let beat = performance.now();
setInterval(() => {
  const now = performance.now();
  const lag = now - beat - 1000;
  if (lag > 1500) log(`메인 스레드 ${(lag / 1000).toFixed(1)}초 지연${document.hidden ? ' (화면 꺼짐)' : ''}`);
  beat = now;
}, 1000);

async function changeChapter(idx, keepPlaying) {
  book.chapter = idx;
  try { storage?.setItem(lastChapterKey(dbType, bookId), String(idx)); } catch (e) { /* 무시 */ }
  const wasActive = keepPlaying && S.active;
  S.token++; wakeGenerator(); clearClips(); S.active = false;
  follow(true, false);
  await loadText();
  if (wasActive) { S.active = true; setMediaSession(); restartAt(S.cur, true); }
  renderPlayBtn(); renderStatus();
}

function setMediaSession() {
  if (!('mediaSession' in navigator)) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: book.title || 'BookOasis',
    artist: book.format === 'epub' ? book.chapters[book.chapter] || '' : '',
    album: t('media_album'),
  });
  const h = navigator.mediaSession.setActionHandler.bind(navigator.mediaSession);
  try {
    h('play', () => { log('[세션] 재생 요청'); S.userPaused = false; player.play(); });
    h('pause', () => { log('[세션] 일시정지 요청'); S.userPaused = true; player.pause(); });
    h('previoustrack', () => { log('[세션] 이전 요청'); restartAt(S.cur - 1); });
    h('nexttrack', () => { log('[세션] 다음 요청'); restartAt(S.cur + 1); });
  } catch (e) { /* 일부 브라우저는 핸들러 일부만 지원 */ }
}

// ---- 본문 렌더링 ----
// 조각마다 <span class="s" data-s=번호>. 문단은 PARAS_PER_BLOCK개씩 블록으로 묶어 둔다(나중에 창 방식 렌더링용).
// content-visibility:auto는 쓰지 않는다 — 건너뛴 블록의 높이가 추정치라 먼 위치로 점프하면 목표가
// 화면 밖으로 밀려났다(2026-09-26 실측). 대신 전체를 한 번 레이아웃한다: 1.3MB TXT 기준 데스크톱 약 0.5초.
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const esc = (s) => s.replace(/[&<>"]/g, (c) => ESC[c]);
let hlEls = [];

function renderText() {
  const tr = performance.now();
  const paras = paragraphRuns(S.text, S.segments);
  if (!paras.length) {
    placeholder(t('no_text'));
    hlEls = [];
    return;
  }
  const html = [];
  for (let b = 0; b < paras.length; b += PARAS_PER_BLOCK) {
    html.push('<div class="blk">');
    for (const runs of paras.slice(b, b + PARAS_PER_BLOCK)) {
      if (runs.length === 1 && runs[0].seg < 0) { html.push(`<p class="scene">${esc(S.text.slice(runs[0].from, runs[0].to))}</p>`); continue; }
      html.push('<p>');
      for (const r of runs) html.push(`<span class="s" data-s="${r.seg}">${esc(S.text.slice(r.from, r.to))}</span>`);
      html.push('</p>');
    }
    html.push('</div>');
  }
  $('text').innerHTML = html.join('');
  hlEls = [];
  void $('text').offsetHeight; // 레이아웃까지 포함해 잰다
  log(`본문 표시 ${paras.length.toLocaleString()}문단, ${(performance.now() - tr).toFixed(0)}ms`);
}

// ---- 자동 스크롤 ----
// 사용자가 직접 스크롤(터치/휠/키)하면 따라가기를 멈추고 "읽는 곳으로" 버튼을 띄운다.
// 스크롤 이벤트 자체는 보지 않는다 — 우리가 부른 smooth 스크롤도 scroll 이벤트를 내기 때문.
let following = true;
// render=false: 곧이어 restartAt/loadText가 새 위치로 다시 그리므로 옛 위치로 한 번 더 스크롤하지 않는다
function follow(on, render = true) {
  following = on;
  $('toCurrent').hidden = on || !S.pieces.length || !ui.follow;
  if (on && render) renderNow({ instant: false });
}
function onUserScroll() {
  if (!following || !ui.follow) return;
  following = false;
  $('toCurrent').hidden = false;
}
window.addEventListener('wheel', onUserScroll, { passive: true });
window.addEventListener('touchmove', onUserScroll, { passive: true });
window.addEventListener('keydown', (e) => { if (['PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'Home', 'End', ' '].includes(e.key) && e.target === document.body) onUserScroll(); });

function scrollToCurrent(instant) {
  const el = hlEls[0];
  if (!el) return;
  const topBar = document.querySelector('.top').getBoundingClientRect().bottom;
  const dockTop = $('dock').getBoundingClientRect().top;
  const rect = el.getBoundingClientRect();
  const band = dockTop - topBar;
  // 보이는 영역의 위쪽 15%~60% 안에 있으면 그대로 둔다 (문장마다 화면이 흔들리지 않게)
  if (!instant && rect.top >= topBar + band * 0.15 && rect.bottom <= topBar + band * 0.6) return;
  const target = window.scrollY + rect.top - topBar - band * 0.3;
  window.scrollTo({ top: Math.max(0, target), behavior: instant ? 'auto' : 'smooth' });
}

// ---- 화면 갱신 ----
function renderNow({ instant = false } = {}) {
  const n = S.pieces.length;
  $('seek').value = String(S.cur);
  $('seek').style.setProperty('--p', `${n > 1 ? (S.cur / (n - 1)) * 100 : 0}%`);
  $('pos').textContent = `${n ? (S.cur + 1).toLocaleString() : 0} / ${n.toLocaleString()}`;
  $('pct').textContent = `${n ? Math.floor((S.cur / n) * 100) : 0}%`;
  renderStats();
  if (document.hidden) return;
  for (const el of hlEls) el.classList.remove('cur');
  hlEls = [...$('text').querySelectorAll(`.s[data-s="${S.cur}"]`)];
  for (const el of hlEls) el.classList.add('cur');
  if (following && ui.follow) scrollToCurrent(instant);
}

function renderStats() {
  kv($('stats'), {
    '위치': `${S.pieces.length ? S.cur + 1 : 0} / ${S.pieces.length}`,
    '버퍼': `${Math.round(planner.bufferedSec)}초`,
    '생성 속도': S.genSec > 0 ? `${(S.audioSec / S.genSec).toFixed(1)}배` : '-',
    '끊김': `${S.stalls}회`,
    '설정': `${settings.voice} · 음질 ${settings.steps} · ${settings.speed}×`,
  });
}

// <audio>의 순간 상태가 아니라 의도로 그린다 — 조각을 갈아 끼울 때마다 pause 이벤트가 나서
// player.paused만 보면 문장 경계마다 ▶가 깜박인다. 자동 재개를 포기한 경우만 멈춘 것으로 본다.
function isPausedByUser() {
  return S.userPaused || (player.paused && S.resumeTries >= 3);
}

function renderPlayBtn() {
  const playing = S.active && !S.waiting && !isPausedByUser();
  const waiting = S.active && S.waiting;
  // 아이콘이 SVG라 .hidden 속성이 없다(HTMLElement 전용) — 속성을 직접 켜고 끈다
  $('icPlay').toggleAttribute('hidden', playing || waiting);
  $('icPause').toggleAttribute('hidden', !playing);
  $('icWait').toggleAttribute('hidden', !waiting);
  $('playBtn').setAttribute('aria-label', t(playing ? 'pause' : waiting ? 'waiting_stop' : 'play'));
}

function renderStatus() {
  let msg = '';
  if (S.loading) msg = t('status_model');
  else if (S.active && S.waiting) msg = t('status_generating');
  else if (S.active && isPausedByUser()) msg = t('status_paused');
  $('status').textContent = msg;
}

// ---- 문장 눌러서 이동 ----
let pickTimer = null;
let picked = null;
function clearPick() {
  for (const el of $('text').querySelectorAll('.s.pick')) el.classList.remove('pick');
  $('jumpChip').hidden = true;
  picked = null;
  clearTimeout(pickTimer);
}
$('text').addEventListener('click', (e) => {
  const span = e.target.closest('.s');
  if (!span) return;
  const i = Number(span.dataset.s);
  if (!(i >= 0) || getSelection().toString()) return;
  clearPick();
  if (i === S.cur) return;
  picked = i;
  for (const el of $('text').querySelectorAll(`.s[data-s="${i}"]`)) el.classList.add('pick');
  $('jumpText').textContent = S.pieces[i];
  $('jumpChip').hidden = false;
  $('toCurrent').hidden = true;
  pickTimer = setTimeout(() => { clearPick(); if (!following) $('toCurrent').hidden = false; }, 8000);
});
$('jumpGo').onclick = () => {
  const i = picked;
  clearPick();
  if (i === null) return;
  following = true;
  $('toCurrent').hidden = true;
  restartAt(i);
  if (!S.active) renderNow();
};
$('toCurrent').onclick = () => follow(true);

// ---- 시트 ----
function openSheet(id) {
  $('backdrop').hidden = false;
  $(id).hidden = false;
}
function closeSheets() {
  $('backdrop').hidden = true;
  $('settingsSheet').hidden = true;
  $('chapterSheet').hidden = true;
}
$('backdrop').onclick = closeSheets;
window.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeSheets(); $('devOverlay').hidden = true; } });

function segGroup(el, options, current, onPick) {
  el.replaceChildren(...options.map(([value, label]) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.setAttribute('aria-pressed', String(value === current));
    b.onclick = () => {
      for (const x of el.children) x.setAttribute('aria-pressed', 'false');
      b.setAttribute('aria-pressed', 'true');
      onPick(value);
    };
    return b;
  }));
}

// 음성/속도/음질이 바뀌면 만들어 둔 오디오를 버리고 지금 문장부터 다시 만든다
function changeVoice(patch) {
  Object.assign(settings, patch);
  $('speedBtn').textContent = `${settings.speed}×`;
  S.genSec = 0; S.audioSec = 0;
  renderStats();
  if (S.active) restartAt(S.cur);
}

function renderSettings() {
  segGroup($('voiceGroup'), VOICES.map((v) => [v, t(v.startsWith('F') ? 'voice_female' : 'voice_male', { n: v.slice(1) })]), settings.voice, (v) => changeVoice({ voice: v }));
  segGroup($('speedGroup'), SPEEDS.map((v) => [v, `${v}×`]), settings.speed, (v) => changeVoice({ speed: v }));
  segGroup($('stepsGroup'), STEPS.map(([v, k]) => [v, t(k)]), settings.steps, (v) => changeVoice({ steps: v }));
  segGroup($('fontGroup'), FONT_SIZES.map((v) => [v, String(v)]), ui.fontSize, (v) => { ui.fontSize = v; saveUi(); applyUi(); renderNow({ instant: true }); });
  segGroup($('themeGroup'), THEMES.map(([v, k]) => [v, t(k)]), ui.theme, (v) => { ui.theme = v; saveUi(); applyUi(); });
  $('speedBtn').textContent = `${settings.speed}×`;
}
$('followToggle').onchange = () => { ui.follow = $('followToggle').checked; saveUi(); follow(ui.follow); };
$('settingsBtn').onclick = () => { renderSettings(); openSheet('settingsSheet'); };
$('speedBtn').onclick = () => {
  const next = SPEEDS[(SPEEDS.indexOf(settings.speed) + 1) % SPEEDS.length] ?? SPEEDS[1];
  changeVoice({ speed: next });
  toast(t('speed_toast', { speed: next }));
};

$('chapterBtn').onclick = () => {
  $('chapterList').replaceChildren(...book.chapters.map((t, i) => {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    if (i === book.chapter) b.setAttribute('aria-current', 'true');
    const n = document.createElement('span'); n.className = 'n'; n.textContent = String(i + 1);
    const name = document.createElement('span'); name.textContent = t;
    b.append(n, name);
    b.onclick = () => { closeSheets(); if (i !== book.chapter) changeChapter(i, true); };
    li.append(b);
    return li;
  }));
  openSheet('chapterSheet');
  $('chapterList').querySelector('[aria-current]')?.scrollIntoView({ block: 'center' });
};

// ---- 개발 로그 오버레이 ----
$('devBtn').onclick = () => { closeSheets(); renderStats(); $('devOverlay').hidden = false; $('log').scrollTop = 1e9; };
$('closeDev').onclick = () => { $('devOverlay').hidden = true; };
$('testLink').href = `/experimental/tts${location.search}`;
$('copyLog').onclick = async () => {
  const text = `${navigator.userAgent}\n${$('env').innerText}\n${$('loadInfo').innerText}\n${$('stats').innerText}\n---\n${$('log').textContent}`;
  try { await navigator.clipboard.writeText(text); $('copyLog').textContent = t('dev_copied'); setTimeout(() => { $('copyLog').textContent = t('dev_copy'); }, 1500); }
  catch (e) { const r = document.createRange(); r.selectNodeContents($('log')); getSelection().removeAllRanges(); getSelection().addRange(r); }
};

// ---- 조작 ----
// 닫기: 도서 메뉴/상세/뷰어는 새 탭으로 여니 그 탭을 닫아 원래 BookOasis 창으로 돌아간다.
// 스크립트가 연 탭이 아니면(주소를 직접 연 경우 등) 브라우저가 닫기를 막으므로, 같은 탭에서 첫 화면으로 간다
// (새 창을 띄우지 않는다 — 예전 ← 버튼은 BookOasis 창이 두 개가 되곤 했다).
$('closeBtn').onclick = () => {
  saveOffset();
  reportListen(true, true);
  window.close();
  setTimeout(() => { if (!window.closed) location.href = '/'; }, 150);
};
$('playBtn').onclick = togglePlay;
$('prevBtn').onclick = () => { follow(true, false); restartAt(S.cur - 1); };
$('nextBtn').onclick = () => { follow(true, false); restartAt(S.cur + 1); };
$('seek').oninput = () => {
  // 끄는 동안은 위치 표시만 바꾸고, 놓았을 때 이동한다
  const i = Number($('seek').value), n = S.pieces.length;
  $('seek').style.setProperty('--p', `${n > 1 ? (i / (n - 1)) * 100 : 0}%`);
  $('pos').textContent = `${(i + 1).toLocaleString()} / ${n.toLocaleString()}`;
  $('pct').textContent = `${n ? Math.floor((i / n) * 100) : 0}%`;
};
$('seek').onchange = () => {
  const i = Number($('seek').value);
  follow(true, false);
  restartAt(i);
  if (!S.active) renderNow({ instant: true }); // 먼 위치는 smooth 스크롤이 오래 걸린다
};
$('loadBtn').onclick = () => loadModel(env.hasWebGpu, false);

// 개발 편의: 스페이스 재생/정지, ←/→ 문장 이동 (입력창 밖에서만)
window.addEventListener('keydown', (e) => {
  if (e.target !== document.body || !S.tts) return;
  if (e.key === ' ') { e.preventDefault(); togglePlay(); }
  else if (e.key === 'ArrowLeft') restartAt(S.cur - 1);
  else if (e.key === 'ArrowRight') restartAt(S.cur + 1);
});

// ---- 시작 ----
const env = { hasWebGpu: false };
applyUi();
// 모델 카드가 뜨고 사라지며 하단 바 높이가 바뀐다 — 떠 있는 버튼 위치와 본문 아래 여백을 맞춘다
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--dock-h', `${Math.ceil($('dock').getBoundingClientRect().height)}px`);
}).observe($('dock'));
function placeholder(msg) {
  const p = document.createElement('p'); p.className = 'placeholder'; p.textContent = msg;
  $('text').replaceChildren(p);
  hlEls = [];
}

// i18n.translateDOM은 aria-label을 다루지 않아 여기서 채운다
function translatePage() {
  window.i18n?.translateDOM();
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria.replace(/^tts\./, '')));
  document.documentElement.lang = window.i18n?.currentLang || 'ko';
  document.title = book.title ? `${t('page_title')} · ${book.title}` : t('page_title');
}

(async () => {
  try { await window.i18n?.init(); } catch (e) { /* 번역을 못 불러오면 템플릿의 한국어 그대로 */ }
  translatePage();
  env.hasWebGpu = await detectEnv();
  if (!bookId) {
    placeholder(t('no_book_id'));
    return;
  }
  try {
    await fetchSync();
    renderSettings();
    await loadBookInfo();
    await loadText();
  } catch (e) {
    log('도서 불러오기 실패: ' + e.message);
    placeholder(e.message);
    return;
  }
  const cached = await modelCached();
  if (cached) {
    log('브라우저에 저장된 모델이 있어 바로 불러옵니다');
    await loadModel(env.hasWebGpu, true);
  } else {
    $('modelCard').hidden = false;
  }
})();
