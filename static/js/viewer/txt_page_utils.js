import { viewerStorage } from './storage.js';

const localStorage = viewerStorage;

export function getTxtPageGapPx(scrollWrapper) {
  if (!scrollWrapper) return 0;
  const pageStep = localStorage.getItem('comic_page_step') || '1';
  if (pageStep !== '2') return 0;

  // In page mode, multi-column styles are applied to contentArea (not wrapper).
  const contentArea = document.getElementById('txt-content-area');
  const target = contentArea || scrollWrapper;
  const styles = window.getComputedStyle(target);
  const gap = parseFloat(styles.columnGap);
  return Number.isFinite(gap) ? gap : 0;
}

export function getTxtPageAdvanceWidth(scrollWrapper) {
  if (!scrollWrapper) return 0;
  const base = Math.max(1, Math.floor(scrollWrapper.clientWidth));
  return base + getTxtPageGapPx(scrollWrapper);
}

export function snapTxtPageScrollLeft(scrollWrapper) {
  if (!scrollWrapper) return;
  const stepWidth = getTxtPageAdvanceWidth(scrollWrapper);
  const maxScroll = Math.max(0, scrollWrapper.scrollWidth - scrollWrapper.clientWidth);
  const snapped = Math.min(maxScroll, Math.max(0, Math.round(scrollWrapper.scrollLeft / stepWidth) * stepWidth));
  scrollWrapper.scrollLeft = snapped;
}
