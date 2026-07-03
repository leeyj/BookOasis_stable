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
let imageWorker = null;
let _workerRequestId = 1;
const _workerPending = new Map();
let _workerCleanupAdded = false;

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
      try { imageWorker && imageWorker.terminate(); } catch (e) {}
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
  document.getElementById('comic-viewer-container').style.display = 'flex';
  document.getElementById('comic-fit-controls').style.display = 'flex';

  comicCurrentPage = pagesRead > 0 ? pagesRead - 1 : 0;
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
  
  if (state.currentViewerFormat === 'epub') {
    const slider = document.getElementById('viewer-page-slider');
    if (slider && overlayInfoEl) {
      overlayInfoEl.textContent = `${slider.value}%`;
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

    for (let i = 0; i < comicTotalPages; i++) {
      const img = document.createElement('img');
      img.className = 'comic-scroll-img';
      img.dataset.index = i;
      img.dataset.src = FileLoader.getPageStreamUrl(i);
      img.alt = `Page ${i + 1}`;
      img.loading = 'lazy';
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
      rootMargin: '0px',
      threshold: 0.3
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
      }
    }, observerOptions);

    imgElements.forEach(img => {
      observer.observe(img);
    });

    isScrollingToTarget = true;
    setTimeout(() => {
      const targetImg = imgElements[comicCurrentPage];
      if (targetImg) {
        loadScrollImage(targetImg);
        targetImg.scrollIntoView({ block: 'start' });
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

    comicLoadingTimer = setTimeout(() => {
      document.querySelectorAll('.comic-page-img').forEach(img => img.style.opacity = '0');
      showViewerLoading('Loading...', 'Preparing pages');
    }, delay);

    wrapper.innerHTML = '<div class="comic-page-pair" style="visibility: hidden;"></div>';
    const pairContainer = wrapper.querySelector('.comic-page-pair');
    if (pageIndices.length === 1 && pairContainer) {
      pairContainer.classList.add('single-page');
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
          pairContainer.innerHTML = '';
          imageElements.forEach((loadedImg) => {
            if (loadedImg) {
              loadedImg.style.opacity = '1';
              pairContainer.appendChild(loadedImg);
            }
          });
          pairContainer.style.visibility = 'visible';
          hideViewerLoading();

          if (comicCurrentPage === 0 && pageIndices.length === 1) {
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
        imgEl.style.opacity = '1';
      };

      const url = FileLoader.getPageStreamUrl(pageIndex);
      imgEl.src = url;
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

function preloadNextPages() {
  const preloadCount = 2;
  const basePage = getComicDisplayPageIndex(comicCurrentPage);
  for (let i = 1; i <= preloadCount; i++) {
    const nextIdx = basePage + i;
    if (nextIdx < comicTotalPages) {
      const preloadImg = new Image();
      preloadImg.src = FileLoader.getPageStreamUrl(nextIdx);
    }
  }
}
