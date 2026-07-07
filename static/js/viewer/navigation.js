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

  // ── iOS Safari 스크롤 락 패턴 (조건부) ────────────────────────────────────
  // TXT/EPUB 스크롤 모드에서 실제 스크롤은 body가 아닌 내부 컨테이너
  // (#txt-scroll-wrapper 등)에서 발생하므로 window.scrollY = 0이 대부분.
  // body가 스크롤되지 않은 상태에서 body { position:fixed }를 적용하면
  // iOS Safari가 내부 컨테이너의 scrollTop을 리셋시키는 부작용이 생긴다.
  //
  // 규칙:
  //   window.scrollY > 0 → body가 실제로 스크롤됨 → iOS body-lock 적용
  //   window.scrollY = 0 → 내부 컨테이너가 스크롤됨 → body-lock 생략
  //                          내부 컨테이너 scrollTop은 별도로 보존
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isScrollMode = scrollMode === 'scroll';

  if (isOpening) {
    if (isScrollMode) {
      const bodyScrollY = window.scrollY || window.pageYOffset || 0;

      if (bodyScrollY > 0) {
        // body가 실제로 스크롤된 경우에만 iOS body-lock 적용
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.top = `-${bodyScrollY}px`;
        document.body.style.width = '100%';
        menu.dataset.savedBodyScrollY = String(bodyScrollY);
        menu.dataset.iosBodyLock = 'true';
        console.log(`[Viewer-Nav] iOS body-lock applied. bodyScrollY=${bodyScrollY}`);
      } else {
        // 내부 컨테이너가 스크롤된 경우 — scrollTop만 기록해둠 (body-lock 없음)
        menu.dataset.iosBodyLock = 'false';
        const innerScrollers = [
          'txt-scroll-wrapper',
          'comic-scroll-container',
          'epub-viewer-container',
        ];
        const scrollData = {};
        innerScrollers.forEach(id => {
          const el = document.getElementById(id);
          if (el && el.scrollTop > 0) scrollData[id] = el.scrollTop;
        });
        menu.dataset.savedInnerScroll = JSON.stringify(scrollData);
        console.log(`[Viewer-Nav] Inner scroll saved:`, scrollData);
      }
    }

    Renderer.updatePageInfo();
    // 현재 스크롤 모드에 따라 너비 슬라이더 행 가시성 동기화
    const widthRow = document.getElementById('overlay-width-row');
    if (widthRow) widthRow.classList.toggle('visible', isScrollMode);

  } else {
    if (isScrollMode) {
      if (menu.dataset.iosBodyLock === 'true') {
        // body-lock 해제 및 body 스크롤 위치 복원
        const savedScrollY = parseInt(menu.dataset.savedBodyScrollY || '0', 10);
        document.body.style.overflow = 'auto';
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        window.scrollTo(0, savedScrollY);
        console.log(`[Viewer-Nav] iOS body-lock released. bodyScrollY restored=${savedScrollY}`);
      } else {
        // 내부 컨테이너 scrollTop 복원
        try {
          const scrollData = JSON.parse(menu.dataset.savedInnerScroll || '{}');
          Object.entries(scrollData).forEach(([id, top]) => {
            const el = document.getElementById(id);
            if (el) el.scrollTop = top;
          });
        } catch (e) { /* ignore */ }
      }
      delete menu.dataset.savedBodyScrollY;
      delete menu.dataset.savedInnerScroll;
      delete menu.dataset.iosBodyLock;
    }
  }

  // ────────────────────────────────────────────────────────────────────────
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
