import { state } from '../../state.js';
import { saveProgress } from '../../viewer_progress.js';
import { updateProgressPercent as updateProgressPercentBase, syncSeekBarUI } from './location_progress.js';
import { getScrollMode } from './ui_helpers.js';
import * as storage from './epub_storage.js';

export function normalizeInitialEpubProgress(pagesRead, totalPages) {
  const rawRead = Number.isFinite(Number(pagesRead)) ? Number(pagesRead) : 0;
  const rawTotal = Number.isFinite(Number(totalPages)) ? Number(totalPages) : 0;

  let ratio = 0;

  if (rawTotal > 0) {
    ratio = rawRead / rawTotal;
  } else if (rawRead > 1) {
    ratio = rawRead / 100;
  } else {
    ratio = rawRead;
  }

  const clampedRatio = Math.min(1, Math.max(0, Number.isFinite(ratio) ? ratio : 0));
  const roundedPercent = Math.round(clampedRatio * 100);
  const percent = rawRead > 0 && roundedPercent === 0 ? 1 : roundedPercent;
  const shouldNormalizePersist = rawTotal !== 100 || Math.round(rawRead) !== percent;

  return {
    ratio: clampedRatio,
    percent,
    shouldNormalizePersist
  };
}

export function normalizeSessionUpdatedAtMs(sessionData) {
  if (!sessionData || !sessionData.updatedAt) return 0;
  const ms = Date.parse(String(sessionData.updatedAt));
  return Number.isFinite(ms) ? ms : 0;
}

export async function fetchServerProgressState(bookId) {
  if (!bookId) return null;
  const dbType = state.currentLibraryType || 'general';
  try {
    const res = await fetch(`/api/media/progress-state?db_type=${encodeURIComponent(dbType)}&book_id=${encodeURIComponent(bookId)}`);
    if (!res.ok) return null;
    const data = await res.json();
    if (!data || !data.success || !data.state) return null;
    return data.state;
  } catch (err) {
    console.warn('[Viewer-Epub-Progress] progress-state fetch failed:', err);
    return null;
  }
}

export function updateProgressPercent({
  percent,
  context,
  updateLocalScrollPercent,
  applyEpubSettings
}) {
  const epubSessionPayload = (context.currentLocationCfi || context.currentLocationHref)
    ? {
      epub_session: {
        cfi: context.currentLocationCfi,
        href: context.currentLocationHref,
        index: context.currentLocationIndex,
        percent: Math.min(100, Math.max(0, Math.round(percent))),
        updatedAt: new Date().toISOString()
      }
    }
    : null;

  const currentScrollPercent = updateProgressPercentBase({
    percent,
    stateBookId: state.activeBookId,
    saveProgress,
    syncSeekBar: syncSeekBarUI,
    extraData: epubSessionPayload
  });

  updateLocalScrollPercent(currentScrollPercent);

  if (getScrollMode() === 'page' && (context.currentLocationCfi || context.currentLocationHref)) {
    storage.persistResumeSession(
      { percent: currentScrollPercent },
      state.activeBookId,
      {
        currentLocationCfi: context.currentLocationCfi,
        currentLocationHref: context.currentLocationHref,
        currentLocationIndex: context.currentLocationIndex,
        currentScrollPercent
      }
    );
  }

  return currentScrollPercent;
}

export async function restoreEpubProgress({
  pagesRead,
  totalPages,
  context,
  updateState,
  applyEpubSettings
}) {
  const serverState = await fetchServerProgressState(state.activeBookId);
  const sourcePagesRead = serverState && Number.isFinite(Number(serverState.pages_read))
    ? Number(serverState.pages_read)
    : pagesRead;
  const sourceTotalPages = serverState && Number.isFinite(Number(serverState.total_pages))
    ? Number(serverState.total_pages)
    : totalPages;

  const normalized = normalizeInitialEpubProgress(sourcePagesRead, sourceTotalPages);
  const localSession = storage.loadPersistedResumeSession(state.activeBookId);
  const serverSession = serverState && serverState.epub_session ? serverState.epub_session : null;
  const localUpdatedAt = normalizeSessionUpdatedAtMs(localSession);
  const serverUpdatedAt = normalizeSessionUpdatedAtMs(serverSession);
  const preferredSession = (serverUpdatedAt > localUpdatedAt) ? serverSession : (localSession || serverSession);

  let cfi = context.currentLocationCfi;
  let href = context.currentLocationHref;
  let index = context.currentLocationIndex;

  if (preferredSession && preferredSession.cfi) {
    cfi = preferredSession.cfi;
  } else {
    const fallbackCfi = storage.loadPersistedLocationCfi(state.activeBookId);
    if (fallbackCfi) cfi = fallbackCfi;
  }

  if (preferredSession && preferredSession.href) {
    href = preferredSession.href;
  }
  if (preferredSession && Number.isInteger(preferredSession.index)) {
    index = preferredSession.index;
  }

  let scrollPercent = normalized.percent;
  if (preferredSession && Number.isFinite(Number(preferredSession.percent))) {
    scrollPercent = Math.min(100, Math.max(0, Math.round(Number(preferredSession.percent))));
  }

  updateState({
    currentLocationCfi: cfi,
    currentLocationHref: href,
    currentLocationIndex: index,
    currentScrollPercent: scrollPercent
  });

  applyEpubSettings(
    (cfi || href)
      ? { preferResumeStart: true }
      : { targetRatio: normalized.ratio }
  );

  if (preferredSession && (cfi || href)) {
    storage.persistResumeSession({
      cfi: cfi || null,
      href: href || null,
      index: Number.isInteger(index) ? index : null,
      percent: Number.isFinite(Number(preferredSession.percent)) ? Number(preferredSession.percent) : scrollPercent
    }, state.activeBookId, {
      currentLocationCfi: cfi,
      currentLocationHref: href,
      currentLocationIndex: index,
      currentScrollPercent: scrollPercent
    });
  }

  if (normalized.shouldNormalizePersist && state.activeBookId) {
    saveProgress(state.activeBookId, scrollPercent, 100);
  }
}
