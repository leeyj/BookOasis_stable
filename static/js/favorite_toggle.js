// favorite_toggle.js – 카드 즐겨찾기 별 버튼의 상태 계산/적용/복원 (DOM 요소 하나만 다루는 순수 헬퍼)
//
// 예전에는 버튼의 data-next-status를 그대로 읽어 요청했는데, 성공 후 그 속성을 갱신하지 않고 목록도
// 다시 그리지 않아서 같은 카드의 별을 두 번 누르면 같은 상태(예: 등록)를 또 보내 해제할 수 없었다.
// 다음 상태는 항상 "지금 화면의 별 상태"에서 계산하고, 적용할 때 data-next-status도 함께 맞춘다.

const ACTIVE_ICON_CLASS = 'fa-solid fa-star';
const INACTIVE_ICON_CLASS = 'fa-regular fa-star';

export function readNextFavoriteStatus(btn) {
  return btn && btn.classList.contains('active') ? 0 : 1;
}

export function applyFavoriteState(btn, active) {
  if (!btn) return;
  if (active) btn.classList.add('active');
  else btn.classList.remove('active');
  const icon = btn.querySelector('i');
  if (icon) icon.className = active ? ACTIVE_ICON_CLASS : INACTIVE_ICON_CLASS;
  btn.setAttribute('data-next-status', active ? '0' : '1');
  btn.setAttribute('aria-pressed', active ? 'true' : 'false');
}

export function snapshotFavoriteState(btn) {
  const icon = btn.querySelector('i');
  return {
    active: btn.classList.contains('active'),
    iconClass: icon ? icon.className : null,
    nextStatus: btn.getAttribute('data-next-status'),
    ariaPressed: btn.getAttribute('aria-pressed'),
  };
}

function restoreAttribute(btn, name, value) {
  if (value === null || value === undefined) btn.removeAttribute(name);
  else btn.setAttribute(name, value);
}

export function restoreFavoriteState(btn, snapshot) {
  if (!btn || !snapshot) return;
  if (snapshot.active) btn.classList.add('active');
  else btn.classList.remove('active');
  const icon = btn.querySelector('i');
  if (icon && snapshot.iconClass !== null) icon.className = snapshot.iconClass;
  restoreAttribute(btn, 'data-next-status', snapshot.nextStatus);
  restoreAttribute(btn, 'aria-pressed', snapshot.ariaPressed);
}

// 요청이 끝나기 전에 같은 별을 다시 눌러 서로 엇갈린 요청이 나가는 것을 막는다.
export function isFavoritePending(btn) {
  return !!btn && btn.dataset && btn.dataset.favoritePending === '1';
}

export function setFavoritePending(btn, pending) {
  if (btn && btn.dataset) btn.dataset.favoritePending = pending ? '1' : '0';
}
