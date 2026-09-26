// tts_launcher.js - "음성으로 듣기" 화면(/listen)을 여는 단일 진입점.
// 코어(도서 메뉴·상세 권 목록·뷰어)와 플러그인(detail_view 등)이 같은 경로로 연다 — window.openReader와 같은 방식.
//
// 플러그인 계약 (docs/guide_plugins.md "음성으로 듣기 열기"):
//   window.canListen(fileFormat) → boolean   TXT/EPUB만 true (합성은 브라우저에서 텍스트로 한다)
//   window.openListen(bookId, dbType?)        새 탭으로 열고 준비되면 바로 재생을 시도한다. dbType 생략 시 현재 세션
import { state } from './state.js';

const LISTENABLE_FORMATS = new Set(['txt', 'text', 'epub']);

export function canListen(fileFormat) {
  return LISTENABLE_FORMATS.has(String(fileFormat || '').toLowerCase());
}

export function listenUrl(bookId, dbType = 'general') {
  return `/listen?book_id=${encodeURIComponent(bookId)}&db_type=${encodeURIComponent(dbType || 'general')}&autoplay=1`;
}

// beforeOpen: 열기 전에 기다릴 일 (뷰어는 읽던 위치를 먼저 저장해야 듣기 화면이 그 문장부터 시작한다).
// 팝업 차단을 피하려고 클릭 순간 빈 탭부터 열고, 끝나면 그 탭을 듣기 화면으로 바꾼다.
// about:blank를 기록에 남기지 않아야 듣기 화면의 닫기 버튼이 탭을 닫는다 (location.replace).
export async function openListen(bookId, dbType, { beforeOpen = null } = {}) {
  if (!bookId) return;
  const url = listenUrl(bookId, dbType || state.currentLibraryType || 'general');
  if (!beforeOpen) {
    window.open(url, '_blank');
    return;
  }
  const win = window.open('about:blank', '_blank');
  try { await beforeOpen(); } catch (e) { /* 위치 저장 실패는 듣기를 막지 않는다 */ }
  if (win) win.location.replace(url);
  else window.location.href = url;
}

window.canListen = canListen;
window.openListen = (bookId, dbType) => openListen(bookId, dbType);
