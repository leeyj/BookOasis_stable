// viewer_pdf.js – PDF 뷰어 로직
import { state } from './state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

export let pdfDoc = null;
export let pdfCurrentPage = 1;
export let pdfTotalPages = 0;
let currentRenderTask = null;

export function initPdfViewer(bookId, pagesRead) {
  console.log(`[Viewer-Pdf] initPdfViewer - PDF 렌더링 요청: bookId=${bookId}, pagesRead=${pagesRead}`);
  document.getElementById('pdf-viewer-container').style.display = 'flex';
  pdfCurrentPage = pagesRead > 0 ? pagesRead : 1;
  
  showViewerLoading("PDF 로드 중...", "PDF 도서 파일을 읽어오고 있습니다.<br>잠시만 기다려 주세요.");
  
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
      showViewerError("PDF 로드 실패", err.message);
    });
}

export function renderPdfPage() {
  if (!pdfDoc) return;

  // 기존에 진행 중인 드로잉 작업이 있다면 취소하여 페이지 연타 시 씹힘 방지
  if (currentRenderTask) {
    currentRenderTask.cancel();
    currentRenderTask = null;
  }

  pdfDoc.getPage(pdfCurrentPage).then(page => {
    const canvas = document.getElementById('pdf-canvas');
    const ctx = canvas.getContext('2d');
    
    // 렌더링 영역 크기 기반 가변 스케일 계산 (마진 40px 차감)
    const container = document.getElementById('pdf-render-area') || document.getElementById('pdf-viewer-container');
    
    // 모달이 막 열린 시점이거나 display:none 해제 직후에 clientWidth/clientHeight가 0으로 반환되는 경우가 있으므로,
    // window 창 크기 및 뷰어 바디 컨테이너 크기를 병렬 비교하여 실질적인 측정값을 도출함.
    const bodyContainer = document.getElementById('viewer-body-container');
    const containerWidth = Math.max(container.clientWidth || 0, (bodyContainer ? bodyContainer.clientWidth : 0) || 0, window.innerWidth || 0);
    const containerHeight = Math.max(container.clientHeight || 0, (bodyContainer ? bodyContainer.clientHeight : 0) || 0, window.innerHeight || 0);

    const unscaledViewport = page.getViewport({ scale: 1.0 });
    
    // PDF 상하단 네비바 및 헤더 컨트롤 영역(약 120px)과 캔버스 여백(Margin)을 반영하여
    // 스크롤바가 생기지 않는 완벽한 뷰포트 크기를 계산함
    const scaleX = (containerWidth - 40) / unscaledViewport.width;
    const scaleY = (containerHeight - 120) / unscaledViewport.height;
    const scale = Math.min(scaleX, scaleY); // 화면 비율 내에 온전히 안착하도록 최소 비율 선택

    const viewport = page.getViewport({ scale: scale });
    canvas.height = viewport.height;
    canvas.width = viewport.width;

    const renderCtx = { canvasContext: ctx, viewport };
    
    currentRenderTask = page.render(renderCtx);
    currentRenderTask.promise.then(() => {
      currentRenderTask = null;
      const pageText = `${pdfCurrentPage} / ${pdfTotalPages}`;
      document.getElementById('pdf-page-info').textContent = pageText;
      const overlayInfo = document.getElementById('comic-overlay-page-info');
      if (overlayInfo) overlayInfo.textContent = pageText;

      // 공통 진척도 저장 연동 (0-indexed를 위해 pdfCurrentPage - 1 전달)
      saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
    }).catch(err => {
      // 렌더 태스크 취소 시 발생하는 에러는 정상적인 동작이므로 로그만 남기고 차단
      if (err.name === 'RenderingCancelledException' || err.name === 'RenderingCancelled') {
        console.log(`[Viewer-Pdf] 이전 페이지 렌더링 취소 완료: page_idx=${pdfCurrentPage}`);
      } else {
        console.error(`[Viewer-Pdf] 렌더링 중 오류 발생:`, err);
      }
    });
  });
}

export function nextPdfPage() {
  if (pdfCurrentPage < pdfTotalPages) {
    pdfCurrentPage++;
    renderPdfPage();
  } else {
    import('./viewer_next_episode.js').then(m => {
      m.handleNextEpisode(state.activeBookId);
    });
  }
}

export function prevPdfPage() {
  if (pdfCurrentPage > 1) {
    pdfCurrentPage--;
    renderPdfPage();
  }
}

export function clearPdfViewer() {
  if (currentRenderTask) {
    currentRenderTask.cancel();
    currentRenderTask = null;
  }
  pdfDoc = null;
}
