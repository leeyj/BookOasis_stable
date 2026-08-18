// Thin wrapper for backward compatibility — re-export modular viewer APIs
import * as Viewer from './viewer/viewer_init.js';
import * as Settings from './viewer/reader_settings.js';
import * as Renderer from './viewer/renderer.js';
import * as Nav from './viewer/navigation.js';
import { state } from './state.js';
import { saveProgress } from './viewer_progress.js';

// Re-export commonly used APIs as wrappers to avoid circular-import undefineds
export function initComicViewer(...args) { return (Viewer.initComicViewer || Viewer.initViewer).apply(null, args); }
export function nextComicPage(...args) { return Nav.nextComicPage.apply(null, args); }
export function prevComicPage(...args) { return Nav.prevComicPage.apply(null, args); }
export function comicSliderInput(...args) { return Nav.comicSliderInput.apply(null, args); }
export function comicSliderChange(...args) { return Nav.comicSliderChange.apply(null, args); }
export function setComicFitMode(...args) { return (Renderer.setComicFitMode || Settings.setFitMode).apply(null, args); }
export function toggleComicOverlay(...args) { return Nav.toggleComicOverlay.apply(null, args); }
export function markAsCompleted(...args) { return Nav.markAsCompleted.apply(null, args); }
export function applyComicFitMode(...args) { return Renderer.applyComicFitMode.apply(null, args); }
export function loadComicPage(...args) { return Renderer.loadComicPage.apply(null, args); }
export function comicJumpToFirstPage(...args) { return Nav.comicJumpToFirstPage.apply(null, args); }
export function comicJumpToLastPage(...args) { return Nav.comicJumpToLastPage.apply(null, args); }
export function getComicReadingDirection(...args) { return Settings.getComicReadingDirection.apply(null, args); }
export function toggleComicReadingDirection(...args) { return Settings.toggleComicReadingDirection.apply(null, args); }
export function getComicPageStep(...args) { return Settings.getComicPageStep.apply(null, args); }
export function toggleComicPageStep(...args) { return Settings.toggleComicPageStep.apply(null, args); }
export function setComicPageStep(...args) { return Settings.setComicPageStep.apply(null, args); }
export function setComicScrollWidth(px) { return Settings.setScrollWidth(px); }
export function getTapZoneDirection(...args) { return Settings.getTapZoneDirection.apply(null, args); }
export function toggleTapZoneDirection(...args) { return Settings.toggleTapZoneDirection.apply(null, args); }
export function initTapZoneDirection(...args) { return Settings.initTapZoneDirection.apply(null, args); }
export function getComicSplitSpread(...args) { return Settings.getComicSplitSpread.apply(null, args); }
export function toggleComicSplitSpread(...args) { return Settings.toggleComicSplitSpread.apply(null, args); }
export function initSplitSpread(...args) { return Settings.initSplitSpread.apply(null, args); }
export function syncSplitSpreadMode(...args) { return Renderer.syncSplitSpreadMode.apply(null, args); }
export function syncSplitSpreadModeForScrollMode(...args) { return Renderer.syncSplitSpreadModeForScrollMode.apply(null, args); }
export function getPhysicalProgress(...args) { return Renderer.getPhysicalProgress.apply(null, args); }
export function clearComicViewer(...args) { return Renderer.clearComicViewer.apply(null, args); }

// Expose legacy globals on window as live bindings
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'comicCurrentPage', {
    get() { return Renderer.getComicCurrentPage(); },
    set(v) { return Renderer.setComicCurrentPage(v); }
  });
  Object.defineProperty(window, 'comicTotalPages', {
    get() { return Renderer.getComicTotalPages(); },
    set(v) { return Renderer.setComicTotalPages(v); }
  });
  Object.defineProperty(window, 'comicPageStep', {
    get() { return Settings.getComicPageStep(); },
    set(v) { Settings.setComicPageStep(v); }
  });
  Object.defineProperty(window, 'comicFitMode', {
    get() { return Settings.getFitMode(); },
    set(v) { Settings.setFitMode(v); }
  });
  Object.defineProperty(window, 'comicReadingDirection', {
    get() { return Settings.getComicReadingDirection(); },
    set(v) { Settings.setComicReadingDirection(v); }
  });

  // Also expose functions globally for legacy callers
  window.initComicViewer = initComicViewer;
  window.clearComicViewer = clearComicViewer;
  window.nextComicPage = nextComicPage;
  window.prevComicPage = prevComicPage;
  window.setComicFitMode = setComicFitMode;
  window.toggleComicOverlay = toggleComicOverlay;
  window.markAsCompleted = markAsCompleted;
  window.setComicScrollWidth = setComicScrollWidth; // 스크롤 너비 조절 (600~900px)
}

export const ComicViewer = {
  async init(bookId, pagesRead, totalPages) {
    return initComicViewer(bookId, pagesRead, totalPages);
  },
  prepareForClose() {
    if (!state.activeBookId) return;
    // 분할 보기(가상 절반-페이지) 상태에서 그대로 getComicCurrentPage()/getComicTotalPages()를
    // 보내면 실제 페이지 수의 2배가 서버 books.total_pages에 그대로 저장되어 버려서,
    // 다음에 책을 열 때 존재하지 않는 페이지를 요청하며 400 에러가 나는 원인이 된다.
    // 반드시 물리 페이지 기준으로 환산해서 저장해야 한다.
    const { page, total } = Renderer.getPhysicalProgress();
    if (!total || total <= 0) return;
    saveProgress(state.activeBookId, page, total);
  },
  destroy() {
    clearComicViewer();
  },
  prevPage() {
    prevComicPage();
  },
  nextPage() {
    nextComicPage();
  },
  jumpTo(target) {
    if (target === 'first') {
      comicJumpToFirstPage();
    } else if (target === 'last') {
      comicJumpToLastPage();
    }
  },
  applySettings(options) {
    if (options && options.fitMode) {
      setComicFitMode(options.fitMode);
    }
    applyComicFitMode();
  }
};

