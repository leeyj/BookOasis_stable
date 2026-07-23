// fileloader.js — 스트림 URL과 total_pages 동적 조회
import { state } from '../state.js';

export function getPageStreamUrl(pageIdx) {
  return `/api/media/stream?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&page_idx=${pageIdx}`;
}

export async function fetchTotalPagesIfNeeded(bookId, currentTotal) {
  if (currentTotal && currentTotal > 0) return currentTotal;
  try {
    const libType = state.currentLibraryType || 'general';
    const res = await fetch(`/api/media/books/${bookId}/info?type=${libType}`);
    if (res.status === 404) {
      if (typeof window.handleBookDeletedFallback === 'function') {
        window.handleBookDeletedFallback('해당 도서(카테고리)가 서버에서 삭제되었습니다.');
      }
      return 0;
    }
    const data = await res.json();
    if (data && data.success && data.total_pages > 0) {
      return data.total_pages;
    }
  } catch (e) {
    console.warn('[fileloader] fetchTotalPagesIfNeeded failed', e);
  }
  return currentTotal || 0;
}
