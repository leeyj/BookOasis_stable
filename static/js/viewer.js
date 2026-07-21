// viewer.js – 미디어 뷰어 라이프사이클 및 단축키 코어 조율기
import { state } from './state.js';
import { nextComicPage, prevComicPage, setComicFitMode, toggleComicOverlay, markAsCompleted as markComicAsCompleted, getComicReadingDirection, toggleComicReadingDirection, toggleComicPageStep, comicJumpToFirstPage, comicJumpToLastPage } from './viewer_comic.js';
import { prevTxtPage, nextTxtPage, applyTxtSettings, txtJumpToFirstPage, txtJumpToLastPage } from './viewer_txt.js';
import { nextPdfPage, prevPdfPage, pdfJumpToFirstPage, pdfJumpToLastPage } from './viewer_pdf.js';
import { initFullscreenStateSync, isViewerInFullscreen, toggleFullscreenViewer } from './viewer/fullscreen_controller.js';
import { initViewerSeekBar } from './viewer/seekbar_controller.js';
import {
  configureLifecycleController,
  getActiveViewerInstance,
  openReader,
  closeMediaViewer,
} from './viewer/lifecycle_controller.js';
import {
  configureInputController,
  initKeyboardListener,
  initWheelListener,
  syncHotspotPointerEvents,
  initViewerClickToggle,
} from './viewer/input_controller.js';
export { toggleFullscreenViewer };
export { initKeyboardListener, initWheelListener, syncHotspotPointerEvents, initViewerClickToggle };
export { openReader, closeMediaViewer, initViewerSeekBar };

initFullscreenStateSync();

// Unused legacy EPUB functions (stubbed for compatibility)
export async function initEpubViewer(bookId, pagesRead, totalPages) {}
export async function clearEpubViewer() {}
export async function epubPrevPage() {}
export async function epubNextPage() {}
export async function applyEpubSettings(options) {}
export async function changeEpubScrollMode(scrollMode) {}
import { updateFontSize, toggleTheme, updateLineHeight, updateParagraphSpacing } from './viewer_settings.js';

// 사용자 정의 폰트 목록 로드 및 드롭다운 바인딩
export function loadCustomFontsList() {
  fetch('/api/media/fonts')
    .then(res => res.json())
    .then(data => {
      if (data.success && data.fonts) {
        window.customFonts = data.fonts;
        console.log("[Viewer-Fonts] Custom fonts loaded: ", window.customFonts);

        let styleContent = '';
        data.fonts.forEach(f => {
            const fontFaceName = `CustomFont_${f.name.replace(/\s+/g, '_')}`;
            styleContent += `@font-face { font-family: '${fontFaceName}'; src: url("${f.url}"); }\n`;
        });
        if (styleContent) {
            let styleEl = document.getElementById('viewer-custom-fonts-style');
            if (!styleEl) {
                styleEl = document.createElement('style');
                styleEl.id = 'viewer-custom-fonts-style';
                document.head.appendChild(styleEl);
            }
            styleEl.innerHTML = styleContent;
        }

        const select = document.getElementById('viewer-font-select');
        if (select) {
          const sortedFontsDesc = [...data.fonts].sort((a, b) =>
            String(b.name || '').localeCompare(String(a.name || ''), undefined, { sensitivity: 'base' })
          );

          // 기존 기본 옵션만 남기고 초기화
          select.innerHTML = `
            <option value="batang">KoPub 바탕</option>
            <option value="gothic">나눔고딕</option>
            <option value="pretendard">Pretendard</option>
          `;
          sortedFontsDesc.forEach(font => {
            const opt = document.createElement('option');
            opt.value = font.name;
            opt.textContent = font.name;
            select.appendChild(opt);
          });

          // 현재 선택된 폰트 복원
          const savedFont = localStorage.getItem('viewer_font_family') || 'batang';
          select.value = savedFont;
        }
      }
    })
    .catch(err => console.error("[Viewer-Fonts] Failed to fetch custom fonts list:", err));
}

// 이전 페이지 통합 조율
export function prevPage() {
  console.log('[Viewer-Core] prevPage() called');
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.prevPage === 'function') {
    activeViewerInstance.prevPage();
    return;
  }
  const isRtl = localStorage.getItem('comic_reading_direction') === 'rtl';
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    if (getComicReadingDirection() === 'rtl') {
      nextComicPage();
    } else {
      prevComicPage();
    }
  } else if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    prevPdfPage();
  } else if (document.getElementById('epub-viewer-container').style.display !== 'none') {
    if (isRtl) {
      epubNextPage();
    } else {
      epubPrevPage();
    }
  } else if (document.getElementById('txt-viewer-container').style.display !== 'none') {
    prevTxtPage();
  }
}

// 다음 페이지 통합 조율
export function nextPage() {
  console.log('[Viewer-Core] nextPage() called');
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.nextPage === 'function') {
    activeViewerInstance.nextPage();
    return;
  }
  const isRtl = localStorage.getItem('comic_reading_direction') === 'rtl';
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    if (getComicReadingDirection() === 'rtl') {
      prevComicPage();
    } else {
      nextComicPage();
    }
  } else if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    nextPdfPage();
  } else if (document.getElementById('epub-viewer-container').style.display !== 'none') {
    if (isRtl) {
      epubPrevPage();
    } else {
      epubNextPage();
    }
  } else if (document.getElementById('txt-viewer-container').style.display !== 'none') {
    nextTxtPage();
  }
}

configureInputController({
  toggleFullscreenViewer,
  isViewerInFullscreen,
  closeMediaViewer,
  nextPage,
  prevPage,
  toggleComicOverlay,
});

configureLifecycleController({
  loadCustomFontsList,
  initViewerSeekBar,
  syncHotspotPointerEvents,
  clearEpubViewer,
});

// 공통 환경 설정 트리거 함수
export function changeFontSize(dir) {
  updateFontSize(dir);
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
}

export function toggleReaderTheme() {
  toggleTheme();
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
}

// HTML 인라인 이벤트 연동을 위해 글로벌 윈도우 객체에 바인딩
window.onViewerFontChange = function (value) {
  console.log(`[Viewer-Core] Font family changed to: ${value}`);
  localStorage.setItem('viewer_font_family', value);
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
};

window.onViewerLineHeightChange = function (value) {
  console.log(`[Viewer-Core] Line height changed to: ${value}`);
  updateLineHeight(value);
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
};

window.onViewerParagraphSpacingChange = function (value) {
  console.log(`[Viewer-Core] Paragraph spacing changed to: ${value}`);
  updateParagraphSpacing(value);
  const activeViewerInstance = getActiveViewerInstance();
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
};

window.setScrollMode = function (mode) {
  console.log(`[Viewer-Core] Scroll mode changed to: ${mode}`);
  const previousMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (previousMode === mode) return; // 동일 모드 클릭 시 무시
  localStorage.setItem('viewer_scroll_mode', mode);

  const btnPage = document.getElementById('btn-scroll-page');
  const btnScroll = document.getElementById('btn-scroll-continuous');
  if (mode === 'page') {
    if (btnPage) btnPage.classList.add('active');
    if (btnScroll) btnScroll.classList.remove('active');
  } else {
    if (btnPage) btnPage.classList.remove('active');
    if (btnScroll) btnScroll.classList.add('active');
  }

  // 너비 슬라이더 행: 스크롤 모드일 때만 표시
  const widthRow = document.getElementById('overlay-width-row');
  if (widthRow) {
    widthRow.classList.toggle('visible', mode === 'scroll');
  }

  // ── 보기 모드 전환 중 즉시 피드백 오버레이 ──────────────────────
  // 전체 뷰어를 덮는 반투명 블러 배경 + 중앙 알림 라벨
  // pointer-events: all → 터치/클릭 완전 차단
  const viewerBody = document.getElementById('viewer-body-container');
  const existingBanner = document.getElementById('viewer-mode-switch-banner');
  if (existingBanner) existingBanner.remove();

  const banner = document.createElement('div');
  banner.id = 'viewer-mode-switch-banner';
  banner.style.cssText = `
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: 20000;
    pointer-events: all;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: wait;
  `;
  banner.innerHTML = `
    <div style="
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(168, 85, 247, 0.6);
      color: #fff;
      padding: 0.9rem 2rem;
      border-radius: 50px;
      font-size: 1rem;
      font-weight: 600;
      white-space: nowrap;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 20px rgba(168,85,247,0.2);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    ">
      <i class="fa-solid fa-arrows-rotate" style="color:#a855f7; font-size:1rem;"></i>
      보기 모드 전환 중...
    </div>
  `;
  if (viewerBody) viewerBody.appendChild(banner);

  // 만화책 뷰어가 활성화되어 있는 경우, 스크롤 모드를 적용하여 다시 렌더링
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    const mod = import('./viewer_comic.js');
    mod.then(m => {
      const setStep = m.setComicPageStep || m.setComicPageStep;
      if (mode === 'scroll' && typeof setStep === 'function') {
        setStep(1);
      }
      const apply = m.applyComicFitMode || m.setComicFitMode || (window && window.setComicFitMode);
      if (typeof apply === 'function') apply();
      const load = m.loadComicPage || m.loadComicPage;
      if (typeof load === 'function') load();
    }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_comic:', err));
  }

  // 다음 프레임에서 실제 렌더링 (banner가 화면에 그려진 뒤 실행)
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      applyTxtSettings({ previousMode });
      changeEpubScrollMode(mode);
      syncHotspotPointerEvents();
      // 전환 완료 후 배너 제거
      setTimeout(() => {
        const b = document.getElementById('viewer-mode-switch-banner');
        if (b) b.remove();
      }, 400);
    });
  });
};

export function viewerJumpToFirst() {
  const fmt = state.currentViewerFormat;
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (fmt === 'zip' || fmt === 'cbz') {
    if (typeof comicJumpToFirstPage === 'function') comicJumpToFirstPage();
  } else if (fmt === 'epub') {
    // EPUB도 TxtViewer를 사용하므로 txtJumpToFirstPage 호출
    if (typeof txtJumpToFirstPage === 'function') txtJumpToFirstPage();
  } else if (fmt === 'pdf') {
    if (typeof pdfJumpToFirstPage === 'function') pdfJumpToFirstPage();
  } else if (fmt === 'txt') {
    if (typeof txtJumpToFirstPage === 'function') txtJumpToFirstPage();
  }

  // iOS Safari scroll mode: overlay close path can restore stale inner scroll.
  // When user explicitly jumps, skip one-time inner scroll restore.
  if (overlayMenu && scrollMode === 'scroll' && (fmt === 'epub' || fmt === 'txt')) {
    overlayMenu.dataset.skipInnerScrollRestore = 'true';
  }

  toggleComicOverlay();
}

export function viewerJumpToLast() {
  const fmt = state.currentViewerFormat;
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (fmt === 'zip' || fmt === 'cbz') {
    if (typeof comicJumpToLastPage === 'function') comicJumpToLastPage();
  } else if (fmt === 'epub') {
    // EPUB도 TxtViewer를 사용하므로 txtJumpToLastPage 호출
    if (typeof txtJumpToLastPage === 'function') txtJumpToLastPage();
  } else if (fmt === 'pdf') {
    if (typeof pdfJumpToLastPage === 'function') pdfJumpToLastPage();
  } else if (fmt === 'txt') {
    if (typeof txtJumpToLastPage === 'function') txtJumpToLastPage();
  }

  // Same guard for explicit jump-to-last in scroll mode.
  if (overlayMenu && scrollMode === 'scroll' && (fmt === 'epub' || fmt === 'txt')) {
    overlayMenu.dataset.skipInnerScrollRestore = 'true';
  }

  toggleComicOverlay();
}

window.viewerJumpToFirst = viewerJumpToFirst;
window.viewerJumpToLast = viewerJumpToLast;
window.jumpToFirstPage = viewerJumpToFirst;
window.jumpToLastPage = viewerJumpToLast;
window.prevPage = prevPage;
window.nextPage = nextPage;
window.toggleTheme = toggleReaderTheme;
window.toggleComicReadingDirection = function () {
  toggleComicReadingDirection();
  if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    if (typeof window.applyPdfFitMode === 'function') {
      window.applyPdfFitMode();
    }
  } else if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    import('./viewer_comic.js').then(m => {
      const load = m.loadComicPage;
      if (typeof load === 'function') load();
    });
  }
};

window.toggleComicPageStep = function () {
  toggleComicPageStep();
  if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    if (typeof window.applyPdfFitMode === 'function') {
      window.applyPdfFitMode();
    }
  } else if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    import('./viewer_comic.js').then(m => {
      const load = m.loadComicPage;
      if (typeof load === 'function') load();
    });
  } else if (document.getElementById('txt-viewer-container').style.display !== 'none') {
    applyTxtSettings();
  } else if (document.getElementById('epub-viewer-container').style.display !== 'none') {
    applyEpubSettings({ preservePagePosition: true });
  }
};

// 최초 로드 시 사용자 폰트 사전 로딩
loadCustomFontsList();





// 통합 읽음 완료 처리기 (ZIP, PDF, EPUB, TXT 전체 포맷 완독 조율)
export function markAsCompleted() {
  const fmt = state.currentViewerFormat;
  console.log(`[Viewer-Core] markAsCompleted 수동 호출 - Format: ${fmt}, Book ID: ${state.activeBookId}`);

  if (fmt === 'zip' || fmt === 'cbz') {
    markComicAsCompleted();
  } else if (fmt === 'pdf') {
    const pdfInfo = document.getElementById('pdf-page-info');
    let totalPages = 100;
    if (pdfInfo) {
      const parts = pdfInfo.textContent.split('/');
      if (parts.length === 2) {
        totalPages = parseInt(parts[1].trim(), 10) || 100;
      }
    }
    import('./viewer_progress.js').then(m => {
      m.saveProgress(state.activeBookId, totalPages - 1, totalPages);
      m.flushProgress().then(() => {
        alert(window.i18n.t('viewer.read_completed'));
        toggleComicOverlay();
      });
    });
  } else if (fmt === 'epub') {
    import('./viewer_progress.js').then(m => {
      m.saveProgress(state.activeBookId, 100, 100);
      m.flushProgress().then(() => {
        alert(window.i18n.t('viewer.read_completed'));
        toggleComicOverlay();
      });
    });
  } else if (fmt === 'txt') {
    const pageInfo = document.getElementById('comic-overlay-page-info');
    let totalPages = 100;
    if (pageInfo) {
      const match = pageInfo.textContent.match(/\/.*?(\d+)/);
      if (match && match[1]) {
        totalPages = parseInt(match[1].trim(), 10) || 100;
      }
    }
    import('./viewer_progress.js').then(m => {
      m.saveProgress(state.activeBookId, totalPages - 1, totalPages);
      m.flushProgress().then(() => {
        alert(window.i18n.t('viewer.read_completed'));
        toggleComicOverlay();
      });
    });
  }
}

// 글로벌 핸들러 노출에 사용될 함수 재내보내기 (Re-export)
window.openReader = openReader;
window.markAsCompleted = markAsCompleted;
window.toggleComicOverlay = toggleComicOverlay;
export { toggleComicOverlay, setComicFitMode, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, prevTxtPage, nextTxtPage };
