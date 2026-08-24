// scan_activity_status.js – 백그라운드 스캔 상태 폴링 및 카테고리 스피너 제어 루틴 (ui.js에서 분리)
import { state } from './state.js';
import { parseServerDateTime } from './utils/time.js';

let statusIntervalId = null;
let wasScanningPrevious = false;
let lastActiveLibIds = new Set();
let lastIsHeaderScanning = false;
let scanLatchTimerMap = new Map();
let latestSystemStatus = null;

function escapeActivityText(value) {
  const node = document.createElement('div');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

function escapeActivityAttribute(value) {
  return escapeActivityText(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function getScanActivityTaskInfo(task, isPending = false) {
  const taskType = task?.type || task?.task_type || 'background';
  const kwargs = task?.kwargs || {};
  const libraryId = kwargs.library_id;
  const dbType = kwargs.db_type || state.currentLibraryType || 'general';
  const stage = String(task?.stage || '').trim();
  const names = {
    library_scan: '카테고리 스캔',
    cover_scan: '표지 스캔',
    lazy_scan: '미디어 검색',
    gdrive_copy: 'Drive 복사',
  };
  const title = task?.library_name
    || (taskType === 'lazy_scan' ? '전체 시스템' : libraryId != null ? `Library ${libraryId} (${dbType})` : '백그라운드 작업');
  const detail = isPending ? `${names[taskType] || '백그라운드 작업'} 대기 중` : stage || `${names[taskType] || '백그라운드 작업'} 진행 중`;
  const startedAt = task?.started_at || task?.enqueued_at;
  return { title, detail, startedAt };
}

function formatScanActivityElapsed(startedAt) {
  if (!startedAt) return '';
  const started = parseServerDateTime(startedAt);
  if (!started) return '';
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
  if (elapsedSeconds < 60) return `${elapsedSeconds}초`;
  const minutes = Math.floor(elapsedSeconds / 60);
  if (minutes < 60) return `${minutes}분`;
  return `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
}

function renderScanActivity(data) {
  latestSystemStatus = data;
  const button = document.getElementById('btn-scan-activity');
  const summary = document.getElementById('scan-activity-summary');
  const list = document.getElementById('scan-activity-list');
  if (!button || !summary || !list) return;

  const running = data?.raw_status?.running || null;
  const pending = Array.isArray(data?.raw_status?.pending) ? data.raw_status.pending : [];
  const isActive = Boolean(data?.success && data?.is_active);
  button.classList.toggle('is-active', isActive);

  const tasks = [];
  if (running) tasks.push({ task: running, pending: false });
  pending.forEach(task => tasks.push({ task, pending: true }));
  if (tasks.length === 0 && isActive && Array.isArray(data?.tasks)) {
    data.tasks.forEach(detail => tasks.push({
      task: { type: 'background', library_name: '시스템 유지보수', stage: detail },
      pending: false,
    }));
  }
  button.title = tasks.length > 0 ? `스캔 활동 ${tasks.length}건` : '스캔 활동';
  summary.textContent = running
    ? `실행 중 · 대기 ${pending.length}건`
    : pending.length ? `대기 ${pending.length}건` : tasks.length ? '실행 중' : '대기 중';
  if (tasks.length === 0) {
    list.innerHTML = `
      <div class="scan-activity-empty">
        <i class="fa-regular fa-circle-check" aria-hidden="true"></i>
        <span>진행 중인 스캔이 없습니다.</span>
      </div>`;
    return;
  }

  list.innerHTML = tasks.map(({ task, pending: isPending }) => {
    const info = getScanActivityTaskInfo(task, isPending);
    const elapsed = isPending ? '' : formatScanActivityElapsed(info.startedAt);
    return `
      <div class="scan-activity-item${isPending ? ' is-pending' : ''}">
        <span class="scan-activity-item-icon">
          <i class="fa-solid ${isPending ? 'fa-clock' : 'fa-circle-notch fa-spin'}" aria-hidden="true"></i>
        </span>
        <div class="scan-activity-item-copy">
          <div class="scan-activity-item-title" title="${escapeActivityAttribute(info.title)}">${escapeActivityText(info.title)}</div>
          <div class="scan-activity-item-detail" title="${escapeActivityAttribute(info.detail)}">${escapeActivityText(info.detail)}</div>
        </div>
        <span class="scan-activity-item-time">${escapeActivityText(elapsed)}</span>
      </div>`;
  }).join('');
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

function updateCategoryScanSpinners(data) {
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
      scanLatchTimerMap.clear();
      console.log('[ScanSpinner] 🏁 백그라운드 스캔 완수. 리스트 자동 갱신');
      if (state.currentLibraryId === 'home') {
        if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
      } else if (state.currentLibraryId === 'history') {
        if (typeof window.loadReadingHistory === 'function') window.loadReadingHistory();
      } else if (state.currentLibraryId !== 'settings') {
        if (typeof window.loadBooksList === 'function') window.loadBooksList(false);
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

window.addEventListener('library:categories-rendered', () => {
  applyCategoryScanSpinnersState();
});

export function startSystemStatusPolling() {
  if (statusIntervalId) return;

  const poll = async () => {
    try {
      const res = await fetch(`/api/system/status?type=${state.currentLibraryType}`);
      const data = await res.json();
      updateCategoryScanSpinners(data);
      renderScanActivity(data);
    } catch (err) {
      console.error('[ScanSpinner] 상태 조회 실패:', err);
    }
  };

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
