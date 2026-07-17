// input_controller.js - keyboard/wheel/hotspot/click input handlers for viewer
import { state } from '../state.js';

let _deps = {
  toggleFullscreenViewer: null,
  isViewerInFullscreen: null,
  closeMediaViewer: null,
  nextPage: null,
  prevPage: null,
  toggleComicOverlay: null,
};

let keyboardListenerInitialized = false;
let wheelLock = false;
let viewerClickToggleInited = false;

export function configureInputController(deps = {}) {
  _deps = { ..._deps, ...deps };
}

function callDep(name, ...args) {
  const fn = _deps[name];
  if (typeof fn === 'function') {
    return fn(...args);
  }
  return undefined;
}

export function initKeyboardListener() {
  if (keyboardListenerInitialized) return;
  keyboardListenerInitialized = true;

  document.addEventListener('keydown', (e) => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;

    switch (e.key) {
      case 'f':
      case 'F':
        e.preventDefault();
        callDep('toggleFullscreenViewer');
        break;
      case 'Escape': {
        const inFullscreen = !!(
          viewerModal.classList.contains('fullscreen-mode') ||
          (typeof _deps.isViewerInFullscreen === 'function' && _deps.isViewerInFullscreen())
        );
        if (inFullscreen) {
          callDep('toggleFullscreenViewer');
        } else {
          callDep('closeMediaViewer');
        }
        break;
      }
      case 'ArrowRight':
      case ' ':
        e.preventDefault();
        callDep('nextPage');
        break;
      case 'ArrowLeft':
        e.preventDefault();
        callDep('prevPage');
        break;
      default:
        break;
    }
  });

  initWheelListener();
  initViewerClickToggle();
  syncHotspotPointerEvents();
}

export function initWheelListener() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (!hotspot) return;

  hotspot.addEventListener(
    'contextmenu',
    (e) => {
      const viewerModal = document.getElementById('media-viewer-modal');
      if (!viewerModal || viewerModal.style.display !== 'flex') return;

      const fmt = (state.currentViewerFormat || '').toLowerCase();
      const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
      if (fmt === 'epub' && scrollMode === 'page') {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    true
  );

  hotspot.addEventListener(
    'wheel',
    (e) => {
      const viewerModal = document.getElementById('media-viewer-modal');
      if (!viewerModal || viewerModal.style.display !== 'flex') return;

      const isComic = document.getElementById('comic-viewer-container').style.display !== 'none';
      const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
      const isComicScroll = isComic && scrollMode === 'scroll';
      const comicImageWrapper = document.querySelector('.comic-image-wrapper');
      const isComicWidth = isComic && comicImageWrapper && comicImageWrapper.classList.contains('fit-width');
      const isTxt = document.getElementById('txt-viewer-container').style.display !== 'none';
      const isPdf = document.getElementById('pdf-viewer-container').style.display !== 'none';
      const epubEl = document.getElementById('epub-viewer-container');
      const isEpub = epubEl ? epubEl.style.display !== 'none' : false;

      // 1. Scroll-capable mode delegates wheel to native container scrolling.
      if (isComicScroll || isComicWidth || (isTxt && scrollMode === 'scroll')) {
        let targetScrollEl = null;
        if (isComicScroll || isComicWidth) {
          targetScrollEl = comicImageWrapper;
        } else if (isTxt) {
          targetScrollEl = document.getElementById('txt-scroll-wrapper');
        }

        if (targetScrollEl) {
          targetScrollEl.scrollBy({
            top: e.deltaY,
            behavior: 'auto',
          });
          e.preventDefault();
          return;
        }
      }

      // 2. EPUB scroll mode forwards wheel into iframe document.
      if (isEpub && scrollMode === 'scroll') {
        const iframe = document.querySelector('#epub-render-area iframe');
        if (iframe && iframe.contentWindow) {
          iframe.contentWindow.scrollBy(0, e.deltaY);
          e.preventDefault();
          return;
        }
      }

      // 3. Page-turn mode routes wheel events to prev/next actions.
      if (scrollMode === 'page' || (isComic && !isComicWidth) || isPdf || isTxt || isEpub) {
        e.preventDefault();
        if (wheelLock) return;

        if (e.deltaY > 30) {
          wheelLock = true;
          callDep('nextPage');
          setTimeout(() => {
            wheelLock = false;
          }, 600);
        } else if (e.deltaY < -30) {
          wheelLock = true;
          callDep('prevPage');
          setTimeout(() => {
            wheelLock = false;
          }, 600);
        }
      }
    },
    { passive: false }
  );
}

export function syncHotspotPointerEvents() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!hotspot || !viewerModal) {
    console.warn('[syncHotspotPointerEvents] hotspot 또는 viewerModal이 존재하지 않습니다.');
    return;
  }

  if (viewerModal.style.display !== 'flex') {
    console.log('[syncHotspotPointerEvents] 뷰어 모달이 flex 상태가 아님. 생략.');
    return;
  }

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const fmt = (state.currentViewerFormat || '').toLowerCase();
  const isComic = fmt === 'zip' || fmt === 'cbz';
  const isTxt = fmt === 'txt';
  const isEpub = fmt === 'epub';

  const isScrollActive = scrollMode === 'scroll' && (isComic || isTxt || isEpub);

  console.log(
    `[syncHotspotPointerEvents] format=${fmt}, scrollMode=${scrollMode}, isScrollActive=${isScrollActive}, isEpub=${isEpub}`
  );

  if (isEpub) {
    viewerModal.classList.remove('scroll-mode-active');
    document.body.style.overflow = 'hidden';
  } else {
    viewerModal.classList.toggle('scroll-mode-active', isScrollActive);
    document.body.style.overflow = isScrollActive ? 'auto' : 'hidden';
  }

  const shouldHideHotspot = (isEpub && scrollMode === 'scroll') || isScrollActive;
  if (shouldHideHotspot) {
    hotspot.style.display = 'none';
    console.log('[syncHotspotPointerEvents] 핫스팟 비활성화(none) 적용됨.');
  } else {
    hotspot.style.display = 'flex';
    console.log('[syncHotspotPointerEvents] 핫스팟 활성화(flex) 적용됨.');
  }
}

export function initViewerClickToggle() {
  const viewerBody = document.getElementById('viewer-body-container');
  if (!viewerBody || viewerClickToggleInited) return;
  viewerClickToggleInited = true;

  const TAP_THRESHOLD = 10;
  let touchStartX = null;
  let touchStartY = null;
  let touchStartClientX = null;
  let lastTouchEndTime = 0;

  document.addEventListener(
    'touchstart',
    (e) => {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchStartClientX = e.touches[0].clientX;
      }
    },
    { passive: true }
  );

  document.addEventListener(
    'touchmove',
    (e) => {
      if (touchStartX === null) return;
      const dx = Math.abs(e.touches[0].clientX - touchStartX);
      const dy = Math.abs(e.touches[0].clientY - touchStartY);
      if (dx > TAP_THRESHOLD || dy > TAP_THRESHOLD) {
        touchStartX = null;
        touchStartY = null;
      }
    },
    { passive: true }
  );

  document.addEventListener(
    'touchend',
    (e) => {
      if (touchStartX === null) return;

      const endX = touchStartClientX;
      touchStartX = null;
      touchStartY = null;
      touchStartClientX = null;

      const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
      if (scrollMode !== 'scroll') return;

      const target = e.target || document.elementFromPoint(endX, window.innerHeight / 2);
      if (!target) return;
      if (
        target.closest('#comic-overlay-menu') ||
        target.closest('.viewer-controls') ||
        target.closest('.floating-close-btn') ||
        target.closest('#common-viewer-hotspot') ||
        target.closest('button') ||
        target.closest('input') ||
        target.closest('select')
      ) {
        return;
      }

      const viewerModal = document.getElementById('media-viewer-modal');
      if (!viewerModal || viewerModal.style.display !== 'flex') return;

      const width = window.innerWidth;
      console.log(`[Viewer-Touch-Toggle] touchend tap: endX=${endX}, width=${width}, ratio=${endX / width}`);

      if (endX >= width * 0.3 && endX <= width * 0.7) {
        console.log('[Viewer-Touch-Toggle] Triggering toggleComicOverlay() from touchend');
        lastTouchEndTime = Date.now();
        callDep('toggleComicOverlay');
      }
    },
    { passive: true }
  );

  viewerBody.addEventListener('click', (e) => {
    if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;
    if (e.pointerType === 'touch') return;
    if (Date.now() - lastTouchEndTime < 500) return;

    console.log('[Viewer-Click-Toggle] Mouse click detected. Target:', e.target);

    if (
      e.target.closest('#comic-overlay-menu') ||
      e.target.closest('.viewer-controls') ||
      e.target.closest('.floating-close-btn') ||
      e.target.closest('#common-viewer-hotspot') ||
      e.target.closest('button') ||
      e.target.closest('input') ||
      e.target.closest('select')
    ) {
      return;
    }

    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode === 'scroll') {
      const clickX = e.clientX;
      const width = window.innerWidth;
      if (clickX >= width * 0.3 && clickX <= width * 0.7) {
        console.log('[Viewer-Click-Toggle] Triggering toggleComicOverlay() from mouse click');
        callDep('toggleComicOverlay');
      }
    }
  });
}
