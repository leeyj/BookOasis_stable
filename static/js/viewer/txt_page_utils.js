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

export function getTxtPageMaxScroll(scrollWrapper) {
  if (!scrollWrapper) return 0;
  return Math.max(0, scrollWrapper.scrollWidth - scrollWrapper.clientWidth);
}

// 챕터의 마지막 페이지(컬럼 스프레드)는 폭이 꽉 차지 않는 경우가 많아,
// maxScroll이 stepWidth의 정확한 배수가 아닐 수 있다. 이 경우 "가장 가까운
// stepWidth 배수"로의 단순 반올림은 실제로는 마지막 페이지(maxScroll)에 더
// 가까운 위치를 그 앞 페이지로 잘못 판정할 수 있다 — next 탭이 챕터 경계에
// 영영 도달 못 하거나(snapTxtPageScrollLeft), resize 시 마지막 페이지에 있던
// 사용자가 앞 페이지로 되돌아가 버리는(handleResize) 문제로 이어진다.
export function isTxtScrollLeftAtMaxPage(scrollWrapper) {
  if (!scrollWrapper) return false;
  const stepWidth = getTxtPageAdvanceWidth(scrollWrapper);
  if (stepWidth <= 0) return false;
  const maxScroll = getTxtPageMaxScroll(scrollWrapper);
  const current = scrollWrapper.scrollLeft;
  const roundedStop = Math.min(maxScroll, Math.max(0, Math.round(current / stepWidth) * stepWidth));
  return Math.abs(current - maxScroll) < Math.abs(current - roundedStop);
}

export function snapTxtPageScrollLeft(scrollWrapper) {
  if (!scrollWrapper) return;
  const stepWidth = getTxtPageAdvanceWidth(scrollWrapper);
  if (stepWidth <= 0) return;

  const maxScroll = getTxtPageMaxScroll(scrollWrapper);
  const current = scrollWrapper.scrollLeft;
  const roundedStop = Math.min(maxScroll, Math.max(0, Math.round(current / stepWidth) * stepWidth));
  scrollWrapper.scrollLeft = isTxtScrollLeftAtMaxPage(scrollWrapper) ? maxScroll : roundedStop;
}

// 삽화 이미지의 max-height가 뷰포트(vh) 기준으로 박혀 있으면, 실제 한 페이지(컬럼)
// 높이는 상하 여백만큼 뷰포트보다 작으므로 이미지가 페이지 하나를 넘겨버려
// (이미지는 컬럼 중간에서 쪼갤 수 없는 요소라) 다음 페이지가 통째로 빈 페이지가 된다.
// 실제 컬럼 높이 기준으로 max-height를 다시 계산해 덮어쓴다.
export function applyTxtImageMaxHeight(scrollWrapper, contentArea) {
  if (!scrollWrapper || !contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const images = contentArea.querySelectorAll('img');
  if (!images.length) return;

  if (scrollMode !== 'page') {
    // 스크롤 모드는 컬럼 개념이 없어 원래(vh 기준) 제한을 그대로 둔다.
    images.forEach((img) => { img.style.maxHeight = ''; });
    return;
  }

  const columnHeight = contentArea.clientHeight;
  if (!Number.isFinite(columnHeight) || columnHeight <= 0) return;

  const IMG_VERTICAL_MARGIN = 48; // 서버 렌더링 시 img에 붙는 margin: 1.5rem auto (상+하)
  const SAFETY_BUFFER = 8;
  const maxHeightPx = Math.max(80, Math.floor(columnHeight - IMG_VERTICAL_MARGIN - SAFETY_BUFFER));
  images.forEach((img) => { img.style.maxHeight = `${maxHeightPx}px`; });
}

export function applyTxtTwoPageTrailingSpacer(scrollWrapper, contentArea) {
  if (!scrollWrapper || !contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const pageStep = localStorage.getItem('comic_page_step') || '1';
  if (scrollMode !== 'page' || pageStep !== '2') return;

  // Recalculate from a clean baseline to avoid oscillation across repeated renders.
  // (marginRight/spacer-div 방식은 둘 다 실기기 로그로 무효 확인됨 — 아래 참고)
  contentArea.style.marginRight = '0px';
  // .txt-content CSS 규칙이 width:100%로 고정돼 있어(CSS class, tab_media_library_viewer.css),
  // 아래 실측 전에 반드시 인라인 width를 걷어내야 "이전 홀수 보정으로 넓혀둔 폭"이
  // 이번 측정에 섞여 들어가지 않는다.
  contentArea.style.width = '';

  if (!Number.isFinite(scrollWrapper.clientWidth) || scrollWrapper.clientWidth <= 0) return;

  // column-count:auto + 고정 column-width 조합에서는 컨텐츠가 필요로 하는 만큼
  // 컬럼이 옆으로 늘어나며 contentArea.scrollWidth가 실제 컬럼 개수를 그대로
  // 반영한다(이전엔 이 값이 항상 2컬럼 폭에 고정된다고 잘못 가정해, column-count를
  // 임시로 1로 풀어 높이 기반으로 페이지 수를 역산했다 — 하지만 그 측정은 컬럼
  // 폭이 아닌 컨테이너 전체 폭으로 줄바꿈되어 실제보다 짧은 높이를 재는 바람에
  // 홀수 컬럼 챕터를 짝수로 오판해, 마지막 스프레드가 이미 본 컬럼을 다시
  // 보여주는(중복 표시) 버그의 원인이었다). 실측 scrollWidth로 직접 역산한다.
  const styles = window.getComputedStyle(contentArea);
  const columnWidthPx = parseFloat(styles.columnWidth);
  const columnGapPx = parseFloat(styles.columnGap) || 0;
  if (!Number.isFinite(columnWidthPx) || columnWidthPx <= 0) return;
  const columnUnitWidth = columnWidthPx + columnGapPx;
  if (columnUnitWidth <= 0) return;

  const pageCount = Math.max(1, Math.round((contentArea.scrollWidth + columnGapPx) / columnUnitWidth));
  // pageCount === 1(표지처럼 챕터 전체가 컬럼 1개 분량뿐인 경우)은 예외다.
  // 이 경우 이미지(1컬럼) + 빈 2번째 컬럼이 처음부터 한 스프레드로 같이 보이므로
  // 별도의 스냅 지점(여백)이 필요 없다. 그런데도 여백을 붙이면, 이미 다 본 콘텐츠인데
  // maxScrollLeft가 그만큼 늘어나 "아직 안 끝났다"고 오판해 다음 챕터로 가기 전에
  // 빈 여백으로 한 번 더 넘겨야 하는(=빈 페이지가 낀 것처럼 보이는) 버그가 생긴다.
  const hasOddTailPage = pageCount > 1 && pageCount % 2 === 1;

  if (hasOddTailPage) {
    // 시도했던 방식과 실패 원인(둘 다 실기기 로그로 확인):
    // 1) margin-right → 스크롤 컨테이너가 자식의 trailing margin을 scrollWidth
    //    계산에 넣지 않는 브라우저 동작 때문에 무효.
    // 2) 빈 <div> 스페이서(강제 컬럼 나눔/높이 오버플로우) → .txt-content가
    //    CSS에서 width:100%로 고정돼 있어, "실제 필요한 컬럼 수"를 넘는 여분
    //    컬럼은 콘텐츠가 흘러넘칠 때만 브라우저가 예외적으로 추가해주는 오버플로우
    //    컬럼이라 빈 스페이서만으로는 새 컬럼이 보장되지 않았다.
    // 최종: width를 아예 "짝수 컬럼 개수 분량"으로 명시적으로 늘려 버린다.
    // column-count:auto는 이 명시된 width를 기준으로 정확히 그만큼의 컬럼을
    // 배정하므로(콘텐츠 양과 무관한 순수 기하 계산), 남는 마지막 컬럼은 항상
    // 확실히 비워진 채로 존재한다.
    const evenColumnCount = pageCount + 1;
    const targetWidth = Math.round(evenColumnCount * columnWidthPx + (evenColumnCount - 1) * columnGapPx);
    contentArea.style.width = `${targetWidth}px`;
  }
}
