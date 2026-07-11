import { state } from '../../state.js';
import { closeMediaViewer } from '../../viewer.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from '../../view_manager.js';
import {
  getScrollMode,
  getReadingDirection,
  syncPageStepUI
} from './ui_helpers.js';
import { createNoSectionRecovery } from './recovery.js';
import {
  getCurrentRatioFromScroll,
  syncSeekBarUI,
  ensureLocations
} from './location_progress.js';

// 분할 모듈 연동
import * as storage from './epub_storage.js';
import * as cover from './epub_cover.js';
import * as navigation from './epub_navigation.js';
import * as progress from './epub_progress.js';
import * as settings from './epub_settings.js';

export let epubBook = null;
export let epubTotalPages = 100;

let currentScrollPercent = 0;
let mergedContentEl = null;
let epubRendition = null;
let currentLocationCfi = null;
let currentLocationHref = null;
let currentLocationIndex = null;
let renditionAtEnd = false;
let isScrollListenerBound = false;
let epubScrollHandler = null;
let epubScrollTouchHandler = null;
let epubScrollNextEpisodeTriggered = false;
let activeCoverFallbackUrl = '/static/images/default_cover.jpg';

const RENDITION_LOCATIONS_CHARS = 1600;

// 상태 전송 헬퍼
function getContext() {
  return {
    activeBookId: state.activeBookId,
    currentLocationCfi,
    currentLocationHref,
    currentLocationIndex,
    currentScrollPercent,
    mergedContentEl,
    renditionAtEnd
  };
}

function updateContext(partial = {}) {
  if (partial.currentLocationCfi !== undefined) currentLocationCfi = partial.currentLocationCfi;
  if (partial.currentLocationHref !== undefined) currentLocationHref = partial.currentLocationHref;
  if (partial.currentLocationIndex !== undefined) currentLocationIndex = partial.currentLocationIndex;
  if (partial.currentScrollPercent !== undefined) currentScrollPercent = partial.currentScrollPercent;
  if (partial.mergedContentEl !== undefined) mergedContentEl = partial.mergedContentEl;
  if (partial.renditionAtEnd !== undefined) renditionAtEnd = partial.renditionAtEnd;
}

function getStorageContext() {
  return {
    currentLocationCfi,
    currentLocationHref,
    currentLocationIndex,
    currentScrollPercent
  };
}

function getReadableSpineItems() {
  const items = (epubBook && epubBook.spine && epubBook.spine.spineItems) ? epubBook.spine.spineItems : [];
  return items.filter(item => item && item.linear !== 'no');
}

const {
  isNoSectionFoundError,
  fallbackDisplayFromSpine,
  displayAdjacentSpine,
  safeRenditionDisplay
} = createNoSectionRecovery(getReadableSpineItems);

function goForwardByReadingDirection() {
  if (getReadingDirection() === 'rtl') {
    epubPrevPage();
    return;
  }
  epubNextPage();
}

function goBackwardByReadingDirection() {
  if (getReadingDirection() === 'rtl') {
    epubNextPage();
    return;
  }
  epubPrevPage();
}

function isAtAbsoluteEndInPageMode() {
  if (!epubRendition) return false;

  const loc = epubRendition.currentLocation && epubRendition.currentLocation();
  const items = getReadableSpineItems();
  const normalizeHref = href => (href ? String(href).split('#')[0] : '');

  const currentHref = normalizeHref(loc && loc.start ? loc.start.href : null);
  const lastHref = items.length > 0 ? normalizeHref(items[items.length - 1].href) : '';
  const atLastSpineByHref = !!currentHref && !!lastHref && currentHref === lastHref;

  return !!renditionAtEnd || atLastSpineByHref;
}

function isAtAbsoluteEndInScrollMode(container) {
  if (!container) return false;

  const nearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 2;
  if (!nearBottom) return false;

  // 모바일/브라우저 반올림 오차로 인한 조기 종료를 막기 위해 비율 기준을 함께 확인합니다.
  const ratio = getCurrentRatioFromScroll(container);
  if (!Number.isFinite(ratio) || ratio < 0.999) {
    console.log('[EPUB-EndCheck] blocked by ratio threshold', {
      activeBookId: state.activeBookId,
      scrollTop: container.scrollTop,
      clientHeight: container.clientHeight,
      scrollHeight: container.scrollHeight,
      ratio,
      threshold: 0.999,
      scrollMode: getScrollMode(),
    });
    return false;
  }

  if (!epubRendition) {
    console.log('[EPUB-EndCheck] no rendition, treat as end', {
      activeBookId: state.activeBookId,
      scrollTop: container.scrollTop,
      clientHeight: container.clientHeight,
      scrollHeight: container.scrollHeight,
      ratio,
      scrollMode: getScrollMode(),
    });
    return true;
  }

  const loc = epubRendition.currentLocation && epubRendition.currentLocation();
  const items = getReadableSpineItems();
  const normalizeHref = href => (href ? String(href).split('#')[0] : '');

  const currentHref = normalizeHref(
    loc && loc.end ? loc.end.href : (loc && loc.start ? loc.start.href : null)
  );
  const lastHref = items.length > 0 ? normalizeHref(items[items.length - 1].href) : '';
  const atLastSpineByHref = !!currentHref && !!lastHref && currentHref === lastHref;
  const atEndFlag = !!(loc && loc.atEnd);
  const result = atEndFlag || !!renditionAtEnd || atLastSpineByHref;

  console.log('[EPUB-EndCheck] near bottom evaluation', {
    activeBookId: state.activeBookId,
    scrollTop: container.scrollTop,
    clientHeight: container.clientHeight,
    scrollHeight: container.scrollHeight,
    ratio,
    atEndFlag,
    renditionAtEnd,
    currentHref,
    lastHref,
    atLastSpineByHref,
    result,
    scrollMode: getScrollMode(),
  });

  return result;
}

function normalizeHrefForCompare(href) {
  return href ? String(href).split('#')[0] : '';
}

async function displayAdjacentFromKnownPointer(direction, baseHref, baseIndex) {
  if (!epubRendition) return false;

  const items = getReadableSpineItems();
  if (!items.length) return false;

  const normalizedBaseHref = normalizeHrefForCompare(baseHref || currentLocationHref);
  let currentPos = -1;

  if (normalizedBaseHref) {
    currentPos = items.findIndex(item => normalizeHrefForCompare(item && item.href) === normalizedBaseHref);
  }

  if (currentPos < 0) {
    const idx = Number.isInteger(baseIndex) ? baseIndex : currentLocationIndex;
    if (Number.isInteger(idx)) {
      currentPos = Math.max(0, Math.min(items.length - 1, idx));
    }
  }

  if (currentPos < 0) return false;

  const targetPos = direction === 'prev' ? currentPos - 1 : currentPos + 1;
  if (targetPos < 0 || targetPos >= items.length) return false;

  const target = items[targetPos];
  if (!target || !target.href) return false;

  await safeRenditionDisplay(epubRendition, target.href);
  return navigation.hasRenderableRenditionLocation(epubRendition);
}

async function recoverBlankPageModeView(direction = 'next', context = {}) {
  await navigation.recoverBlankPageModeView({
    epubRendition,
    direction,
    context,
    displayAdjacentFromKnownPointer,
    displayAdjacentSpine,
    fallbackDisplayFromSpine
  });
}

function updateProgressPercent(percent) {
  progress.updateProgressPercent({
    percent,
    context: getContext(),
    updateLocalScrollPercent: val => { currentScrollPercent = val; },
    applyEpubSettings
  });
}

function bindContainerScroll() {
  if (isScrollListenerBound) return;
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  const triggerNextEpisodeIfNeeded = () => {
    if (getScrollMode() !== 'scroll') return;
    const isAtEnd = isAtAbsoluteEndInScrollMode(container);
    console.log('[EPUB-EndCheck] triggerNextEpisodeIfNeeded', {
      activeBookId: state.activeBookId,
      isAtEnd,
      alreadyTriggered: epubScrollNextEpisodeTriggered,
      scrollMode: getScrollMode(),
    });
    if (isAtEnd && !epubScrollNextEpisodeTriggered) {
      epubScrollNextEpisodeTriggered = true;
      console.log('[EPUB-EndCheck] trigger next episode from scroll listener', {
        activeBookId: state.activeBookId,
      });
      import('../../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId));
    }
  };

  epubScrollHandler = () => {
    if (getScrollMode() !== 'scroll') return;
    const ratio = getCurrentRatioFromScroll(container);
    updateProgressPercent(ratio * 100);
    triggerNextEpisodeIfNeeded();
  };
  container.addEventListener('scroll', epubScrollHandler, { passive: true });

  epubScrollTouchHandler = () => {
    triggerNextEpisodeIfNeeded();
  };
  container.addEventListener('touchend', epubScrollTouchHandler, { passive: true });
  container.addEventListener('touchcancel', epubScrollTouchHandler, { passive: true });

  isScrollListenerBound = true;
}

async function destroyRendition() {
  if (!epubRendition) return;

  try {
    const location = epubRendition.currentLocation();
    if (location && location.start) {
      currentLocationCfi = location.start.cfi || currentLocationCfi;
      currentLocationHref = location.start.href || currentLocationHref;
      currentLocationIndex = Number.isInteger(location.start.index) ? location.start.index : currentLocationIndex;
    }
    storage.persistResumeSession({}, state.activeBookId, getStorageContext());
    storage.persistCurrentLocationCfi(currentLocationCfi, state.activeBookId, getStorageContext());
  } catch (_) {
    // ignore
  }

  try {
    epubRendition.destroy();
  } catch (_) {
    // ignore
  }

  epubRendition = null;
  renditionAtEnd = false;
}

export function initEpubViewer(bookId, pagesRead, totalPages) {
  if (typeof ePub === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/epubjs@0.3.88/dist/epub.min.js';
    script.onload = () => _doInitEpubViewer(bookId, pagesRead, totalPages);
    script.onerror = err => {
      console.error('EPUB library load failed:', err);
      alert(i18n.t('viewer.epub_lib_fail'));
      closeMediaViewer();
    };
    document.head.appendChild(script);
    return;
  }

  _doInitEpubViewer(bookId, pagesRead, totalPages);
}

async function _doInitEpubViewer(bookId, pagesRead, totalPages) {
  const container = document.getElementById('epub-viewer-container');
  const renderArea = document.getElementById('epub-render-area');
  if (!container || !renderArea) return;

  container.style.display = 'flex';
  renderArea.innerHTML = '';

  showViewerLoading(
    i18n.t('viewer.loading_epub_title') || 'EPUB 준비 중',
    i18n.t('viewer.loading_epub_sub') || '책 전체 내용을 로드하는 중입니다...'
  );

  const url = `/api/media/pdf?db_type=${state.currentLibraryType}&book_id=${bookId}&_cb=${new Date().getTime()}&ext=.epub`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const buffer = await res.arrayBuffer();
    epubBook = ePub(buffer);

    await epubBook.opened;
    await epubBook.ready;

    if (epubBook) {
      if (!epubBook.packaging) {
        epubBook.packaging = {
          metadata: {},
          spine: [],
          manifest: {}
        };
      }
      if (epubBook.spine && epubBook.spine.spineItems) {
        epubBook.spine.spineItems.forEach(item => {
          if (item && !item.book) {
            item.book = epubBook;
          }
        });
      }
    }

    const coverUrl = await cover.resolveActiveBookCoverFallbackUrl(bookId);
    activeCoverFallbackUrl = coverUrl || '/static/images/default_cover.jpg';

    bindContainerScroll();
    settings.bindViewportListeners({ epubBook, applyEpubSettings });

    await progress.restoreEpubProgress({
      pagesRead,
      totalPages,
      context: getContext(),
      updateState: updateContext,
      applyEpubSettings
    });

    hideViewerLoading();
  } catch (err) {
    hideViewerLoading();
    console.error('[Viewer-Epub] init failed:', err);
    showViewerError(i18n.t('viewer.error_epub_title') || 'EPUB 로드 오류', err.message);
  }
}

export function applyEpubSettings(options = {}) {
  settings.applyEpubSettingsInternal({
    options,
    epubBook,
    getEpubRendition: () => epubRendition,
    setEpubRendition: val => { epubRendition = val; },
    getContext,
    updateContext,
    destroyRendition,
    activeCoverFallbackUrl,
    updateProgressPercent,
    recoverBlankPageModeView,
    epubNextPage,
    epubPrevPage,
    goBackwardByReadingDirection,
    goForwardByReadingDirection,
    getStorageContext,
    RENDITION_LOCATIONS_CHARS,
    safeRenditionDisplay
  }).catch(err => {
    console.error('[Viewer-Epub] apply settings failed:', err);
  });
}

function extractVisibleAnchorText() {
  let anchorText = '';
  try {
    const renderArea = document.getElementById('epub-render-area');
    if (!renderArea) return '';
    
    const isPageModeRendered = renderArea.querySelector('iframe') !== null;
    let targetDoc = document;
    let containerEl = renderArea;
    let minTop = 50; // 스크롤 모드 상단 여백 고려

    if (isPageModeRendered && epubRendition) {
      const contents = epubRendition.getContents();
      if (contents && contents.length > 0) {
        targetDoc = contents[0].document;
        containerEl = targetDoc.body;
        minTop = 0; // iframe 내부는 바로 시작
      } else {
        return '';
      }
    }

    const viewportWidth = targetDoc.documentElement.clientWidth || window.innerWidth;
    const xPositions = [viewportWidth / 2, viewportWidth * 0.25, viewportWidth * 0.75];
    const yOffsets = [minTop + 20, minTop + 50, minTop + 100, minTop + 150];

    // TreeWalker 대신 화면 좌표에 광선을 쏘는 elementsFromPoint(s) 사용
    // epub.js가 보이지 않는 DOM 찌꺼기를 남겨두어 BoundingClientRect가 꼬이는 버그 완벽 회피
    for (let y of yOffsets) {
      for (let x of xPositions) {
        const elements = targetDoc.elementsFromPoint(x, y);
        for (let el of elements) {
          // 투명 오버레이를 뚫고, 자신이 직접 텍스트 노드를 품고 있는 가장 깊은 본문 요소를 찾음
          let hasDirectText = false;
          for (let child of el.childNodes) {
            if (child.nodeType === Node.TEXT_NODE && child.nodeValue.trim().length >= 5) {
              hasDirectText = true;
              break;
            }
          }
          
          if (hasDirectText) {
            const text = el.textContent.replace(/\s+/g, ' ').trim();
            if (text.length >= 10) {
              anchorText = text.substring(0, 100);
              console.log(`[Viewer-Epub] Anchor extracted via elementsFromPoint (x:${x}, y:${y}):`, anchorText);
              return anchorText;
            }
          }
        }
      }
    }
  } catch (e) {
    console.warn('[Viewer-Epub] Failed to extract anchor text:', e);
  }
  return anchorText;
}

export function changeEpubScrollMode() {
  if (!epubBook) return;

  const context = getContext();
  const currentScrollPercent = context.currentScrollPercent;
  
  const anchorText = extractVisibleAnchorText();
  if (anchorText) {
    sessionStorage.setItem('viewer_epub_transition_anchor', anchorText);
    console.log('[Viewer-Epub] Extracted anchor text:', anchorText);
  } else {
    sessionStorage.removeItem('viewer_epub_transition_anchor');
  }

  // 모드 전환 전 현재 위치를 스토리지에 명시적 강제 플러시 저장
  import('./epub_storage.js').then(storage => {
    storage.persistResumeSession(
      { percent: currentScrollPercent },
      context.activeBookId,
      {
        currentLocationCfi: context.currentLocationCfi,
        currentLocationHref: context.currentLocationHref,
        currentLocationIndex: context.currentLocationIndex,
        currentScrollPercent
      }
    );
    console.log('[Viewer-Epub] Explicit storage flush completed for mode transition');

    // 메모리 파라미터가 아닌, 처음 켜는 것처럼 스토리지에서 복구(preferResumeStart) 지시
    applyEpubSettings({ preferResumeStart: true });
  }).catch(err => {
    console.warn('[Viewer-Epub] flush before transition failed:', err);
    applyEpubSettings({ preferResumeStart: true });
  });
}

export function epubPrevPage() {
  if (!epubBook) return;

  const scrollMode = getScrollMode();
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  if (scrollMode === 'scroll') {
    container.scrollBy({ top: -window.innerHeight * 0.8, behavior: 'smooth' });
    return;
  }

  const navState = navigation.getNavigationState();
  if (!epubRendition) return;
  if (navState.isEpubRelayouting || navState.isEpubPageNavigating) {
    navigation.queuePageNavigation('prev');
    return;
  }

  navigation.setEpubPageNavigating(true);

  let baseHref = currentLocationHref;
  let baseIndex = currentLocationIndex;
  try {
    const loc = epubRendition.currentLocation && epubRendition.currentLocation();
    if (loc && loc.start) {
      baseHref = loc.start.href || baseHref;
      if (Number.isInteger(loc.start.index)) {
        baseIndex = loc.start.index;
      }
    }
  } catch (_) {
    // ignore
  }

  epubRendition.prev()
    .then(() => recoverBlankPageModeView('prev', { baseHref, baseIndex }))
    .catch(err => {
      if (isNoSectionFoundError(err)) {
        displayAdjacentSpine(epubRendition, 'prev').then(ok => {
          if (!ok) {
            fallbackDisplayFromSpine(epubRendition, false);
          }
        });
        return;
      }
      console.warn('[Viewer-Epub] prev failed:', err);
    })
    .finally(() => {
      navigation.setEpubPageNavigating(false);
      navigation.flushQueuedPageNavigation({
        next: epubNextPage,
        prev: epubPrevPage
      });
    });
}

export function epubNextPage() {
  if (!epubBook) return;

  const scrollMode = getScrollMode();
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  if (scrollMode === 'scroll') {
    const isAtEnd = isAtAbsoluteEndInScrollMode(container);
    console.log('[EPUB-EndCheck] epubNextPage(scroll mode)', {
      activeBookId: state.activeBookId,
      isAtEnd,
      alreadyTriggered: epubScrollNextEpisodeTriggered,
      scrollTop: container.scrollTop,
      clientHeight: container.clientHeight,
      scrollHeight: container.scrollHeight,
    });
    if (isAtEnd) {
      epubScrollNextEpisodeTriggered = true;
      console.log('[EPUB-EndCheck] trigger next episode from epubNextPage', {
        activeBookId: state.activeBookId,
      });
      import('../../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId));
    } else {
      container.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' });
    }
    return;
  }

  const navState = navigation.getNavigationState();
  if (!epubRendition) return;
  if (navState.isEpubRelayouting || navState.isEpubPageNavigating) {
    navigation.queuePageNavigation('next');
    return;
  }

  if (isAtAbsoluteEndInPageMode()) {
    import('../../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId));
    return;
  }

  navigation.setEpubPageNavigating(true);

  let baseHref = currentLocationHref;
  let baseIndex = currentLocationIndex;
  try {
    const loc = epubRendition.currentLocation && epubRendition.currentLocation();
    if (loc && loc.start) {
      baseHref = loc.start.href || baseHref;
      if (Number.isInteger(loc.start.index)) {
        baseIndex = loc.start.index;
      }
    }
  } catch (_) {
    // ignore
  }

  epubRendition.next()
    .then(() => recoverBlankPageModeView('next', { baseHref, baseIndex }))
    .catch(err => {
      if (isNoSectionFoundError(err)) {
        displayAdjacentSpine(epubRendition, 'next').then(ok => {
          if (ok) return;

          if (!isAtAbsoluteEndInPageMode()) {
            safeRenditionDisplay(epubRendition, currentLocationCfi || null);
            return;
          }

          import('../../viewer_next_episode.js').then(m => m.handleNextEpisodeDirect(state.activeBookId));
        });
        return;
      }
      console.warn('[Viewer-Epub] next failed:', err);
    })
    .finally(() => {
      navigation.setEpubPageNavigating(false);
      navigation.flushQueuedPageNavigation({
        next: epubNextPage,
        prev: epubPrevPage
      });
    });
}

export function clearEpubViewer() {
  settings.unbindViewportListeners();

  destroyRendition().finally(() => {
    const container = document.getElementById('epub-viewer-container');
    if (container) {
      if (epubScrollHandler) {
        container.removeEventListener('scroll', epubScrollHandler);
      }
      if (epubScrollTouchHandler) {
        container.removeEventListener('touchend', epubScrollTouchHandler);
        container.removeEventListener('touchcancel', epubScrollTouchHandler);
      }
    }

    if (epubBook) {
      epubBook.destroy();
      epubBook = null;
    }

    mergedContentEl = null;
    currentLocationCfi = null;
    currentLocationHref = null;
    currentLocationIndex = null;
    renditionAtEnd = false;
    currentScrollPercent = 0;
    epubScrollNextEpisodeTriggered = false;
    epubScrollHandler = null;
    epubScrollTouchHandler = null;
    isScrollListenerBound = false;
    navigation.resetNavigationState();
  });
}

export function syncEpubSeekBar() {
  syncSeekBarUI(currentScrollPercent);
}

export function epubSliderInput(slider, val) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip && slider) {
    tooltip.textContent = `${val}%`;
    tooltip.style.display = 'block';

    const trackWidth = slider.offsetWidth;
    const percent = val / 100;
    const thumbOffset = percent * trackWidth;
    tooltip.style.left = `calc(${thumbOffset}px - 14px)`;
  }

  const badge = document.getElementById('comic-overlay-page-info');
  if (badge) badge.textContent = `${val}%`;
}

export function epubSliderChange(slider, val) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) tooltip.style.display = 'none';

  const ratio = Math.min(1, Math.max(0, val / 100));
  const scrollMode = getScrollMode();
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  if (scrollMode === 'scroll') {
    const totalScroll = container.scrollHeight - container.clientHeight;
    container.scrollTop = totalScroll * ratio;
    updateProgressPercent(ratio * 100);
    return;
  }

  if (!epubBook || !epubRendition) {
    updateProgressPercent(ratio * 100);
    return;
  }

  // 비율이 0% (처음) 또는 100% (끝) 인 경우, Locations 계산 에러를 완벽 방지하기 위해 spine 직접 매핑
  if (ratio === 0) {
    const items = getReadableSpineItems();
    if (items.length > 0 && items[0].href) {
      safeRenditionDisplay(epubRendition, items[0].href).then(() => {
        updateProgressPercent(0);
      });
      return;
    }
  } else if (ratio === 1) {
    const items = getReadableSpineItems();
    if (items.length > 0 && items[items.length - 1].href) {
      safeRenditionDisplay(epubRendition, items[items.length - 1].href).then(() => {
        updateProgressPercent(100);
      });
      return;
    }
  }

  ensureLocations(epubBook, RENDITION_LOCATIONS_CHARS).catch(err => {
    console.warn('[Viewer-Epub] slider locations generation failed:', err);
  }).then(async () => {
    let cfi = null;
    try {
      if (epubBook.locations && epubBook.locations.length > 0) {
        cfi = epubBook.locations.cfiFromPercentage(Math.min(0.999, ratio));
      } else {
        // 위치 정보(locations)가 아직 준비되지 않은 경우, 전체 스파인(Spine) 개수 대비 비율 인덱스로 폴백 매핑
        const items = getReadableSpineItems();
        if (items.length > 0) {
          const targetIndex = Math.min(items.length - 1, Math.floor(items.length * ratio));
          cfi = items[targetIndex].href;
          console.log(`[Viewer-Epub] Locations not ready, fallback to spine index: ${targetIndex}/${items.length}`);
        }
      }
    } catch (err) {
      console.warn('[Viewer-Epub] slider cfiFromPercentage failed:', err);
    }
    await safeRenditionDisplay(epubRendition, cfi);
  }).then(() => {
    updateProgressPercent(ratio * 100);
  }).catch(err => {
    console.warn('[Viewer-Epub] slider move failed:', err);
  });
}

export function epubJumpToFirstPage() {
  epubSliderChange(null, 0);
}

export function epubJumpToLastPage() {
  epubSliderChange(null, 100);
}

export const EpubViewer = {
  async init(bookId, pagesRead, totalPages) {
    return initEpubViewer(bookId, pagesRead, totalPages);
  },
  destroy() {
    clearEpubViewer();
    const pane = document.getElementById('epub-viewer-container');
    if (pane) pane.style.display = 'none';
  },
  prevPage() {
    epubPrevPage();
  },
  nextPage() {
    epubNextPage();
  },
  jumpTo(target) {
    if (target === 'first') {
      epubJumpToFirstPage();
    } else if (target === 'last') {
      epubJumpToLastPage();
    }
  },
  applySettings(options) {
    applyEpubSettings(options);
  }
};
