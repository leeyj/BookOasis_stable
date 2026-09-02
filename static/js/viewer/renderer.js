// renderer.js — 이미지 삽입 및 렌더링 로직
import { state } from '../state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from '../view_manager.js';
import { saveProgress } from '../viewer_progress.js';
import * as Settings from './reader_settings.js';
import * as FileLoader from './fileloader.js';

export let comicCurrentPage = 0;
export let comicTotalPages = 0;
let comicLoadingTimer = null;
let comicLoadTraceSeq = 0;
let observer = null;
let isScrollingToTarget = false;
let scrollProgressHandler = null;
let scrollTouchEndHandler = null;
let scrollEndCheckTimer = null;
let scrollPreloadTriggered = false;
let scrollNextEpisodeTriggered = false;
let imageWorker = null;
let _workerRequestId = 1;
const _workerPending = new Map();
let _workerCleanupAdded = false;
const activePreloadSet = new Set();
const blobCacheMap = new Map();
const splitCropCacheMap = new Map();
let currentPreloadQueue = [];
let isPreloading = false;
let splitModeActive = false;

function createComicLoadTrace(details = {}) {
  const traceId = ++comicLoadTraceSeq;
  const startedAt = (typeof performance !== 'undefined' && typeof performance.now === 'function')
    ? performance.now()
    : Date.now();
  const prefix = `[Viewer-Comic][LoadTrace#${traceId}]`;

  console.log(`${prefix} start`, details);

  return {
    traceId,
    log(step, extra = {}) {
      const now = (typeof performance !== 'undefined' && typeof performance.now === 'function')
        ? performance.now()
        : Date.now();
      const elapsedMs = Math.round(now - startedAt);
      console.log(`${prefix} ${step} +${elapsedMs}ms`, extra);
    }
  };
}

function clearBlobCache() {
  blobCacheMap.forEach((objectUrl) => {
    try {
      URL.revokeObjectURL(objectUrl);
    } catch (e) {}
  });
  blobCacheMap.clear();
  splitCropCacheMap.forEach((objectUrl) => {
    try {
      URL.revokeObjectURL(objectUrl);
    } catch (e) {}
  });
  splitCropCacheMap.clear();
  currentPreloadQueue = [];
}

// ──────────────────────────────────────────────────
// 페이지 좌/우 분할 보기 지원 헬퍼
// ──────────────────────────────────────────────────

// virtualIdx(가상 절반-페이지 인덱스) -> { physical(실제 이미지 인덱스), side('left'|'right') }
function splitVirtualIndex(virtualIdx) {
  const physical = Math.floor(virtualIdx / 2);
  const sub = virtualIdx % 2; // 0 = 읽기 순서상 첫번째 절반, 1 = 두번째 절반
  const firstSide = Settings.getComicReadingDirection() === 'rtl' ? 'right' : 'left';
  const side = sub === 0 ? firstSide : (firstSide === 'left' ? 'right' : 'left');
  return { physical, side };
}

// 분할 모드에서 comicTotalPages는 가상(절반) 페이지 수이므로, 실제 이미지 개수로 환산
function getPhysicalTotalPages() {
  return splitModeActive ? Math.max(1, Math.ceil(comicTotalPages / 2)) : comicTotalPages;
}

// 분할 설정 토글 시(또는 책 최초 로드 시) comicCurrentPage/comicTotalPages를
// 물리 페이지 공간 <-> 가상 절반-페이지 공간 사이에서 왕복 변환한다.
export function syncSplitSpreadMode() {
  const nowOn = Settings.getComicSplitSpread();
  if (nowOn === splitModeActive) return;
  if (nowOn) {
    comicTotalPages = comicTotalPages * 2;
    comicCurrentPage = comicCurrentPage * 2;
  } else {
    comicTotalPages = getPhysicalTotalPages();
    comicCurrentPage = Math.floor(comicCurrentPage / 2);
  }
  splitModeActive = nowOn;
}

// 스크롤 모드는 분할 보기를 지원하지 않는다(1차 범위 밖). 페이지 모드에서 분할 보기를 켠
// 채로 스크롤 모드로 전환하면 comicTotalPages/comicCurrentPage가 가상(절반-페이지) 값으로
// 남아있어, 스크롤 모드의 페이지 순회 루프와 진행률 저장이 모두 실제 페이지 수의 2배를
// 물리 인덱스인 것처럼 취급해버린다 — 저장된 분할 설정(Settings)은 건드리지 않고, 스크롤
// 모드에 있는 동안만 강제로 물리 공간으로 되돌린다. 페이지 모드로 복귀하면 다시 동기화한다.
export function syncSplitSpreadModeForScrollMode(isScrollMode) {
  if (isScrollMode) {
    if (splitModeActive) {
      comicTotalPages = getPhysicalTotalPages();
      comicCurrentPage = splitVirtualIndex(comicCurrentPage).physical;
      splitModeActive = false;
    }
  } else {
    syncSplitSpreadMode();
  }
}

// 서버로 보낼 진행률(항상 물리 페이지 기준 — books.total_pages 오염 방지)
export function getPhysicalProgress() {
  const page = splitModeActive ? splitVirtualIndex(comicCurrentPage).physical : comicCurrentPage;
  return { page, total: getPhysicalTotalPages() };
}

// 물리 페이지 전체 이미지를 fetch/blob 캐시하고 object URL을 반환 (기존 인라인 로직을 함수로 추출)
function getWholePageObjectUrl(bookId, physicalIndex) {
  const cacheKey = `${bookId}_${physicalIndex}`;
  if (blobCacheMap.has(cacheKey)) {
    return Promise.resolve(blobCacheMap.get(cacheKey));
  }
  const url = FileLoader.getPageStreamUrl(physicalIndex);
  // 지금 화면에 띄울 페이지라 최우선 — 동시에 출발하는 프리페치 워커들과 대역폭/커넥션을
  // 두고 경쟁하면 안 되므로 Fetch Priority Hints로 브라우저에 우선순위를 명시한다
  // (미지원 브라우저는 이 옵션을 그냥 무시하므로 별도 분기 불필요).
  return fetch(url, { priority: 'high' })
    .then((res) => {
      if (!res.ok) throw new Error('Fetch fail');
      return res.blob();
    })
    .then((blob) => {
      const activeBookId = state.activeBookId;
      if (activeBookId !== bookId) throw new Error('book switched');
      const objUrl = URL.createObjectURL(blob);
      blobCacheMap.set(cacheKey, objUrl);
      return objUrl;
    })
    .catch(() => url); // 폴백: 원본 스트림 URL 그대로 반환
}

// 분할 모드용: 물리 페이지를 잘라 절반 이미지의 object URL을 반환 (가상 인덱스 기준 캐시)
function getSplitCroppedImageUrl(bookId, virtualIndex, physicalIndex, side) {
  const cropKey = `${bookId}_${virtualIndex}`;
  if (splitCropCacheMap.has(cropKey)) {
    return Promise.resolve(splitCropCacheMap.get(cropKey));
  }
  return getWholePageObjectUrl(bookId, physicalIndex).then((wholeUrl) => new Promise((resolve, reject) => {
    const tempImg = new Image();
    tempImg.onload = () => {
      const halfW = Math.round(tempImg.naturalWidth / 2) || 1;
      const sx = side === 'left' ? 0 : (tempImg.naturalWidth - halfW);
      const canvas = document.createElement('canvas');
      canvas.width = halfW;
      canvas.height = tempImg.naturalHeight;
      canvas.getContext('2d').drawImage(tempImg, sx, 0, halfW, tempImg.naturalHeight, 0, 0, halfW, tempImg.naturalHeight);
      canvas.toBlob((blob) => {
        if (!blob) { reject(new Error('split crop failed')); return; }
        const croppedUrl = URL.createObjectURL(blob);
        splitCropCacheMap.set(cropKey, croppedUrl);
        resolve(croppedUrl);
      }, 'image/jpeg', 0.92);
    };
    tempImg.onerror = () => reject(new Error('split crop source load failed'));
    tempImg.src = wholeUrl;
  }));
}

function ensureImageWorker() {
  if (imageWorker) return;
  try {
    imageWorker = new Worker(new URL('./workers/image_worker.js', import.meta.url), { type: 'module' });
    imageWorker.onmessage = (ev) => {
      const msg = ev.data || {};
      const id = msg.id;
      const entry = _workerPending.get(id);
      if (!entry) return;
      _workerPending.delete(id);
      if (msg.success && msg.buffer) {
        try {
          const blob = new Blob([msg.buffer], { type: msg.contentType || 'image/jpeg' });
          const url = URL.createObjectURL(blob);
          entry.resolve({ objectUrl: url });
        } catch (e) {
          entry.reject(e);
        }
      } else {
        entry.reject(new Error(msg.error || 'worker fetch failed'));
      }
    };
  } catch (e) {
    imageWorker = null;
  }
  if (imageWorker && !_workerCleanupAdded) {
    _workerCleanupAdded = true;
    window.addEventListener('unload', () => {
      try { imageWorker && imageWorker.terminate(); } catch (e) { }
    });
  }
}

function fetchImageWithWorker(url) {
  const maxAttempts = 3; // initial try + 2 retries
  const baseTimeout = 10000; // ms
  let attempt = 0;

  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      attempt += 1;
      if (typeof Worker === 'undefined') return reject(new Error('Worker unsupported'));
      ensureImageWorker();
      const reqId = _workerRequestId++;
      const timeout = setTimeout(() => {
        if (_workerPending.has(reqId)) {
          _workerPending.delete(reqId);
          const err = new Error('worker timeout');
          if (attempt < maxAttempts) {
            const backoff = 200 * Math.pow(2, attempt - 1);
            console.warn(`[viewer][worker] timeout, retrying #${attempt} after ${backoff}ms`, url);
            setTimeout(tryOnce, backoff);
          } else {
            reject(err);
          }
        }
      }, baseTimeout);

      _workerPending.set(reqId, {
        resolve: (res) => { clearTimeout(timeout); resolve(res); },
        reject: (err) => { clearTimeout(timeout); reject(err); }
      });

      try {
        imageWorker.postMessage({ action: 'fetch', url, id: reqId });
      } catch (e) {
        clearTimeout(timeout);
        _workerPending.delete(reqId);
        if (attempt < maxAttempts) {
          const backoff = 200 * Math.pow(2, attempt - 1);
          console.warn(`[viewer][worker] postMessage failed, retrying #${attempt} after ${backoff}ms`, e);
          setTimeout(tryOnce, backoff);
        } else {
          reject(e);
        }
      }
    };

    tryOnce();
  });
}

let isInitializingProgress = false;

export async function initRenderer(bookId, pagesRead, totalPages) {
  isInitializingProgress = true;

  // 이전 도서 캐시 및 DOM 상태 완전 초기화 (도서간 이미지 교차 오염 방지)
  clearComicViewer();
  clearBlobCache();

  // 뷰어 초기화가 시작되는 즉시 로딩 오버레이를 화면에 노출합니다.
  showViewerLoading('Loading...', 'Preparing pages');

  document.getElementById('comic-viewer-container').style.display = 'flex';
  document.getElementById('comic-fit-controls').style.display = 'flex';

  let initialPage = pagesRead > 0 ? pagesRead - 1 : 0;

  // 크로스 디바이스(모바일-PC) 동기화: 서버의 최신 진행도 상태(progress-state)를 비동기 조회하여 최신 위치 복원
  try {
    const res = await fetch(`/api/media/progress-state?db_type=${state.currentLibraryType}&book_id=${bookId}`);
    if (res.ok) {
      const data = await res.json();
      if (data.success && data.state && typeof data.state.pages_read === 'number' && data.state.pages_read > 0) {
        const serverPageIdx = data.state.pages_read - 1;
        console.log(`[Viewer-Comic] Server progress-state fetched: page ${data.state.pages_read} (local fallback: ${pagesRead})`);
        initialPage = serverPageIdx;
      }
    }
  } catch (err) {
    console.warn('[Viewer-Comic] Failed to fetch server progress-state, fallback to client params:', err);
  }

  comicCurrentPage = initialPage;
  comicTotalPages = await FileLoader.fetchTotalPagesIfNeeded(bookId, totalPages);
  splitModeActive = false; // 책마다 항상 물리 페이지 공간에서 시작

  Settings.initReadingDirection();
  Settings.initPageStep();
  Settings.initSplitSpread();
  // 저장된 분할 설정이 켜져 있어도, 스크롤 모드가 기본값으로 저장돼 있으면 분할 보기는
  // 적용하지 않는다(스크롤 모드는 분할 보기 미지원) — 그렇지 않으면 스크롤 모드의 페이지
  // 순회 루프가 가상(절반-페이지) 총 페이지 수를 물리 인덱스로 오인해 범위를 벗어난다.
  const initialScrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  syncSplitSpreadModeForScrollMode(initialScrollMode === 'scroll');
  Settings.initScrollWidth(); // 저장된 스크롤 너비 복원
  applyComicFitMode();
  loadComicPage();

  isInitializingProgress = false;
}



// Accessors for module state to allow safe updates from other modules
export function getComicCurrentPage() { return comicCurrentPage; }
export function setComicCurrentPage(v) { comicCurrentPage = v; }
export function getComicTotalPages() { return comicTotalPages; }
export function setComicTotalPages(v) { comicTotalPages = v; }
export function setIsScrollingToTarget(v) { isScrollingToTarget = v; }
export function getIsScrollingToTarget() { return isScrollingToTarget; }

export function setComicFitMode(mode) {
  Settings.setFitMode(mode);
  applyComicFitMode();
}

export function applyComicFitMode() {
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (!wrapper) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  wrapper.classList.remove('fit-height', 'fit-width', 'scroll-mode');
  wrapper.classList.add(Settings.getFitMode() === 'width' ? 'fit-width' : 'fit-height');

  if (scrollMode === 'scroll') {
    wrapper.classList.add('scroll-mode');
  }

  // 스크롤 너비 CSS 변수 적용
  Settings.applyScrollWidth();
}

export function updatePageInfo() {
  const overlayInfoEl = document.getElementById('comic-overlay-page-info');

  if (state.currentViewerFormat === 'epub' || state.currentViewerFormat === 'txt') {
    const slider = document.getElementById('viewer-page-slider');
    if (slider && overlayInfoEl) {
      const maxVal = slider.max || '1';
      const curVal = slider.value || '1';
      overlayInfoEl.textContent = `${curVal} / ${maxVal}`;
    }
    const overlayTitleEl = document.getElementById('overlay-title-text');
    if (overlayTitleEl) overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;
    return;
  }

  if (state.currentViewerFormat === 'pdf') {
    const pdfInfo = document.getElementById('pdf-page-info');
    if (pdfInfo && overlayInfoEl) {
      overlayInfoEl.textContent = pdfInfo.textContent;
    }
    const overlayTitleEl = document.getElementById('overlay-title-text');
    if (overlayTitleEl) overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;
    return;
  }

  const indices = getComicPageIndices();
  const totalPages = comicTotalPages || '?';
  const startPage = indices[0] + 1;
  const endPage = indices[indices.length - 1] + 1;
  const textInfo = indices.length === 2
    ? `${startPage}-${endPage} / ${totalPages}`
    : `${startPage} / ${totalPages}`;

  if (overlayInfoEl) overlayInfoEl.textContent = textInfo;

  const overlayTitleEl = document.getElementById('overlay-title-text');
  if (overlayTitleEl) overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;

  syncSeekBar();
}

function getComicDisplayPageIndex(basePage) {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isTwoPage = scrollMode !== 'scroll' && Settings.getComicPageStep() === 2;
  // "한 장 밀기" 보정 - 스프레드 짝의 기준(basePage)만 화면 표시용으로 밀어준다.
  // 진행률 저장에 쓰이는 실제 comicCurrentPage는 건드리지 않는다.
  const shiftedBase = isTwoPage
    ? Math.min(basePage + Settings.getSpreadShiftOffset(), Math.max(0, comicTotalPages - 1))
    : basePage;
  const displayPage = !isTwoPage
    ? shiftedBase
    : (Settings.getComicReadingDirection() === 'rtl'
      ? Math.min(shiftedBase + 1, Math.max(0, comicTotalPages - 1))
      : shiftedBase);
  return displayPage;
}

function getComicPageIndices() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const displayPageIndex = getComicDisplayPageIndex(comicCurrentPage);
  if (scrollMode === 'scroll' || Settings.getComicPageStep() !== 2) {
    return [displayPageIndex];
  }

  if (Settings.getComicReadingDirection() === 'rtl') {
    // basePage(comicCurrentPage) 다음 페이지가 없어서 getComicDisplayPageIndex가
    // basePage 그대로 clamp한 경우 = 짝이 없는 마지막 홀수 페이지.
    // 이 경우 직전 스프레드에서 이미 보여준 (basePage - 1) 페이지와 재조합하면
    // 마지막 전 페이지가 두 번 반복 노출되므로, 짝 없이 단독 표시한다.
    if (displayPageIndex === comicCurrentPage) {
      return [comicCurrentPage];
    }
    const prevPage = displayPageIndex - 1;
    const indices = prevPage >= 0 ? [displayPageIndex, prevPage] : [displayPageIndex];
    return indices;
  }

  const nextPage = displayPageIndex + 1;
  const indices = nextPage < comicTotalPages ? [displayPageIndex, nextPage] : [displayPageIndex];
  return indices;
}

export function loadComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (!wrapper) return;

  const loadTrace = createComicLoadTrace({
    activeBookId: state.activeBookId,
    currentPage: comicCurrentPage,
    totalPages: comicTotalPages,
    scrollMode
  });

  if (scrollProgressHandler) {
    wrapper.removeEventListener('scroll', scrollProgressHandler);
    scrollProgressHandler = null;
  }
  scrollPreloadTriggered = false;
  scrollNextEpisodeTriggered = false;

  if (observer) {
    observer.disconnect();
    observer = null;
  }

  if (scrollMode === 'scroll') {
    showViewerLoading('Loading...');
    loadTrace.log('scroll-mode loading overlay shown');

    wrapper.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const imgElements = [];
    let firstLoaded = false;

    const loadScrollImage = (img) => {
      if (!img || img.dataset.loaded === '1' || !img.dataset.src) return;
      const url = img.dataset.src;
      img.dataset.loaded = '1';

      loadTrace.log('scroll image fetch start', { index: img.dataset.index, url });

      const handleImgLoad = () => {
        loadTrace.log('scroll image loaded', { index: img.dataset.index });
        img.style.opacity = '1';
        img.style.minHeight = '0';
        if (!firstLoaded) {
          firstLoaded = true;
          loadTrace.log('scroll initial image visible');
          hideViewerLoading();
        }
      };

      img.onload = handleImgLoad;
      img.onerror = () => {
        loadTrace.log('scroll image load failed', { index: img.dataset.index });
        console.error(`[Viewer-Comic] Scroll image load failed: page_idx=${img.dataset.index}`);
        img.style.opacity = '1';
        img.style.minHeight = '0';
        if (!firstLoaded) {
          firstLoaded = true;
          hideViewerLoading();
        }
        showViewerError('Error', 'Failed to load image');
      };

      img.src = url;
    };

    const preloadScrollImagesAround = (baseIndex, leadCount = 20) => {
      for (let offset = 1; offset <= leadCount; offset++) {
        const nextImg = imgElements[baseIndex + offset];
        if (nextImg) {
          loadScrollImage(nextImg);
        }
      }
    };

    for (let i = 0; i < comicTotalPages; i++) {
      const img = document.createElement('img');
      img.className = 'comic-scroll-img';
      img.dataset.index = i;
      img.dataset.src = FileLoader.getPageStreamUrl(i);
      img.alt = `Page ${i + 1}`;
      img.dataset.loaded = '0';

      // 초기 로딩 시 깨진 이미지(엑박) 안 보이게 처리 (투명화 & 최소 높이)
      img.style.opacity = '0';
      img.style.transition = 'opacity 0.3s ease';
      img.style.minHeight = '60vh';

      fragment.appendChild(img);
      imgElements.push(img);
    }

    wrapper.appendChild(fragment);

    const observerOptions = {
      root: wrapper,
      rootMargin: '2000px',
      threshold: 0.1
    };

    observer = new IntersectionObserver((entries) => {
      if (isScrollingToTarget) return;

      let bestEntry = null;
      let maxRatio = 0;

      entries.forEach(entry => {
        if (entry.isIntersecting) {
          loadScrollImage(entry.target);
          if (entry.intersectionRatio > maxRatio) {
            maxRatio = entry.intersectionRatio;
            bestEntry = entry;
          }
        }
      });

      if (bestEntry) {
        const pageIdx = parseInt(bestEntry.target.dataset.index, 10);
        if (pageIdx !== comicCurrentPage) {
          comicCurrentPage = pageIdx;
          updatePageInfo();
          saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
        }
        preloadScrollImagesAround(pageIdx, 15);
      }
    }, observerOptions);

    imgElements.forEach(img => {
      observer.observe(img);
    });

    const progressHandler = () => {
      if (scrollPreloadTriggered || !state.activeBookId || comicTotalPages <= 1) return;

      const maxScrollTop = Math.max(1, wrapper.scrollHeight - wrapper.clientHeight);
      const scrollRatio = wrapper.scrollTop / maxScrollTop;
      if (scrollRatio < 0.9) return;

      scrollPreloadTriggered = true;
      saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);

      return;
    };

    // 스크롤 모드에서의 명시적인 최하단 오버 스크롤 감지 로직 (휠 & 드래그)
    let touchStartY = 0;
    let bottomReachedTime = 0;

    const handleScrollWheelNextEpisode = (e) => {
      if (scrollNextEpisodeTriggered || !state.activeBookId || comicTotalPages <= 0) return;
      if (comicCurrentPage < comicTotalPages - 1) return;

      const maxScrollTop = Math.max(1, wrapper.scrollHeight - wrapper.clientHeight);
      const isAtBottom = wrapper.scrollTop >= maxScrollTop - 16;

      if (!isAtBottom) {
        bottomReachedTime = 0;
        return;
      }

      // 최초 바닥 감지 시점 기록
      if (bottomReachedTime === 0) {
        bottomReachedTime = Date.now();
      }

      // 바닥 도달 후 최소 250ms가 경과하기 전에 연속으로 들어온 휠은 무시 (관성 휠 휩쓸림 방지)
      if (Date.now() - bottomReachedTime < 250) {
        return;
      }

      // 최하단이고, 휠을 아래로(deltaY > 0) 굴릴 때만
      if (e.deltaY > 0) {
        console.log("[Viewer-Comic] Bottom reached & wheel down. Triggering next episode modal.");
        scrollNextEpisodeTriggered = true;
        setTimeout(() => { scrollNextEpisodeTriggered = false; }, 2000);
        // 만화책 스크롤 모드에서는 휠 오버로 인한 불시 이동을 막기 위해 무조건 모달 확인을 거치도록 forceModal=true 인자를 지원하게끔 handleNextEpisodeDirect를 호출합니다.
        import('../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId, true));
      }
    };

    const handleScrollTouchStart = (e) => {
      if (e.touches && e.touches[0]) {
        touchStartY = e.touches[0].clientY;
      }
    };

    const handleScrollTouchEnd = (e) => {
      if (scrollNextEpisodeTriggered || !state.activeBookId || comicTotalPages <= 0) return;
      if (comicCurrentPage < comicTotalPages - 1) return;
      if (!e.changedTouches || !e.changedTouches[0]) return;

      const touchEndY = e.changedTouches[0].clientY;
      const diffY = touchStartY - touchEndY; // 양수이면 화면을 위로 쓸어올림 (아래로 더 보려 함)

      const maxScrollTop = Math.max(1, wrapper.scrollHeight - wrapper.clientHeight);
      const isAtBottom = wrapper.scrollTop >= maxScrollTop - 25; // 터치는 오차범위 25px 확보

      if (!isAtBottom) {
        bottomReachedTime = 0;
        return;
      }

      // 최초 바닥 감지 시점 기록
      if (bottomReachedTime === 0) {
        bottomReachedTime = Date.now();
      }

      // 바닥 도달 후 최소 250ms가 경과하기 전에 연속으로 들어온 터치는 무시
      if (Date.now() - bottomReachedTime < 250) {
        return;
      }

      // 최하단이고, 드래그하여 올린 거리가 40px 이상일 때
      if (diffY > 40) {
        console.log("[Viewer-Comic] Bottom reached & touch drag up. Triggering next episode modal.");
        scrollNextEpisodeTriggered = true;
        setTimeout(() => { scrollNextEpisodeTriggered = false; }, 2000);
        import('../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId, true));
      }
    };

    scrollProgressHandler = progressHandler;
    wrapper.addEventListener('scroll', scrollProgressHandler, { passive: true });
    wrapper.addEventListener('wheel', handleScrollWheelNextEpisode, { passive: true });

    wrapper.addEventListener('touchstart', handleScrollTouchStart, { passive: true });

    if (scrollTouchEndHandler) {
      wrapper.removeEventListener('touchend', scrollTouchEndHandler);
      wrapper.removeEventListener('touchcancel', scrollTouchEndHandler);
    }
    scrollTouchEndHandler = handleScrollTouchEnd;
    wrapper.addEventListener('touchend', scrollTouchEndHandler, { passive: true });
    wrapper.addEventListener('touchcancel', scrollTouchEndHandler, { passive: true });

    isScrollingToTarget = true;
    setTimeout(() => {
      const targetImg = imgElements[comicCurrentPage];
      if (targetImg) {
        loadScrollImage(targetImg);
        targetImg.scrollIntoView({ block: 'start' });
        preloadScrollImagesAround(comicCurrentPage, 15);
      }
      setTimeout(() => {
        isScrollingToTarget = false;
      }, 300);
    }, 100);

    updatePageInfo();

  } else {
    const pageIndices = getComicPageIndices();
    loadTrace.log('page-mode render start', { pageIndices });

    // 현재 페이지(들) 자체의 fetch를 기다리지 않고 다음 페이지 프리페치를 바로 같이 출발시킨다.
    // 예전엔 현재 페이지 이미지가 로드 완료된 뒤(onload)에야 preloadNextPages()가 시작돼서,
    // 프리페치 파이프라인이 항상 "현재 페이지 로딩 시간만큼" 늦게 출발했다 — 그래서 처음 펼친
    // 페이지(들) 다음 페이지부터는 프리페치가 못 따라잡고 매번 로딩이 뜨는 패턴이 반복됐다.
    // 지금은 현재 페이지 fetch와 다음 페이지 프리페치가 병렬로 같이 출발한다.
    loadTrace.log('page-mode preload started in parallel with current page fetch', { pageIndices });
    preloadNextPages();

    if (comicLoadingTimer) {
      clearTimeout(comicLoadingTimer);
      comicLoadingTimer = null;
    }

    const delayStr = localStorage.getItem('comic_loading_delay');
    const delay = (delayStr !== null) ? parseInt(delayStr, 10) : 700;

    let loadedCount = 0;
    const expectedLoads = pageIndices.length;
    // 2쪽 보기 모드에서 전체 페이지가 홀수라 마지막 한 장만 남는 경우.
    // (전체 1페이지짜리 도서에서 첫 장을 단독 표시하는 경우는 제외 — 그건 화면 꽉 채움이 맞다)
    const isTwoPageTailSingle = (scrollMode !== 'scroll') && Settings.getComicPageStep() === 2
      && expectedLoads === 1 && comicCurrentPage > 0;
    const imageElements = [];

    // 기존 페이지 페어 요소가 이미 렌더링되어 떠 있는지 확인합니다.
    const hasExistingPair = !!wrapper.querySelector('.comic-page-pair');
    loadTrace.log('page-mode loading timer scheduled', {
      delay,
      hasExistingPair,
      pageIndices
    });
    if (!hasExistingPair) {
      // 최초 기동 시에는 즉시 로딩을 보여줍니다.
      comicLoadingTimer = setTimeout(() => {
        loadTrace.log('page-mode loading overlay shown');
        showViewerLoading('Loading...', 'Preparing pages');
      }, delay);
    } else {
      // 기존에 떠 있는 페이지가 있을 경우에는 백그라운드 다운로드가 지정 시간보다 지체될 때만 지연 노출되도록 타이머 마진을 늘려줍니다.
      comicLoadingTimer = setTimeout(() => {
        loadTrace.log('page-mode loading overlay shown (existing pair)');
        showViewerLoading('Loading...', 'Preparing pages');
      }, delay + 400);
    }

    pageIndices.forEach((pageIndex, index) => {
      const imgEl = document.createElement('img');
      imgEl.className = `comic-page-img ${expectedLoads === 2 ? (index === 0 ? 'comic-page-img-left' : 'comic-page-img-right') : ''}`.trim();
      imgEl.dataset.index = pageIndex;
      imgEl.alt = `Page ${pageIndex + 1}`;
      imgEl.loading = 'eager';
      imgEl.style.opacity = '0';

      // onerror 중복 트리거 방지 플래그
      let _errorFired = false;

      imgEl.onload = () => {
        loadedCount += 1;
        imageElements[index] = imgEl;
        loadTrace.log('page image loaded', {
          pageIndex,
          loadedCount,
          expectedLoads
        });
        if (loadedCount === expectedLoads) {
          if (comicLoadingTimer) {
            clearTimeout(comicLoadingTimer);
            comicLoadingTimer = null;
          }

          // 이미지가 백그라운드 상에서 완전히 로드된 이 시점에만 기존 DOM을 밀고 새 페이지를 끼워넣습니다. (더블 버퍼링 기법)
          const removeCenterGap = (localStorage.getItem('remove_2page_center_gap') === '1');
          wrapper.innerHTML = `<div class="comic-page-pair ${removeCenterGap ? 'no-center-gap' : ''}" style="visibility: hidden;"></div>`;
          const pairContainer = wrapper.querySelector('.comic-page-pair');
          if (expectedLoads === 1 && pairContainer && !isTwoPageTailSingle) {
            pairContainer.classList.add('single-page');
          }

          imageElements.forEach((loadedImg) => {
            if (loadedImg) {
              loadedImg.style.opacity = '1';
              if (isTwoPageTailSingle) {
                loadedImg.classList.add('comic-page-img-left');
              }
              pairContainer.appendChild(loadedImg);
            }
          });
          if (isTwoPageTailSingle) {
            const blankSlot = document.createElement('div');
            blankSlot.className = 'comic-page-blank-slot';
            pairContainer.appendChild(blankSlot);
          }
          pairContainer.style.visibility = 'visible';
          loadTrace.log('page images committed to DOM', {
            pageIndices,
            expectedLoads
          });
          hideViewerLoading();
          loadTrace.log('page-mode loading overlay hidden');


          if (comicCurrentPage === 0 && expectedLoads === 1) {
            const aspectRatio = imageElements[0].naturalWidth / imageElements[0].naturalHeight;
            if (aspectRatio < 0.7) {
              setComicFitMode('width');
            } else {
              setComicFitMode('height');
            }
          }
        }
      };

      imgEl.onerror = () => {
        if (_errorFired) return; // Worker fallback 재시도 시 중복 onerror 방지
        _errorFired = true;
        loadTrace.log('page image load failed', { pageIndex });
        console.error(`[Viewer-Comic] Image load failed: page_idx=${pageIndex}`);
        if (comicLoadingTimer) {
          clearTimeout(comicLoadingTimer);
          comicLoadingTimer = null;
        }
        showViewerError('Error', 'Failed to load image');
      };

      // 🌟 Blob 캐시 맵에서 Object URL을 즉시 히트하여 브라우저 대기 및 지연 제거 (BookId 바인딩)
      const currentBookId = state.activeBookId;
      if (splitModeActive) {
        const { physical, side } = splitVirtualIndex(pageIndex);
        loadTrace.log('page image (split) fetch start', { pageIndex, physical, side });
        getSplitCroppedImageUrl(currentBookId, pageIndex, physical, side)
          .then((url) => {
            const activeBookId = state.activeBookId;
            if (activeBookId !== currentBookId) return;
            loadTrace.log('page image (split) crop ready', { pageIndex, physical, side });
            imgEl.src = url;
          })
          .catch((err) => {
            loadTrace.log('page image (split) crop failed', { pageIndex, error: String(err) });
            imgEl.onerror();
          });
      } else {
        const cacheKey = `${currentBookId}_${pageIndex}`;
        if (blobCacheMap.has(cacheKey)) {
          loadTrace.log('page image cache hit', { pageIndex, cacheKey });
          imgEl.src = blobCacheMap.get(cacheKey);
        } else {
          loadTrace.log('page image fetch start', { pageIndex, cacheKey });
          getWholePageObjectUrl(currentBookId, pageIndex).then((url) => {
            const activeBookId = state.activeBookId;
            if (activeBookId !== currentBookId) return;
            loadTrace.log('page image blob ready', { pageIndex });
            imgEl.src = url;
          });
        }
      }
    });

    updatePageInfo();
    if (!isInitializingProgress) {
      const { page: physicalPage, total: physicalTotal } = getPhysicalProgress();
      saveProgress(state.activeBookId, physicalPage, physicalTotal);
    }
    loadTrace.log('page-mode render setup complete');
  }
}

function syncSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  if (!slider) return;
  slider.max = comicTotalPages || 1;
  slider.value = comicCurrentPage + 1;
  const endLabel = document.getElementById('seekbar-end-label');
  if (endLabel) endLabel.textContent = comicTotalPages || '?';
}

export function showSeekbarTooltip(slider, page) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (!tooltip) return;

  const min = parseInt(slider.min, 10) || 1;
  const max = parseInt(slider.max, 10) || 1;
  const ratio = (page - min) / (max - min || 1);
  const trackWidth = slider.offsetWidth;
  const thumbHalf = 9;
  const leftPx = thumbHalf + ratio * (trackWidth - thumbHalf * 2);

  tooltip.textContent = page;
  tooltip.style.left = `${leftPx}px`;
  tooltip.classList.add('visible');
}

export function hideSeekbarTooltip() {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) tooltip.classList.remove('visible');
}

// 서버 쪽 백그라운드 프리페치(stream_page_service.py)도 스레드풀 4개로 병렬 처리하므로
// 클라이언트 큐도 같은 폭으로 맞춘다. 순수 직렬(1개씩)로 받으면 페이지당 왕복 지연이 있는
// 원격(gdrive) 도서에서 빠르게 넘기는 속도를 못 따라가 "1~2페이지 이후 로딩"이 반복됐다.
const PRELOAD_CONCURRENCY = 4;

async function _preloadWorker(currentBookId) {
  while (currentPreloadQueue.length > 0) {
    // shift()는 동기 호출이라 await 지점이 끼어들기 전에 각 워커가 서로 다른 인덱스를 가져가므로
    // 별도 락 없이도 워커 간 중복 소비가 발생하지 않는다.
    const nextIdx = currentPreloadQueue.shift();
    if (nextIdx === undefined) break;

    // 책이 닫혔거나 다른 책으로 전환되었다면 워커 즉시 탈출
    const activeBookId = state.activeBookId;
    if (activeBookId !== currentBookId) {
      break;
    }

    // 범위 검사 및 이미 캐싱된 것은 패스 (분할 모드에서도 프리로드 대상은 항상 물리 페이지 인덱스)
    const cacheKey = `${currentBookId}_${nextIdx}`;
    if (nextIdx >= getPhysicalTotalPages() || nextIdx < 0 || blobCacheMap.has(cacheKey)) {
      continue;
    }

    try {
      const url = FileLoader.getPageStreamUrl(nextIdx);
      // 현재 페이지 fetch(priority: 'high')에 대역폭/커넥션 우선순위를 양보한다 —
      // 프리페치를 현재 페이지와 병렬로 미리 출발시키되, 초기 로딩 자체가 느려지지 않도록.
      const response = await fetch(url, { priority: 'low' });
      if (response.ok) {
        const blob = await response.blob();

        // 비동기 fetch가 완료된 시점에 다시 한 번 책 전환 여부 체크
        const postActiveBookId = state.activeBookId;
        if (postActiveBookId !== currentBookId) {
          break;
        }

        const objectUrl = URL.createObjectURL(blob);
        blobCacheMap.set(cacheKey, objectUrl);
      }
    } catch (e) {
      console.error(`[Preload-Blob Fail] Page ${nextIdx}:`, e);
    }
  }
}

async function startSequentialPreload(pageList) {
  const currentBookId = state.activeBookId;
  currentPreloadQueue = pageList;
  if (isPreloading) return;

  isPreloading = true;
  try {
    await Promise.all(
      Array.from({ length: PRELOAD_CONCURRENCY }, () => _preloadWorker(currentBookId))
    );
  } finally {
    isPreloading = false;
  }
}

function preloadNextPages() {
  // 이전 펜딩된 프리로드 이미지들의 다운로드를 강제 차단하여 브라우저 HTTP 커넥션 큐를 확보
  activePreloadSet.forEach(img => {
    img.onload = null;
    img.onerror = null;
    img.src = ""; 
  });
  activePreloadSet.clear();

  const preloadCount = 10;
  const basePage = getComicDisplayPageIndex(comicCurrentPage);
  // 분할 모드에서는 양쪽 절반이 같은 물리 이미지를 공유하므로 물리 페이지 기준으로만 프리로드한다.
  const basePhysical = splitModeActive ? splitVirtualIndex(basePage).physical : basePage;
  const physicalTotal = getPhysicalTotalPages();

  const pagesToLoad = [];
  for (let i = 1; i <= preloadCount; i++) {
    const nextIdx = basePhysical + i;
    if (nextIdx < physicalTotal) {
      pagesToLoad.push(nextIdx);
    }
  }

  // 🌟 공유 큐 기반 병렬(4-워커) 백그라운드 프리로드 시작
  startSequentialPreload(pagesToLoad);
}

export function clearComicViewer() {
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (wrapper) {
    if (scrollProgressHandler) {
      wrapper.removeEventListener('scroll', scrollProgressHandler);
      scrollProgressHandler = null;
    }
    if (scrollTouchEndHandler) {
      wrapper.removeEventListener('touchend', scrollTouchEndHandler);
      wrapper.removeEventListener('touchcancel', scrollTouchEndHandler);
      scrollTouchEndHandler = null;
    }
    wrapper.innerHTML = '';
  }
  if (scrollEndCheckTimer) {
    clearTimeout(scrollEndCheckTimer);
    scrollEndCheckTimer = null;
  }
  scrollPreloadTriggered = false;
  scrollNextEpisodeTriggered = false;
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  if (comicLoadingTimer) {
    clearTimeout(comicLoadingTimer);
    comicLoadingTimer = null;
  }
  activePreloadSet.clear();
  clearBlobCache();
}
