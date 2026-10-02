// book_menu/actions.js – 도서 컨텍스트 메뉴 항목의 실행 동작.
// 각 액션은 (target, ui)를 받는다. target: 메뉴를 연 도서(book_context_menu.js의 현재 대상),
// ui: { close(): 메뉴 닫기, point: 메뉴를 연 좌표 {x, y} }.
// 새 항목은 여기 함수 하나 + BOOK_MENU_ACTIONS 등록 + menu_rules.js 규칙 + context_menus.html <li>.
import { state } from '../state.js';
import { openListen } from '../tts_launcher.js';
import * as api from '../api.js';
import { openBookDetail } from '../modal.js';
import { loadBooksList, loadReadingHistory } from '../book_list.js';
import { loadDashboardData } from '../dashboard.js?v=20260917-home-widget-plugin-ui-v1';
import { clearBookSelection } from '../book_selection.js';
import { refreshSystemStatus } from '../scan_activity_status.js';
import { getBookScanScope, getLazyScanSeriesTarget, isDiagnoseAllowed, isLazyScanAllowed } from './menu_rules.js';
import { openBookDiagnosis } from '../book_diagnosis.js';

function selectedOf(target) {
  return Array.isArray(target?.selectedBooks) ? target.selectedBooks : [];
}

export function canDiagnoseFromCurrentBookMenu() {
  return isDiagnoseAllowed(state.currentUser || window.currentUser || {}, state.currentLibraryType);
}

function diagnose(target, ui) {
  if (!target || !target.id) return;
  ui.close();
  openBookDiagnosis(state.currentLibraryType || 'general', target.id, target.title || '');
}

export function canRunLazyScanFromCurrentBookMenu() {
  return isLazyScanAllowed(state.currentUser || window.currentUser || {}, state.currentLibraryType);
}

async function scan(target, ui) {
  if (!target || !target.id) return;
  const { id, title } = target;

  const selectedBooks = selectedOf(target);
  const scanScope = getBookScanScope(target);
  if (selectedBooks.length > 1) {
    const vm = await import('../view_manager.js');
    try {
      const result = await api.enqueueBatchBookScan(
        state.currentLibraryType,
        selectedBooks.map(book => book.id),
        { scope: scanScope }
      );
      if (!result?.success) {
        vm.showToast(result?.error || '다중 도서 스캔 요청에 실패했습니다.', 'error');
        return;
      }
      ui.close();
      clearBookSelection();
      refreshSystemStatus();
      vm.showToast(result.message || `선택한 ${selectedBooks.length}개 작품의 스캔을 대기열에 추가했습니다.`, 'success');
    } catch (error) {
      console.error('[BookContextMenu] 다중 스캔 요청 실패:', error);
      vm.showToast('다중 도서 스캔 요청 중 서버 통신 오류가 발생했습니다.', 'error');
    }
    return;
  }

  import('../view_manager.js').then(async (vm) => {
    try {
      const result = await api.enqueueBatchBookScan(state.currentLibraryType, [id], { scope: scanScope });
      if (!result?.success) {
        vm.showToast(result?.error || `"${title}" 스캔 요청에 실패했습니다.`, 'error');
        return;
      }

      ui.close();
      clearBookSelection();
      refreshSystemStatus();
      vm.showToast(result.message || `"${title}" 스캔이 대기열에 추가되었습니다.`, 'success');
    } catch (err) {
      console.error('단일 도서 스캔 대기열 등록 오류:', err);
      vm.showToast('도서 스캔 요청 중 서버 통신 오류가 발생했습니다.', 'error');
    }
  });
}

async function lazyScan(target, ui) {
  if (!target || !canRunLazyScanFromCurrentBookMenu()) return;

  const selectedBooks = selectedOf(target);
  const seriesTarget = selectedBooks.length > 1 ? null : getLazyScanSeriesTarget(target);
  const bookIds = selectedBooks.length > 1
    ? selectedBooks.map(book => Number(book.id)).filter(id => Number.isInteger(id) && id > 0)
    : [Number(target.id)];
  if (!seriesTarget && (!target.id || !bookIds.length)) return;

  ui.close();
  const vm = await import('../view_manager.js');
  try {
    const result = seriesTarget
      ? await api.triggerSeriesLazyScan(state.currentLibraryType, seriesTarget.libraryId, seriesTarget.seriesName)
      : await api.triggerBooksLazyScan(state.currentLibraryType, bookIds);
    vm.showToast(result?.success ? result.message : (result?.error || 'Lazy-Scanner 요청에 실패했습니다.'), result?.success ? 'success' : 'error');
    if (result?.success) clearBookSelection();
  } catch (error) {
    console.error('[BookContextMenu] Lazy-Scanner 요청 실패:', error);
    vm.showToast('Lazy-Scanner 요청 중 서버 통신 오류가 발생했습니다.', 'error');
  }
}

function searchMeta(target) {
  if (!target || !target.id) return;
  const { id, title } = target;

  const selectedBooks = selectedOf(target);
  if (selectedBooks.length > 1) {
    if (typeof window.openMetadataSearchQueue === 'function') {
      window.openMetadataSearchQueue(selectedBooks.map(book => ({ id: book.id, title: book.title })));
    } else {
      import('../view_manager.js').then(vm => vm.showToast('다중 메타정보 검색 기능을 불러오지 못했습니다.', 'error'));
    }
    return;
  }

  if (typeof window.openMetadataSearchModal === 'function') {
    window.openMetadataSearchModal(id, title);
  } else if (typeof window.openAladinSearchModal === 'function') {
    window.openAladinSearchModal(id, title);
  } else {
    console.error('[Global Trigger ERROR] window.openMetadataSearchModal 함수가 바인딩되지 않았습니다.');
  }
}

function addToCollection(target) {
  if (!target || !target.id) return;
  const { id, title } = target;
  const selectedBooks = selectedOf(target);
  import('../tab_collections.js').then((colls) => {
    if (selectedBooks.length > 1) {
      colls.openAddToCollectionModal({
        title: `선택한 ${selectedBooks.length}개 작품`,
        items: selectedBooks.map(book => ({ book_id: book.id, title: book.title })),
      });
    } else {
      colls.openAddToCollectionModal({ book_id: id, title: title });
    }
  });
}

function addSeriesToCollection(target) {
  if (!target) return;
  const selectedBooks = selectedOf(target);
  if (selectedBooks.length > 1) {
    const seriesItems = Array.from(new Map(
      selectedBooks
        .map(book => String(book.seriesName || '').trim())
        .filter(Boolean)
        .map(name => [name, { series_name: name, title: name }])
    ).values());
    if (!seriesItems.length) return;
    import('../tab_collections.js').then((colls) => {
      colls.openAddToCollectionModal({
        title: `선택한 ${seriesItems.length}개 시리즈`,
        items: seriesItems,
      });
    });
    return;
  }

  const seriesName = String(target.seriesName || '').trim();
  if (!seriesName) return;
  import('../tab_collections.js').then((colls) => {
    colls.openAddToCollectionModal({ series_name: seriesName, title: seriesName });
  });
}

function pageTurn(target, ui) {
  if (!target || !target.id) return;
  const url = '/experimental/page-turn?book_id=' + encodeURIComponent(target.id) +
    '&db_type=' + encodeURIComponent(state.currentLibraryType || 'general') + '&format=comic';
  window.open(url, '_blank');
  ui.close();
}

function tts(target, ui) {
  if (!target || !target.id) return;
  openListen(target.id, state.currentLibraryType || 'general');
  ui.close();
}

// 듣기 화면을 열지 않고 여기서 바로 요청한다 (본문을 받아 조각내는 데 몇 초 걸릴 수 있다).
// 설정은 이 책을 마지막으로 들은 설정, 없으면 듣기 기본값. 진행 상황은 스캔 활동(알림 영역)에 보인다.
async function ttsPregen(target, ui) {
  if (!target || !target.id) return;
  const bookId = target.id;
  const dbType = state.currentLibraryType || 'general';
  const title = target.title || '';
  ui.close();
  const tr = (key, vars) => window.i18n?.t?.(`tts.${key}`, vars) || key;
  const notify = (msg, type) => (typeof window.showToast === 'function' ? window.showToast(msg, type) : alert(msg));
  try {
    const { savedListenState, submitPregen } = await import('../tts/tts_pregen_client.js');
    const { settings, position } = await savedListenState(dbType, bookId);
    const quality = tr(Number(settings.steps) === 4 ? 'quality_normal' : 'quality_best');
    if (!window.confirm(tr('pregen_confirm_menu', { title, conf: `${settings.voice} · ${quality} · ${settings.speed}×` }))) return;
    notify(tr('pregen_preparing'), 'info');
    // 마지막으로 읽거나 들은 곳부터 먼저 만든다
    const data = await submitPregen({ dbType, bookId, settings, startAt: position });
    notify(tr(data.created ? 'pregen_requested' : 'pregen_already'), 'success');
    refreshSystemStatus();
  } catch (e) {
    notify(tr('pregen_request_failed', { error: e.message === 'https required' ? tr('pregen_https') : e.message }), 'error');
  }
}

function removeUnreadTargetCards({ id, isSeriesScope, seriesName, libraryId }) {
  if (state.currentLibraryId !== 'home' && state.currentLibraryId !== 'history') return;

  const historyContainer = state.currentLibraryId === 'home'
    ? document.getElementById('dashboard-history-row')
    : document.getElementById('books-list-container');
  if (!historyContainer) return;

  historyContainer.querySelectorAll('.book-card').forEach((card) => {
    const sameBook = String(card.dataset.bookId || '') === String(id);
    const sameSeries = isSeriesScope
      && String(card.dataset.seriesName || '') === String(seriesName || '')
      && String(card.dataset.libraryId || '') === String(libraryId ?? '');
    if (sameBook || sameSeries) card.remove();
  });
}

// 읽음/읽지 않음 변경 후 현재 위치한 탭/뷰에 맞추어 라이브 리로드
async function refreshAfterReadStateChange(libraryId) {
  if (state.currentLibraryId === 'home') {
    await loadDashboardData();
  } else if (state.currentLibraryId === 'history') {
    await loadReadingHistory();
  } else {
    // 상세 뷰 혹은 일반 도서 목록 새로고침
    // (구 모달 구조 시절의 #book-detail-modal / .detail-title-text 참조는 지금의
    // #book-detail-view / state.detailSeriesName 구조로 바뀐 뒤 갱신되지 않아 죽은
    // 참조로 남아있었음 — 상세 화면에서 읽지 않음 처리해도 진행률 표시가 새로고침
    // 안 되던 원인)
    const detailView = document.getElementById('book-detail-view');
    const isDetailViewOpen = !!detailView && detailView.style.display !== 'none';
    if (isDetailViewOpen) {
      const currentSeriesName = String(state.detailSeriesName || '').trim();
      if (currentSeriesName) {
        openBookDetail(null, currentSeriesName, libraryId || state.currentLibraryId);
      }
    } else {
      await loadBooksList();
    }
  }
}

async function markUnread(target, ui) {
  if (!target || !target.id) return;
  const { id, title, markUnreadScope, seriesName, libraryId } = target;
  const isSeriesScope = markUnreadScope === 'series';
  const selectedBooks = selectedOf(target);

  import('../view_manager.js').then(async (vm) => {
    try {
      if (selectedBooks.length > 1) {
        const uniqueTargets = new Map();
        selectedBooks.forEach((book) => {
          const scope = book.markUnreadScope === 'series'
            && String(book.seriesName || '').trim()
            && book.libraryId !== null
            ? 'series'
            : 'book';
          const key = scope === 'series'
            ? `${scope}:${book.libraryId ?? ''}:${String(book.seriesName || '').trim()}`
            : `${scope}:${book.libraryId ?? ''}:${book.id}`;
          if (!uniqueTargets.has(key)) uniqueTargets.set(key, { ...book, scope });
        });

        let succeeded = 0;
        const failures = [];
        for (const book of uniqueTargets.values()) {
          try {
            const result = await api.markBookAsUnread(state.currentLibraryType, book.id, {
              scope: book.scope,
              seriesName: book.seriesName,
              libraryId: book.libraryId,
            });
            if (result?.success) succeeded += 1;
            else failures.push({ title: book.title, error: result?.error || '변경 실패' });
          } catch (error) {
            failures.push({ title: book.title, error: error.message || '서버 통신 오류' });
          }
        }

        vm.showToast(
          `선택 항목 읽지 않음 처리: ${succeeded}/${uniqueTargets.size}개${failures.length ? ` (실패 ${failures.length}개)` : ''}`,
          failures.length ? 'warning' : 'success'
        );
        if (failures.length) console.warn('[BookContextMenu] 다중 읽지 않음 처리 실패:', failures);
        ui.close();
        clearBookSelection();
        if (state.currentLibraryId === 'home') await loadDashboardData();
        else if (state.currentLibraryId === 'history') await loadReadingHistory();
        else await loadBooksList();
        return;
      }

      const res = await api.markBookAsUnread(state.currentLibraryType, id, {
        scope: isSeriesScope ? 'series' : 'book',
        seriesName,
        libraryId,
      });
      if (res.success) {
        const targetLabel = isSeriesScope ? '시리즈 전체가' : '도서가';
        vm.showToast(`"${title}" ${targetLabel} 읽지 않은 상태(0%)로 변경되었습니다.`, 'success');
        removeUnreadTargetCards({ id, isSeriesScope, seriesName, libraryId });
        ui.close();
        await refreshAfterReadStateChange(libraryId);
      } else {
        vm.showToast(`변경 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('도서 읽지않음 처리 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

// "읽지 않은 상태로 변경"의 대칭 액션. 다중 선택 시에는 상태가 혼재될 수 있어(일부만 완독 등)
// 토글 자체를 노출하지 않으므로(menu_rules.js 참고) 단일 대상만 처리한다.
async function markRead(target, ui) {
  if (!target || !target.id) return;
  const { id, title, markUnreadScope, seriesName, libraryId } = target;
  const isSeriesScope = markUnreadScope === 'series';

  import('../view_manager.js').then(async (vm) => {
    try {
      const res = await api.markBookAsRead(state.currentLibraryType, id, {
        scope: isSeriesScope ? 'series' : 'book',
        seriesName,
        libraryId,
      });
      if (res.success) {
        const targetLabel = isSeriesScope ? '시리즈 전체가' : '도서가';
        vm.showToast(`"${title}" ${targetLabel} 읽은 상태(완독)로 변경되었습니다.`, 'success');
        ui.close();
        await refreshAfterReadStateChange(libraryId);
      } else {
        vm.showToast(`변경 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('도서 읽음 처리 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

// 다른 서브메뉴(volume-cover-align-context-menu)를 메뉴를 연 좌표에 새로 연다.
function coverAlign(target, ui) {
  const bookId = target?.id;
  const align = target?.coverAlign;
  const selectedBooks = selectedOf(target);
  const bulkBookIds = selectedBooks.length > 1 ? selectedBooks.map(book => book.id) : null;
  const { x, y } = ui.point;
  ui.close();
  return window.showVolumeCoverAlignContextMenu?.(x, y, bookId, align, bulkBookIds);
}

// context_menus.html의 data-action 값 → 액션
export const BOOK_MENU_ACTIONS = {
  'scan': scan,
  'lazy-scan': lazyScan,
  'search-meta': searchMeta,
  'add-to-collection': addToCollection,
  'add-series-to-collection': addSeriesToCollection,
  'page-turn': pageTurn,
  'tts': tts,
  'tts-pregen': ttsPregen,
  'mark-unread': markUnread,
  'mark-read': markRead,
  'cover-align': coverAlign,
  'diagnose': diagnose,
};
