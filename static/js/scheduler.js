// scheduler.js – 라이브러리 스케줄 목록 로딩 및 관리 UI 전용 모듈
import { state } from './state.js';
import * as api from './api.js';

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
      
      let html = '';
      data.libraries.forEach(lib => {
        let statusBadge = '';
        if (lib.scan_status === 'scanning') {
          statusBadge = `<span class="badge-scan-status scanning"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('settings.status_scanning')}</span>`;
        } else if (lib.scan_status === 'failed') {
          statusBadge = `<span class="badge-scan-status failed">${i18n.t('settings.status_failed')}</span>`;
        } else {
          statusBadge = `<span class="badge-scan-status ready">${i18n.t('settings.status_ready')}</span>`;
        }
        
        const cleanName = lib.name.replace(/'/g, "\\'");
        const cleanRcloneRcUrl = (lib.rclone_rc_url || '').replace(/'/g, "\\'");
        const cleanCronSchedule = (lib.cron_schedule || '').replace(/'/g, "\\'");

        html += `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); hover: background: rgba(255,255,255,0.02);">
            <td style="padding: 1rem; font-weight: 600; color: #fff;">${lib.name}</td>
            <td style="padding: 1rem; color: #94a3b8; font-family: monospace; font-size: 0.8rem; white-space: pre-line;">${lib.physical_path}</td>
            <td style="padding: 1rem; text-align: center;">${statusBadge}</td>
            <td style="padding: 1rem; text-align: center;">
              <button class="btn-toggle" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" onclick="openScanSettingsModal(${lib.id}, '${cleanName}', ${lib.is_remote}, '${cleanRcloneRcUrl}', '${cleanCronSchedule}', ${lib.vfs_refresh_before_scan || 0})" title="상세 설정">
                <i class="fa-solid fa-gear"></i> ${i18n.t('settings.col_config') || '설정'}
              </button>
            </td>
            <td style="padding: 1rem; text-align: center;">
              <button class="btn-toggle active" style="white-space: nowrap; padding: 0.3rem 0.6rem; font-size: 0.75rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.2rem;" onclick="showScheduleActionMenu(event, ${lib.id}, '${cleanName}', '${lib.last_scanned_at || '-'}')" title="작업 메뉴 열기">
                ${i18n.t('settings.col_action') || '작업'} <i class="fa-solid fa-chevron-down" style="font-size: 0.65rem;"></i>
              </button>
            </td>
          </tr>
        `;
      });
      container.innerHTML = html;
    } else {
      container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.fetch_failed')}: ${data.error}</td></tr>`;
    }
  } catch (e) {
    console.error('스케줄 조회 에러:', e);
    container.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.server_error')}</td></tr>`;
  }
}

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

export function showScheduleActionMenu(event, libraryId, name, lastScannedAt) {
  event.stopPropagation();
  activeLibraryId = libraryId;
  activeLibraryName = name;

  const menu = document.getElementById('schedule-action-context-menu');
  if (!menu) return;

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
  document.getElementById('scan-settings-cron').value = cronSchedule;
  
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
