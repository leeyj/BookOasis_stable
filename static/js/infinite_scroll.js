// infinite_scroll.js – IntersectionObserver 기반 무한 스크롤 제어 모듈
import { state } from './state.js';
import { loadBooksList } from './book_list.js';

let infiniteScrollObserver = null;

export function initInfiniteScrollObserver() {
  const spinner = document.getElementById('infinite-scroll-spinner');
  if (!spinner) return;

  if (infiniteScrollObserver) {
    infiniteScrollObserver.disconnect();
  }

  infiniteScrollObserver = new IntersectionObserver((entries) => {
    const entry = entries[0];
    if (entry.isIntersecting) {
      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') return;
      if (state.currentLibraryId === 'history' || state.currentLibraryId === 'home' || state.currentLibraryId === 'settings') return;
      if (state.isLoading || !state.hasMore) return;

      console.log('[InfiniteScroll-Observer] Spinner intersected -> Loading next page...');
      loadBooksList(true);
    }
  }, {
    root: null,
    rootMargin: '0px 0px 800px 0px', // 최하단 도달 800px 전 미리 로딩 (휠 스크롤 감지 최적화)
    threshold: 0
  });

  infiniteScrollObserver.observe(spinner);
}
