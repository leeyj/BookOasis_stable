export async function ensureLocations(book, charsPerLocation) {
  if (!book) return;
  if (!book.locations || !book.locations.length) {
    await book.locations.generate(charsPerLocation);
  }
}

export function getCurrentRatioFromScroll(container, fallbackPercent) {
  if (!container) return fallbackPercent / 100;
  const totalScroll = container.scrollHeight - container.clientHeight;
  if (totalScroll <= 0) return 0;
  return Math.min(1, Math.max(0, container.scrollTop / totalScroll));
}

export async function getCurrentRatioFromRendition({ book, rendition, fallbackPercent, charsPerLocation }) {
  if (!book || !rendition) return fallbackPercent / 100;

  const location = rendition.currentLocation();
  const cfi = location && location.start ? location.start.cfi : null;
  if (!cfi) return fallbackPercent / 100;

  await ensureLocations(book, charsPerLocation);
  const ratio = book.locations.percentageFromCfi(cfi);
  return Number.isFinite(ratio) ? Math.min(1, Math.max(0, ratio)) : (fallbackPercent / 100);
}

export async function getCurrentRatio({
  container,
  scrollMode,
  book,
  rendition,
  fallbackPercent,
  charsPerLocation
}) {
  if (!container) return fallbackPercent / 100;
  if (scrollMode === 'scroll') {
    return getCurrentRatioFromScroll(container, fallbackPercent);
  }
  return getCurrentRatioFromRendition({
    book,
    rendition,
    fallbackPercent,
    charsPerLocation
  });
}

export function updateProgressPercent({ percent, stateBookId, saveProgress, syncSeekBar, extraData = null }) {
  const clamped = Math.min(100, Math.max(0, Math.round(percent)));
  saveProgress(stateBookId, clamped, 100, extraData);
  if (typeof syncSeekBar === 'function') {
    syncSeekBar(clamped);
  }
  return clamped;
}

export function syncSeekBarUI(percent) {
  const slider = document.getElementById('viewer-page-slider');
  if (slider) {
    slider.min = 0;
    slider.max = 100;
    slider.value = percent;
  }

  const endLabel = document.getElementById('seekbar-end-label');
  if (endLabel) endLabel.textContent = '100%';

  const badge = document.getElementById('comic-overlay-page-info');
  if (badge) badge.textContent = `${percent}%`;
}
