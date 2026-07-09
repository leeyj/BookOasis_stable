// viewer.js – 미디어 뷰어 라이프사이클 및 단축키 코어 조율기
import { state } from './state.js';
import { ComicViewer, initComicViewer, clearComicViewer, nextComicPage, prevComicPage, setComicFitMode, toggleComicOverlay, markAsCompleted as markComicAsCompleted, getComicReadingDirection, toggleComicReadingDirection, getComicPageStep, toggleComicPageStep, setComicPageStep, comicJumpToFirstPage, comicJumpToLastPage } from './viewer_comic.js';
import { TxtViewer, initTxtViewer, prevTxtPage, nextTxtPage, applyTxtSettings, txtJumpToFirstPage, txtJumpToLastPage } from './viewer_txt.js';
import { PdfViewer, initPdfViewer, nextPdfPage, prevPdfPage, clearPdfViewer, pdfJumpToFirstPage, pdfJumpToLastPage } from './viewer_pdf.js';

export let activeViewerInstance = null;

let epubModule = null;
async function getEpubModule() {
  if (!epubModule) {
    epubModule = await import(`./viewer_epub.js?v=${new Date().getTime()}`);
  }
  return epubModule;
}

export async function initEpubViewer(bookId, pagesRead, totalPages) {
  const m = await getEpubModule();
  m.initEpubViewer(bookId, pagesRead, totalPages);
}

export async function clearEpubViewer() {
  const m = await getEpubModule();
  m.clearEpubViewer();
}

export async function epubPrevPage() {
  const m = await getEpubModule();
  m.epubPrevPage();
}

export async function epubNextPage() {
  const m = await getEpubModule();
  m.epubNextPage();
}

export async function applyEpubSettings(options) {
  const m = await getEpubModule();
  m.applyEpubSettings(options);
}

export async function changeEpubScrollMode(scrollMode) {
  const m = await getEpubModule();
  m.changeEpubScrollMode(scrollMode);
}
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
          // 기존 기본 옵션만 남기고 초기화
          select.innerHTML = `
            <option value="batang">KoPub 바탕</option>
            <option value="gothic">나눔고딕</option>
            <option value="pretendard">Pretendard</option>
          `;
          data.fonts.forEach(font => {
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

// openReader: 포맷별 뷰어 디스패치 초기화
export function openReader(bookId, format, title, pagesRead, totalPages) {
  console.log(`[Viewer-Core] openReader 시작 - Book ID: ${bookId}, Format: ${format}, Title: ${title}`);
  
  // 다음권 조작 검증용 Arming 상태 초기화
  import('./viewer_next_episode.js').then(m => {
    if (m.clearNextEpisodeArm) {
      console.log('[Viewer-Core] Resetting next episode arming state for new reader session');
      m.clearNextEpisodeArm();
    }
  }).catch(() => {});

  state.activeBookId = bookId;
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;

  // Stacking Context(쌓임 맥락) 왜곡으로 인한 레이아웃 밀림 방지를 위해 body 바로 하위로 이동
  if (viewerModal.parentNode !== document.body) {
    document.body.appendChild(viewerModal);
  }

  viewerModal.style.display = 'flex';
  document.getElementById('viewer-title-text').textContent = title;

  // 뷰어 모달을 연 경우, 히스토리 스택에 #viewer 상태를 추가
  if (window.location.hash !== '#viewer') {
    history.pushState({ view: 'viewer', bookId, libraryId: state.currentLibraryId }, '', '#viewer');
  }

  // 브라우저 자체의 스크롤바 완전 격리 (이중 스크롤 방지)
  document.body.style.setProperty('overflow', 'hidden', 'important');
  document.documentElement.style.setProperty('overflow', 'hidden', 'important');

  // 새 만화 로드 시 오버레이 메뉴를 숨김 상태로 초기화
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (overlayMenu) overlayMenu.style.display = 'none';

  // 플로팅 닫기 버튼도 초기에는 숨김 처리 (오버레이가 닫힌 채 시작되므로)
  const floatingCloseBtn = document.querySelector('.floating-close-btn');
  if (floatingCloseBtn) floatingCloseBtn.style.display = 'none';

  // 모든 뷰어 영역 및 컨트롤 숨김
  document.querySelectorAll('.viewer-pane').forEach(p => p.style.display = 'none');
  document.getElementById('txt-controls').style.display = 'none';
  document.getElementById('comic-fit-controls').style.display = 'none';

  // 공용 오버레이 조작 패널 분기 제어
  const overlayComicFit = document.getElementById('overlay-comic-fit-group');
  const overlayTxtControls = document.getElementById('overlay-txt-controls-row');
  if (overlayComicFit) overlayComicFit.style.display = 'none';
  if (overlayTxtControls) overlayTxtControls.style.display = 'none';

  // 폰트 목록 갱신 및 UI 상태 동기화
  loadCustomFontsList();

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

  // 너비 슬라이더 행: 스크롤 모드일 때만 표시 (뷰어 열기 시 초기화)
  const widthRow = document.getElementById('overlay-width-row');
  if (widthRow) widthRow.classList.toggle('visible', scrollMode === 'scroll');

  // 저장된 스크롤 너비 복원 (CSS 변수 및 슬라이더 UI)
  const savedScrollWidth = parseInt(localStorage.getItem('comic_scroll_width'), 10) || 800;
  const widthSlider = document.getElementById('comic-scroll-width-slider');
  const widthLabel = document.getElementById('comic-scroll-width-label');
  if (widthSlider) widthSlider.value = savedScrollWidth;
  if (widthLabel) widthLabel.textContent = `${savedScrollWidth}px`;
  // CSS 변수는 comic-image-wrapper가 생성된 후 applyScrollWidth()에서 적용됨

  const fmt = format.toLowerCase();
  state.currentViewerFormat = fmt;

  // 기존 활성화된 뷰어가 있다면 명시적으로 정리(destroy)
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
      initViewerSeekBar();
    });
  } else if (fmt === 'txt') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_text') || '텍스트 보기';
    activeViewerInstance = TxtViewer;
    activeViewerInstance.init(bookId, pagesRead);
    initViewerSeekBar();
  } else if (fmt === 'pdf') {
    activeViewerInstance = PdfViewer;
    activeViewerInstance.init(bookId, pagesRead, totalPages);
    initViewerSeekBar();
  } else if (fmt === 'epub') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_epub') || 'EPUB 보기';
    getEpubModule().then(m => {
      activeViewerInstance = m.EpubViewer;
      activeViewerInstance.init(bookId, pagesRead, totalPages);
      initViewerSeekBar();
    });
  } else {
    alert(i18n.t('viewer.unsupported_format'));
    closeMediaViewer();
  }
  syncHotspotPointerEvents();
}

export function closeMediaViewer(triggerBack = true, isTransitioning = false) {
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;

  if (!isTransitioning) {
    viewerModal.classList.remove('fullscreen-mode');
    viewerModal.style.display = 'none';
    document.getElementById('fullscreen-icon').className = 'fa-solid fa-expand';
    // 브라우저 스크롤 및 iOS body-lock 스타일 완벽히 복원
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

  // 포맷별 정리 함수 위임 호출
  if (activeViewerInstance && typeof activeViewerInstance.destroy === 'function') {
    try {
      console.log(`[Viewer-Core] activeViewerInstance.destroy() 실행`);
      activeViewerInstance.destroy();
    } catch (e) {
      console.warn('[Viewer-Core] Error destroying viewer instance:', e);
    }
    activeViewerInstance = null;
  } else {
    clearComicViewer();
    clearEpubViewer();
    clearPdfViewer();
  }

  // 대기 중인 진척도 저장 예약 건 즉시 동기화(Flush) 및 메인 뷰 데이터 리로드
  import('./viewer_progress.js').then(m => {
    const flushPromise = m.flushProgress();
    if (m.resetPreloadState) m.resetPreloadState();

    const reloadData = () => {
      console.log("[Viewer-Core] DB Progress flush 완료. 화면 데이터 갱신을 실행합니다.");
      if (state.currentLibraryId === 'home') {
        import('./dashboard.js').then(d => d.loadDashboardData());
      } else if (state.currentLibraryId === 'history') {
        import('./book_list.js').then(b => b.loadReadingHistory());
      }

      // 도서 상세 화면이 노출되어 있는 경우 상세 영역도 실시간 리렌더링
      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') {
        const titleEl = detailView.querySelector('.book-detail-title');
        if (titleEl) {
          const seriesName = titleEl.textContent.replace(i18n.t('detail.edit_info'), '').trim();
          import('./modal.js').then(mod => {
            mod.openBookDetail(null, seriesName, state.currentLibraryId);
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

  // 수동 닫기 버튼을 누른 경우에만 브라우저 히스토리 스택 원상복구
  if (triggerBack && !isTransitioning && window.location.hash === '#viewer') {
    history.back();
  }
}

export function toggleFullscreenViewer() {
  const modal = document.getElementById('media-viewer-modal');
  const icon = document.getElementById('fullscreen-icon');
  const isFullscreen = modal.classList.contains('fullscreen-mode');
  if (isFullscreen) {
    modal.classList.remove('fullscreen-mode');
    icon.className = 'fa-solid fa-expand';
  } else {
    modal.classList.add('fullscreen-mode');
    icon.className = 'fa-solid fa-compress';
  }
}

// 이전 페이지 통합 조율
export function prevPage() {
  console.log('[Viewer-Core] prevPage() called');
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

let keyboardListenerInitialized = false;

export function initKeyboardListener() {
  if (keyboardListenerInitialized) return;
  keyboardListenerInitialized = true;
  document.addEventListener('keydown', e => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;
    switch (e.key) {
      case 'f':
      case 'F':
        e.preventDefault();
        toggleFullscreenViewer();
        break;
      case 'Escape':
        if (viewerModal.classList.contains('fullscreen-mode')) {
          toggleFullscreenViewer();
        } else {
          closeMediaViewer();
        }
        break;
      case 'ArrowRight':
      case ' ':
        e.preventDefault();
        nextPage();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        prevPage();
        break;
    }
  });

  // 마우스 휠 및 모바일 터치 스크롤 리스너 함께 초기화
  initWheelListener();
  initViewerClickToggle();
  syncHotspotPointerEvents();
}

let wheelLock = false;

// 마우스 휠 이벤트 리스너 통합 조율 (핫스팟으로 막힌 휠 복원 및 페이지 모드 연속 전환 차단)
export function initWheelListener() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (!hotspot) return;

  hotspot.addEventListener('contextmenu', e => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;

    const fmt = (state.currentViewerFormat || '').toLowerCase();
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (fmt === 'epub' && scrollMode === 'page') {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  hotspot.addEventListener('wheel', e => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;

    const isComic = document.getElementById('comic-viewer-container').style.display !== 'none';
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    const isComicScroll = isComic && scrollMode === 'scroll';
    const isComicWidth = isComic && document.querySelector('.comic-image-wrapper') && document.querySelector('.comic-image-wrapper').classList.contains('fit-width');
    const isTxt = document.getElementById('txt-viewer-container').style.display !== 'none';
    const isPdf = document.getElementById('pdf-viewer-container').style.display !== 'none';
    const isEpub = document.getElementById('epub-viewer-container').style.display !== 'none';

    // 1. 만화 뷰어 스크롤/웹툰 모드, 텍스트 뷰어 세로 스크롤 모드일 경우 -> 휠 스크롤 직접 위임 전달
    if (isComicScroll || isComicWidth || (isTxt && scrollMode === 'scroll')) {
      let targetScrollEl = null;
      if (isComicScroll || isComicWidth) {
        targetScrollEl = document.querySelector('.comic-image-wrapper');
      } else if (isTxt) {
        targetScrollEl = document.getElementById('txt-scroll-wrapper');
      }

      if (targetScrollEl) {
        targetScrollEl.scrollBy({
          top: e.deltaY,
          behavior: 'auto'
        });
        e.preventDefault();
        return;
      }
    }

    // 2. EPUB 세로 스크롤 모드일 경우 -> 내부 iframe으로 휠 스크롤 전파
    if (isEpub && scrollMode === 'scroll') {
      const iframe = document.querySelector('#epub-render-area iframe');
      if (iframe && iframe.contentWindow) {
        iframe.contentWindow.scrollBy(0, e.deltaY);
        e.preventDefault();
        return;
      }
    }

    // 3. 페이지 전환 모드 (만화 height 맞춤, TXT 가로 페이지, EPUB 가로 페이지 등)
    if (scrollMode === 'page' || (isComic && !isComicWidth) || isPdf || isTxt || isEpub) {
      e.preventDefault();
      if (wheelLock) return;

      if (e.deltaY > 30) {
        wheelLock = true;
        nextPage();
        setTimeout(() => { wheelLock = false; }, 600);
      } else if (e.deltaY < -30) {
        wheelLock = true;
        prevPage();
        setTimeout(() => { wheelLock = false; }, 600);
      }
    }
  }, { passive: false });
}

// 공통 환경 설정 트리거 함수
export function changeFontSize(dir) {
  updateFontSize(dir);
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
}

export function toggleReaderTheme() {
  toggleTheme();
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
  if (activeViewerInstance && typeof activeViewerInstance.applySettings === 'function') {
    activeViewerInstance.applySettings();
  } else {
    applyTxtSettings();
    applyEpubSettings();
  }
};

window.setScrollMode = function (mode) {
  console.log(`[Viewer-Core] Scroll mode changed to: ${mode}`);
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

  applyTxtSettings();
  changeEpubScrollMode(mode);
  syncHotspotPointerEvents();
};

// ==========================================
// 시크바 통합 이벤트 라우터
// ==========================================
let _viewerSeekbarInited = false;

function initViewerSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  if (!slider) return;

  if (_viewerSeekbarInited) return;
  _viewerSeekbarInited = true;

  slider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;

    if (fmt === 'zip' || fmt === 'cbz') {
      import('./viewer_comic.js').then(m => {
        const fn = m.comicSliderInput || m.comicSliderInput || (window && window.comicSliderInput);
        if (typeof fn === 'function') fn(slider, val); else console.warn('[Viewer-Core] comicSliderInput not available');
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_comic:', err));
    } else if (fmt === 'epub') {
      import('./viewer_epub.js').then(m => {
        const fn = m.epubSliderInput || (window && window.epubSliderInput);
        if (typeof fn === 'function') fn(slider, val); else console.warn('[Viewer-Core] epubSliderInput not available');
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_epub:', err));
    } else if (fmt === 'txt') {
      import('./viewer_txt.js').then(m => {
        const fn = m.txtSliderInput;
        if (typeof fn === 'function') fn(slider, val);
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_txt:', err));
    } else if (fmt === 'pdf') {
      const tooltip = document.getElementById('seekbar-tooltip');
      if (tooltip) {
        tooltip.textContent = val;
        tooltip.style.display = 'block';
      }
      const pageInfo = document.getElementById('comic-overlay-page-info');
      if (pageInfo) {
        pageInfo.textContent = `${val} / ${slider.max}`;
      }
    }
  });

  slider.addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;

    if (fmt === 'zip' || fmt === 'cbz') {
      import('./viewer_comic.js').then(m => {
        const fn = m.comicSliderChange || (window && window.comicSliderChange);
        if (typeof fn === 'function') fn(slider, val); else console.warn('[Viewer-Core] comicSliderChange not available');
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_comic:', err));
    } else if (fmt === 'epub') {
      import('./viewer_epub.js').then(m => {
        const fn = m.epubSliderChange || (window && window.epubSliderChange);
        if (typeof fn === 'function') fn(slider, val); else console.warn('[Viewer-Core] epubSliderChange not available');
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_epub:', err));
    } else if (fmt === 'txt') {
      import('./viewer_txt.js').then(m => {
        const fn = m.txtSliderChange;
        if (typeof fn === 'function') fn(slider, val);
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_txt:', err));
    } else if (fmt === 'pdf') {
      import('./viewer_pdf.js').then(m => {
        if (typeof m.pdfJumpToPage === 'function') {
          m.pdfJumpToPage(val);
        }
      }).catch(err => console.warn('[Viewer-Core] Failed to import viewer_pdf:', err));
    }
  });
}

export function viewerJumpToFirst() {
  const fmt = state.currentViewerFormat;
  if (fmt === 'zip' || fmt === 'cbz') {
    if (typeof comicJumpToFirstPage === 'function') comicJumpToFirstPage();
  } else if (fmt === 'epub') {
    getEpubModule().then(m => m.epubJumpToFirstPage());
  } else if (fmt === 'pdf') {
    if (typeof pdfJumpToFirstPage === 'function') pdfJumpToFirstPage();
  } else if (fmt === 'txt') {
    if (typeof txtJumpToFirstPage === 'function') txtJumpToFirstPage();
  }
  toggleComicOverlay();
}

export function viewerJumpToLast() {
  const fmt = state.currentViewerFormat;
  if (fmt === 'zip' || fmt === 'cbz') {
    if (typeof comicJumpToLastPage === 'function') comicJumpToLastPage();
  } else if (fmt === 'epub') {
    getEpubModule().then(m => m.epubJumpToLastPage());
  } else if (fmt === 'pdf') {
    if (typeof pdfJumpToLastPage === 'function') pdfJumpToLastPage();
  } else if (fmt === 'txt') {
    if (typeof txtJumpToLastPage === 'function') txtJumpToLastPage();
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

// 모바일 해상도(window.innerWidth <= 1200)이면서 만화/텍스트 스크롤 모드인 경우 핫스팟 레이어 감춤 처리하여 브라우저 순정 터치 스크롤 허용 (특히 iOS Safari 대응)
export function syncHotspotPointerEvents() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!hotspot || !viewerModal) {
    console.warn('[syncHotspotPointerEvents] hotspot 또는 viewerModal이 존재하지 않습니다.');
    return;
  }

  // 뷰어 모달이 실제로 열려 있는 상태가 아니라면 바디 스크롤을 건드리지 않고 즉각 탈출
  if (viewerModal.style.display !== 'flex') {
    console.log('[syncHotspotPointerEvents] 뷰어 모달이 flex 상태가 아님. 생략.');
    return;
  }

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const fmt = (state.currentViewerFormat || '').toLowerCase();
  const isComic = (fmt === 'zip' || fmt === 'cbz');
  const isTxt = (fmt === 'txt');
  const isPdf = (fmt === 'pdf');
  const isEpub = (fmt === 'epub');

  const isScrollActive = scrollMode === 'scroll' && (isComic || isTxt || isEpub);

  console.log(`[syncHotspotPointerEvents] format=${fmt}, scrollMode=${scrollMode}, isScrollActive=${isScrollActive}, isEpub=${isEpub}`);

  if (viewerModal) {
    // [이중 스크롤바 해결] EPUB의 경우 바디 스크롤은 hidden으로 잠가 이중 스크롤바의 생성을 방지합니다.
    if (isEpub) {
      viewerModal.classList.remove('scroll-mode-active');
      document.body.style.overflow = 'hidden';
    } else {
      viewerModal.classList.toggle('scroll-mode-active', isScrollActive);
      // iOS Safari 대응: 세로 스크롤 모드일 때는 body의 overflow: hidden을 풀어주어야 터치 스크롤 버블링이 락 걸리지 않음
      if (isScrollActive) {
        document.body.style.overflow = 'auto';
      } else {
        document.body.style.overflow = 'hidden';
      }
    }
  }

  // EPUB은 scroll 모드에서만 iframe 내부 네이티브 스크롤을 위해 핫스팟을 숨기고,
  // page 모드에서는 핫스팟(30/40/30)을 사용해 안정적인 클릭 네비게이션을 보장합니다.
  // 또한 만화/TXT/PDF 등 모든 포맷에서 세로 스크롤 모드가 켜진 경우에는 휠/네이티브 스크롤 보증을 위해 핫스팟을 숨깁니다.
  const shouldHideHotspot = (isEpub && scrollMode === 'scroll') || isScrollActive;

  if (shouldHideHotspot) {
    hotspot.style.display = 'none';
    console.log('[syncHotspotPointerEvents] 핫스팟 비활성화(none) 적용됨.');
  } else {
    hotspot.style.display = 'flex';
    console.log('[syncHotspotPointerEvents] 핫스팟 활성화(flex) 적용됨.');
  }
}

// 핫스팟 포인터 이벤트가 비활성화(none)되었을 때 오버레이를 켜고 끌 수 있도록 백그라운드 클릭 이벤트 중계
let _viewerClickToggleInited = false;
export function initViewerClickToggle() {
  const viewerBody = document.getElementById('viewer-body-container');
  if (!viewerBody || _viewerClickToggleInited) return;
  _viewerClickToggleInited = true;

  // ── 터치 탭 감지 (document 레벨) ─────────────────────────────────────────
  // body.overflow = 'auto' 상태(스크롤 모드)에서 iOS Safari는 viewerBody의
  // touch 이벤트를 body 스크롤로 소비해버려 viewerBody 리스너가 발화되지 않는다.
  // document 레벨에 리스너를 달아 이 문제를 우회한다.
  //
  // 스크롤 vs 탭 구분:
  //   touchstart → touchend 사이 이동 거리가 TAP_THRESHOLD(10px) 이하 = 탭
  //   탭 판정 시 touchend에서 직접 오버레이 토글 → click 이벤트 의존 제거
  const TAP_THRESHOLD = 10;
  let _touchStartX = null;
  let _touchStartY = null;
  let _touchStartClientX = null; // 오버레이 위치 계산용

  document.addEventListener('touchstart', e => {
    if (e.touches.length === 1) {
      _touchStartX = e.touches[0].clientX;
      _touchStartY = e.touches[0].clientY;
      _touchStartClientX = e.touches[0].clientX;
    }
  }, { passive: true });

  document.addEventListener('touchmove', e => {
    if (_touchStartX === null) return;
    const dx = Math.abs(e.touches[0].clientX - _touchStartX);
    const dy = Math.abs(e.touches[0].clientY - _touchStartY);
    if (dx > TAP_THRESHOLD || dy > TAP_THRESHOLD) {
      // 스크롤로 판정 → 시작 좌표 무효화하여 touchend에서 탭 처리 안 함
      _touchStartX = null;
      _touchStartY = null;
    }
  }, { passive: true });

  // 마우스(데스크톱) click 이벤트는 별도로 유지 (touch 환경에서는 중복 방지 필요 없음 — touchend가 먼저 처리)
  let _lastTouchEndTime = 0;
  
  // touchend 이벤트 리스너의 끝부분을 수정하여 _lastTouchEndTime 기록
  const originalTouchEnd = document.addEventListener('touchend', e => {
    if (_touchStartX === null) return; // 스크롤로 판정된 경우 무시

    const endX = _touchStartClientX;
    _touchStartX = null;
    _touchStartY = null;
    _touchStartClientX = null;

    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode !== 'scroll') return; // 스크롤 모드에서만 처리

    // 오버레이/컨트롤/버튼 등 인터랙티브 요소 탭이면 무시
    const target = e.target || document.elementFromPoint(endX, window.innerHeight / 2);
    if (!target) return;
    if (target.closest('#comic-overlay-menu') ||
      target.closest('.viewer-controls') ||
      target.closest('.floating-close-btn') ||
      target.closest('#common-viewer-hotspot') ||
      target.closest('button') ||
      target.closest('input') ||
      target.closest('select')) {
      return;
    }

    // 뷰어 모달이 열려있는 상태인지 확인
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;

    const width = window.innerWidth;
    console.log(`[Viewer-Touch-Toggle] touchend tap: endX=${endX}, width=${width}, ratio=${endX / width}`);

    // 화면 가로폭 기준 30% ~ 70% 사이의 중앙 영역 탭 시에만 오버레이 토글
    if (endX >= width * 0.3 && endX <= width * 0.7) {
      console.log('[Viewer-Touch-Toggle] Triggering toggleComicOverlay() from touchend');
      _lastTouchEndTime = Date.now(); // 터치 토글 시간 기록
      toggleComicOverlay();
    }
  }, { passive: true });

  viewerBody.addEventListener('click', e => {
    // 터치 디바이스에서는 touchend가 이미 처리하므로 click 이벤트는 건너뜀
    if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;
    // PointerEvent로 터치 유입 감지 (일부 브라우저 대응)
    if (e.pointerType === 'touch') return;
    // iOS Safari 대응: 최근 500ms 이내에 touchend로 토글이 일어난 경우 click 무시
    if (Date.now() - _lastTouchEndTime < 500) return;

    console.log('[Viewer-Click-Toggle] Mouse click detected. Target:', e.target);

    if (e.target.closest('#comic-overlay-menu') ||
      e.target.closest('.viewer-controls') ||
      e.target.closest('.floating-close-btn') ||
      e.target.closest('#common-viewer-hotspot') ||
      e.target.closest('button') ||
      e.target.closest('input') ||
      e.target.closest('select')) {
      return;
    }

    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode === 'scroll') {
      const clickX = e.clientX;
      const width = window.innerWidth;
      if (clickX >= width * 0.3 && clickX <= width * 0.7) {
        console.log('[Viewer-Click-Toggle] Triggering toggleComicOverlay() from mouse click');
        toggleComicOverlay();
      }
    }
  });
}



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
export { toggleComicOverlay, setComicFitMode, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, prevTxtPage, nextTxtPage, initViewerSeekBar };
