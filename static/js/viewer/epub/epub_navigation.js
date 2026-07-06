import { getScrollMode, getReadingDirection } from './ui_helpers.js';
import { state } from '../../state.js';

let isEpubPageNavigating = false;
let isEpubRelayouting = false;
let pendingPageNavDirection = null;

export function getNavigationState() {
  return { isEpubPageNavigating, isEpubRelayouting };
}

export function setEpubRelayouting(val) {
  isEpubRelayouting = val;
}

export function setEpubPageNavigating(val) {
  isEpubPageNavigating = val;
}

export function queuePageNavigation(direction) {
  if (direction !== 'next' && direction !== 'prev') return;
  pendingPageNavDirection = direction;
}

export function flushQueuedPageNavigation(actions) {
  if (isEpubRelayouting || isEpubPageNavigating) return;
  const direction = pendingPageNavDirection;
  if (!direction) return;

  pendingPageNavDirection = null;
  if (direction === 'next') {
    actions.next();
  } else {
    actions.prev();
  }
}

export function resetNavigationState() {
  isEpubPageNavigating = false;
  isEpubRelayouting = false;
  pendingPageNavDirection = null;
}

export async function recoverBlankPageModeView({
  epubRendition,
  direction = 'next',
  context = {},
  displayAdjacentFromKnownPointer,
  displayAdjacentSpine,
  fallbackDisplayFromSpine
}) {
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

export function hasRenderableRenditionLocation(rendition) {
  if (!rendition || typeof rendition.currentLocation !== 'function') return false;
  try {
    const loc = rendition.currentLocation();
    const start = loc && loc.start ? loc.start : null;
    return !!(start && (start.cfi || start.href || Number.isInteger(start.index)));
  } catch (_) {
    return false;
  }
}
