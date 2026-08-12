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

  // txt_settings_apply.js가 columnWidth를 이 값으로 픽셀 고정하므로,
  // 스프레드 폭 기반의 어림 판정 대신 실제 컬럼(페이지) 개수를 역산해 홀짝을 정확히 판정한다.
  // (기존의 fraction±0.12 휴리스틱은 기기별 서브픽셀/폰트 반올림 오차에 취약해
  //  홀수 챕터에서 페이지 반복(PC) / 챕터 전환 안 됨(Android) 버그의 원인이었다.)
  const gap = getTxtPageGapPx(scrollWrapper);
  const singleColWidth = Math.max(1, (stepWidth - gap) / 2);
  const totalWidth = scrollWrapper.scrollWidth;
  const pageCount = Math.max(1, Math.round((totalWidth + gap) / (singleColWidth + gap)));
  const hasOddTailPage = pageCount % 2 === 1;

  if (hasOddTailPage) {
    contentArea.style.paddingRight = `${Math.round(stepWidth / 2)}px`;
  }
}
