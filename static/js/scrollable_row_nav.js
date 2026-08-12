/* scrollable_row_nav.js - 가로 스크롤 행 섹션의 좌/우 네비게이션 공용 헬퍼
   (대시보드 최근/신규 읽은 도서 행, 스마트 추천 장르/태그 행 등에서 공유) */

export function scrollRow(rowId, dir) {
  const rowEl = document.getElementById(rowId);
  if (!rowEl) return;
  const scrollAmount = rowEl.clientWidth * 0.7;
  rowEl.scrollBy({ left: dir === 'left' ? -scrollAmount : scrollAmount, behavior: 'smooth' });
}

export function buildRowNavButtonsHtml(rowId, prevTitle, nextTitle) {
  return `
    <div class="section-nav-btns">
      <button data-scroll-row-nav="${rowId}" data-dir="left" class="btn-nav-arrow" title="${prevTitle}"><i class="fa-solid fa-chevron-left"></i></button>
      <button data-scroll-row-nav="${rowId}" data-dir="right" class="btn-nav-arrow" title="${nextTitle}"><i class="fa-solid fa-chevron-right"></i></button>
    </div>
  `;
}

export function initScrollableRowNavDelegation() {
  if (window.__scrollableRowNavDelegationBound) return;

  document.addEventListener('click', (event) => {
    const btn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-scroll-row-nav]')
      : null;
    if (!btn) return;

    event.preventDefault();
    const rowId = btn.getAttribute('data-scroll-row-nav');
    const dir = btn.getAttribute('data-dir') || 'left';
    scrollRow(rowId, dir);
  }, true);

  window.__scrollableRowNavDelegationBound = true;
}

initScrollableRowNavDelegation();
