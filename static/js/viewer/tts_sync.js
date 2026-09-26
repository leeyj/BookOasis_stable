// tts_sync.js - 뷰어(읽기)와 브라우저 TTS(듣기) 위치 동기화.
// 읽기 위치는 기존 진도(user_progress) 파이프라인과 별개로 /api/media/tts/position에 kind=read로
// 보고하고, 뷰어를 열 때 듣기 위치가 더 최근이면 그 문장으로 이동한다 (더 최근 쪽을 따르고 알림 — 2026-09-24 결정).
// viewer_txt.js ↔ viewer_progress.js 순환 import를 피하려고, 현재 읽기 위치는 뷰어가 등록한 provider로 받는다.
import { state } from '../state.js';
import { makeAnchor, resolveOffset, offsetToChunk } from './text_position_utils.js';

const REPORT_MIN_GAP_MS = 30_000;
const REPORT_DEBOUNCE_MS = 3_000;
const OPEN_QUIET_MS = 4_000; // 연 직후(시작 위치 복원 중)의 위치는 아직 사용자가 읽은 곳이 아니다
const FETCH_TIMEOUT_MS = 1_500;

let positionProvider = null;
let openedAt = 0;
let lastReportAt = 0;
let dirty = false;
let debounceTimer = null;

function isTextViewer() {
  return state.currentViewerFormat === 'txt' || state.currentViewerFormat === 'epub';
}

// provider(): {chapter_idx, char_offset, text_len, anchor} | null
export function setReadPositionProvider(provider) {
  positionProvider = provider;
  openedAt = Date.now();
  dirty = false;
  lastReportAt = 0;
}

function readBody() {
  if (!positionProvider || !state.activeBookId || !isTextViewer()) return null;
  let position = null;
  try { position = positionProvider(); } catch (e) { position = null; }
  if (!position || !position.anchor) return null;
  return JSON.stringify({
    db_type: state.currentLibraryType || 'general',
    book_id: state.activeBookId,
    kind: 'read',
    ...position,
  });
}

// 뷰어의 "듣기" 버튼: 바뀐 게 없어도 지금 읽는 위치를 바로 보내고 저장될 때까지 기다린다.
// 듣기 화면은 더 최근 쪽(읽기/듣기)을 따르므로, 이게 먼저 저장돼야 읽던 문장에서 시작한다.
export async function reportReadNow() {
  const body = readBody();
  if (!body) return;
  clearTimeout(debounceTimer);
  dirty = false;
  lastReportAt = Date.now();
  try {
    await fetch('/api/media/tts/position', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  } catch (e) { /* 실패하면 듣기 화면이 예전 위치에서 시작할 뿐 */ }
}

function send(useBeacon) {
  const body = readBody();
  if (!body) return;
  dirty = false;
  lastReportAt = Date.now();
  try {
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon('/api/media/tts/position', new Blob([body], { type: 'application/json' }));
      return;
    }
    fetch('/api/media/tts/position', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true,
    }).catch(() => {});
  } catch (e) { /* 동기화 보고 실패는 읽기에 영향을 주지 않는다 */ }
}

// 페이지 이동 등 읽기 진도가 바뀔 때마다 호출된다 (viewer_progress.saveProgress). 서버 쓰기를 줄이려고 30초에 한 번만.
export function noteReadActivity() {
  if (!isTextViewer() || !positionProvider) return;
  if (Date.now() - openedAt < OPEN_QUIET_MS) return;
  dirty = true;
  if (Date.now() - lastReportAt < REPORT_MIN_GAP_MS) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => send(false), REPORT_DEBOUNCE_MS);
}

// 뷰어를 닫거나 화면을 떠날 때 — 마지막 위치를 바로 보낸다
export function flushReadReport(useBeacon = true) {
  if (!dirty) return;
  clearTimeout(debounceTimer);
  send(useBeacon);
}

export async function fetchSyncState(dbType, bookId) {
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = setTimeout(() => controller?.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`/api/media/tts/position?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}&_ts=${Date.now()}`, {
      cache: 'no-store', signal: controller?.signal,
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data && data.success ? data.state : null;
  } catch (e) {
    return null; // 느리거나 실패하면 동기화 없이 기존대로 연다
  } finally {
    clearTimeout(timer);
  }
}

// 듣기 위치가 더 최근이면 뷰어가 열어야 할 {chunkIdx, anchorText}를 돌려준다.
// TXT: 전체 텍스트 기준 오프셋 → 뷰어 4000자 청크. EPUB: 챕터 번호 그대로, 문장은 앵커로 찾는다.
export function listenTargetForTxt(syncState, fullText, chunks) {
  const listen = syncState && syncState.latest === 'listen' ? syncState.listen : null;
  if (!listen || !fullText || !chunks || !chunks.length) return null;
  const offset = resolveOffset(fullText, listen);
  return { chunkIdx: offsetToChunk(chunks, offset).chunkIdx, anchorText: makeAnchor(fullText, offset) };
}

export function listenTargetForEpub(syncState, totalChapters) {
  const listen = syncState && syncState.latest === 'listen' ? syncState.listen : null;
  if (!listen || !totalChapters) return null;
  const chunkIdx = Math.max(0, Math.min(totalChapters - 1, Number(listen.chapter_idx) || 0));
  return { chunkIdx, anchorText: listen.anchor || '' };
}
