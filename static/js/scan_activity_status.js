// scan_activity_status.js – 백그라운드 스캔 상태 폴링 및 카테고리 스피너 제어 루틴 (ui.js에서 분리)
import { state } from './state.js';
import { parseServerDateTime } from './utils/time.js';
import {
  clearableCount,
  escapeActivityText,
  finishedWhileWatching,
  notificationDetail,
  notificationItemHtml,
  notificationTitle,
  summarizeNotifications,
  tr,
} from './notification_render.js';
import { initNotificationCards, restoreCardExpansions } from './notification_cards.js';

let statusIntervalId = null;
let wasScanningPrevious = false;
let lastActiveLibIds = new Set();
let lastIsHeaderScanning = false;
let scanLatchTimerMap = new Map();
let latestSystemStatus = null;
let refreshStatusPoll = null;
let seenRecentBatchScanIds = null;

export function refreshSystemStatus() {
  return refreshStatusPoll ? refreshStatusPoll() : Promise.resolve();
}

// 보고 있는 동안 끝난 작업만 토스트로 알린다 (진행 중으로 본 track_key가 최근 완료로 넘어왔을 때).
let previousRunningTrackKeys = null;
const toastedFinishedIds = new Set();
function notifyFinishedWhileWatching(items) {
  const { runningKeys, finished } = finishedWhileWatching(items, previousRunningTrackKeys);
  previousRunningTrackKeys = runningKeys;
  if (typeof window.showToast !== 'function') return;
  finished.forEach(item => {
    if (toastedFinishedIds.has(item.id)) return;
    toastedFinishedIds.add(item.id);
    const toastType = item.tone === 'error' ? 'error' : item.tone === 'muted' ? 'info' : 'success';
    window.showToast(`${notificationTitle(item)} · ${notificationDetail(item)}`, toastType);
  });
}

function renderScanActivity(data) {
  latestSystemStatus = data;
  const button = document.getElementById('btn-scan-activity');
  const summary = document.getElementById('scan-activity-summary');
  const list = document.getElementById('scan-activity-list');
  if (!button || !summary || !list) return;

  const items = Array.isArray(data?.notifications) ? data.notifications : [];
  notifyFinishedWhileWatching(items);
  const summaryInfo = summarizeNotifications(items);

  // 진행 중 = 주황 점(깜빡임), 조치 필요 = 빨간 점(고정), 항목이 없으면 아이콘을 흐리게 (숨기지 않는다).
  button.classList.toggle('is-active', summaryInfo.isRunning);
  button.classList.toggle('has-warning', summaryInfo.hasWarning);
  button.classList.toggle('is-idle', summaryInfo.isEmpty);
  // 모바일에선 이 버튼이 드로어 푸터로 옮겨가 있어 ☰/푸터에 점을 대신 띄운다 (mobile.css .drawer-scan-dot)
  document.querySelectorAll('[data-role="scan-activity-mirror"]').forEach(el => {
    el.classList.toggle('is-active', summaryInfo.isRunning);
    el.classList.toggle('has-warning', summaryInfo.hasWarning);
  });

  summary.textContent = summaryInfo.text;
  const titleText = tr('notify.title', {}, '알림');
  const buttonTitle = summaryInfo.isEmpty ? titleText : `${titleText} · ${summaryInfo.text}`;
  button.title = buttonTitle;
  button.setAttribute('aria-label', buttonTitle);
  const clearButton = document.getElementById('btn-clear-notifications');
  if (clearButton) clearButton.hidden = clearableCount(items) === 0;

  if (items.length === 0) {
    list.innerHTML = `
      <div class="scan-activity-empty">
        <i class="fa-regular fa-bell" aria-hidden="true"></i>
        <span>${escapeActivityText(tr('notify.empty', {}, '새 알림이 없습니다.'))}</span>
      </div>`;
    return;
  }
  initNotificationCards(list, { refresh: () => refreshSystemStatus() });
  list.innerHTML = items.map(notificationItemHtml).join('');
  restoreCardExpansions(list);
}

// 알림을 닫을 때 그 시각을 서버에 남긴다 - 이후 폴링부터 지금 본 항목은 '읽음'이 된다.
function markNotificationsSeen() {
  const items = Array.isArray(latestSystemStatus?.notifications) ? latestSystemStatus.notifications : [];
  if (!items.some(i => i.read === false)) return;
  fetch('/api/notifications/seen', { method: 'POST' })
    .then(() => refreshSystemStatus())
    .catch(err => console.warn('[Notifications] mark seen failed:', err));
}

// [지우기]: 최근 완료는 숨기고 참고 카드는 '알고 있음'으로 (서버 규칙: notification_service.clear_notifications).
// 진행 중·조치 필요 항목은 남는다. 토스트 [되돌리기]로 직전 상태를 복원한다.
async function clearNotifications() {
  const items = Array.isArray(latestSystemStatus?.notifications) ? latestSystemStatus.notifications : [];
  const count = clearableCount(items);
  if (!count) return;
  const toast = (msg, type, options) => (typeof window.showToast === 'function' ? window.showToast(msg, type, options) : null);
  try {
    const res = await fetch('/api/notifications/clear', { method: 'POST' });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'clear failed');
    await refreshSystemStatus();
    toast(escapeActivityText(tr('notify.cleared', { count: count.toLocaleString() }, `알림 ${count}건을 지웠습니다.`)), 'success', {
      actionLabel: tr('notify.clear_undo', {}, '되돌리기'),
      onAction: () => undoClearNotifications(data),
    });
  } catch (err) {
    console.warn('[Notifications] clear failed:', err);
    toast(escapeActivityText(tr('notify.clear_failed', {}, '알림을 지우지 못했습니다.')), 'error');
  }
}

async function undoClearNotifications(cleared) {
  try {
    const res = await fetch('/api/notifications/clear/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        previous_cleared_ms: cleared.previous_cleared_ms || 0,
        muted_group_keys: cleared.muted_group_keys || [],
      }),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'undo failed');
    await refreshSystemStatus();
    if (typeof window.showToast === 'function') window.showToast(escapeActivityText(tr('notify.clear_undone', {}, '지운 알림을 되돌렸습니다.')), 'info');
  } catch (err) {
    console.warn('[Notifications] undo clear failed:', err);
  }
}

function setScanActivityPopoverOpen(open) {
  const button = document.getElementById('btn-scan-activity');
  const popover = document.getElementById('scan-activity-popover');
  if (!button || !popover) return;
  const wasOpen = !popover.hidden;
  popover.hidden = !open;
  button.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open && latestSystemStatus) renderScanActivity(latestSystemStatus);
  // 닫을 때 읽음 처리한다 - 열자마자 지우면 '새 알림' 표시를 볼 틈이 없다.
  if (wasOpen && !open) markNotificationsSeen();
}

function initScanActivityPopover() {
  const button = document.getElementById('btn-scan-activity');
  const closeButton = document.getElementById('btn-close-scan-activity');
  const popover = document.getElementById('scan-activity-popover');
  if (!button || !closeButton || !popover || button.dataset.bound === '1') return;
  button.dataset.bound = '1';
  button.addEventListener('click', event => {
    event.stopPropagation();
    setScanActivityPopoverOpen(popover.hidden);
  });
  closeButton.addEventListener('click', () => setScanActivityPopoverOpen(false));
  document.getElementById('btn-clear-notifications')?.addEventListener('click', () => clearNotifications());
  popover.addEventListener('click', event => event.stopPropagation());
  document.addEventListener('click', () => setScanActivityPopoverOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') setScanActivityPopoverOpen(false);
  });
}

function applyCategoryScanSpinnersState() {
  const headerSpinner = document.getElementById('header-category-scan-spinner');
  if (headerSpinner) {
    headerSpinner.style.display = lastIsHeaderScanning ? 'inline-block' : 'none';
  }

  document.querySelectorAll('li[data-role="sidebar-category-dynamic"]').forEach(li => {
    const libId = li.getAttribute('data-category-id') || li.getAttribute('data-id');
    const sp = li.querySelector('.category-scan-spinner');
    if (sp) {
      // 사이드바에는 항상 현재 세션 타입(state.currentLibraryType)의 카테고리만 렌더링되므로,
      // 그 타입 기준으로 복합키를 만들어야 다른 타입의 동일 id 스캔과 섞이지 않는다.
      const isScanning = libId && lastActiveLibIds.has(`${state.currentLibraryType}:${libId}`);
      sp.style.display = isScanning ? 'inline-block' : 'none';
    }
  });
}

function updateCategoryScanSpinners(data, scanRefresh = {}) {
  const now = Date.now();
  const currentActiveLibIds = new Set();
  let isGlobalOrCurrentLibScanning = false;

  if (data && data.success && data.is_active) {
    wasScanningPrevious = true;

    const checkTask = (t) => {
      if (!t) return;
      const taskType = t.type || t.task_type;
      const kwargs = t.kwargs || {};
      const libId = kwargs.library_id;
      // library_id는 물리 DB(db_type)마다 별도 시퀀스라, 타입 없이 숫자만 비교하면
      // 서로 다른 세션의 라이브러리가 우연히 같은 id를 가질 때 스캔 스피너가 엉뚱한
      // 카테고리 옆에도 뜨는 버그가 생긴다 - 반드시 "dbType:libId" 복합키로 구분한다.
      const taskDbType = kwargs.db_type || 'general';

      if (taskType === 'lazy_scan') {
        isGlobalOrCurrentLibScanning = true;
      } else if (libId !== undefined && libId !== null) {
        currentActiveLibIds.add(`${taskDbType}:${libId}`);
        if (taskDbType === state.currentLibraryType && String(state.currentLibraryId) === String(libId)) {
          isGlobalOrCurrentLibScanning = true;
        }
      } else {
        isGlobalOrCurrentLibScanning = true;
      }
    };

    if (data.raw_status) {
      if (data.raw_status.running) checkTask(data.raw_status.running);
      if (Array.isArray(data.raw_status.pending)) {
        data.raw_status.pending.forEach(checkTask);
      }
    }

    if (currentActiveLibIds.size === 0 && data.tasks && data.tasks.length > 0) {
      isGlobalOrCurrentLibScanning = true;
    }

    currentActiveLibIds.forEach(libId => {
      scanLatchTimerMap.set(libId, now);
    });
  } else {
    if (wasScanningPrevious) {
      wasScanningPrevious = false;
      // 스캔이 끝난 라이브러리의 상세 화면이 열려 있으면 그 상세도 함께 갱신한다
      // (아래에서 scanLatchTimerMap을 비우기 전의 활성 목록으로 판단해야 한다).
      const detailView = document.getElementById('book-detail-view');
      const detailLibraryKey = `${state.currentLibraryType}:${state.detailLibraryId}`;
      const shouldRefreshDetail = Boolean(
        !scanRefresh.detailRefreshed
        && detailView
        && detailView.style.display !== 'none'
        && state.detailSeriesName
        && state.detailBookIds?.length
        && (lastActiveLibIds.has(detailLibraryKey) || lastIsHeaderScanning)
      );
      scanLatchTimerMap.clear();
      console.log('[ScanSpinner] 🏁 백그라운드 스캔 완수. 리스트 자동 갱신');
      if (state.currentLibraryId === 'home') {
        if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
      } else if (state.currentLibraryId === 'history') {
        if (typeof window.loadReadingHistory === 'function') window.loadReadingHistory();
      } else if (state.currentLibraryId !== 'settings') {
        if (scanRefresh.listInvalidated) {
          // 같은 폴링에서 완료된 도서 스캔이 이미 이 목록을 무효화했다 - 이중 갱신하지 않는다.
        } else if (typeof window.invalidateBookListAfterScan === 'function') {
          window.invalidateBookListAfterScan();
        } else if (typeof window.loadBooksList === 'function') {
          window.loadBooksList(false);
        }
      }
      if (shouldRefreshDetail && typeof window.openBookDetail === 'function') {
        window.openBookDetail(
          null,
          state.detailSeriesName,
          state.detailLibraryId,
          state.detailRepresentativeBookId,
          state.detailDisplayTitle
        );
      }
    }
  }

  // 3초 유예(Latch) 타임 이내 항목 유지하여 태스크 전환 순간 미세 깜빡임 완벽 방지
  const effectiveActiveLibIds = new Set();
  scanLatchTimerMap.forEach((ts, libId) => {
    if (now - ts < 3000) {
      effectiveActiveLibIds.add(libId);
    } else {
      scanLatchTimerMap.delete(libId);
    }
  });

  lastActiveLibIds = effectiveActiveLibIds;
  lastIsHeaderScanning = isGlobalOrCurrentLibScanning || effectiveActiveLibIds.has(`${state.currentLibraryType}:${state.currentLibraryId}`);

  applyCategoryScanSpinnersState();
}

function isRecentlyFinishedScan(task) {
  const finishedAt = parseServerDateTime(task?.finished_at);
  if (!finishedAt) return false;
  const age = Date.now() - finishedAt.getTime();
  return age >= -60000 && age <= 120000;
}

// 2초 폴링 사이에 끝나 is_active 전환을 못 본 빠른 도서 스캔(단일/시리즈 즉시 스캔)도
// 서버가 내려주는 recent_book_scans로 감지해서 현재 목록과 열려 있는 상세를 갱신한다.
function refreshDetailAfterBookScan(data) {
  const none = { listInvalidated: false, detailRefreshed: false };
  const recentScans = (Array.isArray(data?.raw_status?.recent_book_scans)
    ? data.raw_status.recent_book_scans
    : []).filter(task => task?.type === 'batch_book_scan');
  const currentIds = new Set(recentScans.map(task => String(task.id ?? task.key ?? '')));

  const isInitialStatus = seenRecentBatchScanIds === null;
  const newlyFinished = recentScans.filter(task =>
    ['completed', 'failed', 'cancelled'].includes(task?.status)
    && (isInitialStatus
      ? isRecentlyFinishedScan(task)
      : !seenRecentBatchScanIds.has(String(task.id ?? task.key ?? '')))
  );
  seenRecentBatchScanIds = currentIds;
  if (!newlyFinished.length) return none;

  const currentType = String(state.currentLibraryType || 'general');
  const currentLibraryId = String(state.currentLibraryId || '');
  const affectsList = newlyFinished.some(task => {
    const kwargs = task.kwargs || {};
    const taskLibraryId = kwargs.library_id;
    return String(kwargs.db_type || 'general') === currentType
      && (
        taskLibraryId == null
        || currentLibraryId === 'all'
        || currentLibraryId === 'favorite'
        || String(taskLibraryId) === currentLibraryId
      );
  });
  let listInvalidated = false;
  if (affectsList && typeof window.invalidateBookListAfterScan === 'function') {
    window.invalidateBookListAfterScan();
    listInvalidated = true;
  }

  const detailView = document.getElementById('book-detail-view');
  if (typeof window.openBookDetail !== 'function'
      || !detailView || detailView.style.display === 'none'
      || !state.detailBookIds?.length) {
    return { listInvalidated, detailRefreshed: false };
  }

  const detailBookIds = new Set(state.detailBookIds.map(id => String(id)));
  const affectsDetail = newlyFinished.some(task => {
    const kwargs = task.kwargs || {};
    if (String(kwargs.db_type || 'general') !== currentType) return false;
    const scannedIds = Array.isArray(kwargs.book_ids) ? kwargs.book_ids : [];
    return scannedIds.some(id => detailBookIds.has(String(id)));
  });
  if (!affectsDetail) return { listInvalidated, detailRefreshed: false };

  console.log('[ScanDetailRefresh] 도서 스캔 완료로 열린 상세 페이지를 갱신합니다.');
  window.openBookDetail(
    null,
    state.detailSeriesName,
    state.detailLibraryId,
    state.detailRepresentativeBookId,
    state.detailDisplayTitle
  );
  return { listInvalidated, detailRefreshed: true };
}

window.addEventListener('library:categories-rendered', () => {
  applyCategoryScanSpinnersState();
});

export function startSystemStatusPolling() {
  if (statusIntervalId) return;

  const poll = async () => {
    try {
      const res = await fetch(`/api/system/status?type=${state.currentLibraryType}`);
      const data = await res.json();
      const scanRefresh = refreshDetailAfterBookScan(data);
      updateCategoryScanSpinners(data, scanRefresh);
      renderScanActivity(data);
    } catch (err) {
      console.error('[ScanSpinner] 상태 조회 실패:', err);
    }
  };

  refreshStatusPoll = poll;
  // 최초 1회 즉시 실행 후 2초 주기 반응형 폴링
  poll();
  statusIntervalId = setInterval(poll, 2000);
}

// 스크립트 로드 시 즉시 시작
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initScanActivityPopover();
    startSystemStatusPolling();
  });
} else {
  initScanActivityPopover();
  startSystemStatusPolling();
}
