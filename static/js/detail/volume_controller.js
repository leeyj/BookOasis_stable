// volume_controller.js – 권별(Volume) 목록 필터링, 정렬 및 뷰 상태 관리

export const detailVolumeViewState = {
  key: '',
  unreadOnly: false,
  sortOrder: 'oldest'
};

export function applyDetailVolumeView() {
  const section = document.querySelector('.volumes-section');
  if (!section) return;

  // 리스트 모드(.volumes-list + .volume-card) 또는 그리드 모드(.volumes-list-grid + .vol-grid-card) 모두 지원
  const list = section.querySelector('.volumes-list') || section.querySelector('.volumes-list-grid');
  const cards = Array.from(section.querySelectorAll('.volume-card, .vol-grid-card'));

  cards.sort((left, right) => {
    // data-title 기반 자연 정렬 (파일명 순서 기준)
    const titleA = left.dataset.title || '';
    const titleB = right.dataset.title || '';
    const cmp = titleA.localeCompare(titleB, 'ko', { numeric: true, sensitivity: 'base' });
    return detailVolumeViewState.sortOrder === 'newest' ? -cmp : cmp;
  });

  let visibleCount = 0;
  cards.forEach(card => {
    if (list) list.appendChild(card);
    const isNotCompleted = card.dataset.isCompleted !== '1';
    const visible = !detailVolumeViewState.unreadOnly || isNotCompleted;
    card.style.display = visible ? '' : 'none';
    if (visible) visibleCount += 1;
  });

  const unreadButton = section.querySelector('[data-detail-unread-filter]');
  if (unreadButton) {
    unreadButton.classList.toggle('active', detailVolumeViewState.unreadOnly);
    unreadButton.setAttribute('aria-pressed', String(detailVolumeViewState.unreadOnly));
  }
  section.querySelectorAll('[data-detail-sort]').forEach(button => {
    const active = button.dataset.detailSort === detailVolumeViewState.sortOrder;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });

  const empty = section.querySelector('.volumes-empty-filter');
  if (empty) empty.style.display = visibleCount === 0 ? 'block' : 'none';
}

export function toggleDetailUnreadFilter() {
  detailVolumeViewState.unreadOnly = !detailVolumeViewState.unreadOnly;
  applyDetailVolumeView();
}

export function setDetailVolumeSort(sortOrder) {
  detailVolumeViewState.sortOrder = sortOrder === 'newest' ? 'newest' : 'oldest';
  applyDetailVolumeView();
}
