// scheduler.js – 라이브러리 스케줄 목록 로딩 및 관리 UI 전용 모듈
import { state } from './state.js';
import * as api from './api.js';

// 환경설정 (스케줄 관리) 리스트 로드 및 렌더링
export async function loadLibrarySchedules() {
  const container = document.getElementById('settings-libraries-list');
  if (!container) return;
  container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:#a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><span style="display:inline-block; margin-top:0.5rem;">${i18n.t('settings.loading_schedules')}</span></td></tr>`;
  
  try {
    const data = await api.fetchLibrarySchedules(state.currentLibraryType);
    if (data.success) {
      if (data.libraries.length === 0) {
        container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:#94a3b8;">${i18n.t('settings.no_categories')}</td></tr>`;
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
        
        let vfsCheckbox = '';
        let rcloneRcInputHtml = '';
        if (lib.is_remote === 1) {
          const checked = lib.vfs_refresh_before_scan === 1 ? 'checked' : '';
          vfsCheckbox = `
            <div style="margin-top: 0.35rem; display: flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; color: #c084fc;">
              <input type="checkbox" id="vfs-refresh-${lib.id}" style="cursor: pointer; accent-color: #a855f7; width: auto;" ${checked}>
              <label for="vfs-refresh-${lib.id}" style="cursor: pointer; margin: 0;">${i18n.t('settings.vfs_refresh_before_scan')}</label>
            </div>
          `;
          rcloneRcInputHtml = `
            <input type="text" id="rclone-rc-${lib.id}" class="form-control input-sm" style="width: 100%; max-width: 220px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 0.35rem 0.6rem; border-radius: 4px;" value="${lib.rclone_rc_url || ''}" placeholder="예: http://localhost:5572">
          `;
        } else {
          vfsCheckbox = `
            <div style="margin-top: 0.35rem; font-size: 0.75rem; color: #64748b;">
              <i class="fa-solid fa-hard-drive"></i> ${i18n.t('settings.local_storage')}
            </div>
          `;
          rcloneRcInputHtml = `
            <span style="font-size: 0.78rem; color: #64748b;"><i class="fa-solid fa-ban"></i> ${i18n.t('settings.not_required_local')}</span>
          `;
        }
 
        html += `
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); hover: background: rgba(255,255,255,0.02);">
            <td style="padding: 1rem; font-weight: 600; color: #fff;">${lib.name}</td>
            <td style="padding: 1rem; color: #94a3b8; font-family: monospace; font-size: 0.8rem;">${lib.physical_path}</td>
            <td style="padding: 1rem; text-align: left;">
              ${rcloneRcInputHtml}
            </td>
            <td style="padding: 1rem;">
              <input type="text" id="cron-${lib.id}" class="form-control input-sm" style="width: 100%; max-width: 180px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 0.35rem 0.6rem; border-radius: 4px;" value="${lib.cron_schedule || ''}" placeholder="예: 0 3 * * *">
              ${vfsCheckbox}
            </td>
            <td style="padding: 1rem; color: #94a3b8;">${lib.last_scanned_at || '-'}</td>
            <td style="padding: 1rem; text-align: center;">${statusBadge}</td>
            <td style="padding: 1rem; text-align: center;">
              <div style="display: flex; gap: 0.3rem; justify-content: center;">
                <button class="btn-toggle active" style="white-space: nowrap; padding: 0.3rem 0.5rem; font-size: 0.75rem; border-radius: 4px;" onclick="saveLibrarySchedule(${lib.id}, '${lib.name.replace(/'/g, "\\'")}')" title="설정 저장"><i class="fa-regular fa-floppy-disk"></i> ${i18n.t('common.save')}</button>
                <button class="btn-toggle" style="white-space: nowrap; padding: 0.3rem 0.5rem; font-size: 0.75rem; border-radius: 4px; background: #a855f7; border-color: #a855f7; color: #fff;" onclick="runLibraryScanNow(${lib.id}, '${lib.name.replace(/'/g, "\\'")}', false)" title="변경된 파일만 점진적 스캔"><i class="fa-solid fa-play"></i> ${i18n.t('settings.btn_scan')}</button>
                <button class="btn-toggle" style="white-space: nowrap; padding: 0.3rem 0.5rem; font-size: 0.75rem; border-radius: 4px; background: #ea580c; border-color: #ea580c; color: #fff;" onclick="runLibraryScanNow(${lib.id}, '${lib.name.replace(/'/g, "\\'")}', true)" title="모든 파일의 메타데이터와 오프셋을 강제로 전체 재색인"><i class="fa-solid fa-arrows-rotate"></i> ${i18n.t('settings.btn_force_scan')}</button>
              </div>
            </td>
          </tr>
        `;
      });
      container.innerHTML = html;
    } else {
      container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.fetch_failed')}: ${data.error}</td></tr>`;
    }
  } catch (e) {
    console.error('스케줄 조회 에러:', e);
    container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:#ef4444;">${i18n.t('settings.server_error')}</td></tr>`;
  }
}

// 스케줄 저장
export async function saveLibrarySchedule(libraryId, name) {
  const inputEl = document.getElementById(`cron-${libraryId}`);
  if (!inputEl) return;
  const cronVal = inputEl.value.trim();
  
  const vfsRefreshEl = document.getElementById(`vfs-refresh-${libraryId}`);
  const vfsRefresh = vfsRefreshEl && vfsRefreshEl.checked ? 'true' : 'false';
  
  const rcloneRcEl = document.getElementById(`rclone-rc-${libraryId}`);
  const rcloneRcVal = rcloneRcEl ? rcloneRcEl.value.trim() : '';
  
  try {
    const data = await api.updateLibrarySchedule(state.currentLibraryType, libraryId, cronVal, vfsRefresh, rcloneRcVal);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('scheduler.save_success', {name: name}), 'success');
      } else {
        alert(i18n.t('scheduler.save_done'));
      }
      loadLibrarySchedules();
    } else {
      alert(i18n.t('scheduler.save_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('스케줄 변경 API 요청 에러:', e);
    alert(i18n.t('scheduler.server_error'));
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
