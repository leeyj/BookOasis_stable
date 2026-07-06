import { state } from '../../state.js';

export function getEpubLocationKey(bookId) {
  const lib = state.currentLibraryType || 'default';
  const id = bookId || state.activeBookId;
  if (!id) return null;
  return `epub_last_cfi:${lib}:${id}`;
}

export function getEpubSessionKey(bookId) {
  const lib = state.currentLibraryType || 'default';
  const id = bookId || state.activeBookId;
  if (!id) return null;
  return `epub_last_session:${lib}:${id}`;
}

export function persistResumeSession(partial = {}, bookId, { currentLocationCfi, currentLocationHref, currentLocationIndex, currentScrollPercent }) {
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
    // ignore
  }
}

export function persistCurrentLocationCfi(cfi, bookId, context) {
  if (!cfi) return;
  const key = getEpubLocationKey(bookId);
  if (!key) return;
  try {
    localStorage.setItem(key, cfi);
    persistResumeSession({ cfi }, bookId, context);
  } catch (_) {
    // ignore
  }
}

export function loadPersistedResumeSession(bookId) {
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

export function loadPersistedLocationCfi(bookId) {
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
