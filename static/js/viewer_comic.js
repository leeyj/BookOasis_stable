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
    const totalPages = Renderer.getComicTotalPages();
    if (!state.activeBookId || !totalPages || totalPages <= 0) return;
    saveProgress(state.activeBookId, Renderer.getComicCurrentPage(), totalPages);
  },
  destroy() {
    clearComicViewer();
  },
  prevPage() {
    const isRtl = localStorage.getItem('comic_reading_direction') === 'rtl';
    if (isRtl) {
      nextComicPage();
    } else {
      prevComicPage();
    }
  },
  nextPage() {
    const isRtl = localStorage.getItem('comic_reading_direction') === 'rtl';
    if (isRtl) {
      prevComicPage();
    } else {
      nextComicPage();
    }
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

