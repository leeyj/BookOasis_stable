// library_sort_menu.js – 도서 목록 정렬 드롭다운 (헤더 정렬 버튼).
// 정렬 값은 서버(/api/media/list sort, repositories/series_list_options.py)와 같은 목록을 쓴다.
import { bindFloatingMenuOutsideClose, hideFloatingMenu, isFloatingMenuOpen, positionMenuAtElement } from './context_menu_manager.js';

export const SORT_OPTIONS = [
  { value: 'asc', labelKey: 'book_list.sort_asc', icon: 'fa-solid fa-arrow-down-a-z' },
  { value: 'desc', labelKey: 'book_list.sort_desc', icon: 'fa-solid fa-arrow-up-z-a' },
  { value: 'folder_asc', labelKey: 'book_list.sort_folder_asc', icon: 'fa-solid fa-folder' },
  { value: 'folder_desc', labelKey: 'book_list.sort_folder_desc', icon: 'fa-solid fa-folder-open' },
  { value: 'date_desc', labelKey: 'book_list.sort_date_desc', icon: 'fa-solid fa-sort-numeric-down-alt' },
  { value: 'date_asc', labelKey: 'book_list.sort_date_asc', icon: 'fa-solid fa-sort-numeric-up' },
  { value: 'count_desc', labelKey: 'book_list.sort_count_desc', icon: 'fa-solid fa-arrow-down-wide-short' },
  { value: 'count_asc', labelKey: 'book_list.sort_count_asc', icon: 'fa-solid fa-arrow-up-short-wide' },
  { value: 'score_desc', labelKey: 'book_list.sort_score_desc', icon: 'fa-solid fa-star' },
];

const MENU_ID = 'library-sort-menu';

export function getSortOption(value) {
  return SORT_OPTIONS.find((option) => option.value === value) || SORT_OPTIONS[0];
}

export function normalizeSortValue(value) {
  return getSortOption(value).value;
}

function ensureMenu() {
  let menu = document.getElementById(MENU_ID);
  if (menu) return menu;
  menu = document.createElement('div');
  menu.id = MENU_ID;
  menu.className = 'context-menu library-sort-menu';
  menu.style.display = 'none';
  menu.innerHTML = `
    <div class="context-menu-header"><span class="context-menu-title"></span></div>
    <ul class="context-menu-list"></ul>
  `;
  document.body.appendChild(menu);
  // 정렬 버튼 자체를 누른 클릭은 버튼 쪽 토글이 처리하도록 바깥 클릭으로 보지 않는다
  bindFloatingMenuOutsideClose(menu, {
    shouldIgnoreEvent: (event) => !!(event && event.target && event.target.closest && event.target.closest('[data-role="library-sort-toggle"]')),
  });
  return menu;
}

function renderMenu(menu, current, onSelect) {
  menu.querySelector('.context-menu-title').textContent = i18n.t('header.sort_title');
  const list = menu.querySelector('.context-menu-list');
  list.innerHTML = '';
  SORT_OPTIONS.forEach((option) => {
    const li = document.createElement('li');
    li.className = 'context-menu-item library-sort-item';
    li.classList.toggle('active', option.value === current);
    li.innerHTML = `<i class="${option.icon}"></i> <span></span><i class="fa-solid fa-check library-sort-check"></i>`;
    li.querySelector('span').textContent = i18n.t(option.labelKey);
    li.addEventListener('click', () => {
      hideFloatingMenu(menu);
      if (option.value !== current) onSelect(option.value);
    });
    list.appendChild(li);
  });
}

// 정렬 버튼을 누르면 열고, 열려 있으면 닫는다.
export function toggleLibrarySortMenu(anchorEl, { current, onSelect }) {
  const menu = ensureMenu();
  if (isFloatingMenuOpen(menu)) {
    hideFloatingMenu(menu);
    return;
  }
  renderMenu(menu, current, onSelect);
  positionMenuAtElement(menu, anchorEl, { zIndex: 20050 });
}
