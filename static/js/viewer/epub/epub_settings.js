import { getViewerSettings } from '../../viewer_settings.js';
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
import { bindRenditionInteractionHandlers } from './interactions.js';
import {
  ensureLocations,
  getCurrentRatio
} from './location_progress.js';
import { buildMergedContent } from './content_builder.js';
import { activateRenditionPageMode } from './page_mode.js';
import { applyBaseContainerStyles, renderScrollMode } from './scroll_mode.js';

import * as storage from './epub_storage.js';
import * as navigation from './epub_navigation.js';

let applySettingsRunId = 0;
let viewportResizeRaf = null;

export function getApplySettingsRunId() {
  return applySettingsRunId;
}

export function bindViewportListeners({ epubBook, applyEpubSettings }) {
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

export function unbindViewportListeners() {
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

export async function applyEpubSettingsInternal({
  options = {},
  epubBook,
  getEpubRendition,
  setEpubRendition,
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
}) {
  const runId = ++applySettingsRunId;

  const container = document.getElementById('epub-viewer-container');
  const renderArea = document.getElementById('epub-render-area');
  if (!container || !renderArea || !epubBook) return;

  const { theme, fontSize, fontFamily, lineHeight, paragraphSpacing } = getViewerSettings();
  const fontCSS = resolveFontCSS(fontFamily);
  const scrollMode = getScrollMode();
  navigation.setEpubRelayouting(true);

  try {
    const epubRendition = getEpubRendition();
    const context = getContext();

    if (scrollMode === 'page' && options.preservePagePosition && epubRendition) {
      try {
        const liveLoc = epubRendition.currentLocation && epubRendition.currentLocation();
        if (liveLoc && liveLoc.start) {
          const newCfi = liveLoc.start.cfi || context.currentLocationCfi;
          const newHref = liveLoc.start.href || context.currentLocationHref;
          const newIndex = Number.isInteger(liveLoc.start.index) ? liveLoc.start.index : context.currentLocationIndex;

          updateContext({
            currentLocationCfi: newCfi,
            currentLocationHref: newHref,
            currentLocationIndex: newIndex
          });

          storage.persistResumeSession({
            cfi: newCfi,
            href: newHref,
            index: newIndex
          }, context.activeBookId, getStorageContext());
        }
      } catch (_) {
        // ignore
      }
    }

    const contextUpdated = getContext();
    const preservePagePosition = !!options.preservePagePosition;
    const preferResumeStart = (
      !!options.preferResumeStart && !!(contextUpdated.currentLocationCfi || contextUpdated.currentLocationHref || contextUpdated.currentScrollPercent)
    );
    const explicitRatio = Number.isFinite(options.targetRatio) ? options.targetRatio : null;
    const fallbackRatio = contextUpdated.currentScrollPercent / 100;

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
              fallbackPercent: contextUpdated.currentScrollPercent,
              charsPerLocation: RENDITION_LOCATIONS_CHARS
            })
          : fallbackRatio);
    const ratio = baseRatio === null ? null : Math.min(1, Math.max(0, baseRatio));

    if (runId !== applySettingsRunId) return;

    applyBaseContainerStyles(container, renderArea, theme);

    if (scrollMode === 'scroll') {
      await destroyRendition();
      const coverFallbackUrl = activeCoverFallbackUrl || '/static/images/default_cover.jpg';

      const mergedEl = await renderScrollMode({
        container,
        renderArea,
        mergedContentEl: contextUpdated.mergedContentEl,
        book: epubBook,
        ratio: ratio === null ? fallbackRatio : ratio,
        buildMergedContent: book => buildMergedContent(book, { coverFallbackUrl }),
        applyMergedThemeStyles,
        themeSettings: { theme, fontCSS, fontSize, lineHeight, paragraphSpacing },
        updateProgressPercent,
        isRunCurrent: () => runId === applySettingsRunId,
        currentLocationHref: contextUpdated.currentLocationHref
      });

      updateContext({ mergedContentEl: mergedEl });
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
      currentLocationCfi: contextUpdated.currentLocationCfi,
      currentLocationHref: contextUpdated.currentLocationHref,
      setCurrentLocation: location => {
        if (!location) return;
        const currentContext = getContext();
        const nextCfi = location.cfi || currentContext.currentLocationCfi;
        const nextHref = location.href || currentContext.currentLocationHref;
        const nextIndex = Number.isInteger(location.index) ? location.index : currentContext.currentLocationIndex;

        updateContext({
          currentLocationCfi: nextCfi,
          currentLocationHref: nextHref,
          currentLocationIndex: nextIndex
        });

        storage.persistResumeSession({
          cfi: nextCfi,
          href: nextHref,
          index: nextIndex
        }, currentContext.activeBookId, getStorageContext());
        if (nextCfi) {
          storage.persistCurrentLocationCfi(nextCfi, currentContext.activeBookId, getStorageContext());
        }
      },
      setRenditionAtEnd: atEnd => {
        updateContext({ renditionAtEnd: atEnd });
      },
      updateProgressPercent,
      isRunCurrent: () => runId === applySettingsRunId
    });

    if (renderedRendition) {
      setEpubRendition(renderedRendition);
    }

    if (runId !== applySettingsRunId) return;

    const freshRendition = getEpubRendition();
    if (scrollMode === 'page' && freshRendition && !navigation.hasRenderableRenditionLocation(freshRendition)) {
      await recoverBlankPageModeView('next');
    }

    if (ratio !== null) {
      updateProgressPercent(ratio * 100);
    } else {
      // ratio가 null이더라도 (모드 전환 등의 상황), 현재 스크롤 백분율로 슬라이더 범위 및 값을 0~100% 규격으로 확실히 리셋 동기화
      updateProgressPercent(contextUpdated.currentScrollPercent);
    }
  } finally {
    if (runId === applySettingsRunId) {
      navigation.setEpubRelayouting(false);
      navigation.flushQueuedPageNavigation({
        next: epubNextPage,
        prev: epubPrevPage
      });
    }
  }
}
