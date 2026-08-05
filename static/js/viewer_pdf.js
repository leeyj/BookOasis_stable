// viewer_pdf.js – PDF 뷰어 로직
import { state } from './state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { getComicPageStep, getComicReadingDirection } from './viewer_comic.js';

export let pdfDoc = null;
export let pdfCurrentPage = 1;
export let pdfTotalPages = 0;
let isInitializingPdfProgress = false;
let currentRenderTasks = [];

export async function initPdfViewer(bookId, pagesRead, totalPages) {
  isInitializingPdfProgress = true;
  console.log(`[Viewer-Pdf] initPdfViewer - PDF 렌더링 요청: bookId=${bookId}, pagesRead=${pagesRead}, totalPages=${totalPages}`);
  
  document.getElementById('pdf-viewer-container').style.display = 'flex';

  let initialPage = pagesRead > 0 ? Math.max(1, parseInt(pagesRead, 10) || 1) : 1;

  // 크로스 디바이스(모바일-PC) 동기화: 서버 최신 진행도(progress-state)를 비동기 조회하여 최신 위치 복원
  try {
    const libType = state.currentLibraryType || 'general';
    const stateRes = await fetch(`/api/media/progress-state?db_type=${libType}&book_id=${bookId}`);
    if (stateRes.ok) {
      const stateData = await stateRes.json();
      if (stateData && stateData.success && stateData.state && typeof stateData.state.pages_read === 'number' && stateData.state.pages_read > 0) {
        initialPage = stateData.state.pages_read;
        console.log(`[Viewer-Pdf] Server progress-state fetched: page ${initialPage} (local fallback: ${pagesRead})`);
      }
    }
  } catch (err) {
    console.warn('[Viewer-Pdf] Failed to fetch server progress-state:', err);
  }

  pdfCurrentPage = initialPage;
  pdfTotalPages = totalPages || 0;
  
  // 뷰어 진입 시 totalPages가 0이면 백엔드 API를 통해 동적 계산 시도 (DB 동기화용)
  if (pdfTotalPages === 0) {
    try {
      showViewerLoading('페이지 정보 동기화 중...');
      const libType = state.currentLibraryType || 'general';
      const res = await fetch(`/api/media/books/${bookId}/info?type=${libType}`);
      const data = await res.json();
      if (data.success && data.total_pages > 0) {
        pdfTotalPages = data.total_pages;
      }
    } catch (e) {
      console.warn('[Viewer-Pdf] 동적 페이지 로딩 실패:', e);
    }
  }

  showViewerLoading(i18n.t("viewer.loading_pdf_title") || "PDF 준비 중", i18n.t("viewer.loading_pdf_sub") || "잠시만 기다려 주세요...");
  
  const url = `/api/media/pdf?db_type=${state.currentLibraryType}&book_id=${bookId}`;
  pdfjsLib.getDocument({
    url: url,
    disableAutoFetch: true,  // 브라우저가 전체 파일을 백그라운드에서 전부 받는 행위 억제
    disableStream: false,    // 스트림 단위로 조각 수신 허용
    cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@2.16.105/cmaps/',
    cMapPacked: true
  }).promise
    .then(doc => { 
      pdfDoc = doc; 
      pdfTotalPages = doc.numPages; 
      hideViewerLoading();
      renderPdfPage(); 
      isInitializingPdfProgress = false;
    })
    .catch(err => { 
      isInitializingPdfProgress = false;
      hideViewerLoading();
      showViewerError(i18n.t("viewer.error_pdf_title"), err.message);
    });
}

// 2장 보기 상태 전환을 실시간 적용하기 위해 글로벌 바인딩 지원
window.applyPdfFitMode = function() {
  renderPdfPage();
};

export function renderPdfPage() {
  if (!pdfDoc) return;

  // 기존 진행 중인 모든 렌더링 태스크 강제 취소
  currentRenderTasks.forEach(task => {
    if (task) {
      try { task.cancel(); } catch (e) {}
    }
  });
  currentRenderTasks = [];

  const renderArea = document.getElementById('pdf-render-area');
  if (!renderArea) return;
  renderArea.innerHTML = ''; // 캔버스 영역 소거

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'scroll') {
    // ── 1. 연속 세로 스크롤 모드 (Continuous Vertical Scroll) ──
    renderArea.style.overflowY = 'auto';
    renderArea.style.overflowX = 'hidden';
    renderArea.style.flexDirection = 'column';
    renderArea.style.justifyContent = 'flex-start';
    renderArea.style.alignItems = 'center';
    renderArea.style.height = '100%';
    renderArea.style.width = '100%';
    renderArea.style.padding = '20px 10px';
    renderArea.style.gap = '20px';

    const areaRect = renderArea.getBoundingClientRect();
    const storedWidth = parseInt(localStorage.getItem('comic_scroll_width') || '800', 10);
    const availableWidth = Math.max(300, Math.min(areaRect.width - 20, storedWidth));

    // 전체 페이지에 대한 Canvas 요소를 세로로 배열
    for (let pageNum = 1; pageNum <= pdfTotalPages; pageNum++) {
      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-canvas-element pdf-scroll-page';
      canvas.dataset.pageNum = pageNum;
      canvas.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
      canvas.style.display = 'block';
      canvas.style.marginBottom = '20px';
      renderArea.appendChild(canvas);

      renderSinglePdfCanvas(pageNum, canvas, availableWidth, null);
    }

    // 스크롤 시 현재 보는 페이지 탐지 및 진행도 자동 반영
    if (!renderArea._pdfScrollBound) {
      renderArea._pdfScrollBound = true;
      let scrollTimer = null;
      renderArea.addEventListener('scroll', () => {
        if (scrollTimer) clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
          if (!pdfDoc || pdfTotalPages <= 0) return;
          const canvases = renderArea.querySelectorAll('.pdf-scroll-page');
          const areaTop = renderArea.getBoundingClientRect().top;
          let activePage = pdfCurrentPage;

          for (let i = 0; i < canvases.length; i++) {
            const rect = canvases[i].getBoundingClientRect();
            if (rect.top - areaTop <= renderArea.clientHeight / 2 && rect.bottom - areaTop >= 50) {
              activePage = parseInt(canvases[i].dataset.pageNum, 10) || activePage;
            }
          }

          if (activePage !== pdfCurrentPage) {
            pdfCurrentPage = activePage;
            updatePdfPageInfo();
            if (state.activeBookId && pdfTotalPages > 0) {
              saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
            }
          }
        }, 80);
      });
    }

    // 초기 활성 페이지로 스크롤 위치 이동
    requestAnimationFrame(() => {
      const targetCvs = renderArea.querySelector(`.pdf-scroll-page[data-page-num="${pdfCurrentPage}"]`);
      if (targetCvs) {
        targetCvs.scrollIntoView({ block: 'start' });
      }
    });

  } else {
    // ── 2. 페이지 넘김 모드 (1장/2장 화면 맞춤) ──
    renderArea.style.overflow = 'hidden';
    renderArea.style.flexDirection = 'row';
    renderArea.style.justifyContent = 'center';
    renderArea.style.alignItems = 'center';
    renderArea.style.height = '100%';
    renderArea.style.width = '100%';
    renderArea.style.padding = '10px';

    const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
    const direction = (typeof getComicReadingDirection === 'function') ? getComicReadingDirection() : 'ltr';

    let pagesToRender = [];
    if (step === 2) {
      let p1 = pdfCurrentPage;
      let p2 = pdfCurrentPage + 1;
      if (p2 <= pdfTotalPages) {
        if (direction === 'rtl') {
          pagesToRender = [p2, p1];
        } else {
          pagesToRender = [p1, p2];
        }
      } else {
        pagesToRender = [p1];
      }
    } else {
      pagesToRender = [pdfCurrentPage];
    }

    const removeCenterGap = (localStorage.getItem('remove_2page_center_gap') === '1');
    if (removeCenterGap) {
      renderArea.style.gap = '0px';
    } else {
      renderArea.style.gap = '10px';
    }

    const areaRect = renderArea.getBoundingClientRect();
    const areaStyle = window.getComputedStyle(renderArea);
    const padLeft = parseFloat(areaStyle.paddingLeft || '0') || 0;
    const padRight = parseFloat(areaStyle.paddingRight || '0') || 0;
    const padTop = parseFloat(areaStyle.paddingTop || '0') || 0;
    const padBottom = parseFloat(areaStyle.paddingBottom || '0') || 0;
    const gapPx = pagesToRender.length === 2 ? (parseFloat(areaStyle.columnGap || areaStyle.gap || '0') || 0) : 0;

    const innerWidth = Math.max(1, areaRect.width - padLeft - padRight);
    const innerHeight = Math.max(1, areaRect.height - padTop - padBottom);

    const availableWidth = pagesToRender.length === 2
      ? Math.max(1, (innerWidth - gapPx) / 2)
      : innerWidth;
    const availableHeight = innerHeight;

    pagesToRender.forEach(pageNum => {
      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-canvas-element';
      if (removeCenterGap) {
        canvas.style.boxShadow = 'none';
      } else {
        canvas.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
      }
      canvas.style.display = 'block';
      renderArea.appendChild(canvas);

      renderSinglePdfCanvas(pageNum, canvas, availableWidth, availableHeight);
    });
  }

  updatePdfPageInfo();

  if (!isInitializingPdfProgress && state.activeBookId && pdfTotalPages > 0) {
    saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
  }
}

// 개별 PDF 페이지 캔버스 렌더링 헬퍼
function renderSinglePdfCanvas(pageNum, canvas, availWidth, availHeight) {
  pdfDoc.getPage(pageNum).then(page => {
    const ctx = canvas.getContext('2d');
    const unscaledViewport = page.getViewport({ scale: 1.0 });

    let scale;
    if (availHeight && availHeight > 0) {
      const scaleX = availWidth / unscaledViewport.width;
      const scaleY = availHeight / unscaledViewport.height;
      scale = Math.min(scaleX, scaleY);
    } else {
      scale = availWidth / unscaledViewport.width;
    }

    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const rawDpr = window.devicePixelRatio || 1;
    const dpr = Math.min(isMobile ? 2.5 : 4.0, Math.max(rawDpr * 2.0, isMobile ? 2.0 : 3.0));
    const viewport = page.getViewport({ scale: scale * dpr });
    
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width / dpr}px`;
    canvas.style.height = `${viewport.height / dpr}px`;
    canvas.style.flex = '0 0 auto';

    if (ctx) {
      ctx.imageSmoothingEnabled = true;
      if (typeof ctx.imageSmoothingQuality !== 'undefined') {
        ctx.imageSmoothingQuality = 'high';
      }
    }

    const renderCtx = { canvasContext: ctx, viewport };
    const renderTask = page.render(renderCtx);
    currentRenderTasks.push(renderTask);

    renderTask.promise.then(() => {
      currentRenderTasks = currentRenderTasks.filter(t => t !== renderTask);
    }).catch(err => {
      if (err.name !== 'RenderingCancelledException' && err.name !== 'RenderingCancelled') {
        console.error(`[Viewer-Pdf] Page ${pageNum} rendering error:`, err);
      }
    });
  }).catch(err => {
    console.error(`[Viewer-Pdf] getPage failed for page ${pageNum}:`, err);
  });
}

export function updatePdfPageInfo() {
  const pageInfoEl = document.getElementById('pdf-page-info');
  if (pageInfoEl) {
    pageInfoEl.textContent = `${pdfCurrentPage} / ${pdfTotalPages}`;
  }

  const overlayInfoEl = document.getElementById('comic-overlay-page-info');
  if (overlayInfoEl) {
    overlayInfoEl.textContent = `${pdfCurrentPage} / ${pdfTotalPages}`;
  }

  const slider = document.getElementById('viewer-page-slider');
  if (slider) {
    slider.max = pdfTotalPages || 1;
    slider.value = pdfCurrentPage;
  }
  const endLabel = document.getElementById('seekbar-end-label');
  if (endLabel) {
    endLabel.textContent = pdfTotalPages || '?';
  }

  const overlayTitleEl = document.getElementById('overlay-title-text');
  if (overlayTitleEl) {
    overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;
  }
}

export function prevPdfPage() {
  if (pdfDoc && pdfCurrentPage > 1) {
    const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
    pdfCurrentPage = Math.max(1, pdfCurrentPage - step);
    renderPdfPage();
    saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
  }
}

export function nextPdfPage() {
  if (pdfDoc) {
    if (pdfCurrentPage < pdfTotalPages) {
      const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
      pdfCurrentPage = Math.min(pdfTotalPages, pdfCurrentPage + step);
      renderPdfPage();
      saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
    } else {
      import('./viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    }
  }
}

export function clearPdfViewer() {
  currentRenderTasks.forEach(task => {
    if (task) {
      try { task.cancel(); } catch (e) {}
    }
  });
  currentRenderTasks = [];
  pdfDoc = null;
}

export function pdfJumpToFirstPage() {
  if (pdfDoc && pdfCurrentPage !== 1) {
    pdfCurrentPage = 1;
    renderPdfPage();
  }
}

export function pdfJumpToLastPage() {
  if (pdfDoc && pdfCurrentPage !== pdfTotalPages) {
    pdfCurrentPage = pdfTotalPages;
    renderPdfPage();
  }
}

export function pdfJumpToPage(pageNum) {
  if (pdfDoc) {
    const targetPage = Math.max(1, Math.min(pdfTotalPages, pageNum));
    if (pdfCurrentPage !== targetPage) {
      pdfCurrentPage = targetPage;
      renderPdfPage();
    }
  }
}

export function pdfSliderChange(slider, val) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) tooltip.style.display = 'none';
  pdfJumpToPage(val);
}

export const PdfViewer = {
  async init(bookId, pagesRead, totalPages) {
    return initPdfViewer(bookId, pagesRead, totalPages);
  },
  prepareForClose() {
    if (!state.activeBookId || !pdfDoc || !pdfTotalPages || pdfTotalPages <= 0) return;
    saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
  },
  destroy() {
    clearPdfViewer();
    const renderArea = document.getElementById('pdf-render-area');
    if (renderArea) renderArea.innerHTML = '';
    const pane = document.getElementById('pdf-viewer-container');
    if (pane) pane.style.display = 'none';
  },
  prevPage() {
    prevPdfPage();
  },
  nextPage() {
    nextPdfPage();
  },
  jumpTo(target) {
    if (target === 'first') {
      pdfJumpToFirstPage();
    } else if (target === 'last') {
      pdfJumpToLastPage();
    }
  },
  applySettings(options) {
    if (typeof window.applyPdfFitMode === 'function') {
      window.applyPdfFitMode();
    }
  }
};
