// renderer.js — 이미지 삽입 및 렌더링 로직
import { state } from '../state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from '../view_manager.js';
import { saveProgress } from '../viewer_progress.js';
import * as Settings from './reader_settings.js';
import * as FileLoader from './fileloader.js';

export let comicCurrentPage = 0;
export let comicTotalPages = 0;
let comicLoadingTimer = null;
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
let currentPreloadQueue = [];
let isPreloading = false;

function clearBlobCache() {
  blobCacheMap.forEach((objectUrl) => {
    try {
      URL.revokeObjectURL(objectUrl);
    } catch (e) {}
  });
  blobCacheMap.clear();
  currentPreloadQueue = [];
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

export async function initRenderer(bookId, pagesRead, totalPages) {
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

  Settings.initReadingDirection();
  Settings.initPageStep();
  Settings.initScrollWidth(); // 저장된 스크롤 너비 복원
  applyComicFitMode();
  loadComicPage();
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
  const infoEl = document.getElementById('comic-page-info');
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

  if (infoEl) infoEl.textContent = textInfo;
  if (overlayInfoEl) overlayInfoEl.textContent = textInfo;

  const overlayTitleEl = document.getElementById('overlay-title-text');
  if (overlayTitleEl) overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;

  syncSeekBar();
}

function getComicDisplayPageIndex(basePage) {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const displayPage = (scrollMode === 'scroll' || Settings.getComicPageStep() !== 2)
    ? basePage
    : (Settings.getComicReadingDirection() === 'rtl'
      ? Math.min(basePage + 1, Math.max(0, comicTotalPages - 1))
      : basePage);
  return displayPage;
}

function getComicPageIndices() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const displayPageIndex = getComicDisplayPageIndex(comicCurrentPage);
  if (scrollMode === 'scroll' || Settings.getComicPageStep() !== 2) {
    return [displayPageIndex];
  }

  if (Settings.getComicReadingDirection() === 'rtl') {
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

    wrapper.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const imgElements = [];
    let firstLoaded = false;

    const loadScrollImage = (img) => {
      if (!img || img.dataset.loaded === '1' || !img.dataset.src) return;
      const url = img.dataset.src;
      img.dataset.loaded = '1';

      const handleImgLoad = () => {
        img.style.opacity = '1';
        img.style.minHeight = '0';
        if (!firstLoaded) {
          firstLoaded = true;
          hideViewerLoading();
        }
      };

      img.onload = handleImgLoad;
      img.onerror = () => {
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

    if (comicLoadingTimer) {
      clearTimeout(comicLoadingTimer);
      comicLoadingTimer = null;
    }

    const delayStr = localStorage.getItem('comic_loading_delay');
    const delay = (delayStr !== null) ? parseInt(delayStr, 10) : 300;

    // 기존 페이지 페어 요소가 이미 렌더링되어 떠 있는지 확인합니다.
    const hasExistingPair = !!wrapper.querySelector('.comic-page-pair');
    if (!hasExistingPair) {
      // 최초 기동 시에는 즉시 로딩을 보여줍니다.
      comicLoadingTimer = setTimeout(() => {
        showViewerLoading('Loading...', 'Preparing pages');
      }, delay);
    } else {
      // 기존에 떠 있는 페이지가 있을 경우에는 백그라운드 다운로드가 지정 시간보다 지체될 때만 지연 노출되도록 타이머 마진을 늘려줍니다.
      comicLoadingTimer = setTimeout(() => {
        showViewerLoading('Loading...', 'Preparing pages');
      }, delay + 100);
    }

    let loadedCount = 0;
    const expectedLoads = pageIndices.length;
    const imageElements = [];

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
        if (loadedCount === expectedLoads) {
          if (comicLoadingTimer) {
            clearTimeout(comicLoadingTimer);
            comicLoadingTimer = null;
          }

          // 이미지가 백그라운드 상에서 완전히 로드된 이 시점에만 기존 DOM을 밀고 새 페이지를 끼워넣습니다. (더블 버퍼링 기법)
          const removeCenterGap = (localStorage.getItem('remove_2page_center_gap') === '1');
          wrapper.innerHTML = `<div class="comic-page-pair ${removeCenterGap ? 'no-center-gap' : ''}" style="visibility: hidden;"></div>`;
          const pairContainer = wrapper.querySelector('.comic-page-pair');
          if (expectedLoads === 1 && pairContainer) {
            pairContainer.classList.add('single-page');
          }

          imageElements.forEach((loadedImg) => {
            if (loadedImg) {
              loadedImg.style.opacity = '1';
              pairContainer.appendChild(loadedImg);
            }
          });
          pairContainer.style.visibility = 'visible';
          hideViewerLoading();

          if (comicCurrentPage === 0 && expectedLoads === 1) {
            const aspectRatio = imageElements[0].naturalWidth / imageElements[0].naturalHeight;
            if (aspectRatio < 0.7) {
              setComicFitMode('width');
            } else {
              setComicFitMode('height');
            }
          }

          preloadNextPages();
        }
      };

      imgEl.onerror = () => {
        if (_errorFired) return; // Worker fallback 재시도 시 중복 onerror 방지
        _errorFired = true;
        console.error(`[Viewer-Comic] Image load failed: page_idx=${pageIndex}`);
        if (comicLoadingTimer) {
          clearTimeout(comicLoadingTimer);
          comicLoadingTimer = null;
        }
        showViewerError('Error', 'Failed to load image');
      };

      // 🌟 Blob 캐시 맵에서 Object URL을 즉시 히트하여 브라우저 대기 및 지연 제거
      if (blobCacheMap.has(pageIndex)) {
        imgEl.src = blobCacheMap.get(pageIndex);
      } else {
        const url = FileLoader.getPageStreamUrl(pageIndex);
        fetch(url)
          .then((res) => {
            if (!res.ok) throw new Error('Fetch fail');
            return res.blob();
          })
          .then((blob) => {
            const objUrl = URL.createObjectURL(blob);
            blobCacheMap.set(pageIndex, objUrl);
            imgEl.src = objUrl;
          })
          .catch((err) => {
            // fetch 에러 시 원본 뷰어 스트림 경로로 폴백 복구
            imgEl.src = url;
          });
      }
    });

    updatePageInfo();
    saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
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

async function startSequentialPreload(pageList) {
  const currentBookId = state.currentBookId || (window.state ? window.state.currentBookId : null);
  currentPreloadQueue = pageList;
  if (isPreloading) return;

  isPreloading = true;
  while (currentPreloadQueue.length > 0) {
    const nextIdx = currentPreloadQueue.shift();

    // 책이 닫혔거나 다른 책으로 전환되었다면 루프 즉시 탈출
    const activeBookId = state.currentBookId || (window.state ? window.state.currentBookId : null);
    if (activeBookId !== currentBookId) {
      break;
    }

    // 범위 검사 및 이미 캐싱된 것은 패스
    if (nextIdx >= comicTotalPages || nextIdx < 0 || blobCacheMap.has(nextIdx)) {
      continue;
    }

    try {
      const url = FileLoader.getPageStreamUrl(nextIdx);
      const response = await fetch(url);
      if (response.ok) {
        const blob = await response.blob();
        
        // 비동기 fetch가 완료된 시점에 다시 한 번 책 전환 여부 체크
        const postActiveBookId = state.currentBookId || (window.state ? window.state.currentBookId : null);
        if (postActiveBookId !== currentBookId) {
          break;
        }

        const objectUrl = URL.createObjectURL(blob);
        blobCacheMap.set(nextIdx, objectUrl);
      }
    } catch (e) {
      console.error(`[Preload-Blob Fail] Page ${nextIdx}:`, e);
    }
  }
  isPreloading = false;
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
  
  const pagesToLoad = [];
  for (let i = 1; i <= preloadCount; i++) {
    const nextIdx = basePage + i;
    if (nextIdx < comicTotalPages) {
      pagesToLoad.push(nextIdx);
    }
  }

  // 🌟 순차적 큐 기반 백그라운드 프리로드 시작
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
