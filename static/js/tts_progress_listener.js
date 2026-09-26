// tts_progress_listener.js - 듣기 창(/listen, 새 탭)이 읽기 진행도를 저장하면 BroadcastChannel로 알려 준다.
// 여기서 받아 열려 있는 목록·상세·홈을 다시 불러와 진행 막대/이어보기/최근 읽은 도서를 맞춘다 (새로고침 없이).
// 듣는 동안 10초마다 알림이 오므로, 이 탭이 가려져 있으면 모아 두었다가 돌아왔을 때 한 번만 갱신한다.
import { state } from './state.js';

const CHANNEL = 'bookoasis-tts-progress'; // static/js/tts/tts_player.js와 같아야 한다
const SETTLE_MS = 2500; // 서버가 진행도를 메모리 버퍼에서 DB로 옮기는 간격(기본 2초)을 기다린다

let pending = null; // { db_type, book_ids:Set }
let timer = null;

function detailVisible() {
  const view = document.getElementById('book-detail-view');
  return !!view && view.style.display !== 'none';
}

function refresh() {
  timer = null;
  const msg = pending;
  pending = null;
  if (!msg || String(msg.db_type) !== String(state.currentLibraryType || 'general')) return;

  // 목록: 스크롤 유지 새로고침. 상세가 열려 있으면 목록으로 돌아올 때 갱신되도록 예약만 된다.
  window.invalidateBookListAfterScan?.();

  if (detailVisible()) {
    const ids = new Set((state.detailBookIds || []).map(Number));
    if ([...msg.book_ids].some((id) => ids.has(id)) && typeof window.openBookDetail === 'function') {
      window.openBookDetail(null, state.detailSeriesName, state.detailLibraryId,
        state.detailRepresentativeBookId, state.detailDisplayTitle);
    }
  } else if (state.currentLibraryId === 'home') {
    window.loadDashboardData?.(); // 홈 대시보드의 이어 읽기/최근 읽은 도서 (스캔 완료 때와 같은 경로)
  }
}

function schedule(delay) {
  clearTimeout(timer);
  timer = setTimeout(refresh, delay);
}

if (typeof BroadcastChannel === 'function') {
  const channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = (event) => {
    const { db_type: dbType, book_id: bookId } = event.data || {};
    if (!bookId) return;
    if (!pending || pending.db_type !== dbType) pending = { db_type: dbType, book_ids: new Set() };
    pending.book_ids.add(Number(bookId));
    if (!document.hidden) schedule(SETTLE_MS);
  };
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && pending) schedule(500);
  });
}
