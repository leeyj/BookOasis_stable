// viewer_pdf.js – PDF 뷰어 로직
import { state } from './state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { getComicPageStep, getComicReadingDirection, getSpreadShiftOffset, resetSpreadShiftOffset } from './viewer_comic.js';
import { initPageStep } from './viewer/reader_settings.js';
import { ensurePdfJs, pdfJsAssetBase } from './utils/script_loader.js';

export let pdfDoc = null;
export let pdfCurrentPage = 1;
export let pdfTotalPages = 0;
let isInitializingPdfProgress = false;
let currentRenderTasks = [];
// 페이지 넘김 모드에서 새 페이지가 다 그려지기 전엔 렌더 영역을 비우지 않고 이전 페이지를
// 그대로 보여주기 위한 세대(generation) 번호. 사용자가 렌더 완료 전에 또 페이지를 넘기면
// 값이 올라가므로, 뒤늦게 도착한 이전 세대의 렌더 결과가 최신 화면을 덮어쓰지 않도록 막는다.
let pdfRenderGeneration = 0;

export async function initPdfViewer(bookId, pagesRead, totalPages) {
  isInitializingPdfProgress = true;
  lastMoveDir = 1;
  resetSpreadShiftOffset(); // 이전 책에서 켜뒀던 "한 장 밀기" 보정이 새 책에 남지 않도록 초기화
  // 만화 뷰어를 거치지 않고 PDF를 세션 첫 책으로 열어도 2쪽보기 버튼/한 장 밀기 버튼
  // 표시 상태(display)가 저장된 설정값과 어긋나지 않도록 여기서도 동기화한다.
  initPageStep();
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
  // 총 쪽수가 0이어도 서버(/info)에 묻지 않는다 - 서버는 pypdfium2로 파일을 직접 열어 세는데,
  // rclone 원격 파일을 처음 열면 그것만 27초 걸렸다(2026-10-25 실측). 쪽수는 pdf.js가 문서를 열면
  // numPages로 알려 주고, 닫을 때 진행도 저장(prepareForClose)이 books.total_pages도 채운다.
  pdfTotalPages = totalPages || 0;

  showViewerLoading(i18n.t("viewer.loading_pdf_title") || "PDF 준비 중", i18n.t("viewer.loading_pdf_sub") || "잠시만 기다려 주세요...");
  
  // pdf.js는 홈에서 미리 받지 않고 PDF를 처음 열 때 불러온다(2.9.5)
  let pdfjsLib;
  try {
    pdfjsLib = await ensurePdfJs();
  } catch (err) {
    console.error('[Viewer-Pdf] pdf.js 불러오기 실패:', err);
    isInitializingPdfProgress = false;
    showViewerError();
    return;
  }

  const url = `/api/media/pdf?db_type=${state.currentLibraryType}&book_id=${bookId}`;
  const assetBase = pdfJsAssetBase();
  pdfjsLib.getDocument({
    url: url,
    // 스트림을 허용하면 첫 요청이 파일 끝까지 읽혀 결국 파일 전체를 받는다(disableAutoFetch는 Range 추가 요청만 막는다).
    // 그래도 이 설정을 쓴다: 차례로 넘길 때 다음 쪽 데이터가 미리 와 있어 빠르다. Range만 쓰면(disableStream: true)
    // 느린 망 넘김이 3~6배 느리고, 객체가 흩어진 PDF는 첫 쪽에 요청이 약 190번 든다(2026-11-27 측정).
    disableAutoFetch: true,
    disableStream: false,
    isEvalSupported: false,  // CVE-2024-4367(2.16 대상). 6.x는 이 옵션이 없어 무시되지만 되돌릴 때를 위해 둔다
    cMapUrl: `${assetBase}cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `${assetBase}standard_fonts/`, // 글꼴이 안 들어 있는 PDF
    wasmUrl: `${assetBase}wasm/`,                       // JPX(JPEG2000)·JBIG2 이미지 디코더
    iccUrl: `${assetBase}iccs/`
  }).promise
    .then(doc => {
      clearPageEntries(); // 이전 책 캔버스가 같은 키(쪽·크기)로 다시 쓰이지 않게
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

export function updatePdfCanvasCssWidth(newWidth) {
  const renderArea = document.getElementById('pdf-render-area');
  if (!renderArea) return;
  const areaRect = renderArea.getBoundingClientRect();
  const availableWidth = Math.max(300, Math.min(areaRect.width - 20, newWidth));
  const canvases = renderArea.querySelectorAll('.pdf-scroll-page');
  // 높이가 함께 바뀌므로, 보던 쪽이 화면에서 같은 자리에 남도록 스크롤을 맞춘다(안 맞추면 다른 쪽으로 넘어간다)
  const current = canvases[pdfCurrentPage - 1];
  const areaTop = renderArea.getBoundingClientRect().top;
  const topBefore = current ? current.getBoundingClientRect().top - areaTop : 0;
  canvases.forEach(canvas => {
    // 높이는 비율대로 줄이고 늘린다('auto'면 아직 안 그린 1x1 자리표시가 정사각형이 된다)
    const w = parseFloat(canvas.style.width) || availableWidth;
    const h = parseFloat(canvas.style.height);
    canvas.style.width = `${availableWidth}px`;
    if (h > 0) canvas.style.height = `${Math.round(h * availableWidth / w)}px`;
  });
  if (current) {
    renderArea.scrollTop += (current.getBoundingClientRect().top - areaTop) - topBefore;
  }
}

// ── 연속 세로 스크롤 모드 ──
// 문서·폭이 같으면 스크롤 뷰를 한 번만 만들고, 넘김(탭·키·슬라이더)은 그 쪽으로 스크롤만 한다.
// 예전에는 넘길 때마다 전체 쪽 캔버스를 다시 만들고 그린 쪽을 모두 버렸다(2026-11-27 측정: 넘겨도 쪽이 안 바뀌거나 앞쪽으로 돌아감).
const SCROLL_RENDER_MARGIN = '800px 0px 800px 0px';   // 이 안에 들어오면 그린다
const SCROLL_KEEP_MARGIN = '2400px 0px 2400px 0px';   // 이 밖으로 나가야 비트맵을 비운다(조금 되돌아가도 다시 그리지 않게)
const SCROLL_MAX_RENDERS = 2;                          // 동시에 그리는 쪽 수(가까운 쪽부터)
let pdfScrollView = null;

function teardownPdfScrollView() {
  if (!pdfScrollView) return;
  pdfScrollView.renderObserver.disconnect();
  pdfScrollView.keepObserver.disconnect();
  pdfScrollView.queue.clear();
  pdfScrollView = null;
}

function scrollAvailableWidth(renderArea) {
  const areaRect = renderArea.getBoundingClientRect();
  const storedWidth = parseInt(localStorage.getItem('comic_scroll_width') || '800', 10);
  return Math.max(300, Math.min(areaRect.width - 20, storedWidth));
}

function scrollViewIsCurrent(renderArea, availableWidth) {
  const v = pdfScrollView;
  return !!v && v.doc === pdfDoc && v.area === renderArea && v.width === availableWidth
    && v.canvases.length === pdfTotalPages && v.canvases.length > 0 && v.canvases[0].isConnected;
}

function scrollPdfToPage(pageNum) {
  const v = pdfScrollView;
  if (!v) return;
  const canvas = v.canvases[pageNum - 1];
  if (!canvas) return;
  v.area.scrollTop += canvas.getBoundingClientRect().top - v.area.getBoundingClientRect().top - 10;
}

function releaseScrollCanvas(canvas) {
  canvas._pdfRendered = false;
  canvas.width = 1;  // 비트맵 메모리만 비운다. style 높이는 그대로라 자리(스크롤 위치)는 안 바뀐다
  canvas.height = 1;
  delete canvas.dataset.drawn;
}

function pumpScrollQueue(view) {
  while (view === pdfScrollView && view.active < SCROLL_MAX_RENDERS && view.queue.size > 0) {
    const areaRect = view.area.getBoundingClientRect();
    const center = areaRect.top + areaRect.height / 2;
    let best = null;
    let bestDist = Infinity;
    view.queue.forEach(c => {
      const r = c.getBoundingClientRect();
      const d = Math.abs((r.top + r.bottom) / 2 - center);
      if (d < bestDist) { bestDist = d; best = c; }
    });
    const canvas = best;
    view.queue.delete(canvas);
    view.active++;
    canvas._pdfRendering = true;
    const pageNum = parseInt(canvas.dataset.pageNum, 10);
    renderSinglePdfCanvas(pageNum, canvas, view.width, null, view.area).then(() => {
      canvas._pdfRendering = false;
      view.active--;
      if (view !== pdfScrollView) return;
      if (canvas._pdfNear) canvas._pdfRendered = true;
      else releaseScrollCanvas(canvas);  // 그리는 동안 멀리 지나갔다
      pumpScrollQueue(view);
    });
  }
}

function buildPdfScrollView(renderArea, availableWidth, renderGeneration) {
  renderArea.innerHTML = '';
  renderArea.style.overflowY = 'auto';
  renderArea.style.overflowX = 'hidden';
  renderArea.style.overflowAnchor = 'none';  // 위쪽 높이 보정은 renderSinglePdfCanvas가 직접 한다(Safari에는 스크롤 앵커가 없다)
  renderArea.style.flexDirection = 'column';
  renderArea.style.justifyContent = 'flex-start';
  renderArea.style.alignItems = 'center';
  renderArea.style.height = '100%';
  renderArea.style.width = '100%';
  renderArea.style.padding = '20px 10px';
  renderArea.style.gap = '20px';

  const startPage = Math.min(Math.max(1, pdfCurrentPage), pdfTotalPages);
  // 자리표시 높이는 이어 볼 쪽의 비율로 잡는다. 예전엔 300px 고정이라 쪽이 그려질 때마다 높이가 바뀌어 위치가 밀렸다.
  pdfDoc.getPage(startPage).then(page => {
    const vp = page.getViewport({ scale: 1.0 });
    return vp.height / vp.width;
  }).catch(() => Math.SQRT2).then(ratio => {
    if (renderGeneration !== pdfRenderGeneration) return;
    const placeholderHeight = Math.round(availableWidth * ratio);
    const canvases = [];
    for (let pageNum = 1; pageNum <= pdfTotalPages; pageNum++) {
      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-canvas-element pdf-scroll-page';
      canvas.dataset.pageNum = pageNum;
      canvas.width = 1;
      canvas.height = 1;
      canvas.style.boxShadow = '0 10px 30px rgba(0,0,0,0.5)';
      canvas.style.display = 'block';
      canvas.style.marginBottom = '20px';
      canvas.style.width = `${availableWidth}px`;
      canvas.style.height = `${placeholderHeight}px`;
      canvas.style.flex = '0 0 auto';
      renderArea.appendChild(canvas);
      canvases.push(canvas);
    }

    const view = {
      doc: pdfDoc, area: renderArea, width: availableWidth, canvases,
      queue: new Set(), active: 0, renderObserver: null, keepObserver: null
    };
    view.renderObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const c = entry.target;
        if (entry.isIntersecting) {
          if (!c._pdfRendered && !c._pdfRendering) view.queue.add(c);
        } else {
          view.queue.delete(c);
        }
      });
      pumpScrollQueue(view);
    }, { root: renderArea, rootMargin: SCROLL_RENDER_MARGIN, threshold: 0 });
    view.keepObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const c = entry.target;
        c._pdfNear = entry.isIntersecting;
        if (!entry.isIntersecting && c._pdfRendered && !c._pdfRendering) releaseScrollCanvas(c);
      });
    }, { root: renderArea, rootMargin: SCROLL_KEEP_MARGIN, threshold: 0 });
    pdfScrollView = view;

    scrollPdfToPage(startPage);
    canvases.forEach(c => { view.keepObserver.observe(c); view.renderObserver.observe(c); });
  });

  // 스크롤 시 현재 보는 페이지 탐지 및 진행도 자동 반영
  if (!renderArea._pdfScrollBound) {
    renderArea._pdfScrollBound = true;
    let scrollTimer = null;
    renderArea.addEventListener('scroll', () => {
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        const v = pdfScrollView;
        if (!pdfDoc || pdfTotalPages <= 0 || !v || v.area !== renderArea) return;
        const areaRect = renderArea.getBoundingClientRect();
        const covers = (c) => {
          const r = c.getBoundingClientRect();
          return r.top - areaRect.top <= renderArea.clientHeight / 2 && r.bottom - areaRect.top >= 50;
        };
        // 지금 쪽이 아직 화면 위쪽을 차지하고 있으면 그대로 둔다(넘김 직후 다음 쪽으로 튀거나 되돌아가지 않게)
        const cur = v.canvases[pdfCurrentPage - 1];
        if (cur && covers(cur)) return;
        let activePage = pdfCurrentPage;
        for (let i = 0; i < v.canvases.length; i++) {
          if (covers(v.canvases[i])) activePage = i + 1;
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
}

// ── 페이지 넘김 모드 미리 그리기 ──
// 넘길 때마다 처음부터 그리면 LAN에서도 70~135ms를 기다렸다(2026-11-27 측정). 화면 묶음(shown), 방금 떠난 묶음,
// 진행 방향의 다음 묶음만 오프스크린 캔버스로 들고 있다가 넘길 때 바꿔 붙인다. 키에 크기·설정이 들어가므로
// 창 크기·2쪽 보기·한 장 밀기·방향이 바뀌면 키가 달라져 낡은 캔버스는 쓰이지 않고 정리된다.
let pageEntries = new Map();  // key -> { key, canvases, sink, promise, settled, ok }
let shownEntry = null;
let lastMoveDir = 1;          // 1 앞으로, -1 뒤로. 미리 그릴 방향

function pdfRenderDpr() {
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  const rawDpr = window.devicePixelRatio || 1;
  return Math.min(isMobile ? 1.5 : 2.0, Math.max(rawDpr, 1.0));
}

function applyPageModeAreaStyle(renderArea, removeCenterGap) {
  renderArea.style.overflow = 'hidden';
  renderArea.style.flexDirection = 'row';
  renderArea.style.justifyContent = 'center';
  renderArea.style.alignItems = 'center';
  renderArea.style.height = '100%';
  renderArea.style.width = '100%';
  renderArea.style.padding = '10px';
  renderArea.style.gap = removeCenterGap ? '0px' : '10px';
}

// anchor(진행 저장 기준 쪽)를 보여 줄 때의 쪽 묶음과 크기
function pageLayoutFor(anchor, renderArea, removeCenterGap) {
  const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
  const direction = (typeof getComicReadingDirection === 'function') ? getComicReadingDirection() : 'ltr';
  const shiftOffset = (step === 2 && typeof getSpreadShiftOffset === 'function') ? getSpreadShiftOffset() : 0;

  let pages;
  if (step === 2) {
    // "한 장 밀기" 보정 - 진행률 저장 기준인 pdfCurrentPage는 그대로 두고, 화면에 짝지어
    // 보여줄 페이지의 기준점만 밀어서 예: (9,10)(11,12) 정렬을 (10,11)로 바꿔 볼 수 있게 한다.
    const p1 = Math.min(anchor + shiftOffset, pdfTotalPages);
    const p2 = p1 + 1;
    if (p2 <= pdfTotalPages) pages = direction === 'rtl' ? [p2, p1] : [p1, p2];
    else pages = [p1];
  } else {
    pages = [anchor];
  }

  const areaRect = renderArea.getBoundingClientRect();
  const areaStyle = window.getComputedStyle(renderArea);
  const padLeft = parseFloat(areaStyle.paddingLeft || '0') || 0;
  const padRight = parseFloat(areaStyle.paddingRight || '0') || 0;
  const padTop = parseFloat(areaStyle.paddingTop || '0') || 0;
  const padBottom = parseFloat(areaStyle.paddingBottom || '0') || 0;
  const gapPx = pages.length === 2 ? (parseFloat(areaStyle.columnGap || areaStyle.gap || '0') || 0) : 0;

  const innerWidth = Math.max(1, areaRect.width - padLeft - padRight);
  const innerHeight = Math.max(1, areaRect.height - padTop - padBottom);
  const width = pages.length === 2 ? Math.max(1, (innerWidth - gapPx) / 2) : innerWidth;
  const height = innerHeight;
  const key = [pages.join(','), Math.round(width), Math.round(height), pdfRenderDpr(), removeCenterGap ? 1 : 0].join('|');
  return { pages, width, height, removeCenterGap, key };
}

function startPageEntry(layout) {
  const canvases = layout.pages.map(() => {
    const canvas = document.createElement('canvas');
    canvas.className = 'pdf-canvas-element';
    canvas.style.boxShadow = layout.removeCenterGap ? 'none' : '0 10px 30px rgba(0,0,0,0.5)';
    canvas.style.display = 'block';
    return canvas;
  });
  const entry = { key: layout.key, canvases, sink: { tasks: [], cancelled: false }, promise: null, settled: false, ok: false };
  entry.promise = Promise.all(
    layout.pages.map((pageNum, i) => renderSinglePdfCanvas(pageNum, canvases[i], layout.width, layout.height, null, entry.sink))
  ).then(results => {
    entry.settled = true;
    entry.ok = !entry.sink.cancelled && results.every(Boolean);
  });
  pageEntries.set(entry.key, entry);
  return entry;
}

function dropPageEntry(entry) {
  entry.sink.cancelled = true;
  entry.sink.tasks.forEach(t => { try { t.cancel(); } catch (e) {} });
  entry.sink.tasks = [];
  // 화면에 붙어 있지 않은 캔버스는 비트맵을 바로 비운다(iOS Safari 캔버스 메모리 한도)
  entry.canvases.forEach(c => { if (!c.isConnected) { c.width = 0; c.height = 0; } });
  if (pageEntries.get(entry.key) === entry) pageEntries.delete(entry.key);
  if (shownEntry === entry) shownEntry = null;
}

function trimPageEntries(keepKeys) {
  Array.from(pageEntries.values()).forEach(e => { if (!keepKeys.has(e.key)) dropPageEntry(e); });
}

function clearPageEntries() {
  Array.from(pageEntries.values()).forEach(dropPageEntry);
  pageEntries = new Map();
  shownEntry = null;
}

// 화면 묶음이 붙은 뒤 호출한다. 방금 떠난 묶음(left)은 버리지 않고 두고, 진행 방향의 다음 묶음을 미리 그린다.
function schedulePagePrefetch(renderArea, removeCenterGap, renderGeneration, left) {
  if (!shownEntry) return;
  const keep = new Set([shownEntry.key]);
  if (left && left !== shownEntry && pageEntries.get(left.key) === left) keep.add(left.key);

  // prevPdfPage / nextPdfPage가 옮겨 갈 쪽과 똑같이 계산한다
  const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
  let nextAnchor = null;
  if (lastMoveDir > 0 && pdfCurrentPage < pdfTotalPages) nextAnchor = Math.min(pdfTotalPages, pdfCurrentPage + step);
  else if (lastMoveDir < 0 && pdfCurrentPage > 1) nextAnchor = Math.max(1, pdfCurrentPage - step);
  const nextLayout = nextAnchor ? pageLayoutFor(nextAnchor, renderArea, removeCenterGap) : null;
  if (nextLayout) keep.add(nextLayout.key);
  trimPageEntries(keep);

  if (!nextLayout || pageEntries.has(nextLayout.key)) return;
  // 화면 교체가 먼저 그려지도록 한 틱 뒤에 시작한다. 그사이 또 넘겼으면 시작하지 않는다.
  setTimeout(() => {
    if (renderGeneration !== pdfRenderGeneration || !pdfDoc || pageEntries.has(nextLayout.key)) return;
    startPageEntry(nextLayout);
  }, 0);
}

export function renderPdfPage() {
  if (!pdfDoc) return;

  const renderArea = document.getElementById('pdf-render-area');
  if (!renderArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'scroll') {
    const availableWidth = scrollAvailableWidth(renderArea);
    if (scrollViewIsCurrent(renderArea, availableWidth)) {
      // 같은 문서·같은 폭: 다시 만들지 않고 그 쪽으로 스크롤만 한다(그린 쪽·진행 중 렌더 유지)
      scrollPdfToPage(pdfCurrentPage);
      updatePdfPageInfo();
      if (!isInitializingPdfProgress && state.activeBookId && pdfTotalPages > 0) {
        saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
      }
      return;
    }
  }

  // 기존 진행 중인 모든 렌더링 태스크 강제 취소
  currentRenderTasks.forEach(task => {
    if (task) {
      try { task.cancel(); } catch (e) {}
    }
  });
  currentRenderTasks = [];
  teardownPdfScrollView();

  const renderGeneration = ++pdfRenderGeneration;

  if (scrollMode === 'scroll') {
    clearPageEntries();
    buildPdfScrollView(renderArea, scrollAvailableWidth(renderArea), renderGeneration);
  } else {
    // ── 2. 페이지 넘김 모드 (1장/2장 화면 맞춤) ──
    const removeCenterGap = (localStorage.getItem('remove_2page_center_gap') === '1');
    applyPageModeAreaStyle(renderArea, removeCenterGap);
    const layout = pageLayoutFor(pdfCurrentPage, renderArea, removeCenterGap);

    if (shownEntry && shownEntry.ok && shownEntry.key === layout.key && shownEntry.canvases[0] && shownEntry.canvases[0].isConnected) {
      // 화면에 이미 같은 묶음이 같은 크기로 있다
      schedulePagePrefetch(renderArea, removeCenterGap, renderGeneration, null);
    } else {
      let entry = pageEntries.get(layout.key);
      if (entry && entry.settled && !entry.ok) { dropPageEntry(entry); entry = null; }
      // 보여 줄 묶음과 지금 화면 묶음만 남기고, 다른 미리 그리기는 취소한다(멀리 뛰면 렌더를 다투지 않게)
      const keep = new Set([layout.key]);
      if (shownEntry) keep.add(shownEntry.key);
      trimPageEntries(keep);
      // 미리 그려 뒀으면 바로, 그리는 중이면 그 작업을 기다린다(다시 시작하지 않는다)
      if (!entry) entry = startPageEntry(layout);

      // 새 캔버스는 다 그려진 뒤 한 번에 바꿔 붙인다(이중 버퍼링). 그동안 이전 쪽이 화면에 남아 흰 화면이 없다.
      entry.promise.then(() => {
        // 그리는 동안 또 넘겼다면(세대 번호 불일치) 이 결과는 낡았으므로 반영하지 않는다
        if (renderGeneration !== pdfRenderGeneration || entry.sink.cancelled) return;
        const left = shownEntry;
        renderArea.innerHTML = '';
        entry.canvases.forEach(canvas => renderArea.appendChild(canvas));
        shownEntry = entry;
        schedulePagePrefetch(renderArea, removeCenterGap, renderGeneration, left);
      });
    }
  }

  updatePdfPageInfo();

  if (!isInitializingPdfProgress && state.activeBookId && pdfTotalPages > 0) {
    saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
  }
}

// 개별 PDF 페이지 캔버스 렌더링 헬퍼. 호출자(페이지 넘김 모드)가 Promise.all로 여러
// 페이지의 완료를 함께 기다려 한 번에 화면에 붙일 수 있도록, 성공/실패/취소 어느
// 경우든 절대 reject하지 않고 항상 resolve하는 프로미스를 반환한다(하나가 실패해도
// 나머지 정상 페이지의 교체 타이밍이 막히면 안 되므로). 값은 다 그렸으면 true, 아니면 false.
// scrollArea(스크롤 모드)를 주면, 화면 위쪽으로 지나간 쪽의 높이가 바뀔 때 그만큼 스크롤을 보정해 보던 위치가 밀리지 않게 한다.
// sink(페이지 모드 묶음)를 주면 렌더 작업을 currentRenderTasks 대신 거기에 두고, 취소 표시가 있으면 그리지 않는다.
function renderSinglePdfCanvas(pageNum, canvas, availWidth, availHeight, scrollArea = null, sink = null) {
  const doc = pdfDoc;
  if (!doc) return Promise.resolve(false);
  return doc.getPage(pageNum).then(page => {
    if ((sink && sink.cancelled) || doc !== pdfDoc) return false;
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

    const dpr = pdfRenderDpr();
    const viewport = page.getViewport({ scale: scale * dpr });

    let above = false;
    let oldHeight = 0;
    if (scrollArea) {
      const r = canvas.getBoundingClientRect();
      above = r.bottom <= scrollArea.getBoundingClientRect().top;
      oldHeight = r.height;
    }

    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${viewport.width / dpr}px`;
    canvas.style.height = `${viewport.height / dpr}px`;
    canvas.style.flex = '0 0 auto';

    if (above) {
      const delta = canvas.getBoundingClientRect().height - oldHeight;
      if (Math.abs(delta) >= 1) scrollArea.scrollTop += delta;
    }

    if (ctx) {
      ctx.imageSmoothingEnabled = true;
      if (typeof ctx.imageSmoothingQuality !== 'undefined') {
        ctx.imageSmoothingQuality = 'high';
      }
    }

    // 6.x는 canvas를 넘기는 방식을 권장한다(canvasContext는 호환용)
    const renderCtx = { canvas, viewport };
    const renderTask = page.render(renderCtx);
    if (sink) sink.tasks.push(renderTask);
    else currentRenderTasks.push(renderTask);
    const untrack = () => {
      if (sink) sink.tasks = sink.tasks.filter(t => t !== renderTask);
      else currentRenderTasks = currentRenderTasks.filter(t => t !== renderTask);
    };

    return renderTask.promise.then(() => {
      untrack();
      return true;
    }).catch(err => {
      untrack();
      if (err.name !== 'RenderingCancelledException' && err.name !== 'RenderingCancelled') {
        console.error(`[Viewer-Pdf] Page ${pageNum} rendering error:`, err);
      }
      return false;
    });
  }).catch(err => {
    console.error(`[Viewer-Pdf] getPage failed for page ${pageNum}:`, err);
    return false;
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
    lastMoveDir = -1;
    renderPdfPage();
    saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
  }
}

export function nextPdfPage() {
  if (pdfDoc) {
    if (pdfCurrentPage < pdfTotalPages) {
      const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
      pdfCurrentPage = Math.min(pdfTotalPages, pdfCurrentPage + step);
      lastMoveDir = 1;
      renderPdfPage();
      saveProgress(state.activeBookId, pdfCurrentPage - 1, pdfTotalPages);
    } else {
      import('./viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    }
  }
}

export function clearPdfViewer() {
  pdfRenderGeneration++; // 진행 중이던 오프스크린 렌더가 나중에 끝나도 화면에 반영되지 않도록 폐기
  teardownPdfScrollView();
  // 닫을 때는 화면 캔버스 비트맵도 바로 비운다(GC를 기다리면 iOS Safari 캔버스 메모리 한도에 걸릴 수 있다)
  if (shownEntry) shownEntry.canvases.forEach(c => { c.width = 0; c.height = 0; });
  clearPageEntries();
  currentRenderTasks.forEach(task => {
    if (task) {
      try { task.cancel(); } catch (e) {}
    }
  });
  currentRenderTasks = [];
  if (pdfDoc) {
    try {
      if (typeof pdfDoc.cleanup === 'function') pdfDoc.cleanup();
      // 6.x는 문서 객체에 destroy()가 없고 loadingTask.destroy()로 해제한다(없으면 닫아도 문서·worker 메모리가 남았다)
      if (typeof pdfDoc.destroy === 'function') pdfDoc.destroy();
      else if (pdfDoc.loadingTask && typeof pdfDoc.loadingTask.destroy === 'function') pdfDoc.loadingTask.destroy();
    } catch (e) {
      console.warn('[Viewer-Pdf] Failed to destroy pdfDoc:', e);
    }
    pdfDoc = null;
  }
}

export function pdfJumpToFirstPage() {
  if (pdfDoc && pdfCurrentPage !== 1) {
    pdfCurrentPage = 1;
    lastMoveDir = 1;
    renderPdfPage();
  }
}

export function pdfJumpToLastPage() {
  if (pdfDoc && pdfCurrentPage !== pdfTotalPages) {
    pdfCurrentPage = pdfTotalPages;
    lastMoveDir = -1;
    renderPdfPage();
  }
}

export function pdfJumpToPage(pageNum) {
  if (pdfDoc) {
    const targetPage = Math.max(1, Math.min(pdfTotalPages, pageNum));
    if (pdfCurrentPage !== targetPage) {
      lastMoveDir = targetPage > pdfCurrentPage ? 1 : -1;
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
  // 마지막 페이지가 화면에 나와 있는지 (슬라이드가 권 끝을 판단할 때 사용)
  isAtLastPage() {
    if (!pdfDoc || !pdfTotalPages) return false;
    if ((localStorage.getItem('viewer_scroll_mode') || 'page') === 'scroll') {
      const renderArea = document.getElementById('pdf-render-area');
      return !!renderArea && renderArea.scrollTop + renderArea.clientHeight >= renderArea.scrollHeight - 2;
    }
    const step = (typeof getComicPageStep === 'function') ? getComicPageStep() : 1;
    return pdfCurrentPage + (step === 2 ? 1 : 0) >= pdfTotalPages;
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
