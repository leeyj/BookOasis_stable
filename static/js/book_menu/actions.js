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
        vm.showToast(result?.error || i18n.t('context_menu.multi_scan_failed'), 'error');
        return;
      }
      ui.close();
      clearBookSelection();
      refreshSystemStatus();
      vm.showToast(result.message || i18n.t('context_menu.multi_scan_queued', { n: selectedBooks.length }), 'success');
    } catch (error) {
      console.error('[BookContextMenu] 다중 스캔 요청 실패:', error);
      vm.showToast(i18n.t('context_menu.multi_scan_error'), 'error');
    }
    return;
  }

  import('../view_manager.js').then(async (vm) => {
    try {
      const result = await api.enqueueBatchBookScan(state.currentLibraryType, [id], { scope: scanScope });
      if (!result?.success) {
        vm.showToast(result?.error || i18n.t('context_menu.scan_failed', { title }), 'error');
        return;
      }

      ui.close();
      clearBookSelection();
      refreshSystemStatus();
      vm.showToast(result.message || i18n.t('context_menu.scan_queued', { title }), 'success');
    } catch (err) {
      console.error('단일 도서 스캔 대기열 등록 오류:', err);
      vm.showToast(i18n.t('context_menu.scan_error'), 'error');
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
    vm.showToast(result?.success ? result.message : (result?.error || i18n.t('context_menu.lazy_failed')), result?.success ? 'success' : 'error');
    if (result?.success) clearBookSelection();
  } catch (error) {
    console.error('[BookContextMenu] Lazy-Scanner 요청 실패:', error);
    vm.showToast(i18n.t('context_menu.lazy_error'), 'error');
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
      import('../view_manager.js').then(vm => vm.showToast(i18n.t('context_menu.multi_meta_load_failed'), 'error'));
    }
    return;
  }

  if (typeof window.openMetadataSearchModal === 'function') {
    window.openMetadataSearchModal(id, title);
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
        title: i18n.t('context_menu.selected_works', { n: selectedBooks.length }),
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
        title: i18n.t('context_menu.selected_series', { n: seriesItems.length }),
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
            else failures.push({ title: book.title, error: result?.error || i18n.t('context_menu.change_failed_short') });
          } catch (error) {
            failures.push({ title: book.title, error: error.message || i18n.t('context_menu.server_error_short') });
          }
        }

        vm.showToast(
          i18n.t('context_menu.bulk_unread_result', { done: succeeded, total: uniqueTargets.size }) + (failures.length ? i18n.t('context_menu.bulk_failed_suffix', { n: failures.length }) : ''),
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
        vm.showToast(i18n.t(isSeriesScope ? 'context_menu.series_marked_unread' : 'context_menu.book_marked_unread', { title }), 'success');
        removeUnreadTargetCards({ id, isSeriesScope, seriesName, libraryId });
        ui.close();
        await refreshAfterReadStateChange(libraryId);
      } else {
        vm.showToast(i18n.t('context_menu.change_failed', { error: res.error }), 'error');
      }
    } catch (err) {
      console.error('도서 읽지않음 처리 API 에러:', err);
      vm.showToast(i18n.t('detail.server_comm_error'), 'error');
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
        vm.showToast(i18n.t(isSeriesScope ? 'context_menu.series_marked_read' : 'context_menu.book_marked_read', { title }), 'success');
        ui.close();
        await refreshAfterReadStateChange(libraryId);
      } else {
        vm.showToast(i18n.t('context_menu.change_failed', { error: res.error }), 'error');
      }
    } catch (err) {
      console.error('도서 읽음 처리 API 에러:', err);
      vm.showToast(i18n.t('detail.server_comm_error'), 'error');
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

// [기기용 받기]: "웹 받기 기기" 프로필로 변환한 EPUB을 받는다(/api/media/books/<id>/epaper).
// 변환을 기다리는 동안 화면을 막지 않고 토스트만 띄운다. 503 = 변환 중(서버가 이어서 하므로 다시 누르면 된다), 422 = 변환 불가.
const epaperInFlight = new Set();

function filenameFromDisposition(header, fallback) {
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header || '');
  if (star) {
    try { return decodeURIComponent(star[1].trim()); } catch (_) { /* 아래 대체 이름 */ }
  }
  const plain = /filename="([^"]+)"/i.exec(header || '');
  return plain ? plain[1] : fallback;
}

// X-Epaper-Glyphs(BookOasis 펌웨어 기기만): 기기 기본 폰트에서 □로 보일 글자 수와 견본, 덜 빠지는 폰트.
// 받기 완료 토스트 하나에 담는다(읽는 화면이 아니라 받는 순간이라 방해하지 않는다).
export function epaperGlyphsMessage(header) {
  if (!header) return '';
  let g;
  try { g = JSON.parse(decodeURIComponent(header)); } catch (_) { return ''; }
  if (!g || !(Number(g.missing) > 0)) return '';
  const parts = [i18n.t('context_menu.epaper_done_glyphs', { count: Number(g.missing), sample: String(g.sample || '') })];
  for (const [font, count] of Array.isArray(g.better) ? g.better : []) {
    parts.push(Number(count) > 0
      ? i18n.t('context_menu.epaper_glyphs_better', { font: String(font), count: Number(count) })
      : i18n.t('context_menu.epaper_glyphs_better_all', { font: String(font) }));
  }
  return parts.join(' · ');
}

async function epaperDownload(target, ui) {
  if (!target || !target.id) return;
  ui.close();
  const bookId = Number(target.id);
  const vm = await import('../view_manager.js');
  if (epaperInFlight.has(bookId)) {
    vm.showToast(i18n.t('context_menu.epaper_converting'), 'info');
    return;
  }
  epaperInFlight.add(bookId);
  vm.showToast(i18n.t('context_menu.epaper_converting'), 'info', { duration: 60000 });
  try {
    const res = await fetch(`/api/media/books/${bookId}/epaper`);
    if (res.status === 503) {
      vm.showToast(i18n.t('context_menu.epaper_retry_later'), 'info', { duration: 6000 });
      return;
    }
    if (res.status === 422) {
      vm.showToast(i18n.t('context_menu.epaper_failed'), 'error', { duration: 6000 });
      return;
    }
    if (!res.ok) {
      let error = '';
      try { error = (await res.json())?.error || ''; } catch (_) { /* 본문 없음 */ }
      vm.showToast(i18n.t('context_menu.epaper_error', { error: error || res.status }), 'error');
      return;
    }
    const blob = await res.blob();
    const name = filenameFromDisposition(res.headers.get('Content-Disposition'), `book_${bookId}.epub`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);  // iOS Safari는 받기를 늦게 시작한다
    const glyphs = epaperGlyphsMessage(res.headers.get('X-Epaper-Glyphs'));
    if (glyphs) vm.showToast(glyphs, 'info', { duration: 12000 });
    else vm.showToast(i18n.t('context_menu.epaper_done'), 'success');
  } catch (err) {
    console.error('[EPAPER] web download failed:', err);
    vm.showToast(i18n.t('detail.server_comm_error'), 'error');
  } finally {
    epaperInFlight.delete(bookId);
  }
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
  'epaper-download': epaperDownload,
};
