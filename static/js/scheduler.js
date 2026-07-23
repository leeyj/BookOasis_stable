// scheduler.js – 라이브러리 스케줄 목록 로딩 및 관리 UI 전용 모듈
import { state } from './state.js';
import * as api from './api.js';

function buildStatusBadge(scanStatus) {
  if (scanStatus === 'scanning') {
    return `<span class="badge-scan-status scanning"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('settings.status_scanning')}</span>`;
  }
  if (scanStatus === 'failed') {
    return `<span class="badge-scan-status failed">${i18n.t('settings.status_failed')}</span>`;
  }
  return `<span class="badge-scan-status ready">${i18n.t('settings.status_ready')}</span>`;
}

function buildScheduleRow(lib) {
  const statusBadge = buildStatusBadge(lib.scan_status);
  const cleanName = lib.name.replace(/'/g, "\\'");
  const cleanRcloneRcUrl = (lib.rclone_rc_url || '').replace(/'/g, "\\'");
  const cleanCronSchedule = (lib.cron_schedule || '').replace(/'/g, "\\'");
  const lastScannedAt = lib.last_scanned_at || '-';

  return `
    <tr data-library-id="${lib.id}" style="border-bottom: 1px solid rgba(255,255,255,0.05); hover: background: rgba(255,255,255,0.02);">
      <td style="padding: 1rem; font-weight: 600; color: #fff;">${lib.name}</td>
      <td style="padding: 1rem; color: #94a3b8; font-family: monospace; font-size: 0.8rem; white-space: pre-line;">${lib.physical_path}</td>
      <td data-role="schedule-status" style="padding: 1rem; text-align: center;">${statusBadge}</td>
      <td style="padding: 1rem; text-align: center;">
        <button class="btn-toggle" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" onclick="openScanSettingsModal(${lib.id}, '${cleanName}', ${lib.is_remote}, '${cleanRcloneRcUrl}', '${cleanCronSchedule}', ${lib.vfs_refresh_before_scan || 0})" title="상세 설정">
          <i class="fa-solid fa-gear"></i> ${i18n.t('settings.col_config') || '설정'}
        </button>
      </td>
      <td style="padding: 1rem; text-align: center;">
        <button class="btn-toggle active" data-role="schedule-action" data-last-scanned-at="${lastScannedAt}" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" onclick="showScheduleActionMenu(event, ${lib.id}, '${cleanName}')" title="작업 메뉴 열기">
          ${i18n.t('settings.col_action') || '작업'} <i class="fa-solid fa-chevron-down" style="font-size: 0.65rem;"></i>
        </button>
      </td>
    </tr>
  `;
}

// 환경설정 (스케줄 관리) 리스트 로드 및 렌더링
export async function loadLibrarySchedules() {
  const container = document.getElementById('settings-libraries-list');
  if (!container) return;
  container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><span style="display:inline-block; margin-top:0.5rem;">${i18n.t('settings.loading_schedules')}</span></td></tr>`;
  
  try {
    const data = await api.fetchLibrarySchedules(state.currentLibraryType);
    if (data.success) {
      if (data.libraries.length === 0) {
        container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;">${i18n.t('settings.no_categories')}</td></tr>`;
        return;
      }

      container.innerHTML = data.libraries.map(buildScheduleRow).join('');
    } else {
      container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.fetch_failed')}: ${data.error}</td></tr>`;
    }
  } catch (e) {
    console.error('스케줄 조회 에러:', e);
    container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.server_error')}</td></tr>`;
  }
}

export async function refreshLibraryScheduleStatuses() {
  const container = document.getElementById('settings-libraries-list');
  if (!container) return;

  try {
    const data = await api.fetchLibrarySchedules(state.currentLibraryType);
    if (!data.success || !Array.isArray(data.libraries) || data.libraries.length === 0) {
      return;
    }

    const existingRows = container.querySelectorAll('tr[data-library-id]');
    if (existingRows.length !== data.libraries.length) {
      loadLibrarySchedules();
      return;
    }

    for (const lib of data.libraries) {
      const row = container.querySelector(`tr[data-library-id="${lib.id}"]`);
      if (!row) {
        loadLibrarySchedules();
        return;
      }

      const statusCell = row.querySelector('[data-role="schedule-status"]');
      const nextStatusHtml = buildStatusBadge(lib.scan_status);
      if (statusCell && statusCell.innerHTML !== nextStatusHtml) {
        statusCell.innerHTML = nextStatusHtml;
      }

      const actionButton = row.querySelector('[data-role="schedule-action"]');
      if (actionButton) {
        actionButton.dataset.lastScannedAt = lib.last_scanned_at || '-';
      }
    }
    if (typeof window.loadLibraries === 'function') {
      window.loadLibraries();
    }
  } catch (e) {
    console.error('스케줄 상태 갱신 에러:', e);
  }
}
window.refreshLibraryScheduleStatuses = refreshLibraryScheduleStatuses;

// 스케줄 저장 (모달 등에서 범용 호출 가능한 헬퍼)
export async function saveLibrarySchedule(libraryId, cronVal, vfsRefresh, rcloneRcVal, name = '') {
  try {
    const data = await api.updateLibrarySchedule(state.currentLibraryType, libraryId, cronVal, vfsRefresh, rcloneRcVal);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('scheduler.save_success', {name: name}), 'success');
      } else {
        alert(i18n.t('scheduler.save_done'));
      }
      loadLibrarySchedules();
      if (typeof window.loadLibraries === 'function') {
        window.loadLibraries();
      }
      return true;
    } else {
      alert(i18n.t('scheduler.save_fail', {error: data.error}));
      return false;
    }
  } catch (e) {
    console.error('스케줄 변경 API 요청 에러:', e);
    alert(i18n.t('scheduler.server_error'));
    return false;
  }
}

// 즉시스캔 실행
export async function runLibraryScanNow(libraryId, name, force = false) {
  try {
    const data = await api.triggerLibraryScan(state.currentLibraryType, libraryId, force);
    if (data.success) {
      const modeText = force ? i18n.t('scheduler.scan_force') : i18n.t('scheduler.scan_incremental');
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('scheduler.scan_req_success', {name: name, modeText: modeText}), 'success');
      } else {
        alert(i18n.t('scheduler.scan_req_done', {modeText: modeText}));
      }
      loadLibrarySchedules();
    } else {
      alert(i18n.t('scheduler.scan_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('즉시 스캔 API 요청 에러:', e);
    alert(i18n.t('scheduler.server_error'));
  }
}

// 일괄 스캔 즉시 실행
export async function runAllLibrariesScanNow(force = false) {
  try {
    const data = await api.triggerAllLibrariesScan(state.currentLibraryType, force);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(data.message, 'success');
      } else {
        alert(data.message);
      }
      loadLibrarySchedules();
    } else {
      alert(i18n.t('scheduler.scan_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('일괄 스캔 API 요청 에러:', e);
    alert(i18n.t('scheduler.server_error'));
  }
}

// HTML 인라인 리스너와의 연동을 위해 글로벌 바인딩
window.runAllLibrariesScanNow = runAllLibrariesScanNow;

let activeLibraryId = null;
let activeLibraryName = '';

function pad2(value) {
  return String(value).padStart(2, '0');
}

function getHelperElements() {
  return {
    mode: document.getElementById('scan-settings-helper-mode'),
    time: document.getElementById('scan-settings-helper-time'),
    weekdayWrap: document.getElementById('scan-settings-helper-weekday-wrap'),
    weekday: document.getElementById('scan-settings-helper-weekday'),
    monthdayWrap: document.getElementById('scan-settings-helper-monthday-wrap'),
    monthday: document.getElementById('scan-settings-helper-monthday'),
    summary: document.getElementById('scan-settings-helper-summary'),
    cronInput: document.getElementById('scan-settings-cron')
  };
}

function safeTimeToParts(timeVal) {
  const raw = String(timeVal || '03:00');
  const parts = raw.split(':');
  const hour = Math.min(23, Math.max(0, parseInt(parts[0], 10) || 3));
  const minute = Math.min(59, Math.max(0, parseInt(parts[1], 10) || 0));
  return { hour, minute };
}

function buildCronFromHelper(mode, timeVal, weekdayVal, monthdayVal) {
  const { hour, minute } = safeTimeToParts(timeVal);
  const mm = String(minute);
  const hh = String(hour);

  if (mode === 'daily') {
    return { cron: `${mm} ${hh} * * *`, summary: `매일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekdays') {
    return { cron: `${mm} ${hh} * * 1-5`, summary: `평일(월~금) ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekend') {
    return { cron: `${mm} ${hh} * * 0,6`, summary: `주말(일/토) ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekly_once') {
    const day = Math.min(6, Math.max(0, parseInt(weekdayVal, 10) || 0));
    const dayLabel = ['일', '월', '화', '수', '목', '금', '토'][day] || '일';
    return { cron: `${mm} ${hh} * * ${day}`, summary: `매주 ${dayLabel}요일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'monthly') {
    const day = Math.min(31, Math.max(1, parseInt(monthdayVal, 10) || 1));
    return { cron: `${mm} ${hh} ${day} * *`, summary: `매월 ${day}일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  return {
    cron: '',
    summary: '직접 입력 모드입니다. 아래 Cron 입력칸을 수정하세요.'
  };
}

function parseHelperStateFromCron(cronVal) {
  const text = String(cronVal || '').trim();
  if (!text) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const fields = text.split(/\s+/);
  if (fields.length !== 5) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const [minF, hourF, domF, monthF, dowF] = fields;
  if (!/^\d+$/.test(minF) || !/^\d+$/.test(hourF)) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const minute = Math.min(59, Math.max(0, parseInt(minF, 10)));
  const hour = Math.min(23, Math.max(0, parseInt(hourF, 10)));

  if (domF === '*' && monthF === '*' && dowF === '*') {
    return { mode: 'daily', hour, minute, weekday: '0', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && dowF === '1-5') {
    return { mode: 'weekdays', hour, minute, weekday: '1', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && (dowF === '0,6' || dowF === '6,0')) {
    return { mode: 'weekend', hour, minute, weekday: '0', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && /^[0-6]$/.test(dowF)) {
    return { mode: 'weekly_once', hour, minute, weekday: dowF, monthday: '1' };
  }
  if (/^\d+$/.test(domF) && monthF === '*' && dowF === '*') {
    const day = Math.min(31, Math.max(1, parseInt(domF, 10)));
    return { mode: 'monthly', hour, minute, weekday: '0', monthday: String(day) };
  }

  return { mode: 'custom', hour, minute, weekday: '0', monthday: '1' };
}

function refreshCronHelperVisibility(mode) {
  const els = getHelperElements();
  if (!els.mode) return;

  if (els.weekdayWrap) {
    els.weekdayWrap.style.display = mode === 'weekly_once' ? 'block' : 'none';
  }
  if (els.monthdayWrap) {
    els.monthdayWrap.style.display = mode === 'monthly' ? 'block' : 'none';
  }
}

function refreshCronHelperSummary() {
  const els = getHelperElements();
  if (!els.mode || !els.summary) return;

  const mode = els.mode.value || 'custom';
  const result = buildCronFromHelper(
    mode,
    els.time ? els.time.value : '03:00',
    els.weekday ? els.weekday.value : '0',
    els.monthday ? els.monthday.value : '1'
  );

  if (mode === 'custom') {
    const currentCron = els.cronInput ? String(els.cronInput.value || '').trim() : '';
    els.summary.textContent = currentCron
      ? `직접 입력 Cron: ${currentCron}`
      : '직접 입력 모드입니다. 아래 Cron 입력칸을 수정하세요.';
    return;
  }

  els.summary.textContent = `${result.summary} | Cron: ${result.cron}`;
}

function hydrateCronHelperFromCron(cronVal) {
  const els = getHelperElements();
  if (!els.mode || !els.time || !els.weekday || !els.monthday) return;

  const parsed = parseHelperStateFromCron(cronVal);
  els.mode.value = parsed.mode;
  els.time.value = `${pad2(parsed.hour)}:${pad2(parsed.minute)}`;
  els.weekday.value = parsed.weekday;
  els.monthday.value = parsed.monthday;

  refreshCronHelperVisibility(parsed.mode);
  refreshCronHelperSummary();
}

export function onCronHelperModeChange() {
  const els = getHelperElements();
  const mode = els.mode ? els.mode.value : 'custom';
  refreshCronHelperVisibility(mode);
  refreshCronHelperSummary();
}
window.onCronHelperModeChange = onCronHelperModeChange;

export function updateCronHelperSummary() {
  refreshCronHelperSummary();
}
window.updateCronHelperSummary = updateCronHelperSummary;

export function applyCronHelperToInput() {
  const els = getHelperElements();
  if (!els.mode || !els.cronInput) return;

  const mode = els.mode.value || 'custom';
  if (mode === 'custom') {
    refreshCronHelperSummary();
    return;
  }

  const result = buildCronFromHelper(
    mode,
    els.time ? els.time.value : '03:00',
    els.weekday ? els.weekday.value : '0',
    els.monthday ? els.monthday.value : '1'
  );
  els.cronInput.value = result.cron;
  refreshCronHelperSummary();
}
window.applyCronHelperToInput = applyCronHelperToInput;

export function showScheduleActionMenu(event, libraryId, name) {
  event.stopPropagation();
  activeLibraryId = libraryId;
  activeLibraryName = name;

  const menu = document.getElementById('schedule-action-context-menu');
  if (!menu) return;

  const lastScannedAt = event.currentTarget?.dataset?.lastScannedAt || '-';

  const lastScanEl = document.getElementById('schedule-action-last-scan');
  if (lastScanEl) {
    lastScanEl.textContent = lastScannedAt || '-';
  }

  // 저장 버튼 이벤트 해제 (모달 세팅이 있으므로 미사용 처리하거나 닫기)
  const saveBtn = document.getElementById('schedule-action-save');
  if (saveBtn) {
    saveBtn.style.display = 'none'; // 액션 메뉴의 저장 옵션은 보이지 않게 처리
  }

  document.getElementById('schedule-action-scan').onclick = () => {
    runLibraryScanNow(activeLibraryId, activeLibraryName, false);
    menu.style.display = 'none';
  };
  document.getElementById('schedule-action-force').onclick = () => {
    runLibraryScanNow(activeLibraryId, activeLibraryName, true);
    menu.style.display = 'none';
  };
  document.getElementById('schedule-action-close').onclick = () => {
    menu.style.display = 'none';
  };

  const rect = event.currentTarget.getBoundingClientRect();
  menu.style.display = 'block';
  
  const menuHeight = menu.offsetHeight || 180;
  const menuWidth = menu.offsetWidth || 200;
  
  let targetY = rect.bottom + window.scrollY;
  let targetX = rect.left + window.scrollX;

  if (rect.bottom + menuHeight > window.innerHeight) {
    targetY = (rect.top - menuHeight) + window.scrollY;
  }
  if (rect.left + menuWidth > window.innerWidth) {
    targetX = (rect.right - menuWidth) + window.scrollX;
  }

  menu.style.left = `${targetX}px`;
  menu.style.top = `${targetY}px`;
}
window.showScheduleActionMenu = showScheduleActionMenu;

// 모달 다이얼로그 제어 함수 추가
export function openScanSettingsModal(libraryId, name, isRemote, rcloneRcUrl, cronSchedule, vfsRefresh) {
  const modal = document.getElementById('library-scan-settings-modal');
  if (!modal) return;

  document.getElementById('scan-settings-library-id').value = libraryId;
  const cronInput = document.getElementById('scan-settings-cron');
  if (cronInput) {
    cronInput.value = cronSchedule;
    cronInput.oninput = () => {
      const modeEl = document.getElementById('scan-settings-helper-mode');
      if (modeEl && modeEl.value === 'custom') {
        refreshCronHelperSummary();
      }
    };
  }
  hydrateCronHelperFromCron(cronSchedule);
  
  document.getElementById('scan-settings-modal-title').innerHTML = `<i class="fa-solid fa-gears" style="color: #a855f7; margin-right: 0.5rem;"></i> [${name}] 스캔 설정`;

  const rcloneContainer = document.getElementById('scan-settings-rclone-container');
  if (isRemote === 1) {
    rcloneContainer.innerHTML = `
      <input type="text" id="scan-settings-rclone" class="form-control" style="width: 100%; box-sizing: border-box; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 0.5rem 0.8rem; border-radius: 6px;" value="${rcloneRcUrl || ''}" placeholder="예: http://localhost:5572">
    `;
  } else {
    rcloneContainer.innerHTML = `
      <span style="font-size: 0.88rem; color: #64748b;"><i class="fa-solid fa-ban"></i> ${i18n.t('settings.not_required_local') || '불필요 (로컬스토리지)'}</span>
    `;
  }

  const vfsContainer = document.getElementById('scan-settings-vfs-container');
  if (isRemote === 1) {
    const checked = vfsRefresh === 1 ? 'checked' : '';
    vfsContainer.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #c084fc; margin-top: 0.5rem;">
        <input type="checkbox" id="scan-settings-vfs-refresh" style="cursor: pointer; accent-color: #a855f7; width: auto;" ${checked}>
        <label for="scan-settings-vfs-refresh" style="cursor: pointer; margin: 0;">${i18n.t('settings.vfs_refresh_before_scan') || '스캔 전 VFS 캐시 새로고침'}</label>
      </div>
    `;
  } else {
    vfsContainer.innerHTML = `
      <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem;">
        <i class="fa-solid fa-hard-drive"></i> ${i18n.t('settings.local_storage') || '로컬 스토리지'}
      </div>
    `;
  }

  modal.style.display = 'flex';
}
window.openScanSettingsModal = openScanSettingsModal;

export function closeScanSettingsModal() {
  const modal = document.getElementById('library-scan-settings-modal');
  if (modal) modal.style.display = 'none';
}
window.closeScanSettingsModal = closeScanSettingsModal;

export async function saveScanSettingsFromModal() {
  const libraryId = document.getElementById('scan-settings-library-id').value;
  const cronVal = document.getElementById('scan-settings-cron').value.trim();
  
  const rcloneRcEl = document.getElementById('scan-settings-rclone');
  const rcloneRcVal = rcloneRcEl ? rcloneRcEl.value.trim() : '';
  
  const vfsRefreshEl = document.getElementById('scan-settings-vfs-refresh');
  const vfsRefresh = vfsRefreshEl && vfsRefreshEl.checked ? 'true' : 'false';

  const success = await saveLibrarySchedule(libraryId, cronVal, vfsRefresh, rcloneRcVal);
  if (success) {
    closeScanSettingsModal();
  }
}
window.saveScanSettingsFromModal = saveScanSettingsFromModal;

// 바깥 클릭 시 메뉴 닫기 핸들러
document.addEventListener('click', (e) => {
  const menu = document.getElementById('schedule-action-context-menu');
  if (menu && !menu.contains(e.target)) {
    menu.style.display = 'none';
  }
});
