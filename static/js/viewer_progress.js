// viewer_progress.js – 독서 진행률 API 전송 디바운싱 및 동기화 모듈
import { state } from './state.js';

let progressTimeout = null;
let pendingProgress = null;

// 도서별 사전 로딩 중복 호출 방지 플래그 저장소
const preloadedBooksSet = new Set();

export function resetPreloadState() {
  preloadedBooksSet.clear();
}

/**
 * 뷰어 내에서 진행률 저장을 예약(디바운스 적용)
 * @param {string|number} bookId - 도서 고유 ID
 * @param {number} pageIdx - 현재 보고 있는 페이지 인덱스 (0-indexed)
 * @param {number} totalPages - 전체 페이지 수
 */
export function saveProgress(bookId, pageIdx, totalPages, extraData = null) {
  pendingProgress = {
    db_type: state.currentLibraryType,
    book_id: bookId,
    page_idx: pageIdx,
    total_pages: totalPages
  };

  if (extraData && typeof extraData === 'object') {
    pendingProgress = {
      ...pendingProgress,
      ...extraData
    };
  }

  // 90% 이상 도달 시 다음 편 백그라운드 사전 캐싱 트리거 (1페이지짜리 단독 도서 예외 방지: totalPages > 1)
  if (totalPages > 1) {
    const progressRatio = (pageIdx + 1) / totalPages;
    if (progressRatio >= 0.9) {
      triggerPreloadNextBook(bookId);
    }
  }

  // 기존 예약 제거 후 3초 뒤 전송
  if (progressTimeout) {
    clearTimeout(progressTimeout);
  }

  progressTimeout = setTimeout(() => {
    flushProgress();
  }, 3000);
}

/**
 * 다음 편 백그라운드 사전 로드 API 호출
 * @param {string|number} bookId 
 */
function triggerPreloadNextBook(bookId) {
  const cacheKey = `${state.currentLibraryType}_${bookId}`;
  if (preloadedBooksSet.has(cacheKey)) {
    return; // 이미 사전 로딩을 요청함
  }

  preloadedBooksSet.add(cacheKey);
  console.log(`[Viewer-Progress] 90% progress reached. Preloading next book for current book_id=${bookId}`);

  fetch('/api/media/preload-next-book', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      db_type: state.currentLibraryType,
      book_id: bookId
    })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      console.log(`[Viewer-Progress] Preload request successfully queued.`, data);
    } else {
      console.warn(`[Viewer-Progress] Preload response message: ${data.error || 'unknown'}`);
    }
  })
  .catch(err => {
    console.error(`[Viewer-Progress] Failed to request preload API:`, err);
  });
}

/**
 * 대기 중인 진척도 저장 예약 건이 있다면 즉시 동기 전송(Flush)하고 청소
 * @param {boolean} useBeacon - 모바일 탭 닫기/이탈 시 sendBeacon 사용 여부
 */
export function flushProgress(useBeacon = false) {
  if (!pendingProgress) return Promise.resolve(null);

  const data = { ...pendingProgress };
  pendingProgress = null;

  if (progressTimeout) {
    clearTimeout(progressTimeout);
    progressTimeout = null;
  }

  console.log(`[Viewer-Progress] Flushing progress: book_id=${data.book_id}, page_idx=${data.page_idx}/${data.total_pages}`);

  // 모바일 탭 닫기/이탈 시 sendBeacon을 사용하여 100% 안전 전송 보장
  if (useBeacon && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
      const sent = navigator.sendBeacon('/api/media/progress', blob);
      if (sent) {
        console.log('[Viewer-Progress] sendBeacon successfully sent progress payload');
        return Promise.resolve(true);
      }
    } catch (e) {
      console.warn('[Viewer-Progress] sendBeacon failed, falling back to fetch:', e);
    }
  }

  // Fetch API를 사용해 백그라운드로 전송 (keepalive 사용으로 브라우저 닫혀도 전송 보장 시도)
  return fetch('/api/media/progress', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data),
    keepalive: true
  }).catch(err => {
    console.error('[Viewer-Progress] Failed to save progress on flush:', err);
    return null;
  });
}

function prepareActiveViewerSnapshot() {
  try {
    import('./viewer/lifecycle_controller.js').then(m => {
      const instance = m.getActiveViewerInstance ? m.getActiveViewerInstance() : null;
      if (instance && typeof instance.prepareForClose === 'function') {
        instance.prepareForClose();
      }
    }).catch(() => {});
  } catch (e) {}
}

// ── 페이지 이탈 / 뒤로가기(popstate) / 탭 전환 / 화면 잠금 시 진행률 즉시 전송 ──
// SPA 브라우저 뒤로가기 버튼 / 모바일 슬라이드 뒤로가기 제스처 대응
window.addEventListener('popstate', () => {
  prepareActiveViewerSnapshot();
  flushProgress(true);
});

window.addEventListener('pagehide', () => {
  prepareActiveViewerSnapshot();
  flushProgress(true);
});

window.addEventListener('beforeunload', () => {
  prepareActiveViewerSnapshot();
  flushProgress(true);
});

// visibilitychange: 모바일 화면 잠금 / 홈 화면 나가기 / 앱 백그라운드 전환 시
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    prepareActiveViewerSnapshot();
    flushProgress(true);
  }
});
