// navigation.js — 페이지 이동 관련 API
import * as Renderer from './renderer.js';
import * as Settings from './reader_settings.js';
import { saveProgress } from '../viewer_progress.js';
import { state } from '../state.js'; // window.state 대신 ES 모듈 import 사용

export function comicSliderInput(slider, val) {
  Renderer.showSeekbarTooltip(slider, val);
  const badge = document.getElementById('comic-overlay-page-info');
  if (badge) badge.textContent = `${val} / ${Renderer.comicTotalPages}`;
}

export function comicSliderChange(slider, val) {
  Renderer.hideSeekbarTooltip();
  Renderer.setComicCurrentPage(val - 1);
  Renderer.loadComicPage();
}

export function toggleComicOverlay() {
  console.log('[Viewer-Nav] toggleComicOverlay() called');
  const menu = document.getElementById('comic-overlay-menu');
  if (!menu) return;
  const isOpening = (menu.style.display === 'none');
  menu.style.display = isOpening ? 'flex' : 'none';

  const pdfNavBar = document.querySelector('.pdf-nav-bar');
  if (pdfNavBar) {
    pdfNavBar.style.display = isOpening ? 'flex' : 'none';
  }
  const epubNavBar = document.querySelector('.epub-nav-bar');
  if (epubNavBar) {
    epubNavBar.style.display = isOpening ? 'flex' : 'none';
  }
  const floatingCloseBtn = document.querySelector('.floating-close-btn');
  if (floatingCloseBtn) {
    floatingCloseBtn.style.display = isOpening ? 'flex' : 'none';
  }

  if (isOpening) {
    Renderer.updatePageInfo();
    // 현재 스크롤 모드에 따라 너비 슬라이더 행 가시성 동기화
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    const widthRow = document.getElementById('overlay-width-row');
    if (widthRow) widthRow.classList.toggle('visible', scrollMode === 'scroll');
  }
}

export function comicJumpToFirstPage() {
  Renderer.setComicCurrentPage(0);
  Renderer.loadComicPage();
}

export function comicJumpToLastPage() {
  Renderer.setComicCurrentPage(Math.max(0, Renderer.getComicTotalPages() - 1));
  Renderer.loadComicPage();
}

export function markAsCompleted() {
  if (Renderer.comicTotalPages > 0) {
    Renderer.setComicCurrentPage(Renderer.getComicTotalPages() - 1);
    Renderer.loadComicPage();

    saveProgress(state.activeBookId, Renderer.getComicCurrentPage(), Renderer.getComicTotalPages());
    import('../viewer_progress.js').then(m => m.flushProgress());

    alert(window.i18n.t('viewer.read_completed'));
    toggleComicOverlay();
  }
}

export function nextComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'scroll') {
    if (Renderer.getComicCurrentPage() < Renderer.getComicTotalPages() - 1) {
      Renderer.setIsScrollingToTarget(true);
      Renderer.setComicCurrentPage(Renderer.getComicCurrentPage() + 1);
      const targetImg = document.querySelector(`.comic-scroll-img[data-index="${Renderer.getComicCurrentPage()}"]`);
      if (targetImg) targetImg.scrollIntoView({ behavior: 'smooth', block: 'start' });
      Renderer.updatePageInfo();
      saveProgress(state.activeBookId, Renderer.getComicCurrentPage(), Renderer.getComicTotalPages());
      setTimeout(() => { Renderer.setIsScrollingToTarget(false); }, 500);
    } else {
      import('../viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    }
  } else {
  const step = Settings.getComicPageStep ? Settings.getComicPageStep() : 1;
    const nextPage = Math.min(Renderer.getComicCurrentPage() + step, Renderer.getComicTotalPages() - 1);
    if (nextPage !== Renderer.getComicCurrentPage()) {
      Renderer.setComicCurrentPage(nextPage);
      Renderer.loadComicPage();
    } else {
      import('../viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    }
  }
}

export function prevComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'scroll') {
    if (Renderer.getComicCurrentPage() > 0) {
      Renderer.setIsScrollingToTarget(true);
      Renderer.setComicCurrentPage(Renderer.getComicCurrentPage() - 1);
      const targetImg = document.querySelector(`.comic-scroll-img[data-index="${Renderer.getComicCurrentPage()}"]`);
      if (targetImg) targetImg.scrollIntoView({ behavior: 'smooth', block: 'start' });
      Renderer.updatePageInfo();
      saveProgress(state.activeBookId, Renderer.getComicCurrentPage(), Renderer.getComicTotalPages());
      setTimeout(() => { Renderer.setIsScrollingToTarget(false); }, 500);
    }
  } else {
    const step = Settings.getComicPageStep ? Settings.getComicPageStep() : 1;
    const prevPage = Math.max(Renderer.getComicCurrentPage() - step, 0);
    if (prevPage !== Renderer.getComicCurrentPage()) {
      Renderer.setComicCurrentPage(prevPage);
      Renderer.loadComicPage();
    }
  }
}
