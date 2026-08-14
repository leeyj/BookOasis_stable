// lifecycle_controller.js - open/close orchestration for viewer modal
import { state } from '../state.js';
import { ComicViewer, clearComicViewer } from '../viewer_comic.js';
import { TxtViewer } from '../viewer_txt.js';
import { PdfViewer, clearPdfViewer } from '../viewer_pdf.js';
import { tryAutoFullscreenOnOpen, exitFullscreenIfNeeded } from './fullscreen_controller.js';
import { shouldAutoFullscreenForFormat } from './platform_profile.js';
import { flushProgress, resetPreloadState } from '../viewer_progress.js';

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

  const fmt = String(format || '').toLowerCase();
  const audioFormats = ['mp3', 'm4b', 'm4a', 'flac', 'aac', 'wav', 'ogg', 'opus', 'audiobook'];
  if (audioFormats.includes(fmt) || state.currentLibraryType === 'audiobook') {
    if (typeof window.openAudioPlayer === 'function') {
      // 오디오북 공통 진입점에서는 전달받은 bookId를 작품 ID로 취급한다.
      // (트랙 단위 재생 진입은 상세/이어보기에서 openAudioPlayer를 직접 호출)
      window.openAudioPlayer(bookId, null, pagesRead);
      return;
    }
  }

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

  // 플랫폼/포맷 정책 기반 자동 전체화면 분기 (수동 전체화면 버튼은 별도로 유지)
  if (shouldAutoFullscreenForFormat(fmt)) {
    tryAutoFullscreenOnOpen();
  }

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
  if (!viewerModal) return Promise.resolve();

  if (activeViewerInstance && typeof activeViewerInstance.prepareForClose === 'function') {
    try {
      activeViewerInstance.prepareForClose();
    } catch (e) {
      console.warn('[Viewer-Core] Error preparing viewer for close:', e);
    }
  }

  const fullscreenExitPromise = exitFullscreenIfNeeded();

  const padPanel = document.getElementById('viewer-padding-overlay-panel');
  if (padPanel) {
    padPanel.style.display = 'none';
  }

  if (!isTransitioning) {
    const menu = document.getElementById('comic-overlay-menu');
    let savedScrollY = 0;
    if (menu && menu.dataset.iosBodyLock === 'true') {
      savedScrollY = parseInt(menu.dataset.savedBodyScrollY || '0', 10);
      menu.dataset.iosBodyLock = 'false';
    }

    viewerModal.classList.remove('fullscreen-mode');
    viewerModal.style.display = 'none';
    const fullscreenIcon = document.getElementById('fullscreen-icon');
    if (fullscreenIcon) fullscreenIcon.className = 'fa-solid fa-expand';

    // body 및 documentElement 인라인 스크롤 락 스타일만 안전 소거 (CSS 변수 유실 방지)
    document.body.style.removeProperty('overflow');
    document.documentElement.style.removeProperty('overflow');

    if (state.systemSettings) {
      import('../settings/general.js').then(m => {
        if (m.applySettingsToUI) m.applySettingsToUI(state.systemSettings);
      }).catch(() => {});
    }

    if (savedScrollY > 0) {
      window.scrollTo(0, savedScrollY);
    }

    // 모바일 브라우저 뷰포트 레이아웃 재계산 및 카테고리 헤더 리플로우 유도
    const forceLayoutRecovery = () => {
      // 강제 리플로우: 일부 모바일 브라우저는 Fullscreen 종료 직후 safe-area/뷰포트
      // 단위(env(), dvh)를 즉시 재계산하지 않아 상단 사이드바(햄버거 메뉴)가
      // 잘못된 크기로 그려진 채 남는 경우가 있어, 실제 스타일 재계산을 강제한다.
      void document.body.offsetHeight;
      window.dispatchEvent(new Event('resize'));
      import('../sidebar_manager.js').then((m) => {
        if (m.syncSidebarResponsiveControls) m.syncSidebarResponsiveControls();
      }).catch(() => {});
    };

    requestAnimationFrame(forceLayoutRecovery);
    // exitFullscreenIfNeeded()는 비동기로 완료되므로, 전환이 실제로 끝난 뒤
    // 한 번 더 복구를 수행해 Fullscreen 종료 타이밍과의 경쟁 상태를 방지한다.
    Promise.resolve(fullscreenExitPromise)
      .then(() => requestAnimationFrame(forceLayoutRecovery))
      .catch(() => {});
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

  const flushPromise = flushProgress(false, true);
  resetPreloadState();

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

  flushPromise
    .then(() => reloadData())
    .catch((error) => {
      console.warn('[Viewer-Core] Immediate progress flush failed; retrying view refresh:', error);
      window.setTimeout(reloadData, 2000);
    });

  if (triggerBack && !isTransitioning && window.location.hash === '#viewer') {
    history.back();
  }

  // 다음 책/에피소드 전환처럼 닫자마자 곧바로 새 뷰어를 여는 호출부가
  // Fullscreen 종료 전환이 실제로 끝날 때까지 기다릴 수 있도록 반환한다.
  // (특히 Android는 exitFullscreen이 비동기로 늦게 끝나는데, 이걸 기다리지 않고
  //  바로 다음 책에서 requestFullscreen을 다시 호출하면 브라우저가 두 번째
  //  요청을 조용히 무시해 화면이 멈춘 것처럼 보이는 문제가 있었다.)
  return Promise.resolve(fullscreenExitPromise);
}

export function handleBookDeletedFallback(reason = '해당 도서(카테고리)가 서버에서 삭제되었습니다.') {
  console.warn(`[Viewer-Fallback] 도서 삭제 감지 404: ${reason}`);
  
  // 1. 진행 중인 뷰어 닫기
  try {
    closeMediaViewer(false);
  } catch (e) {}
  
  // 2. 사용자용 알림 표출
  if (typeof window.showToast === 'function') {
    window.showToast(`⚠️ ${reason} 목록 화면으로 이동합니다.`, 'error');
  } else {
    alert(`⚠️ ${reason}\n목록 화면으로 이동합니다.`);
  }

  // 3. 해시 정리 및 목록으로 안전 이동
  if (window.location.hash === '#viewer') {
    window.location.hash = '';
  }
}

window.handleBookDeletedFallback = handleBookDeletedFallback;
