// table_view/mode.js – 테이블 뷰(관리자 전용 표 보기)를 지금 쓸 수 있는지, 켜져 있는지 판단하고 화면 틀에 반영한다.
// 부팅 때부터 필요한 가벼운 부분만 여기 두고, 표 자체(table_view/index.js)는 처음 켤 때 불러온다.
import { state } from '../state.js';
import { canUseTableView } from './columns.js';

const WIDE_SCREEN_QUERY = '(min-width: 901px)';
export const LIST_VIEW_MODE_STORAGE_KEY = 'library_list_view_mode';

export function isTableViewAvailable() {
  return canUseTableView({
    role: state.currentUser?.role,
    type: state.currentLibraryType,
    libraryId: state.currentLibraryId,
    wide: typeof window.matchMedia === 'function' ? window.matchMedia(WIDE_SCREEN_QUERY).matches : true,
  });
}

// 표 모드는 "선호"로만 기억하고(다른 카테고리·세션에 가도 유지), 쓸 수 없는 곳에선 그리드로 보인다.
export function isTableModeActive() {
  return state.listViewMode === 'table' && isTableViewAvailable();
}

export function setListViewMode(mode) {
  state.listViewMode = mode === 'table' ? 'table' : 'grid';
  try {
    localStorage.setItem(LIST_VIEW_MODE_STORAGE_KEY, state.listViewMode);
  } catch (e) {}
}

// 표 버튼 표시 여부, 선택 표시, 그리드/표 영역 전환(CSS는 #books-grid-view.table-mode 기준)
export function syncTableModeUi() {
  const available = isTableViewAvailable();
  const active = available && state.listViewMode === 'table';
  const tableBtn = document.getElementById('btn-view-table');
  if (tableBtn) {
    tableBtn.hidden = !available;
    tableBtn.classList.toggle('active', active);
  }
  if (active) {
    document.getElementById('btn-group-default')?.classList.remove('active');
    document.getElementById('btn-group-author')?.classList.remove('active');
  }
  document.getElementById('books-grid-view')?.classList.toggle('table-mode', active);
  return active;
}
