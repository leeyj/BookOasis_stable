// author_group_context_menu.js – 작가별 모음 카드 전용 축소 컨텍스트 메뉴
// 일반 도서용 book-context-menu는 단일 책/시리즈 전제 액션(즉시 스캔/읽지 않음 처리 등)이라
// 여러 시리즈의 집계인 작가별 카드에는 성립하지 않으므로, 실제로 동작하는 항목
// (이 작가의 모든 작품을 컬렉션에 추가)만 담은 전용 메뉴를 별도로 둔다.
import { positionMenuAtPoint, hideFloatingMenu, bindFloatingMenuOutsideClose } from './context_menu_manager.js';

let authorGroupContextMenuBound = false;
let currentContextItem = null;

function bindAuthorGroupContextMenuOnce() {
  if (authorGroupContextMenuBound) return;
  authorGroupContextMenuBound = true;
  const menu = document.getElementById('author-group-context-menu');
  if (!menu) return;

  menu.addEventListener('click', (event) => {
    if (event.target.closest('[data-role="author-group-context-close"]')) {
      hideFloatingMenu(menu);
      return;
    }
    const actionEl = event.target.closest('[data-role="author-group-context-action"]');
    if (!actionEl || !currentContextItem) return;
    const action = actionEl.getAttribute('data-action');
    const item = currentContextItem;
    hideFloatingMenu(menu);

    if (action === 'add-to-collection') {
      import('./tab_collections.js').then((colls) => {
        colls.openAddToCollectionModal({
          author_key: item.author_key || '',
          title: item.series_name || item.display_name || '',
        });
      });
    }
  });

  bindFloatingMenuOutsideClose(menu);
}

export function showAuthorGroupContextMenu(x, y, item) {
  bindAuthorGroupContextMenuOnce();
  currentContextItem = item;

  const titleEl = document.getElementById('author-group-ctx-title');
  if (titleEl) titleEl.textContent = item.series_name || item.display_name || '작가 메뉴';

  positionMenuAtPoint('author-group-context-menu', x, y, { zIndex: 20060 });
}

window.showAuthorGroupContextMenu = showAuthorGroupContextMenu;
