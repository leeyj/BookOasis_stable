// viewer_pdf.js – PDF 뷰어 로직
import { state } from './state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { getComicPageStep, getComicReadingDirection } from './viewer_comic.js';

export let pdfDoc = null;
export let pdfCurrentPage = 1;
export let pdfTotalPages = 0;
let currentRenderTasks = [];

export async function initPdfViewer(bookId, pagesRead, totalPages) {
  console.log(`[Viewer-Pdf] initPdfViewer - PDF 렌더링 요청: bookId=${bookId}, pagesRead=${pagesRead}, totalPages=${totalPages}`);
  document.getElementById('pdf-viewer-container').style.display = 'flex';
  pdfCurrentPage = pagesRead > 0 ? pagesRead : 1;
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
    disableStream: false     // 스트림 단위로 조각 수신 허용
  }).promise
    .then(doc => { 
      pdfDoc = doc; 
      pdfTotalPages = doc.numPages; 
      hideViewerLoading();
      renderPdfPage(); 
    })
    .catch(err => { 
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

  // 리더 설정으로부터 보기 모드(1장/2장)와 정렬 방향(LTR/RTL) 획득
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

  // 가용 가능한 최적의 가로/세로 뷰포트 크기 측정
  const container = document.getElementById('pdf-render-area') || document.getElementById('pdf-viewer-container');
  const bodyContainer = document.getElementById('viewer-body-container');
  const containerWidth = Math.max(container.clientWidth || 0, (bodyContainer ? bodyContainer.clientWidth : 0) || 0, window.innerWidth || 0);
  const containerHeight = Math.max(container.clientHeight || 0, (bodyContainer ? bodyContainer.clientHeight : 0) || 0, window.innerHeight || 0);

  // 2장 보기 상태인 경우 개별 가용 가로 길이를 절반으로 배분
  const availableWidth = pagesToRender.length === 2 ? (containerWidth - 60) / 2 : (containerWidth - 40);
  const availableHeight = containerHeight - 40;

  // 페이지 배열 순회하며 캔버스 생성 및 순차 비동기 렌더링 개시
  pagesToRender.forEach(pageNum => {
    const canvas = document.createElement('canvas');
    canvas.className = 'pdf-canvas-element';
    canvas.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
    canvas.style.display = 'block';
    renderArea.appendChild(canvas);

    pdfDoc.getPage(pageNum).then(page => {
      const ctx = canvas.getContext('2d');
      const unscaledViewport = page.getViewport({ scale: 1.0 });

      const scaleX = availableWidth / unscaledViewport.width;
      const scaleY = availableHeight / unscaledViewport.height;
      const scale = Math.min(scaleX, scaleY);

      // DPR 오버샘플링 적용 (Retina 및 고해상도 모니터 대응, 최소 1.5배 보장)
      const dpr = Math.max(window.devicePixelRatio || 1, 1.5);
      const viewport = page.getViewport({ scale: scale * dpr });
      
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / dpr}px`;
      canvas.style.height = `${viewport.height / dpr}px`;

      const renderCtx = { canvasContext: ctx, viewport };
      const renderTask = page.render(renderCtx);
      currentRenderTasks.push(renderTask);

      renderTask.promise.then(() => {
        // 태스크 목록에서 완료된 것 자원 정리
        currentRenderTasks = currentRenderTasks.filter(t => t !== renderTask);
      }).catch(err => {
        if (err.name !== 'RenderingCancelledException' && err.name !== 'RenderingCancelled') {
          console.error(`[Viewer-Pdf] Page ${pageNum} rendering error:`, err);
        }
      });
    });
  });

  // 하단 페이지 바 레이블 및 시크바 동기화 처리
  const pageText = `${pdfCurrentPage} / ${pdfTotalPages}`;
  const pdfInfo = document.getElementById('pdf-page-info');
  if (pdfInfo) pdfInfo.textContent = pageText;
  const overlayInfo = document.getElementById('comic-overlay-page-info');
  if (overlayInfo) overlayInfo.textContent = pageText;

  // 공통 시크바 슬라이더 동기화
  const slider = document.getElementById('viewer-page-slider');
  if (slider) {
    slider.max = pdfTotalPages;
    slider.value = pdfCurrentPage;
    const startLbl = document.getElementById('seekbar-start-label');
    const endLbl = document.getElementById('seekbar-end-label');
    if (startLbl) startLbl.textContent = '1';
    if (endLbl) endLbl.textContent = String(pdfTotalPages);
  }

  // 진척도 저장 연동
  saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
}

export function nextPdfPage() {
  const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
  if (pdfCurrentPage < pdfTotalPages) {
    pdfCurrentPage = Math.min(pdfCurrentPage + step, pdfTotalPages);
    renderPdfPage();
  } else {
    import('./viewer_next_episode.js').then(m => {
      m.handleNextEpisodeDirect(state.activeBookId);
    });
  }
}

export function prevPdfPage() {
  const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
  if (pdfCurrentPage > 1) {
    pdfCurrentPage = Math.max(pdfCurrentPage - step, 1);
    renderPdfPage();
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

export const PdfViewer = {
  async init(bookId, pagesRead, totalPages) {
    return initPdfViewer(bookId, pagesRead, totalPages);
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
