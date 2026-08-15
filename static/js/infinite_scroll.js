// infinite_scroll.js – IntersectionObserver 기반 무한 스크롤 제어 모듈
import { state } from './state.js';
import { loadBooksList, loadPreviousBooksPage } from './book_list.js';

let infiniteScrollObserver = null;
let infiniteScrollTopObserver = null;

export function initInfiniteScrollObserver() {
  const spinner = document.getElementById('infinite-scroll-spinner');
  const spinnerTop = document.getElementById('infinite-scroll-spinner-top');
  const mainContent = document.querySelector('.library-main-content');

  if (spinner) {
    if (infiniteScrollObserver) {
      infiniteScrollObserver.disconnect();
    }

    infiniteScrollObserver = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry.isIntersecting) {
        const detailView = document.getElementById('book-detail-view');
        if (detailView && detailView.style.display !== 'none') return;

        const currentId = state.currentLibraryId || '';
        if (['history', 'home', 'settings', 'collection', 'plugins'].includes(currentId) || currentId.startsWith('plugin_')) return;
        if (state.isLoading || !state.hasMore) return;

        console.log('[InfiniteScroll-Observer] Spinner intersected -> Loading next page...');
        loadBooksList(true);
      }
    }, {
      root: mainContent || null,
      rootMargin: '0px 0px 800px 0px',
      threshold: 0
    });

    infiniteScrollObserver.observe(spinner);
  }

  // 초성 점프 등으로 중간 페이지부터 로드된 경우, 위로 스크롤하면 이전 페이지를 이어붙인다.
  if (spinnerTop) {
    if (infiniteScrollTopObserver) {
      infiniteScrollTopObserver.disconnect();
    }

    infiniteScrollTopObserver = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry.isIntersecting) {
        const detailView = document.getElementById('book-detail-view');
        if (detailView && detailView.style.display !== 'none') return;

        const currentId = state.currentLibraryId || '';
        if (['history', 'home', 'settings', 'collection', 'plugins'].includes(currentId) || currentId.startsWith('plugin_')) return;
        if (state.isLoading || state.isLoadingPrevious || !state.hasPrevious) return;

        console.log('[InfiniteScroll-Observer] Top spinner intersected -> Loading previous page...');
        loadPreviousBooksPage();
      }
    }, {
      root: mainContent || null,
      rootMargin: '800px 0px 0px 0px',
      threshold: 0
    });

    infiniteScrollTopObserver.observe(spinnerTop);
  }
}

