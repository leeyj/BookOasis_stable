// lifecycle_controller.js - open/close orchestration for viewer modal
import { state } from '../state.js';
import { ComicViewer, clearComicViewer } from '../viewer_comic.js';
import { TxtViewer } from '../viewer_txt.js';
import { PdfViewer, clearPdfViewer } from '../viewer_pdf.js';
import { tryAutoFullscreenOnOpen, exitFullscreenIfNeeded } from './fullscreen_controller.js';

let deps = {
  loadCustomFontsList: () => {},
  initViewerSeekBar: () => {},
  syncHotspotPointerEvents: () => {},
  clearEpubViewer: () => {},
};

let activeViewerInstance = null;

export function configureLifecycleController(nextDeps = {}) {
  deps = { ...deps, ...nextDeps };
}

export function getActiveViewerInstance() {
  return activeViewerInstance;
}

export function openReader(bookId, format, title, pagesRead, totalPages) {
  console.log(`[Viewer-Core] openReader 시작 - Book ID: ${bookId}, Format: ${format}, Title: ${title}`);

  import('../viewer_next_episode.js').then((m) => {
    if (m.clearNextEpisodeArm) {
      console.log('[Viewer-Core] Resetting next episode arming state for new reader session');
      m.clearNextEpisodeArm();
    }
  }).catch(() => {});

  state.activeBookId = bookId;
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;

  if (viewerModal.parentNode !== document.body) {
    document.body.appendChild(viewerModal);
  }

  viewerModal.style.display = 'flex';
  document.getElementById('viewer-title-text').textContent = title;

  tryAutoFullscreenOnOpen();

  if (window.location.hash !== '#viewer') {
    history.pushState({ view: 'viewer', bookId, libraryId: state.currentLibraryId }, '', '#viewer');
  }

  document.body.style.setProperty('overflow', 'hidden', 'important');
  document.documentElement.style.setProperty('overflow', 'hidden', 'important');

  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (overlayMenu) overlayMenu.style.display = 'none';

  const floatingCloseBtn = document.querySelector('.floating-close-btn');
  if (floatingCloseBtn) floatingCloseBtn.style.display = 'none';

  document.querySelectorAll('.viewer-pane').forEach((p) => {
    p.style.display = 'none';
  });
  document.getElementById('txt-controls').style.display = 'none';
  document.getElementById('comic-fit-controls').style.display = 'none';

  const overlayComicFit = document.getElementById('overlay-comic-fit-group');
  const overlayTxtControls = document.getElementById('overlay-txt-controls-row');
  if (overlayComicFit) overlayComicFit.style.display = 'none';
  if (overlayTxtControls) overlayTxtControls.style.display = 'none';

  deps.loadCustomFontsList();

  const savedFont = localStorage.getItem('viewer_font_family') || 'batang';
  const select = document.getElementById('viewer-font-select');
  if (select) select.value = savedFont;

  const savedLineHeight = localStorage.getItem('viewer_line_height') || '1.8';
  const selectLineHeight = document.getElementById('viewer-line-height-select');
  if (selectLineHeight) selectLineHeight.value = savedLineHeight;

  const savedParagraphSpacing = localStorage.getItem('viewer_paragraph_spacing') || '1.0';
  const selectParagraphSpacing = document.getElementById('viewer-paragraph-spacing-select');
  if (selectParagraphSpacing) selectParagraphSpacing.value = savedParagraphSpacing;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const btnPage = document.getElementById('btn-scroll-page');
  const btnScroll = document.getElementById('btn-scroll-continuous');
  if (scrollMode === 'page') {
    if (btnPage) btnPage.classList.add('active');
    if (btnScroll) btnScroll.classList.remove('active');
  } else {
    if (btnPage) btnPage.classList.remove('active');
    if (btnScroll) btnScroll.classList.add('active');
  }

  const widthRow = document.getElementById('overlay-width-row');
  if (widthRow) widthRow.classList.toggle('visible', scrollMode === 'scroll');

  const savedScrollWidth = parseInt(localStorage.getItem('comic_scroll_width'), 10) || 800;
  const widthSlider = document.getElementById('comic-scroll-width-slider');
  const widthLabel = document.getElementById('comic-scroll-width-label');
  if (widthSlider) widthSlider.value = savedScrollWidth;
  if (widthLabel) widthLabel.textContent = `${savedScrollWidth}px`;

  const fmt = format.toLowerCase();
  state.currentViewerFormat = fmt;

  if (activeViewerInstance && typeof activeViewerInstance.destroy === 'function') {
    try {
      console.log(`[Viewer-Core] 기존 활성 뷰어 정리: ${state.currentViewerFormat}`);
      activeViewerInstance.destroy();
    } catch (e) {
      console.warn('[Viewer-Core] Failed to destroy active viewer:', e);
    }
  }
  activeViewerInstance = null;

  if (fmt === 'zip' || fmt === 'cbz' || fmt === 'imgdir') {
    if (overlayComicFit) overlayComicFit.style.display = 'flex';
    activeViewerInstance = ComicViewer;
    activeViewerInstance.init(bookId, pagesRead, totalPages).then(() => {
      deps.initViewerSeekBar();
    });
  } else if (fmt === 'txt') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_text') || '텍스트 보기';
    activeViewerInstance = TxtViewer;
    activeViewerInstance.init(bookId, pagesRead);
    deps.initViewerSeekBar();
  } else if (fmt === 'pdf') {
    activeViewerInstance = PdfViewer;
    activeViewerInstance.init(bookId, pagesRead, totalPages);
    deps.initViewerSeekBar();
  } else if (fmt === 'epub') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_epub') || 'EPUB 보기';
    activeViewerInstance = TxtViewer;
    activeViewerInstance.init(bookId, pagesRead);
    deps.initViewerSeekBar();
  } else {
    alert(i18n.t('viewer.unsupported_format'));
    closeMediaViewer();
  }

  deps.syncHotspotPointerEvents();
}

export function closeMediaViewer(triggerBack = true, isTransitioning = false) {
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;

  if (activeViewerInstance && typeof activeViewerInstance.prepareForClose === 'function') {
    try {
      activeViewerInstance.prepareForClose();
    } catch (e) {
      console.warn('[Viewer-Core] Error preparing viewer for close:', e);
    }
  }

  exitFullscreenIfNeeded();

  const padPanel = document.getElementById('viewer-padding-overlay-panel');
  if (padPanel) {
    padPanel.style.display = 'none';
  }

  if (!isTransitioning) {
    viewerModal.classList.remove('fullscreen-mode');
    viewerModal.style.display = 'none';
    document.getElementById('fullscreen-icon').className = 'fa-solid fa-expand';
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('position');
    document.body.style.removeProperty('top');
    document.body.style.removeProperty('width');
    document.documentElement.style.removeProperty('overflow');

    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.width = '';
    document.documentElement.style.overflow = '';
  }

  if (activeViewerInstance && typeof activeViewerInstance.destroy === 'function') {
    try {
      console.log('[Viewer-Core] activeViewerInstance.destroy() 실행');
      activeViewerInstance.destroy();
    } catch (e) {
      console.warn('[Viewer-Core] Error destroying viewer instance:', e);
    }
    activeViewerInstance = null;
  } else {
    clearComicViewer();
    deps.clearEpubViewer();
    clearPdfViewer();
  }

  import('../viewer_progress.js').then((m) => {
    const flushPromise = m.flushProgress();
    if (m.resetPreloadState) m.resetPreloadState();

    const reloadData = () => {
      console.log('[Viewer-Core] DB Progress flush 완료. 화면 데이터 갱신을 실행합니다.');
      if (state.currentLibraryId === 'home') {
        import('../dashboard.js').then((d) => d.loadDashboardData());
      } else if (state.currentLibraryId === 'history') {
        import('../book_list.js').then((b) => b.loadReadingHistory());
      }

      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') {
        const seriesName = String(state.detailSeriesName || '').trim();
        if (seriesName) {
          import('../modal.js').then((mod) => {
            mod.openBookDetail(
              null,
              seriesName,
              state.detailLibraryId || state.currentLibraryId,
              state.detailRepresentativeBookId || null,
              state.detailDisplayTitle || ''
            );
          });
        }
      }
    };

    if (flushPromise && typeof flushPromise.then === 'function') {
      flushPromise.then(() => reloadData());
    } else {
      reloadData();
    }
  });

  if (triggerBack && !isTransitioning && window.location.hash === '#viewer') {
    history.back();
  }
}
