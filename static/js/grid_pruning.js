// grid_pruning.js – 무한 스크롤로 계속 append되는 도서 카드 DOM이 무한정 쌓이는 것을 막는다.
// 서버 페이지네이션/초성 점프/이전 페이지 prepend 로직은 그대로 두고, 이미 뷰포트에서
// 충분히 멀어진(스크롤을 많이 내려서 다시 볼 일이 적은) 상단 카드들만 주기적으로 DOM에서
// 떼어내고, 그 자리를 실제 콘텐츠와 동일한 높이의 spacer로 대체한다. 뗀 카드 엘리먼트는
// 파괴하지 않고 그대로 메모리에 들고 있다가, 사용자가 다시 위로 스크롤하면 같은 엘리먼트를
// 그대로 재삽입한다(=재사용, 새로 만들지 않음) — 처음엔 데이터만 들고 있다가 매번
// createBookCard()로 새로 만들었는데, content-visibility:auto + contain-intrinsic-size의
// "auto" 크기 기억 기능이 엘리먼트 단위로만 적용돼서, 매번 새 엘리먼트를 만들면 그 카드는
// 항상 "한 번도 렌더링된 적 없는" 상태로 취급되어 고정 추정치와 실제 크기 사이 리플로우가
// 계속 반복됐다(위로 스크롤해서 복원이 처음 시작된 지점부터 계속 튀던 현상의 원인). 같은
// 엘리먼트를 재사용하면 이 문제가 원천적으로 없어진다.
//
// 의도적으로 하단(prepend) 방향은 정리하지 않는다: loadPreviousBooksPage()가
// container.scrollHeight 변화량만으로 scrollTop을 보정하는데, 같은 호출 안에서 하단도
// 같이 잘라내면 그 보정 계산이 어긋나 화면이 튀는 부작용이 생길 수 있기 때문이다.
// (하단 누적은 "초성 점프로 위로 점프 후 다시 위로 스크롤"하는 드문 경로에서만 발생하고,
// 원 문제였던 "아래로 계속 스크롤"에는 영향 없다.)

import { createLogger } from './utils/logger.js';

const log = createLogger('grid_pruning');

const MAX_RENDERED_CARDS = 240; // 이 개수를 넘어야 정리를 시도해본다 (그 이하면 비용 대비 효과 없음)
// 현재 스크롤 위치에서 이만큼(화면 높이 배수) 이상 떨어진 행만 정리 대상으로 삼는다.
// RESTORE_VIEWPORT_MARGIN보다 반드시 커야 한다 - prune 직후 spacer 높이는 대략
// (scrollTop - PRUNE_SAFETY_VIEWPORTS*viewport)이므로, 만약 이 값이 RESTORE_VIEWPORT_MARGIN
// 이하면 "scrollTop <= spacerHeight + RESTORE_VIEWPORT_MARGIN*viewport" 복원 조건이 prune
// 직후 곧바로 참이 되어 버려(정리했다가 바로 복원 - flapping) 튀는 원인이 된다.
const PRUNE_SAFETY_VIEWPORTS = 10;
// 스페이서가 이만큼의 화면 높이 안으로 들어오면 복원을 시작한다. scroll 이벤트가 있어야만
// 평가되는 구조라, 트랙패드 fling처럼 한 번의 네이티브 스크롤 모션으로 scrollTop이 수천 px
// 건너뛰면 이 여유 구간 자체를 통째로 건너뛸 수 있다. 복원 자체는 가볍기 때문에 여유를
// 크게 잡아도 비용 부담이 없어 넉넉하게 잡는다.
const RESTORE_VIEWPORT_MARGIN = 8;

let prunedElements = []; // 정리(prune)로 DOM에서 뗀 실제 카드 엘리먼트들 - 파괴하지 않고 화면 순서 그대로 보관
let prunedHeight = 0; // spacer에 반영된, 실측으로 누적된 정리분 총 높이(px)
let topSpacer = null;
let cachedColumns = 0;
let scrollListenerBound = false;
let restoreTicking = false;

function getContainer() {
  return document.getElementById('books-list-container');
}

function getMainContent() {
  return document.querySelector('.library-main-content');
}

export function initGridPruning() {
  bindScrollListener();
}

// 목록 전체 재렌더링(신규 검색/정렬/초성 점프/탭 전환) 시 호출 - pruning 상태를 비운다.
// 컨테이너가 통째로 비워지므로(innerHTML='') 여기 보관 중이던 뗀 엘리먼트도 재사용할 대상이
// 아니게 된다 - 그냥 버린다(GC 대상).
export function resetGridPruning() {
  prunedElements = [];
  prunedHeight = 0;
  topSpacer = null;
  cachedColumns = 0;
}

export function notifyCardsAppended() {
  pruneIfNeeded();
}

export function notifyCardsPrepended() {
  // 뗀 카드 재사용 방식으로 바뀌면서 순서 추적용 데이터 구조가 필요 없어져 할 일이 없다.
  // (기존 ui.js 호출부와의 인터페이스만 유지)
}

// 열(column) 수만 계산한다 - 행 높이는 추정치를 쓰지 않고, 정리 시점에
// 실제 DOM(offsetTop)에서 직접 측정한다(아래 pruneIfNeeded 참고).
function measureGrid(realCards) {
  if (realCards.length < 2) return false;
  const firstTop = realCards[0].offsetTop;
  let columns = 0;
  for (const el of realCards) {
    if (el.offsetTop === firstTop) columns++;
    else break;
  }
  if (columns <= 0 || columns >= realCards.length) return false;
  const rowHeight = realCards[columns].offsetTop - firstTop;
  if (!(rowHeight > 0)) return false; // 열 계산 자체가 잘못됐을 가능성 - 유효성 검사 용도
  cachedColumns = columns;
  return true;
}

function ensureTopSpacer(container) {
  if (topSpacer && topSpacer.isConnected) return topSpacer;
  topSpacer = container.querySelector(':scope > .grid-prune-spacer-top');
  if (!topSpacer) {
    topSpacer = document.createElement('div');
    topSpacer.className = 'grid-prune-spacer-top';
    container.insertBefore(topSpacer, container.firstChild);
  }
  return topSpacer;
}

function pruneIfNeeded() {
  bindScrollListener(); // 모듈 로드 시점에 .library-main-content가 아직 없었을 경우를 대비한 재시도
  const container = getContainer();
  const mainContent = getMainContent();
  if (!container || !mainContent) return;
  const realCards = container.querySelectorAll('.book-card');
  if (realCards.length <= MAX_RENDERED_CARDS) return;
  if (!measureGrid(realCards)) return; // 열 수를 계산할 수 없으면 정리 보류

  const scrollTopBefore = mainContent.scrollTop;
  // 카드 "개수"가 아니라 사용자가 실제로 보고 있는 위치에서의 "거리"를 기준으로 정리 대상을
  // 정한다. 고정 개수만 남기면, 사용자가 아직 뷰포트 근처를 보고 있는 상황에서 코앞의
  // 카드까지 정리해버려 곧바로 restore가 재발화될 수 있다.
  const safeCutoff = scrollTopBefore - mainContent.clientHeight * PRUNE_SAFETY_VIEWPORTS;
  if (safeCutoff <= 0) return; // 아직 그만큼 스크롤하지 않음 - 정리 보류

  // safeCutoff보다 완전히 위(=행의 시작 지점 offsetTop이 safeCutoff 미만)에 있는 행만 정리한다.
  // 마지막 행(realCards.length-cachedColumns 이후)은 항상 남겨서 "남는 첫 카드" 기준점을 확보한다.
  let removeCount = 0;
  for (let i = 0; i + cachedColumns < realCards.length; i += cachedColumns) {
    if (realCards[i].offsetTop >= safeCutoff) break;
    removeCount = i + cachedColumns;
  }
  if (removeCount <= 0) return;

  // spacer 높이는 "행 높이 추정값 × 행 수"가 아니라, 제거 직전 실제 DOM에서 직접 측정한다:
  // 남게 될 첫 카드의 offsetTop − 지워질 첫 카드의 offsetTop = 지워지는 행들이 실제로
  // 차지하던 정확한 픽셀 높이(행마다 제목 줄바꿈 등으로 높이가 달라도 오차가 없다).
  const removedSpan = realCards[removeCount].offsetTop - realCards[0].offsetTop;
  const heightBefore = container.scrollHeight;

  const spacer = ensureTopSpacer(container);
  const removed = [];
  for (let i = 0; i < removeCount; i++) {
    removed.push(realCards[i]);
    realCards[i].remove(); // DOM에서만 제거 - 엘리먼트 자체는 파괴하지 않고 removed에 보관
  }
  prunedElements = prunedElements.concat(removed);
  prunedHeight += removedSpan;
  spacer.style.height = `${prunedHeight}px`;

  const heightAfter = container.scrollHeight;
  const heightDelta = heightAfter - heightBefore;
  mainContent.scrollTop = scrollTopBefore + heightDelta;

  log.debug('prune', {
    removeCount,
    columns: cachedColumns,
    removedSpan,
    prunedElementsTotal: prunedElements.length,
    prunedHeight,
    heightDelta, // 0에 가까워야 정상 - removedSpan 실측이 정확했다는 뜻
    scrollTopBefore,
    scrollTopAfter: mainContent.scrollTop,
  });
}

// 한 번에 복원할 카드 수. prunedElements는 오래 스크롤할수록(여러 번의 prune이 누적되어)
// 수백 개까지 쌓일 수 있는데, 복원 트리거 시점에 전부 한 번에 DOM 삽입하면 그 프레임 하나가
// 무거워져서 위치 보정과 별개로 버벅이며 "순간 이동"처럼 보인다. prune처럼 청크로 나눠
// 여러 프레임에 걸쳐 복원한다.
const RESTORE_CHUNK_SIZE = 120;

function restoreIfNeeded() {
  if (prunedElements.length === 0) return;
  const mainContent = getMainContent();
  if (!mainContent || !topSpacer || !topSpacer.isConnected) return;

  const spacerHeight = topSpacer.offsetHeight;
  if (spacerHeight <= 0) return;
  const restoreThreshold = spacerHeight + mainContent.clientHeight * RESTORE_VIEWPORT_MARGIN;
  if (mainContent.scrollTop > restoreThreshold) return;

  restoreChunk();
}

// prunedElements 중 실제 콘텐츠(남은 카드)에 가장 가까운(=배열 뒤쪽) 청크부터 복원하고,
// 아직 남았으면 다음 애니메이션 프레임에 이어서 계속한다. 정리 시 떼어뒀던 엘리먼트를
// 그대로 재삽입할 뿐 새로 만들지 않는다. 각 청크마다 prune과 동일하게 scrollHeight
// 변화량을 직접 재서 scrollTop을 보정하므로, 청크 하나하나는 시각적으로 안 튄다 - 다만
// 그걸 여러 프레임에 걸쳐 나눠서 하기 때문에 한 프레임의 부담이 줄어든다.
function restoreChunk() {
  const container = getContainer();
  const mainContent = getMainContent();
  if (!container || !mainContent || !topSpacer || prunedElements.length === 0) return;

  const totalBeforeChunk = prunedElements.length;
  const chunkCount = Math.min(RESTORE_CHUNK_SIZE, totalBeforeChunk);
  const chunkStart = totalBeforeChunk - chunkCount;
  const chunkElements = prunedElements.slice(chunkStart);

  const scrollTopBefore = mainContent.scrollTop;
  const heightBefore = container.scrollHeight;

  const fragment = document.createDocumentFragment();
  chunkElements.forEach((el) => fragment.appendChild(el));
  container.insertBefore(fragment, topSpacer.nextSibling);

  prunedElements = prunedElements.slice(0, chunkStart);
  // 이번에 복원한 청크만큼 spacer가 대변하던 높이도 같이 줄여야 하는데, 항목별 실제 높이를
  // 개별로 알 수는 없으니 평균으로 근사한다. 이 근사 오차는 아래 heightBefore/After 실측
  // 보정과는 무관(그건 이번 삽입으로 실제 변한 높이를 그대로 재는 것) - spacer 근사치는
  // 다음 restore/prune 때 다시 실측되며 자연히 정리된다.
  const avgItemHeight = prunedHeight / totalBeforeChunk;
  prunedHeight = Math.max(0, prunedHeight - avgItemHeight * chunkCount);

  if (prunedElements.length === 0) {
    topSpacer.remove();
    topSpacer = null;
    prunedHeight = 0;
  } else {
    topSpacer.style.height = `${Math.round(prunedHeight)}px`;
  }

  const heightAfter = container.scrollHeight;
  const heightDelta = heightAfter - heightBefore;
  mainContent.scrollTop = scrollTopBefore + heightDelta;

  log.debug('restore-chunk', {
    chunkCount,
    remainingPrunedElements: prunedElements.length,
    avgItemHeight,
    prunedHeightAfter: prunedHeight,
    heightDelta, // 0에 가까워야 정상
    scrollTopBefore,
    scrollTopAfter: mainContent.scrollTop,
  });

  if (prunedElements.length > 0) {
    requestAnimationFrame(restoreChunk);
  }
}

function onScroll() {
  if (restoreTicking) return;
  restoreTicking = true;
  requestAnimationFrame(() => {
    restoreTicking = false;
    restoreIfNeeded();
  });
}

function bindScrollListener() {
  if (scrollListenerBound) return;
  const mainContent = getMainContent();
  if (!mainContent) return;
  mainContent.addEventListener('scroll', onScroll, { passive: true });
  scrollListenerBound = true;
}
