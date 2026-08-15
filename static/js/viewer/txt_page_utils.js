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
  contentArea.style.marginRight = '0px';

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

  // Math.ceil은 오차 허용이 없어, 정수 배수에 근접한 값이 서브픽셀 반올림으로
  // 살짝 넘치기만 해도(안드로이드 태블릿처럼 devicePixelRatio가 정수가 아닌
  // 기기에서 흔함) 페이지 수를 한 장 더 있는 것으로 오판한다. ceil 전에
  // 작은 epsilon을 빼서 그 오버슈트를 흡수한다.
  const rawPageCount = naturalHeight / columnHeight;
  const pageCount = Math.max(1, Math.ceil(rawPageCount - 0.02));
  // pageCount === 1(표지처럼 챕터 전체가 컬럼 1개 분량뿐인 경우)은 예외다.
  // 이 경우 이미지(1컬럼) + 빈 2번째 컬럼이 처음부터 한 스프레드로 같이 보이므로
  // 별도의 스냅 지점(여백)이 필요 없다. 그런데도 여백을 붙이면, 이미 다 본 콘텐츠인데
  // maxScrollLeft가 그만큼 늘어나 "아직 안 끝났다"고 오판해 다음 챕터로 가기 전에
  // 빈 여백으로 한 번 더 넘겨야 하는(=빈 페이지가 낀 것처럼 보이는) 버그가 생긴다.
  const hasOddTailPage = pageCount > 1 && pageCount % 2 === 1;

  if (hasOddTailPage) {
    // padding-right는 (box-sizing: border-box인 이 요소의) 컬럼이 쓸 수 있는
    // 폭 자체를 줄여 멀티컬럼 레이아웃을 다시 틀어지게 만든다(컬럼 폭/개수가
    // 재계산되며 스텝 폭 계산과 어긋나 페이지 넘길 때마다 화면이 밀림).
    // margin-right는 자신의 콘텐츠 박스(컬럼 폭)에는 영향 없이 스크롤 컨테이너의
    // scrollWidth만 늘려주므로 안전하다.
    contentArea.style.marginRight = `${Math.round(stepWidth / 2)}px`;
  }
}
