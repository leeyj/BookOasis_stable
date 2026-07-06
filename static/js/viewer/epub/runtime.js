import { getViewerSettings } from '../../viewer_settings.js';
import { state } from '../../state.js';
import { closeMediaViewer } from '../../viewer.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from '../../view_manager.js';
import { saveProgress } from '../../viewer_progress.js';
import {
  getScrollMode,
  getEpubPageStep,
  getReadingDirection,
  getViewportSize,
  getEffectivePageStep,
  syncPageStepUI,
  resolveFontCSS
} from './ui_helpers.js';
import { applyMergedThemeStyles, applyRenditionTheme } from './styles.js';
import { bindRenderAreaClick, bindRenditionInteractionHandlers } from './interactions.js';
import { createNoSectionRecovery } from './recovery.js';
import {
  ensureLocations,
  getCurrentRatioFromScroll,
  getCurrentRatio,
  updateProgressPercent as updateProgressPercentBase,
  syncSeekBarUI
} from './location_progress.js';
import { buildMergedContent } from './content_builder.js';
import { activateRenditionPageMode } from './page_mode.js';
import { applyBaseContainerStyles, renderScrollMode } from './scroll_mode.js';

export let epubBook = null;
export let epubTotalPages = 100;

let currentScrollPercent = 0;
let mergedContentEl = null;
let epubRendition = null;
let currentLocationCfi = null;
let currentLocationHref = null;
let currentLocationIndex = null;
let renditionAtEnd = false;
let viewportResizeRaf = null;
let isScrollListenerBound = false;
let applySettingsRunId = 0;
let activeCoverFallbackUrl = '/static/images/default_cover.jpg';
let isEpubPageNavigating = false;
let isEpubRelayouting = false;
let pendingPageNavDirection = null;

const RENDITION_LOCATIONS_CHARS = 1600;

function getCoverFallbackFromState(bookId = state.activeBookId) {
  const idNum = Number(bookId);
  const pools = [
    Array.isArray(state.currentBooksData) ? state.currentBooksData : [],
    Array.isArray(state.allBooksData) ? state.allBooksData : []
  ];

  for (const pool of pools) {
    const found = pool.find(item => Number(item && item.id) === idNum);
    const cover = found && found.cover_image ? String(found.cover_image).trim() : '';
    if (cover) {
      return `/covers/${encodeURIComponent(cover)}`;
    }
  }

  return '';
}

async function resolveActiveBookCoverFallbackUrl(bookId = state.activeBookId) {
  const fromState = getCoverFallbackFromState(bookId);
  if (fromState) {
    activeCoverFallbackUrl = fromState;
    return activeCoverFallbackUrl;
  }

  try {
    const dbType = encodeURIComponent(state.currentLibraryType || 'general');
    const id = encodeURIComponent(String(bookId || ''));
    if (!id) {
      activeCoverFallbackUrl = '/static/images/default_cover.jpg';
      return activeCoverFallbackUrl;
    }

    const res = await fetch(`/api/media/books/${id}/info?type=${dbType}`);
    if (res.ok) {
      const data = await res.json();
      const cover = data && data.cover_image ? String(data.cover_image).trim() : '';
      if (cover) {
        activeCoverFallbackUrl = `/covers/${encodeURIComponent(cover)}`;
        return activeCoverFallbackUrl;
      }
    }
  } catch (err) {
    console.warn('[Viewer-Epub] cover fallback api lookup failed:', err);
  }

  activeCoverFallbackUrl = '/static/images/default_cover.jpg';
  return activeCoverFallbackUrl;
}

function getEpubLocationKey(bookId = state.activeBookId) {
  const lib = state.currentLibraryType || 'default';
  const id = bookId || state.activeBookId;
  if (!id) return null;
  return `epub_last_cfi:${lib}:${id}`;
}

function getEpubSessionKey(bookId = state.activeBookId) {
  const lib = state.currentLibraryType || 'default';
  const id = bookId || state.activeBookId;
  if (!id) return null;
  return `epub_last_session:${lib}:${id}`;
}

function persistResumeSession(partial = {}, bookId = state.activeBookId) {
  const key = getEpubSessionKey(bookId);
  if (!key) return;

  const payload = {
    cfi: partial.cfi !== undefined ? partial.cfi : currentLocationCfi,
    href: partial.href !== undefined ? partial.href : currentLocationHref,
    index: partial.index !== undefined ? partial.index : currentLocationIndex,
    percent: Number.isFinite(partial.percent) ? partial.percent : currentScrollPercent,
    updatedAt: Date.now()
  };

  if (!payload.cfi && !payload.href) return;

  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch (_) {
    // ignore storage quota/private mode errors
  }
}

function persistCurrentLocationCfi(cfi, bookId = state.activeBookId) {
  if (!cfi) return;
  const key = getEpubLocationKey(bookId);
  if (!key) return;
  try {
    localStorage.setItem(key, cfi);
    persistResumeSession({ cfi }, bookId);
  } catch (_) {
    // ignore storage quota/private mode errors
  }
}

function loadPersistedResumeSession(bookId = state.activeBookId) {
  const key = getEpubSessionKey(bookId);
  if (!key) return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch (_) {
    return null;
  }
}

function loadPersistedLocationCfi(bookId = state.activeBookId) {
  const session = loadPersistedResumeSession(bookId);
  if (session && session.cfi) return session.cfi;

  const key = getEpubLocationKey(bookId);
  if (!key) return null;
  try {
    return localStorage.getItem(key);
  } catch (_) {
    return null;
  }
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
  return hasRenderableRenditionLocation(epubRendition);
}

async function recoverBlankPageModeView(direction = 'next', context = {}) {
  if (!epubRendition) return;

  let hasUsableLocation = false;
  try {
    const loc = epubRendition.currentLocation && epubRendition.currentLocation();
    const start = loc && loc.start ? loc.start : null;
    hasUsableLocation = !!(start && (start.cfi || start.href || Number.isInteger(start.index)));
  } catch (_) {
    hasUsableLocation = false;
  }

  if (hasUsableLocation) return;

  const knownPointerOk = await displayAdjacentFromKnownPointer(
    direction,
    context && context.baseHref ? context.baseHref : null,
    context && Number.isInteger(context.baseIndex) ? context.baseIndex : null
  );
  if (knownPointerOk) return;

  const adjacentOk = await displayAdjacentSpine(epubRendition, direction === 'prev' ? 'prev' : 'next');
  if (adjacentOk) return;

  await fallbackDisplayFromSpine(epubRendition, direction === 'prev');
}

function hasRenderableRenditionLocation(rendition = epubRendition) {
  if (!rendition || typeof rendition.currentLocation !== 'function') return false;
  try {
    const loc = rendition.currentLocation();
    const start = loc && loc.start ? loc.start : null;
    return !!(start && (start.cfi || start.href || Number.isInteger(start.index)));
  } catch (_) {
    return false;
  }
}

function queuePageNavigation(direction) {
  if (direction !== 'next' && direction !== 'prev') return;
  pendingPageNavDirection = direction;
}

function flushQueuedPageNavigation() {
  if (isEpubRelayouting || isEpubPageNavigating) return;
  const direction = pendingPageNavDirection;
  if (!direction) return;

  pendingPageNavDirection = null;
  if (direction === 'next') {
    epubNextPage();
  } else {
    epubPrevPage();
  }
}

function updateProgressPercent(percent) {
  const epubSessionPayload = (currentLocationCfi || currentLocationHref)
    ? {
      epub_session: {
        cfi: currentLocationCfi,
        href: currentLocationHref,
        index: currentLocationIndex,
        percent: Math.min(100, Math.max(0, Math.round(percent))),
        updatedAt: new Date().toISOString()
      }
    }
    : null;

  currentScrollPercent = updateProgressPercentBase({
    percent,
    stateBookId: state.activeBookId,
    saveProgress,
    syncSeekBar: syncSeekBarUI,
    extraData: epubSessionPayload
  });

  if (getScrollMode() === 'page' && (currentLocationCfi || currentLocationHref)) {
    persistResumeSession({ percent: currentScrollPercent });
  }
}

function bindContainerScroll() {
  if (isScrollListenerBound) return;
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  container.addEventListener('scroll', () => {
    if (getScrollMode() !== 'scroll') return;
    const ratio = getCurrentRatioFromScroll(container);
    updateProgressPercent(ratio * 100);
  }, { passive: true });

  isScrollListenerBound = true;
}

function bindViewportListeners() {
  const relayout = () => {
    if (!epubBook) return;
    const container = document.getElementById('epub-viewer-container');
    if (!container || container.style.display === 'none') return;

    if (viewportResizeRaf) {
      cancelAnimationFrame(viewportResizeRaf);
    }
    viewportResizeRaf = requestAnimationFrame(() => {
      viewportResizeRaf = null;
      applyEpubSettings({ preservePagePosition: true });
    });
  };

  window.addEventListener('resize', relayout, { passive: true });
  window.addEventListener('orientationchange', relayout, { passive: true });
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', relayout, { passive: true });
  }

  window.__epubRelayoutHandler = relayout;
}

function unbindViewportListeners() {
  const relayout = window.__epubRelayoutHandler;
  if (!relayout) return;

  window.removeEventListener('resize', relayout);
  window.removeEventListener('orientationchange', relayout);
  if (window.visualViewport) {
    window.visualViewport.removeEventListener('resize', relayout);
  }

  delete window.__epubRelayoutHandler;

  if (viewportResizeRaf) {
    cancelAnimationFrame(viewportResizeRaf);
    viewportResizeRaf = null;
  }
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
    persistResumeSession();
    persistCurrentLocationCfi(currentLocationCfi);
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

async function applyEpubSettingsInternal(options = {}) {
  const runId = ++applySettingsRunId;

  const container = document.getElementById('epub-viewer-container');
  const renderArea = document.getElementById('epub-render-area');
  if (!container || !renderArea || !epubBook) return;

  const { theme, fontSize, fontFamily, lineHeight, paragraphSpacing } = getViewerSettings();
  const fontCSS = resolveFontCSS(fontFamily);
  const scrollMode = getScrollMode();
  isEpubRelayouting = true;

  try {

  // During page-mode relayout (e.g., 1-page <-> 2-page toggle),
  // capture the latest rendition location and prefer pointer-based restore.
  if (scrollMode === 'page' && options.preservePagePosition && epubRendition) {
    try {
      const liveLoc = epubRendition.currentLocation && epubRendition.currentLocation();
      if (liveLoc && liveLoc.start) {
        currentLocationCfi = liveLoc.start.cfi || currentLocationCfi;
        currentLocationHref = liveLoc.start.href || currentLocationHref;
        if (Number.isInteger(liveLoc.start.index)) {
          currentLocationIndex = liveLoc.start.index;
        }
        persistResumeSession({
          cfi: currentLocationCfi,
          href: currentLocationHref,
          index: currentLocationIndex
        });
      }
    } catch (_) {
      // ignore live location read errors and fallback to ratio path
    }
  }

  const preservePagePosition = !!options.preservePagePosition;
  const preferResumeStart = (
    (scrollMode === 'page' && preservePagePosition && !!(currentLocationCfi || currentLocationHref)) ||
    (!!options.preferResumeStart && scrollMode === 'page' && !!(currentLocationCfi || currentLocationHref))
  );
  const explicitRatio = Number.isFinite(options.targetRatio) ? options.targetRatio : null;
  const fallbackRatio = currentScrollPercent / 100;

  // On mode switches, derive ratio from the currently active renderer state,
  // not only from the newly selected mode.
  const ratioSourceMode = preservePagePosition
    ? (epubRendition ? 'page' : 'scroll')
    : scrollMode;

  const baseRatio = preferResumeStart
    ? null
    : explicitRatio !== null
      ? explicitRatio
      : (preservePagePosition
        ? await getCurrentRatio({
          container,
          scrollMode: ratioSourceMode,
          book: epubBook,
          rendition: epubRendition,
          fallbackPercent: currentScrollPercent,
          charsPerLocation: RENDITION_LOCATIONS_CHARS
        })
        : fallbackRatio);
  const ratio = baseRatio === null ? null : Math.min(1, Math.max(0, baseRatio));

  if (runId !== applySettingsRunId) return;

  applyBaseContainerStyles(container, renderArea, theme);

  if (scrollMode === 'scroll') {
    await destroyRendition();
    const coverFallbackUrl = activeCoverFallbackUrl || '/static/images/default_cover.jpg';

    mergedContentEl = await renderScrollMode({
      container,
      renderArea,
      mergedContentEl,
      book: epubBook,
      ratio: ratio === null ? fallbackRatio : ratio,
      buildMergedContent: book => buildMergedContent(book, { coverFallbackUrl }),
      applyMergedThemeStyles,
      themeSettings: { theme, fontCSS, fontSize, lineHeight, paragraphSpacing },
      updateProgressPercent,
      isRunCurrent: () => runId === applySettingsRunId
    });

    return;
  }

  container.style.overflowY = 'hidden';
  container.style.overflowX = 'hidden';
  container.style.scrollBehavior = 'auto';

  const renderedRendition = await activateRenditionPageMode({
    renderArea,
    ratio,
    themeSettings: {
      theme,
      fontCSS,
      fontSize,
      lineHeight,
      paragraphSpacing
    },
    book: epubBook,
    getViewportSize,
    getEpubPageStep,
    getEffectivePageStep,
    syncPageStepUI,
    currentRendition: epubRendition,
    destroyRendition,
    bindRenditionInteractionHandlers,
    getScrollMode,
    goBackward: goBackwardByReadingDirection,
    goForward: goForwardByReadingDirection,
    toggleOverlay: typeof window !== 'undefined' ? window.toggleComicOverlay : null,
    ensureLocations,
    locationsChars: RENDITION_LOCATIONS_CHARS,
    applyRenditionTheme,
    safeRenditionDisplay,
    currentLocationCfi,
    currentLocationHref,
    setCurrentLocation: location => {
      if (!location) return;
      currentLocationCfi = location.cfi || currentLocationCfi;
      currentLocationHref = location.href || currentLocationHref;
      if (Number.isInteger(location.index)) {
        currentLocationIndex = location.index;
      }
      persistResumeSession({
        cfi: currentLocationCfi,
        href: currentLocationHref,
        index: currentLocationIndex
      });
      if (currentLocationCfi) {
        persistCurrentLocationCfi(currentLocationCfi);
      }
    },
    setRenditionAtEnd: atEnd => {
      renditionAtEnd = atEnd;
    },
    updateProgressPercent,
    isRunCurrent: () => runId === applySettingsRunId
  });

  if (renderedRendition) {
    epubRendition = renderedRendition;
  }

  if (runId !== applySettingsRunId) return;

    if (scrollMode === 'page' && epubRendition && !hasRenderableRenditionLocation(epubRendition)) {
      await recoverBlankPageModeView('next');
    }

    if (ratio !== null) {
      updateProgressPercent(ratio * 100);
    }
  } finally {
    if (runId === applySettingsRunId) {
      isEpubRelayouting = false;
      flushQueuedPageNavigation();
    }
  }
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
    await resolveActiveBookCoverFallbackUrl(bookId);

    bindContainerScroll();
    bindRenderAreaClick({
      renderArea,
      getScrollMode,
      goBackward: goBackwardByReadingDirection,
      goForward: goForwardByReadingDirection,
      toggleOverlay: typeof window !== 'undefined' ? window.toggleComicOverlay : null
    });
    bindViewportListeners();

    await restoreEpubProgress(pagesRead, totalPages || 100);

    hideViewerLoading();
  } catch (err) {
    hideViewerLoading();
    console.error('[Viewer-Epub] init failed:', err);
    showViewerError(i18n.t('viewer.error_epub_title') || 'EPUB 로드 오류', err.message);
  }
}

function normalizeInitialEpubProgress(pagesRead, totalPages) {
  const rawRead = Number.isFinite(Number(pagesRead)) ? Number(pagesRead) : 0;
  const rawTotal = Number.isFinite(Number(totalPages)) ? Number(totalPages) : 0;

  let ratio = 0;

  if (rawTotal > 0) {
    ratio = rawRead / rawTotal;
  } else if (rawRead > 1) {
    // If total page info is missing, treat read value as a stored percent-like value.
    ratio = rawRead / 100;
  } else {
    // Already ratio-like input (0~1) from external source.
    ratio = rawRead;
  }

  const clampedRatio = Math.min(1, Math.max(0, Number.isFinite(ratio) ? ratio : 0));
  const roundedPercent = Math.round(clampedRatio * 100);
  // Prevent "read a little" from collapsing to 0% and reopening at page 1.
  const percent = rawRead > 0 && roundedPercent === 0 ? 1 : roundedPercent;

  // EPUB progress must be normalized to total=100 regardless of scanner page metadata.
  const shouldNormalizePersist = rawTotal !== 100 || Math.round(rawRead) !== percent;

  return {
    ratio: clampedRatio,
    percent,
    shouldNormalizePersist
  };
}

function normalizeSessionUpdatedAtMs(sessionData) {
  if (!sessionData || !sessionData.updatedAt) return 0;
  const ms = Date.parse(String(sessionData.updatedAt));
  return Number.isFinite(ms) ? ms : 0;
}

async function fetchServerProgressState(bookId) {
  if (!bookId) return null;
  const dbType = state.currentLibraryType || 'general';
  try {
    const res = await fetch(`/api/media/progress-state?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}`);
    if (!res.ok) return null;
    const data = await res.json();
    if (!data || !data.success || !data.state) return null;
    return data.state;
  } catch (err) {
    console.warn('[Viewer-Epub] progress-state fetch failed:', err);
    return null;
  }
}

async function restoreEpubProgress(pagesRead, totalPages) {
  const serverState = await fetchServerProgressState(state.activeBookId);
  const sourcePagesRead = serverState && Number.isFinite(Number(serverState.pages_read))
    ? Number(serverState.pages_read)
    : pagesRead;
  const sourceTotalPages = serverState && Number.isFinite(Number(serverState.total_pages))
    ? Number(serverState.total_pages)
    : totalPages;

  const normalized = normalizeInitialEpubProgress(sourcePagesRead, sourceTotalPages);
  const localSession = loadPersistedResumeSession(state.activeBookId);
  const serverSession = serverState && serverState.epub_session ? serverState.epub_session : null;
  const localUpdatedAt = normalizeSessionUpdatedAtMs(localSession);
  const serverUpdatedAt = normalizeSessionUpdatedAtMs(serverSession);
  const preferredSession = (serverUpdatedAt > localUpdatedAt) ? serverSession : (localSession || serverSession);

  if (preferredSession && preferredSession.cfi) {
    currentLocationCfi = preferredSession.cfi;
  } else {
    const fallbackCfi = loadPersistedLocationCfi(state.activeBookId);
    if (fallbackCfi) currentLocationCfi = fallbackCfi;
  }

  if (preferredSession && preferredSession.href) {
    currentLocationHref = preferredSession.href;
  }
  if (preferredSession && Number.isInteger(preferredSession.index)) {
    currentLocationIndex = preferredSession.index;
  }

  epubTotalPages = 100;
  currentScrollPercent = normalized.percent;
  if (preferredSession && Number.isFinite(Number(preferredSession.percent))) {
    currentScrollPercent = Math.min(100, Math.max(0, Math.round(Number(preferredSession.percent))));
  }

  applyEpubSettings(
    (currentLocationCfi || currentLocationHref)
      ? { preferResumeStart: true }
      : { targetRatio: normalized.ratio }
  );

  if (preferredSession && (preferredSession.cfi || preferredSession.href)) {
    persistResumeSession({
      cfi: preferredSession.cfi || null,
      href: preferredSession.href || null,
      index: Number.isInteger(preferredSession.index) ? preferredSession.index : null,
      percent: Number.isFinite(Number(preferredSession.percent)) ? Number(preferredSession.percent) : currentScrollPercent
    });
  }

  if (normalized.shouldNormalizePersist && state.activeBookId) {
    // One-time normalization on open for legacy scanner values.
    saveProgress(state.activeBookId, normalized.percent, 100);
  }
}

export function applyEpubSettings(options = {}) {
  applyEpubSettingsInternal(options).catch(err => {
    console.error('[Viewer-Epub] apply settings failed:', err);
  });
}

export function changeEpubScrollMode() {
  if (!epubBook) return;
  applyEpubSettings({ preservePagePosition: true });
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

  if (!epubRendition) return;
  if (isEpubRelayouting) {
    queuePageNavigation('prev');
    return;
  }
  if (isEpubPageNavigating) {
    queuePageNavigation('prev');
    return;
  }

  isEpubPageNavigating = true;

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
    // keep persisted pointer fallback
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
      isEpubPageNavigating = false;
      flushQueuedPageNavigation();
    });
}

export function epubNextPage() {
  if (!epubBook) return;

  const scrollMode = getScrollMode();
  const container = document.getElementById('epub-viewer-container');
  if (!container) return;

  if (scrollMode === 'scroll') {
    const isAtEnd = container.scrollTop + container.clientHeight >= container.scrollHeight - 5;
    if (isAtEnd) {
      import('../../viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    } else {
      container.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' });
    }
    return;
  }

  if (!epubRendition) return;
  if (isEpubRelayouting) {
    queuePageNavigation('next');
    return;
  }
  if (isEpubPageNavigating) {
    queuePageNavigation('next');
    return;
  }

  if (isAtAbsoluteEndInPageMode()) {
    import('../../viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
    return;
  }

  isEpubPageNavigating = true;

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
    // keep persisted pointer fallback
  }

  epubRendition.next()
    .then(() => recoverBlankPageModeView('next', { baseHref, baseIndex }))
    .catch(err => {
      if (isNoSectionFoundError(err)) {
        displayAdjacentSpine(epubRendition, 'next').then(ok => {
          if (ok) return;

          // If adjacent recovery fails away from the real end, stay in-book and avoid false next-episode jump.
          if (!isAtAbsoluteEndInPageMode()) {
            safeRenditionDisplay(epubRendition, currentLocationCfi || null);
            return;
          }

          import('../../viewer_next_episode.js').then(m => m.handleNextEpisode(state.activeBookId));
        });
        return;
      }
      console.warn('[Viewer-Epub] next failed:', err);
    })
    .finally(() => {
      isEpubPageNavigating = false;
      flushQueuedPageNavigation();
    });
}

export function clearEpubViewer() {
  unbindViewportListeners();

  destroyRendition().finally(() => {
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
    isEpubPageNavigating = false;
    isEpubRelayouting = false;
    pendingPageNavDirection = null;
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

  ensureLocations(epubBook, RENDITION_LOCATIONS_CHARS).catch(err => {
    console.warn('[Viewer-Epub] slider locations generation failed:', err);
  }).then(async () => {
    let cfi = null;
    try {
      cfi = epubBook.locations && epubBook.locations.length
        ? epubBook.locations.cfiFromPercentage(Math.min(0.999, ratio))
        : null;
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
