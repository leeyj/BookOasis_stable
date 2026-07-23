// reports.js - 스캔 에러 리포트 클라이언트 제어 모듈
import { state } from '../state.js';
import * as api from '../api.js';

let currentReportErrors = [];
let currentReportPage = 1;
const ITEMS_PER_PAGE = 50;

// 스캔 에러 리포트 탭 초기화 및 라이브러리 목록 적재
export async function initReportsTab() {
  console.log('[Reports] initReportsTab() 호출');
  const libSelect = document.getElementById('report-library-select');
  const fileSelect = document.getElementById('report-file-select');
  const tableBody = document.getElementById('report-detail-table-body');
  
  if (!libSelect) return;
  
  libSelect.innerHTML = `<option value="">${window.i18n ? window.i18n.t('settings.report_select_category') : '-- 카테고리 선택 --'}</option>`;
  fileSelect.innerHTML = `<option value="">${window.i18n ? window.i18n.t('settings.report_select_report') : '-- 리포트 선택 --'}</option>`;
  tableBody.innerHTML = `
    <tr>
      <td colspan="3" style="padding: 2rem; text-align: center; color: #94a3b8;">
        <i class="fa-solid fa-info-circle" style="margin-right: 0.3rem;"></i> ${window.i18n ? window.i18n.t('settings.report_empty_message') : '카테고리와 리포트를 선택하여 상세 오류 내역을 확인하십시오.'}
      </td>
    </tr>
  `;
  
  try {
    loadScanHistory();
    const res = await api.fetchLibraries(state.currentLibraryType || 'general');
    if (res.success && res.libraries) {
      res.libraries.forEach(lib => {
        const option = document.createElement('option');
        option.value = lib.id;
        option.textContent = lib.name;
        libSelect.appendChild(option);
      });
    }
  } catch (err) {
    console.error('[Reports] 라이브러리 목록 로드 실패:', err);
  }
}

// 스캔 히스토리 이력 (최대 20건, 레이지스캔 제외) 비동기 로딩 및 렌더링
export async function loadScanHistory() {
  const tbody = document.getElementById('scan-history-table-body');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="6" style="padding: 2rem; text-align: center; color: #94a3b8;">
        <i class="fa-solid fa-circle-notch fa-spin" style="margin-right: 0.3rem; color: #a855f7;"></i> 최근 스캔 이력을 불러오는 중...
      </td>
    </tr>
  `;

  try {
    const res = await fetch('/api/media/scan-history');
    const data = await res.json();

    if (!data.success || !Array.isArray(data.history) || data.history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="padding: 2rem; text-align: center; color: #94a3b8;">
            <i class="fa-solid fa-info-circle" style="margin-right: 0.3rem;"></i> 최근 기록된 스캔 작업 이력이 없습니다.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = data.history.map(item => {
      const isCron = item.trigger_type === 'cron';
      const triggerBadge = isCron
        ? `<span style="display: inline-block; padding: 0.2rem 0.5rem; background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 4px; font-size: 0.75rem; font-weight: 600;">크론 자동</span>`
        : `<span style="display: inline-block; padding: 0.2rem 0.5rem; background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 4px; font-size: 0.75rem; font-weight: 600;">수동 실행</span>`;

      let statusBadge = `<span style="color: #94a3b8;">대기</span>`;
      if (item.status === 'completed') {
        statusBadge = `<span style="color: #4ade80; font-weight: 600;"><i class="fa-solid fa-circle-check"></i> 완료</span>`;
      } else if (item.status === 'running') {
        statusBadge = `<span style="color: #38bdf8; font-weight: 600;"><i class="fa-solid fa-circle-notch fa-spin"></i> 스캔중</span>`;
      } else if (item.status === 'failed') {
        statusBadge = `<span style="color: #f87171; font-weight: 600;"><i class="fa-solid fa-triangle-exclamation"></i> 실패</span>`;
      }

      const startedAt = item.started_at || item.enqueue_at || '-';
      const finishedAt = item.finished_at || (item.status === 'running' ? '진행 중...' : '-');
      const relativeTime = item.time_ago || '-';

      return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); hover: background: rgba(255,255,255,0.02);">
          <td style="padding: 0.8rem 1rem; font-weight: 600; color: #f8fafc;">${item.library_name}</td>
          <td style="padding: 0.8rem 1rem; text-align: center; color: #a855f7; font-weight: 600; font-size: 0.82rem;">${relativeTime}</td>
          <td style="padding: 0.8rem 1rem; text-align: center; color: #94a3b8; font-family: monospace; font-size: 0.8rem;">${startedAt}</td>
          <td style="padding: 0.8rem 1rem; text-align: center; color: #94a3b8; font-family: monospace; font-size: 0.8rem;">${finishedAt}</td>
          <td style="padding: 0.8rem 1rem; text-align: center;">${triggerBadge}</td>
          <td style="padding: 0.8rem 1rem; text-align: center; font-size: 0.8rem;">${statusBadge}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('[Reports] 스캔 히스토리 로드 실패:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="padding: 2rem; text-align: center; color: #ef4444;">
          스캔 이력을 불러오는 도중 오류가 발생했습니다.
        </td>
      </tr>
    `;
  }
}
window.loadScanHistory = loadScanHistory;

// 라이브러리 선택 변경 시 리포트 파일 리스트 적재
export async function loadReportList() {
  const libSelect = document.getElementById('report-library-select');
  const fileSelect = document.getElementById('report-file-select');
  const tableBody = document.getElementById('report-detail-table-body');
  
  if (!libSelect || !fileSelect) return;
  
  const libraryId = libSelect.value;
  fileSelect.innerHTML = `<option value="">${window.i18n ? window.i18n.t('settings.report_select_report') : '-- 리포트 선택 --'}</option>`;
  tableBody.innerHTML = `
    <tr>
      <td colspan="3" style="padding: 2rem; text-align: center; color: #94a3b8;">
        <i class="fa-solid fa-info-circle" style="margin-right: 0.3rem;"></i> ${window.i18n ? window.i18n.t('settings.report_empty_message') : '리포트를 선택하여 상세 오류 내역을 확인하십시오.'}
      </td>
    </tr>
  `;
  
  if (!libraryId) return;
  
  try {
    const res = await api.fetchScanReports(libraryId);
    if (res.success && res.reports) {
      if (res.reports.length === 0) {
        fileSelect.innerHTML = '<option value="">-- 리포트 없음 --</option>';
        tableBody.innerHTML = `
          <tr>
            <td colspan="3" style="padding: 2rem; text-align: center; color: #4ade80; font-weight: 600;">
              <i class="fa-solid fa-circle-check" style="margin-right: 0.3rem;"></i> 해당 카테고리에는 감지된 스캔 오류 내역이 없습니다. (정상)
            </td>
          </tr>
        `;
        return;
      }
      
      res.reports.forEach(rep => {
        const option = document.createElement('option');
        option.value = rep.filename;
        option.textContent = `${rep.timestamp} (오류: ${rep.errors_count}건)`;
        fileSelect.appendChild(option);
      });
      
      // 첫 번째 리포트 자동 로드
      fileSelect.selectedIndex = 1;
      loadReportDetail();
    }
  } catch (err) {
    console.error('[Reports] 리포트 목록 로드 실패:', err);
  }
}

// 특정 리포트 파일 로딩 및 에러 상세 렌더링
export async function loadReportDetail() {
  const fileSelect = document.getElementById('report-file-select');
  const tableBody = document.getElementById('report-detail-table-body');
  
  if (!fileSelect || !tableBody) return;
  
  const filename = fileSelect.value;
  if (!filename) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="3" style="padding: 2rem; text-align: center; color: #94a3b8;">
          <i class="fa-solid fa-info-circle" style="margin-right: 0.3rem;"></i> 리포트를 선택하여 상세 오류 내역을 확인하십시오.
        </td>
      </tr>
    `;
    return;
  }
  
  tableBody.innerHTML = `
    <tr>
      <td colspan="3" style="padding: 2rem; text-align: center; color: #a855f7;">
        <i class="fa-solid fa-circle-notch fa-spin fa-lg" style="margin-right: 0.3rem;"></i> 리포트 상세 로딩 중...
      </td>
    </tr>
  `;
  
  try {
    const res = await api.fetchReportDetail(filename);
    if (res.success && res.report && res.report.errors) {
      const errors = res.report.errors;
      if (errors.length === 0) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="3" style="padding: 2rem; text-align: center; color: #4ade80; font-weight: 600;">
              <i class="fa-solid fa-circle-check" style="margin-right: 0.3rem;"></i> 감지된 오류 내역이 비어 있습니다.
            </td>
          </tr>
        `;
        document.getElementById('report-pagination-container').innerHTML = '';
        return;
      }
      
      currentReportErrors = errors;
      currentReportPage = 1;
      renderReportPage();
    } else {
      tableBody.innerHTML = `
        <tr>
          <td colspan="3" style="padding: 2rem; text-align: center; color: #ef4444; font-weight: 600;">
            <i class="fa-solid fa-triangle-exclamation" style="margin-right: 0.3rem;"></i> 리포트 세부 데이터 구조가 올바르지 않습니다.
          </td>
        </tr>
      `;
    }
  } catch (err) {
    console.error('[Reports] 리포트 상세 로드 실패:', err);
    tableBody.innerHTML = `
      <tr>
        <td colspan="3" style="padding: 2rem; text-align: center; color: #ef4444; font-weight: 600;">
          <i class="fa-solid fa-triangle-exclamation" style="margin-right: 0.3rem;"></i> 리포트 상세 데이터를 불러오지 못했습니다.
        </td>
      </tr>
    `;
  }
}

function renderReportPage() {
  const tableBody = document.getElementById('report-detail-table-body');
  const paginationContainer = document.getElementById('report-pagination-container');
  
  if (!tableBody) return;
  if (currentReportErrors.length === 0) {
    if (paginationContainer) paginationContainer.innerHTML = '';
    return;
  }
  
  const totalItems = currentReportErrors.length;
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE) || 1;
  
  if (currentReportPage > totalPages) currentReportPage = totalPages;
  if (currentReportPage < 1) currentReportPage = 1;
  
  const startIndex = (currentReportPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalItems);
  const pageErrors = currentReportErrors.slice(startIndex, endIndex);
  
  let html = '';
  pageErrors.forEach(err => {
    let typeBadgeColor = 'rgba(148, 163, 184, 0.15)';
    let typeTextColor = '#94a3b8';
    
    if (err.error_type === 'BadZipFile') {
      typeBadgeColor = 'rgba(239, 68, 68, 0.15)';
      typeTextColor = '#f87171';
    } else if (err.error_type === 'NoCover') {
      typeBadgeColor = 'rgba(234, 179, 8, 0.15)';
      typeTextColor = '#facc15';
    } else if (err.error_type === 'OffsetError') {
      typeBadgeColor = 'rgba(59, 130, 246, 0.15)';
      typeTextColor = '#60a5fa';
    }
    
    let msg = err.message || '';
    if (window.i18n) {
      if (msg === 'ERR_NO_COVER' || msg === '도서 내 표지 이미지가 존재하지 않거나 추출 결과가 0바이트(빈 파일)입니다.') {
        msg = window.i18n.t('scan_errors.ERR_NO_COVER') || msg;
      } else if (msg.startsWith('ERR_OFFSET_FAIL: ')) {
        msg = (window.i18n.t('scan_errors.ERR_OFFSET_FAIL') || 'Offset analysis failed') + ': ' + msg.substring(17);
      } else if (msg.startsWith('오프셋 분석 실패: ')) {
        msg = (window.i18n.t('scan_errors.ERR_OFFSET_FAIL') || 'Offset analysis failed') + ': ' + msg.substring(10);
      } else if (msg.startsWith('ERR_LAZY_COVER_FAIL: ')) {
        msg = (window.i18n.t('scan_errors.ERR_LAZY_COVER_FAIL') || 'Cover restore failed') + ': ' + msg.substring(21);
      } else if (msg.startsWith('Lazy 스캔 중 표지 복원 실패: ')) {
        msg = (window.i18n.t('scan_errors.ERR_LAZY_COVER_FAIL') || 'Cover restore failed') + ': ' + msg.substring(18);
      }
    }

    html += `
      <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">
        <td style="padding: 0.8rem 1rem; color: #f1f5f9; font-weight: 600; word-break: break-all;">${err.filename || ''}</td>
        <td style="padding: 0.8rem 1rem; text-align: center; vertical-align: middle;">
          <span style="background: ${typeBadgeColor}; color: ${typeTextColor}; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; border: 1px solid ${typeTextColor}33;">
            ${err.error_type || 'Unknown'}
          </span>
        </td>
        <td style="padding: 0.8rem 1rem; color: #94a3b8; font-size: 0.82rem; line-height: 1.4; word-break: break-all;">
          <div style="color: #cbd5e1; margin-bottom: 0.2rem; font-weight: 500;">${msg}</div>
          <div style="font-size: 0.74rem; opacity: 0.6; color: #64748b;"><i class="fa-regular fa-folder" style="margin-right: 0.2rem;"></i>${err.file_path || ''}</div>
        </td>
      </tr>
    `;
  });
  tableBody.innerHTML = html;
  
  if (paginationContainer) {
    let paginationHtml = '';
    
    if (currentReportPage > 1) {
      paginationHtml += `<button onclick="window.changeReportPage(${currentReportPage - 1})" class="btn-toggle" style="padding: 0.4rem 0.8rem; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); color: #cbd5e1; border-radius: 4px; cursor: pointer;">이전</button>`;
    }
    
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentReportPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    
    if (endPage - startPage + 1 < maxPagesToShow) {
      startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
      const isActive = i === currentReportPage 
        ? 'background: #a855f7; color: #fff; border: 1px solid #a855f7;' 
        : 'background: rgba(30, 41, 59, 0.6); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1);';
      paginationHtml += `<button onclick="window.changeReportPage(${i})" class="btn-toggle" style="padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; ${isActive}">${i}</button>`;
    }
    
    if (currentReportPage < totalPages) {
      paginationHtml += `<button onclick="window.changeReportPage(${currentReportPage + 1})" class="btn-toggle" style="padding: 0.4rem 0.8rem; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); color: #cbd5e1; border-radius: 4px; cursor: pointer;">다음</button>`;
    }
    
    paginationContainer.innerHTML = paginationHtml;
  }
}

window.changeReportPage = function(page) {
  currentReportPage = page;
  renderReportPage();
};
