// input_controller.js - keyboard/wheel/hotspot/click input handlers for viewer
import { state } from '../state.js';
import { shouldUseAndroidHotspotTouchFallback } from './platform_profile.js';

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

// 만화 뷰어에서 RTL(우->좌) 읽기 방향이 활성화되어 있는지 여부.
// 화면 좌/우 핫스팟 클릭처럼 물리적 화면 위치에 반응하는 조작에서만 사용한다.
function isComicRtlActive() {
  const isComicFormat = ['zip', 'cbz', 'imgdir'].includes((state.currentViewerFormat || '').toLowerCase());
  if (!isComicFormat) return false;
  return (typeof window.Settings !== 'undefined' && typeof window.Settings.getComicReadingDirection === 'function')
    ? window.Settings.getComicReadingDirection() === 'rtl'
    : localStorage.getItem('comic_reading_direction') === 'rtl';
}

function handleViewerKeydown(e) {
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal || viewerModal.style.display !== 'flex') return;

  if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT' || e.target.isContentEditable)) {
    return;
  }

  // 커스텀 매핑 키 (기본값 + localStorage 커스텀 지정키)
  const customNextKeys = (localStorage.getItem('custom_key_next') || 'ArrowRight,Space,PageDown,VolumeDown,ChannelDown,AudioVolumeDown').split(',').map(k => k.trim().toLowerCase());
  const customPrevKeys = (localStorage.getItem('custom_key_prev') || 'ArrowLeft,PageUp,VolumeUp,ChannelUp,AudioVolumeUp').split(',').map(k => k.trim().toLowerCase());
  const customCloseKeys = (localStorage.getItem('custom_key_close') || 'Escape').split(',').map(k => k.trim().toLowerCase());
  const customDashboardKeys = (localStorage.getItem('custom_key_dashboard') || 'Home').split(',').map(k => k.trim().toLowerCase());

  const rawKey = (e.key || '').toLowerCase();
  const codeKey = (e.code || '').toLowerCase();

  // 스페이스바, 화살표, 페이지키, 엔터 등 이중 교차 검증
  const isSpaceKey = rawKey === ' ' || rawKey === 'space' || codeKey === 'space';
  const isArrowRight = rawKey === 'arrowright' || codeKey === 'arrowright';
  const isArrowLeft = rawKey === 'arrowleft' || codeKey === 'arrowleft';
  const isPageDown = rawKey === 'pagedown' || codeKey === 'pagedown';
  const isPageUp = rawKey === 'pageup' || codeKey === 'pageup';
  const isEscapeKey = rawKey === 'escape' || codeKey === 'escape';
  const isEnterKey = rawKey === 'enter' || rawKey === 'return' || codeKey === 'enter';

  // [다음 편 이어서 보기 모달] 노출 중 물리키 및 단축키 핸들링
  const nextModal = document.getElementById('viewer-next-episode-modal');
  if (nextModal && nextModal.style.display !== 'none' && nextModal.style.display !== '') {
    const confirmBtn = document.getElementById('viewer-next-episode-confirm-btn');
    const cancelBtn = document.getElementById('viewer-next-episode-cancel-btn');

    if (isEscapeKey || customCloseKeys.includes(rawKey) || customCloseKeys.includes(codeKey)) {
      e.preventDefault();
      if (cancelBtn) cancelBtn.click();
      return;
    }

    const isNavKeyHit = isEnterKey || isSpaceKey || isArrowRight || isArrowLeft || isPageDown || isPageUp ||
                        customNextKeys.some(k => k === rawKey || k === codeKey || (k === 'space' && isSpaceKey)) ||
                        customPrevKeys.some(k => k === rawKey || k === codeKey || (k === 'space' && isSpaceKey));

    if (isNavKeyHit && confirmBtn) {
      e.preventDefault();
      confirmBtn.click();
      return;
    }
  }

  if (e.key === 'f' || e.key === 'F' || codeKey === 'keyf') {
    e.preventDefault();
    callDep('toggleFullscreenViewer');
    return;
  }

  if (isEscapeKey || customCloseKeys.includes(rawKey) || customCloseKeys.includes(codeKey)) {
    const inFullscreen = !!(
      viewerModal.classList.contains('fullscreen-mode') ||
      (typeof _deps.isViewerInFullscreen === 'function' && _deps.isViewerInFullscreen())
    );
    e.preventDefault();
    if (inFullscreen) {
      callDep('toggleFullscreenViewer');
    } else {
      callDep('closeMediaViewer');
    }
    return;
  }

  if (customDashboardKeys.includes(rawKey) || customDashboardKeys.includes(codeKey) || (e.altKey && (rawKey === 'home' || codeKey === 'home'))) {
    e.preventDefault();
    callDep('closeMediaViewer');
    if (typeof window.showDashboardView === 'function') window.showDashboardView();
    return;
  }

  const isRtl = isComicRtlActive();

  // 화살표 키는 아래 3번에서 읽는 방향(RTL/LTR)에 따라 별도로 분기 처리하므로,
  // 커스텀 Next/Prev 키 기본값에 포함된 ArrowRight/ArrowLeft는 여기서 매칭 대상에서 제외한다.
  // (제외하지 않으면 이 매칭이 먼저 걸려 아래 RTL 분기가 항상 무시됨)
  const isDirectionalArrowKey = (k) => k === 'arrowright' || k === 'arrowleft';

  // 1. 스페이스바, PageDown, 커스텀 Next 키는 읽는 방향에 상관없이 무조건 '다음 스토리 내용(nextPage)'
  const isForwardAction = isSpaceKey || isPageDown ||
                          customNextKeys.some(k => !isDirectionalArrowKey(k) && (k === rawKey || k === codeKey || (k === 'space' && isSpaceKey)));

  // 2. PageUp, 커스텀 Prev 키는 읽는 방향에 상관없이 무조건 '이전 스토리 내용(prevPage)'
  const isBackwardAction = isPageUp ||
                           customPrevKeys.some(k => !isDirectionalArrowKey(k) && (k === rawKey || k === codeKey || (k === 'space' && isSpaceKey)));

  if (isForwardAction) {
    e.preventDefault();
    callDep('nextPage');
    return;
  }

  if (isBackwardAction) {
    e.preventDefault();
    callDep('prevPage');
    return;
  }

  // 3. 화살표 키 (LTR / RTL 시각적 책장 방향 분기)
  if (isArrowRight) {
    e.preventDefault();
    if (isRtl) {
      callDep('prevPage'); // RTL(일본만화): 오른쪽 화살표는 이전 내용
    } else {
      callDep('nextPage'); // LTR(일반도서): 오른쪽 화살표는 다음 내용
    }
    return;
  }

  if (isArrowLeft) {
    e.preventDefault();
    if (isRtl) {
      callDep('nextPage'); // RTL(일본만화): 왼쪽 화살표는 다음 내용
    } else {
      callDep('prevPage'); // LTR(일반도서): 왼쪽 화살표는 이전 내용
    }
    return;
  }
}

export function initKeyboardListener() {
  if (keyboardListenerInitialized) return;
  keyboardListenerInitialized = true;

  document.addEventListener('keydown', handleViewerKeydown);

  // Attach keydown listener bridge to iframe document (for EPUB etc)
  document.addEventListener('click', () => {
    const iframe = document.querySelector('#epub-render-area iframe');
    if (iframe && iframe.contentDocument && !iframe.contentDocument.__keyboardBridgeInited) {
      iframe.contentDocument.__keyboardBridgeInited = true;
      iframe.contentDocument.addEventListener('keydown', handleViewerKeydown);
    }
  }, true);

  initWheelListener();
  initViewerClickToggle();
  syncHotspotPointerEvents();
}

export function initWheelListener() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (!hotspot) return;

  if (shouldUseAndroidHotspotTouchFallback() && !hotspot.dataset.androidTapBound) {
    hotspot.dataset.androidTapBound = '1';

    hotspot.addEventListener(
      'touchend',
      (e) => {
        const viewerModal = document.getElementById('media-viewer-modal');
        if (!viewerModal || viewerModal.style.display !== 'flex') return;

        const target = e.target;
        if (!target || typeof target.closest !== 'function') return;

        // Android 일부 환경에서 onclick/click 합성이 누락되는 케이스를 우회한다.
        if (target.closest('.center-zone')) {
          e.preventDefault();
          e.stopPropagation();
          callDep('toggleComicOverlay');
          return;
        }

        if (target.closest('.left-zone')) {
          e.preventDefault();
          e.stopPropagation();
          callDep(isComicRtlActive() ? 'nextPage' : 'prevPage');
          return;
        }

        if (target.closest('.right-zone')) {
          e.preventDefault();
          e.stopPropagation();
          callDep(isComicRtlActive() ? 'prevPage' : 'nextPage');
        }
      },
      { passive: false }
    );
  }

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
      if (scrollMode === 'page' || (isComic && !isComicWidth)) {
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
  const isPdf = fmt === 'pdf';

  const isScrollActive = scrollMode === 'scroll' && (isComic || isTxt || isEpub || isPdf);

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

  const OVERLAY_INTERACTIVE_SELECTOR = 'button, input, select, textarea, label, a, [role="button"], [data-overlay-keep-open]';

  function handleOverlayBlankTap(target) {
    if (!target || typeof target.closest !== 'function') return false;
    const overlayMenu = document.getElementById('comic-overlay-menu');
    if (!overlayMenu || overlayMenu.style.display !== 'flex') return false;

    const inOverlayMenu = target.closest('#comic-overlay-menu');
    if (!inOverlayMenu) return false;

    const isInteractive = !!target.closest(OVERLAY_INTERACTIVE_SELECTOR);
    if (!isInteractive) {
      callDep('toggleComicOverlay', { source: 'overlay-blank-tap' });
    }

    // 오버레이 내부 터치는 여기서 모두 소비해 하단 핫스팟 토글과 중복되지 않게 한다.
    return true;
  }

  const TAP_THRESHOLD = 15;
  const SWIPE_MIN_DISTANCE = 40;
  const SWIPE_MAX_TIME = 600;

  let touchStartX = null;
  let touchStartY = null;
  let touchStartTime = 0;
  let isMultiTouch = false;
  let lastTouchEndTime = 0;

  document.addEventListener(
    'touchstart',
    (e) => {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchStartTime = Date.now();
        isMultiTouch = false;
      } else {
        isMultiTouch = true;
        touchStartX = null;
        touchStartY = null;
      }
    },
    { passive: true }
  );

  document.addEventListener(
    'touchmove',
    (e) => {
      if (e.touches.length > 1) {
        isMultiTouch = true;
      }
    },
    { passive: true }
  );

  document.addEventListener(
    'touchend',
    (e) => {
      if (touchStartX === null || isMultiTouch) return;
      if (!e.changedTouches || e.changedTouches.length === 0) return;

      const endX = e.changedTouches[0].clientX;
      const endY = e.changedTouches[0].clientY;
      const duration = Date.now() - touchStartTime;

      const diffX = touchStartX - endX; // 양수: Swipe Left(👈), 음수: Swipe Right(👉)
      const diffY = touchStartY - endY;

      const startX = touchStartX;
      const startY = touchStartY;

      touchStartX = null;
      touchStartY = null;

      const target = e.target || document.elementFromPoint(endX, window.innerHeight / 2);
      if (!target) return;

      if (handleOverlayBlankTap(target)) {
        lastTouchEndTime = Date.now();
        return;
      }

      if (
        target.closest('#epub-toc-container') ||
        target.closest('#epub-toc-btn') ||
        target.closest('.viewer-controls') ||
        target.closest('.floating-close-btn') ||
        target.closest('button') ||
        target.closest('input') ||
        target.closest('select')
      ) {
        return;
      }

      const viewerModal = document.getElementById('media-viewer-modal');
      if (!viewerModal || viewerModal.style.display !== 'flex') return;

      const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
      const absX = Math.abs(diffX);
      const absY = Math.abs(diffY);

      // 📱 1) 스와이프 제스처 처리 (페이지 모드일 때 수평 스와이프)
      if (scrollMode === 'page' && absX >= SWIPE_MIN_DISTANCE && absX > absY * 1.2 && duration <= SWIPE_MAX_TIME) {
        const isComic = state.currentViewerFormat === 'zip' || state.currentViewerFormat === 'cbz';
        const isRtl = isComic && (localStorage.getItem('comic_reading_direction') === 'rtl');

        lastTouchEndTime = Date.now();

        if (diffX > 0) {
          // 👈 Swipe Left (오른쪽에서 왼쪽으로 쓸어넘김)
          console.log(`[Viewer-Touch-Swipe] Swipe Left detected (diffX=${diffX}, isRtl=${isRtl})`);
          if (isRtl) {
            callDep('prevPage');
          } else {
            callDep('nextPage');
          }
        } else {
          // 👉 Swipe Right (왼쪽에서 오른쪽으로 쓸어넘김)
          console.log(`[Viewer-Touch-Swipe] Swipe Right detected (diffX=${diffX}, isRtl=${isRtl})`);
          if (isRtl) {
            callDep('nextPage');
          } else {
            callDep('prevPage');
          }
        }
        return;
      }

      // 📱 2) 단순 탭(Tap) 오버레이 토글 처리
      if (absX < TAP_THRESHOLD && absY < TAP_THRESHOLD) {
        const width = window.innerWidth;
        if (endX >= width * 0.3 && endX <= width * 0.7) {
          console.log('[Viewer-Touch-Toggle] Triggering toggleComicOverlay() from touchend tap');
          lastTouchEndTime = Date.now();
          callDep('toggleComicOverlay');
        }
      }
    },
    { passive: true }
  );

  viewerBody.addEventListener('click', (e) => {
    if (e.sourceCapabilities && e.sourceCapabilities.firesTouchEvents) return;
    if (e.pointerType === 'touch') return;
    if (Date.now() - lastTouchEndTime < 500) return;

    if (handleOverlayBlankTap(e.target)) {
      return;
    }

    console.log('[Viewer-Click-Toggle] Mouse click detected. Target:', e.target);

    if (
      e.target.closest('#epub-toc-container') ||
      e.target.closest('#epub-toc-btn') ||
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
