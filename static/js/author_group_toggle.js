/* author_group_toggle.js – 목록 보기 전환: 기본(시리즈) 그리드 / 작가별 모음 / 표(관리자 전용 테이블 뷰) */
import { state } from './state.js';
import { loadBooksList } from './book_list.js';
import { isTableModeActive, setListViewMode, syncTableModeUi } from './table_view/mode.js';

export function applyGroupModeButtonState(mode) {
  const safeMode = mode === 'author' ? 'author' : 'default';
  state.groupMode = safeMode;

  document.querySelectorAll('#group-mode-toggle-group [data-role="grouping-mode-toggle"]').forEach(btn => btn.classList.remove('active'));
  if (safeMode === 'author') {
    document.getElementById('btn-group-author')?.classList.add('active');
  } else {
    document.getElementById('btn-group-default')?.classList.add('active');
  }
  // 표 모드면 선택 표시를 표 버튼으로 옮긴다 (표 버튼 자체의 표시 여부도 여기서 맞춘다)
  syncTableModeUi();
}

// 작가별 카드를 클릭해 특정 작가로 드릴다운한 상태에서도 "작가별" 토글을 계속 활성 표시한다.
// 드릴다운은 작가별 브라우징의 하위 상태일 뿐 "기본" 모드로의 전환이 아니기 때문 —
// 필터를 벗어나려면 "기본" 버튼을 명시적으로 눌러야 한다.
function applyGroupModeState(mode, authorKey) {
  applyGroupModeButtonState(mode);
  localStorage.setItem('library_group_mode', mode);
  state.authorKeyFilter = mode === 'author' ? (authorKey || '') : '';

  state.currentPage = 1;
  state.hasMore = true;

  loadBooksList(false);
}

// 카테고리 진입 자체는 히스토리에 기록되지 않는 기존 구조라, 그룹 모드 전환/드릴다운마다
// 매번 히스토리 엔트리를 남겨야 뒤로가기가 (홈으로 튀지 않고) 이전 그룹 상태로 복귀한다.
function pushGroupModeHistory(mode, authorKey) {
  history.pushState(
    { view: 'group_mode', mode, authorKey: authorKey || '', type: state.currentLibraryType, libraryId: state.currentLibraryId },
    '',
    window.location.href
  );
}

// 표(테이블 뷰)로 전환. 기본/작가별 선택(state.groupMode)은 그대로 두어 그리드로 돌아오면 이어진다.
function switchToTableView() {
  if (isTableModeActive()) return;
  setListViewMode('table');
  if (!syncTableModeUi()) {
    // 쓸 수 없는 곳(일반 사용자·오디오북·좁은 화면 등)에서 눌린 경우 - 그리드 그대로
    setListViewMode('grid');
    return;
  }
  state.authorKeyFilter = '';
  state.currentPage = 1;
  loadBooksList(false);
}

export function switchGroupMode(mode) {
  if (mode === 'table') return switchToTableView();

  const safeMode = mode === 'author' ? 'author' : 'default';
  const leavingTable = state.listViewMode === 'table';
  if (leavingTable) setListViewMode('grid');
  if (!leavingTable && state.groupMode === safeMode && !state.authorKeyFilter) return;

  pushGroupModeHistory(safeMode, '');
  applyGroupModeState(safeMode, '');
}

// 작가별 카드를 클릭했을 때 정규화 그룹 전체로 드릴다운한다 ("작가별" 토글은 유지).
export function openAuthorGroupDrilldown(item) {
  const authorKey = item.author_key || '';
  pushGroupModeHistory('author', authorKey);
  applyGroupModeState('author', authorKey);
}

// popstate로 'group_mode' 히스토리 엔트리에 복귀했을 때 해당 모드/필터를 다시 적용한다.
export function restoreGroupModeView(mode, authorKey) {
  applyGroupModeState(mode === 'author' ? 'author' : 'default', authorKey);
}

window.applyGroupModeButtonState = applyGroupModeButtonState;
window.switchGroupMode = switchGroupMode;
window.onAuthorGroupCardClick = openAuthorGroupDrilldown;
