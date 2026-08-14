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

export function applyTxtTwoPageTrailingSpacer(scrollWrapper, contentArea) {
  if (!scrollWrapper || !contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const pageStep = localStorage.getItem('comic_page_step') || '1';
  if (scrollMode !== 'page' || pageStep !== '2') return;

  // Recalculate from a clean baseline to avoid oscillation across repeated renders.
  contentArea.style.paddingRight = '0px';

  const stepWidth = getTxtPageAdvanceWidth(scrollWrapper);
  if (!Number.isFinite(stepWidth) || stepWidth <= 0) return;

  // scrollWrapper/contentArea는 항상 스프레드(2컬럼) 전체 폭으로 고정 렌더링되므로,
  // 챕터 내용이 1컬럼 분량밖에 안 되는 짧은 챕터에서도 scrollWidth가 항상 2컬럼 폭
  // 그대로 측정되어 실제 컬럼(페이지) 개수를 반영하지 못한다(=늘 짝수로 오판).
  // 대신 컬럼을 임시로 1개로 풀어 "단일 컬럼 기준 총 높이"를 측정하고, 컬럼 1개의
  // 가용 높이로 나눠 실제 컬럼 수를 역산한다 — 폭이 아니라 높이 기반이라 챕터
  // 길이와 무관하게 정확하다.
  const columnHeight = contentArea.clientHeight;
  if (!Number.isFinite(columnHeight) || columnHeight <= 0) return;

  const prevColumnWidth = contentArea.style.columnWidth;
  const prevColumnCount = contentArea.style.columnCount;
  contentArea.style.columnWidth = '';
  contentArea.style.columnCount = '1';
  const naturalHeight = contentArea.scrollHeight;
  contentArea.style.columnWidth = prevColumnWidth;
  contentArea.style.columnCount = prevColumnCount;

  const pageCount = Math.max(1, Math.ceil(naturalHeight / columnHeight));
  const hasOddTailPage = pageCount % 2 === 1;

  if (hasOddTailPage) {
    contentArea.style.paddingRight = `${Math.round(stepWidth / 2)}px`;
  }
}
