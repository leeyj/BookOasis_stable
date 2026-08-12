// scheduler.js – 라이브러리 스케줄 목록 로딩 및 관리 UI 전용 모듈
import { state } from './state.js';
import * as api from './api.js';
import { bindFloatingMenuOutsideClose, hideFloatingMenu, positionMenuAtElement } from './context_menu_manager.js';
import { hydrateCronHelperFromCron, onCronHelperModeChange, updateCronHelperSummary, applyCronHelperToInput } from './cron_helper.js';

function buildStatusBadge(scanStatus) {
  if (scanStatus === 'scanning') {
    return `<span class="badge-scan-status scanning"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('settings.status_scanning')}</span>`;
  }
  if (scanStatus === 'failed') {
    return `<span class="badge-scan-status failed">${i18n.t('settings.status_failed')}</span>`;
  }
  return `<span class="badge-scan-status ready">${i18n.t('settings.status_ready')}</span>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function parseScanDate(value) {
  const raw = String(value || '').trim();
  if (!raw || raw === '-') return null;

  // 서버가 타임존 정보 없이 "YYYY-MM-DD HH:mm:ss" 형태의 로컬 시각을 보내는 경우,
  // new Date()에 그대로 넘기면 브라우저/엔진에 따라 UTC로 해석되어 KST 기준 9시간 오차가 발생할 수 있다.
  // 연-월-일-시-분-초 컴포넌트를 직접 읽어 항상 "로컬 시각"으로 고정 생성해 이 모호함을 없앤다.
  const naiveMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/);
  if (naiveMatch) {
    const [, y, mo, d, h, mi, s] = naiveMatch.map(Number);
    const local = new Date(y, mo - 1, d, h, mi, s);
    return Number.isNaN(local.getTime()) ? null : local;
  }

  // Z 또는 +09:00 같은 타임존 오프셋이 명시된 표준 ISO 문자열은 그대로 위임
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatLastScan(value) {
  const scannedAt = parseScanDate(value);
  if (!scannedAt) {
    return {
      relative: i18n.t('settings.scan_never') || '기록 없음',
      exact: i18n.t('settings.scan_never') || '기록 없음'
    };
  }

  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - scannedAt.getTime()) / 60000));
  let relative;
  if (elapsedMinutes < 1) {
    relative = i18n.t('settings.scan_just_now') || '방금 전';
  } else if (elapsedMinutes < 60) {
    relative = i18n.t('settings.scan_minutes_ago', {count: elapsedMinutes});
  } else if (elapsedMinutes < 1440) {
    relative = i18n.t('settings.scan_hours_ago', {count: Math.floor(elapsedMinutes / 60)});
  } else {
    relative = i18n.t('settings.scan_days_ago', {count: Math.floor(elapsedMinutes / 1440)});
  }

  const pad = value => String(value).padStart(2, '0');
  const exact = `${pad(scannedAt.getMonth() + 1)}.${pad(scannedAt.getDate())} ${pad(scannedAt.getHours())}:${pad(scannedAt.getMinutes())}`;
  return {relative, exact};
}

function compactPath(path) {
  const normalized = String(path || '').replace(/\\/g, '/');
  const segments = normalized.split('/').filter(Boolean);
  if (segments.length <= 3) return normalized;
  return `…/${segments.slice(-3).join('/')}`;
}

function buildCompactPaths(physicalPath) {
  return String(physicalPath || '').split(/\r?\n/).filter(Boolean).map(path => {
    const fullPath = escapeHtml(path.trim());
    const shortPath = escapeHtml(compactPath(path.trim()));
    return `<button type="button" class="schedule-path-toggle" data-role="schedule-path-toggle" data-expanded="false" data-short-path="${shortPath}" data-full-path="${fullPath}" title="${fullPath}">${shortPath}</button>`;
  }).join('');
}

function buildLastScanInfo(lastScannedAt, cronSchedule = '') {
  const scanInfo = formatLastScan(lastScannedAt);
  const hasSchedule = String(cronSchedule || '').trim().length > 0;
  const scheduleLabel = hasSchedule
    ? i18n.t('settings.scan_schedule_enabled')
    : i18n.t('settings.scan_schedule_disabled');
  const tooltip = `${scheduleLabel} · ${scanInfo.exact}`;
  return `<span class="schedule-scan-info" title="${escapeHtml(tooltip)}" aria-label="${escapeHtml(tooltip)}"><span class="schedule-cron-dot ${hasSchedule ? 'enabled' : 'disabled'}" aria-hidden="true"></span><span class="schedule-scan-time">${escapeHtml(scanInfo.relative)}</span></span>`;
}

function buildScheduleRow(lib) {
  const statusBadge = buildStatusBadge(lib.scan_status);
  const cleanName = lib.name.replace(/'/g, "\\'");
  const cleanRcloneRcUrl = (lib.rclone_rc_url || '').replace(/'/g, "\\'");
  const cleanCronSchedule = (lib.cron_schedule || '').replace(/'/g, "\\'");
  const safeNameAttr = escapeHtml(lib.name || '');
  const safeRcloneRcUrlAttr = escapeHtml(lib.rclone_rc_url || '');
  const safeCronScheduleAttr = escapeHtml(lib.cron_schedule || '');
  const lastScannedAt = lib.last_scanned_at || '-';

  return `
    <tr data-library-id="${lib.id}" style="border-bottom: 1px solid rgba(255,255,255,0.05); hover: background: rgba(255,255,255,0.02);">
      <td style="padding: 1rem; font-weight: 600; color: #fff;">${lib.name}</td>
      <td class="schedule-path-cell">${buildCompactPaths(lib.physical_path)}</td>
      <td data-role="schedule-status" style="padding: 1rem; text-align: center;">${statusBadge}</td>
      <td data-role="schedule-scan-info" style="padding: 1rem; text-align: center;">${buildLastScanInfo(lastScannedAt, lib.cron_schedule)}</td>
      <td style="padding: 1rem; text-align: center;">
        <button class="btn-toggle" data-role="schedule-config" data-library-id="${lib.id}" data-library-name="${safeNameAttr}" data-is-remote="${lib.is_remote || 0}" data-rclone-rc-url="${safeRcloneRcUrlAttr}" data-cron-schedule="${safeCronScheduleAttr}" data-vfs-refresh="${lib.vfs_refresh_before_scan || 0}" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" title="상세 설정">
          <i class="fa-solid fa-gear"></i> ${i18n.t('settings.col_config') || '설정'}
        </button>
      </td>
      <td style="padding: 1rem; text-align: center;">
        <button class="btn-toggle active" data-role="schedule-action" data-library-id="${lib.id}" data-library-name="${escapeHtml(lib.name)}" data-last-scanned-at="${lastScannedAt}" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" title="작업 메뉴 열기">
          ${i18n.t('settings.col_action') || '작업'} <i class="fa-solid fa-chevron-down" style="font-size: 0.65rem;"></i>
        </button>
      </td>
    </tr>
  `;
}

function initScheduleActionDelegation() {
  if (window.__scheduleActionDelegationBound) return;

  document.addEventListener('click', (event) => {
    const configBtn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('button[data-role="schedule-config"]')
      : null;
    if (configBtn) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') {
        event.stopImmediatePropagation();
      }

      const libraryId = Number.parseInt(configBtn.dataset.libraryId || '', 10);
      if (!Number.isFinite(libraryId) || libraryId <= 0) return;
      openScanSettingsModal(
        libraryId,
        String(configBtn.dataset.libraryName || '').trim(),
        Number.parseInt(configBtn.dataset.isRemote || '0', 10) || 0,
        String(configBtn.dataset.rcloneRcUrl || ''),
        String(configBtn.dataset.cronSchedule || ''),
        Number.parseInt(configBtn.dataset.vfsRefresh || '0', 10) || 0
      );
      return;
    }

    const btn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('button[data-role="schedule-action"]')
      : null;
    if (btn) {
      event.preventDefault();
      event.stopPropagation();
      if (typeof event.stopImmediatePropagation === 'function') {
        event.stopImmediatePropagation();
      }

      const libraryId = Number.parseInt(btn.dataset.libraryId || '', 10);
      const libraryName = String(btn.dataset.libraryName || '').trim();
      if (!Number.isFinite(libraryId) || libraryId <= 0) return;

      showScheduleActionMenuFromButton(btn, libraryId, libraryName);
      return;
    }

    const pathBtn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="schedule-path-toggle"]')
      : null;
    if (pathBtn) {
      event.preventDefault();
      toggleSchedulePath(pathBtn);
      return;
    }

    const staticAction = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="schedule-scan-all"], [data-role="schedule-apply-helper"], [data-role="schedule-modal-close"], [data-role="schedule-modal-save"]')
      : null;
    if (!staticAction) return;

    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === 'function') {
      event.stopImmediatePropagation();
    }

    const actionRole = staticAction.getAttribute('data-role');
    if (actionRole === 'schedule-scan-all') {
      runAllLibrariesScanNow(false);
      return;
    }
    if (actionRole === 'schedule-apply-helper') {
      applyCronHelperToInput();
      return;
    }
    if (actionRole === 'schedule-modal-close') {
      closeScanSettingsModal();
      return;
    }
    if (actionRole === 'schedule-modal-save') {
      saveScanSettingsFromModal();
    }
  }, true);

  document.addEventListener('change', (event) => {
    const target = event && event.target;
    if (!target || !(target.matches instanceof Function)) return;

    if (target.matches('[data-role="schedule-helper-mode"]')) {
      onCronHelperModeChange();
      return;
    }
    if (target.matches('[data-role="schedule-helper-weekday"]')) {
      updateCronHelperSummary();
    }
  }, true);

  document.addEventListener('input', (event) => {
    const target = event && event.target;
    if (!target || !(target.matches instanceof Function)) return;

    if (target.matches('[data-role="schedule-helper-time"], [data-role="schedule-helper-monthday"]')) {
      updateCronHelperSummary();
    }
  }, true);

  window.__scheduleActionDelegationBound = true;

  bindFloatingMenuOutsideClose('schedule-action-context-menu', {
    eventTypes: ['click'],
    capture: true,
  });
}

// 환경설정 (스케줄 관리) 리스트 로드 및 렌더링
export async function loadLibrarySchedules() {
  initScheduleActionDelegation();
  const container = document.getElementById('settings-libraries-list');
  if (!container) return;
  container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:#a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><span style="display:inline-block; margin-top:0.5rem;">${i18n.t('settings.loading_schedules')}</span></td></tr>`;
  
  try {
    const data = await api.fetchLibrarySchedules(state.currentLibraryType);
    if (data.success) {
      if (data.libraries.length === 0) {
        container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:#94a3b8;">${i18n.t('settings.no_categories')}</td></tr>`;
        return;
      }

      container.innerHTML = data.libraries.map(buildScheduleRow).join('');
    } else {
      container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.fetch_failed')}: ${data.error}</td></tr>`;
    }
  } catch (e) {
    console.error('스케줄 조회 에러:', e);
    container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.server_error')}</td></tr>`;
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

      const scanInfoCell = row.querySelector('[data-role="schedule-scan-info"]');
      const nextScanInfoHtml = buildLastScanInfo(lib.last_scanned_at || '-', lib.cron_schedule);
      if (scanInfoCell && scanInfoCell.innerHTML !== nextScanInfoHtml) {
        scanInfoCell.innerHTML = nextScanInfoHtml;
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

export function toggleSchedulePath(button) {
  const expanded = button.dataset.expanded === 'true';
  button.dataset.expanded = String(!expanded);
  button.textContent = expanded ? button.dataset.shortPath : button.dataset.fullPath;
}
window.toggleSchedulePath = toggleSchedulePath;

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

export function showScheduleActionMenu(event, libraryId, name) {
  const evt = event || window.event;
  if (evt && typeof evt.stopPropagation === 'function') {
    evt.stopPropagation();
  }

  const anchor = evt && evt.currentTarget ? evt.currentTarget : null;
  if (!anchor) return;
  showScheduleActionMenuFromButton(anchor, libraryId, name);
}

export function showScheduleActionMenuFromButton(anchorEl, libraryId, name) {
  if (!anchorEl) return;

  if (typeof anchorEl.blur === 'function') {
    // 모바일/터치 환경에서 포커스 잔상으로 재클릭이 씹히는 케이스를 줄인다.
    anchorEl.blur();
  }

  activeLibraryId = libraryId;
  activeLibraryName = name;

  const menu = document.getElementById('schedule-action-context-menu');
  if (!menu) return;

  const lastScannedAt = anchorEl.dataset?.lastScannedAt || '-';

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
    hideFloatingMenu(menu);
  };
  document.getElementById('schedule-action-force').onclick = () => {
    runLibraryScanNow(activeLibraryId, activeLibraryName, true);
    hideFloatingMenu(menu);
  };
  document.getElementById('schedule-action-close').onclick = () => {
    hideFloatingMenu(menu);
  };

  positionMenuAtElement(menu, anchorEl, { zIndex: 20070 });
}
window.showScheduleActionMenuFromButton = showScheduleActionMenuFromButton;
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
        updateCronHelperSummary();
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

