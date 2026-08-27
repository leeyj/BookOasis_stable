// volume_context_menu.js – 권(볼륨) 카드 전용 커버 정렬 컨텍스트 메뉴
// 이중 페이지 스캔본처럼 표지 이미지가 한쪽으로 치우친 개별 권을 위해,
// 기존 도서 컨텍스트 메뉴(book_context_menu.js)의 "커버 정렬" 항목에서 진입해
// 왼쪽/중앙/오른쪽 정렬을 book_id 단위로 저장한다.
import { positionMenuAtPoint, hideFloatingMenu, bindFloatingMenuOutsideClose } from '../context_menu_manager.js';
import { state } from '../state.js';
import { updateBookCoverAlign } from '../api.js';
import { coverAlignToObjectPosition } from '../cover_fallback.js';

let volumeCoverAlignMenuBound = false;
let currentBookId = null;

function markActiveAlignItem(menu, align) {
  menu.querySelectorAll('[data-role="volume-cover-align-context-action"]').forEach((el) => {
    el.classList.toggle('active', el.getAttribute('data-align') === align);
  });
}

function findVolumeCard(bookId) {
  return document.querySelector(`.vol-grid-card[data-book-id="${bookId}"], .volume-card[data-book-id="${bookId}"]`);
}

function bindVolumeCoverAlignMenuOnce() {
  if (volumeCoverAlignMenuBound) return;
  volumeCoverAlignMenuBound = true;
  const menu = document.getElementById('volume-cover-align-context-menu');
  if (!menu) return;

  menu.addEventListener('click', async (event) => {
    if (event.target.closest('[data-role="volume-cover-align-context-close"]')) {
      hideFloatingMenu(menu);
      return;
    }
    const actionEl = event.target.closest('[data-role="volume-cover-align-context-action"]');
    if (!actionEl || !currentBookId) return;
    const align = actionEl.getAttribute('data-align') || 'center';
    const bookId = currentBookId;
    hideFloatingMenu(menu);

    const card = findVolumeCard(bookId);
    const img = card ? card.querySelector('.vol-grid-thumb, .volume-thumb') : null;
    const previousAlign = (card && card.getAttribute('data-cover-align')) || 'center';

    // 낙관적 업데이트 - 응답 기다리지 않고 즉시 반영, 실패 시에만 되돌림
    if (card) card.setAttribute('data-cover-align', align);
    if (img) img.style.objectPosition = `${coverAlignToObjectPosition(align)} center`;

    try {
      const res = await updateBookCoverAlign(bookId, state.currentLibraryType || 'general', align);
      console.log('[CoverAlign-API] 저장 응답:', res);
      if (!res || !res.success) throw new Error((res && res.error) || '저장 실패');
    } catch (e) {
      console.error('[CoverAlign-API] 저장 실패:', e);
      if (card) card.setAttribute('data-cover-align', previousAlign);
      if (img) img.style.objectPosition = `${coverAlignToObjectPosition(previousAlign)} center`;
      alert('커버 정렬 변경에 실패했습니다.');
    }
  });

  // "커버 정렬" 메뉴 항목(#ctx-cover-align-book) 클릭이 이 서브메뉴를 여는 트리거인데,
  // 두 번째 사용부터는 이 바깥클릭감지 리스너가 이미 등록돼 있어서 그 트리거 클릭 자체를
  // "바깥 클릭"으로 오인해 열리자마자 같은 이벤트 틱 안에서 바로 닫아버렸다 - 제외 처리.
  bindFloatingMenuOutsideClose(menu, {
    shouldIgnoreEvent: (event) => !!(event.target && event.target.closest && event.target.closest('#ctx-cover-align-book')),
  });
}

export function showVolumeCoverAlignContextMenu(x, y, bookId, currentAlign) {
  if (!bookId) return;
  bindVolumeCoverAlignMenuOnce();
  currentBookId = bookId;

  const resolvedAlign = currentAlign || (findVolumeCard(bookId)?.getAttribute('data-cover-align')) || 'center';
  const menu = document.getElementById('volume-cover-align-context-menu');
  if (menu) markActiveAlignItem(menu, resolvedAlign);

  positionMenuAtPoint('volume-cover-align-context-menu', x, y, { zIndex: 20061 });
}

window.showVolumeCoverAlignContextMenu = showVolumeCoverAlignContextMenu;
