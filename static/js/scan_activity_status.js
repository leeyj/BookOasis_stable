// scan_activity_status.js – 백그라운드 스캔 상태 폴링 및 카테고리 스피너 제어 루틴 (ui.js에서 분리)
import { state } from './state.js';
import { parseServerDateTime, formatRelativeTime } from './utils/time.js';

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

function escapeActivityText(value) {
  const node = document.createElement('div');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

function escapeActivityAttribute(value) {
  return escapeActivityText(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function getScanActivityTaskInfo(task, isPending = false, isRecent = false) {
  const taskType = task?.type || task?.task_type || 'background';
  const kwargs = task?.kwargs || {};
  const libraryId = kwargs.library_id;
  const dbType = kwargs.db_type || state.currentLibraryType || 'general';
  const stage = String(task?.stage || '').trim();
  const names = {
    library_scan: '카테고리 스캔',
    cover_scan: '표지 스캔',
    lazy_scan: '미디어 검색',
    batch_book_scan: '선택 도서 스캔',
    gdrive_copy: 'Drive 복사',
  };
  const batchCount = Array.isArray(kwargs.book_ids) ? kwargs.book_ids.length : 0;
  const isSingleBookScan = taskType === 'batch_book_scan' && batchCount === 1;
  const singleBookLabel = isRecent && isSingleBookScan && kwargs.book_title
    ? String(kwargs.book_title)
    : '도서 1권';
  const title = taskType === 'batch_book_scan'
    ? `${task?.library_name ? `${task.library_name} · ` : ''}${isSingleBookScan ? singleBookLabel : `선택 도서 ${batchCount}권`}`
    : task?.library_name
      || (taskType === 'lazy_scan' ? '전체 시스템' : libraryId != null ? `Library ${libraryId} (${dbType})` : '백그라운드 작업');
  const taskName = isSingleBookScan ? '도서 스캔' : (names[taskType] || '백그라운드 작업');
  const statusLabel = task?.status === 'failed' ? '실패' : task?.status === 'cancelled' ? '취소' : '완료';
  const detail = isRecent
    ? (stage || (statusLabel === '완료' ? '스캔 완료' : `스캔 ${statusLabel}`))
    : isPending ? `${taskName} 대기 중` : stage || `${taskName} 진행 중`;
  return { title, detail };
}

function formatScanActivityElapsed(task) {
  let elapsedSeconds = null;
  if (task?.elapsed_seconds !== null && task?.elapsed_seconds !== undefined
      && Number.isFinite(Number(task.elapsed_seconds))) {
    elapsedSeconds = Math.max(0, Math.floor(Number(task.elapsed_seconds)));
  } else {
    const startedAt = task?.started_at || task?.enqueued_at;
    if (!startedAt) return '';
    const started = parseServerDateTime(startedAt);
    if (!started) return '';
    elapsedSeconds = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
  }
  if (elapsedSeconds < 60) return `${elapsedSeconds}초`;
  const minutes = Math.floor(elapsedSeconds / 60);
  if (minutes < 60) return `${minutes}분`;
  return `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
}

// 듣기 서버 미리 만들기 작업 (/api/system/status의 tts_pregen). 스캔과 같은 목록에 섞어 보여 준다.
let seenPregenStatus = null;
function pregenItemHtml(item) {
  const running = item.status === 'running';
  const queued = item.status === 'queued';
  const failed = item.status === 'failed' || item.status === 'cancelled';
  const stateClass = queued ? ' is-pending' : running ? '' : failed ? ' is-failed' : ' is-completed';
  const icon = queued ? 'fa-clock' : running ? 'fa-circle-notch fa-spin' : failed ? 'fa-circle-exclamation' : 'fa-circle-check';
  // 큰 책(조각 1만 개 이상)은 정수 %가 한참 0에 머무므로 소수 한 자리와 조각 수를 같이 보여 준다
  const pct = item.total ? Math.floor((item.done * 1000) / item.total) / 10 : item.percent;
  const count = item.total ? ` (${Number(item.done).toLocaleString()} / ${Number(item.total).toLocaleString()})` : '';
  const detail = queued ? `음성 생성 대기 중${item.total ? ` · ${Number(item.total).toLocaleString()}조각` : ''}`
    : running ? `음성 생성 중 ${pct}%${count}`
      : item.status === 'cancelled' ? '음성 생성 취소' : failed ? '음성 생성 실패' : '음성 생성 완료 · 들을 준비됨';
  const time = running ? `${pct}%` : queued ? '' : failed ? (item.status === 'cancelled' ? '취소' : '실패') : '완료';
  const title = `${item.title || ''}${item.db_type === 'adult' ? ' (성인)' : ''}`;
  return `
      <div class="scan-activity-item${stateClass}">
        <span class="scan-activity-item-icon">
          <i class="fa-solid ${icon}" aria-hidden="true"></i>
        </span>
        <div class="scan-activity-item-copy">
          <div class="scan-activity-item-title" title="${escapeActivityAttribute(title)}"><i class="fa-solid fa-headphones" aria-hidden="true" style="margin-right: 0.3rem; opacity: 0.7;"></i>${escapeActivityText(title)}</div>
          <div class="scan-activity-item-detail">${escapeActivityText(detail)}</div>
        </div>
        <span class="scan-activity-item-time">${escapeActivityText(time)}</span>
      </div>`;
}

// 페이지를 보고 있는 동안 끝난 작업만 알린다 (처음 불러온 목록의 완료 항목은 알리지 않는다)
function notifyPregenTransitions(items) {
  const current = new Map(items.map(i => [`${i.db_type}:${i.id}`, i]));
  if (seenPregenStatus) {
    current.forEach((item, key) => {
      const before = seenPregenStatus.get(key);
      if (before && before !== item.status && (item.status === 'done' || item.status === 'failed')
          && typeof window.showToast === 'function') {
        window.showToast(item.status === 'done'
          ? `음성 미리 만들기 완료: ${item.title}`
          : `음성 미리 만들기 실패: ${item.title}`, item.status === 'done' ? 'success' : 'error');
      }
    });
  }
  seenPregenStatus = new Map([...current].map(([k, i]) => [k, i.status]));
}

// 계속 실패 중인 백그라운드 작업(/api/system/status의 system_warnings, 관리자에게만 내려옴).
// 다음 성공 때 서버가 자동으로 지우므로 여기서는 보여 주기만 한다.
function systemWarningItemHtml(warning) {
  const count = Number(warning?.fail_count || 0);
  const since = warning?.last_ok_at
    ? `마지막 성공 ${formatRelativeTime(warning.last_ok_at)}`
    : `첫 실패 ${formatRelativeTime(warning?.first_failed_at)}`;
  const detail = `${since} · 연속 ${count}회 실패 · ${warning?.message || ''}`;
  return `
      <div class="scan-activity-item is-failed is-system-warning" data-role="system-warning">
        <span class="scan-activity-item-icon">
          <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
        </span>
        <div class="scan-activity-item-copy">
          <div class="scan-activity-item-title" title="${escapeActivityAttribute(warning?.label)}">${escapeActivityText(warning?.label)} 실패 중</div>
          <div class="scan-activity-item-detail" title="${escapeActivityAttribute(detail)}">${escapeActivityText(detail)}</div>
        </div>
        <span class="scan-activity-item-time">경고</span>
      </div>`;
}

function renderScanActivity(data) {
  latestSystemStatus = data;
  const button = document.getElementById('btn-scan-activity');
  const summary = document.getElementById('scan-activity-summary');
  const list = document.getElementById('scan-activity-list');
  if (!button || !summary || !list) return;

  const running = data?.raw_status?.running || null;
  const pending = Array.isArray(data?.raw_status?.pending) ? data.raw_status.pending : [];
  const recentBookScans = Array.isArray(data?.raw_status?.recent_book_scans)
    ? data.raw_status.recent_book_scans
    : [];
  const isActive = Boolean(data?.success && data?.is_active);
  const pregenItems = Array.isArray(data?.tts_pregen) ? data.tts_pregen : [];
  notifyPregenTransitions(pregenItems);
  const pregenActive = pregenItems.some(i => i.status === 'running' || i.status === 'queued');
  const systemWarnings = Array.isArray(data?.system_warnings) ? data.system_warnings : [];
  const hasWarning = systemWarnings.length > 0;
  button.classList.toggle('is-active', isActive || pregenActive);
  button.classList.toggle('has-warning', hasWarning);
  // 모바일에선 이 버튼이 드로어 푸터로 옮겨가 있어 ☰/푸터에 진행 중 점을 대신 띄운다 (mobile.css .drawer-scan-dot)
  document.querySelectorAll('[data-role="scan-activity-mirror"]').forEach(el => {
    el.classList.toggle('is-active', isActive || pregenActive);
    el.classList.toggle('has-warning', hasWarning);
  });

  const tasks = [];
  if (running) tasks.push({ task: running, pending: false });
  pending.forEach(task => tasks.push({ task, pending: true }));
  recentBookScans.forEach(task => tasks.push({ task, pending: false, recent: true }));
  if (tasks.length === 0 && isActive && Array.isArray(data?.tasks)) {
    data.tasks.forEach(detail => tasks.push({
      task: { type: 'background', library_name: '시스템 유지보수', stage: detail },
      pending: false,
    }));
  }
  const total = tasks.length + pregenItems.length;
  button.title = hasWarning
    ? `스캔 활동 · 경고 ${systemWarnings.length}건`
    : (total > 0 ? `스캔 활동 ${total}건` : '스캔 활동');
  summary.textContent = (hasWarning && !running && !pending.length) ? `경고 ${systemWarnings.length}건` : running
    ? `실행 중 · 대기 ${pending.length}건`
    : pending.length ? `대기 ${pending.length}건`
      : recentBookScans.length ? `최근 도서 스캔 ${recentBookScans.length}건`
        : tasks.length ? '실행 중'
          : pregenActive ? '음성 생성 중' : pregenItems.length ? '최근 음성 생성' : '대기 중';
  const warningsHtml = systemWarnings.map(systemWarningItemHtml).join('');
  if (tasks.length === 0 && pregenItems.length === 0) {
    list.innerHTML = warningsHtml || `
      <div class="scan-activity-empty">
        <i class="fa-regular fa-circle-check" aria-hidden="true"></i>
        <span>진행 중인 스캔이 없습니다.</span>
      </div>`;
    return;
  }

  list.innerHTML = warningsHtml + tasks.map(({ task, pending: isPending, recent: isRecent }) => {
    const info = getScanActivityTaskInfo(task, isPending, isRecent);
    const recentStatus = task?.status || 'completed';
    const itemStateClass = isPending ? ' is-pending'
      : isRecent ? ` is-${recentStatus}`
        : '';
    const iconClass = isPending
      ? 'fa-clock'
      : isRecent
        ? (recentStatus === 'completed' ? 'fa-circle-check' : 'fa-circle-exclamation')
        : 'fa-circle-notch fa-spin';
    const elapsed = isRecent
      ? (recentStatus === 'failed' ? '실패' : recentStatus === 'cancelled' ? '취소' : '완료')
      : isPending ? '' : formatScanActivityElapsed(task);
    return `
      <div class="scan-activity-item${itemStateClass}">
        <span class="scan-activity-item-icon">
          <i class="fa-solid ${iconClass}" aria-hidden="true"></i>
        </span>
        <div class="scan-activity-item-copy">
          <div class="scan-activity-item-title" title="${escapeActivityAttribute(info.title)}">${escapeActivityText(info.title)}</div>
          <div class="scan-activity-item-detail" title="${escapeActivityAttribute(info.detail)}">${escapeActivityText(info.detail)}</div>
        </div>
        <span class="scan-activity-item-time">${escapeActivityText(elapsed)}</span>
      </div>`;
  }).join('') + pregenItems.map(pregenItemHtml).join('');
}

function setScanActivityPopoverOpen(open) {
  const button = document.getElementById('btn-scan-activity');
  const popover = document.getElementById('scan-activity-popover');
  if (!button || !popover) return;
  popover.hidden = !open;
  button.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (open && latestSystemStatus) renderScanActivity(latestSystemStatus);
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
