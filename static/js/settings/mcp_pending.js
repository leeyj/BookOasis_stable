// settings/mcp_pending.js - MCP Tier B(대량/파괴적 작업) "제안 → 관리자 승인" 큐 UI
import { escapeHtml } from '../utils/html.js';

function t(key, variables, fallback) {
  return window.i18n ? window.i18n.t(key, variables || {}, fallback) : (fallback || key);
}

function initMcpPendingDelegation() {
  if (window.__mcpPendingDelegationBound) return;

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="mcp-pending-refresh"], [data-role="mcp-approve"], [data-role="mcp-reject"]')
      : null;
    if (!target) return;

    event.preventDefault();
    const role = target.getAttribute('data-role');

    if (role === 'mcp-pending-refresh') {
      loadMcpPendingChanges();
      return;
    }

    const changeId = Number.parseInt(target.getAttribute('data-change-id') || '', 10);
    if (!Number.isFinite(changeId) || changeId <= 0) return;

    if (role === 'mcp-approve') {
      approveMcpChange(changeId);
    } else if (role === 'mcp-reject') {
      rejectMcpChange(changeId);
    }
  }, true);

  window.__mcpPendingDelegationBound = true;
}

export async function loadMcpPendingChanges() {
  initMcpPendingDelegation();
  const tbody = document.getElementById('mcp-pending-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/admin/mcp-pending-changes?status=pending');
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'unknown error');
    renderMcpPendingTable(data.changes || []);
  } catch (err) {
    console.error('[MCP-Pending] 목록 로드 실패:', err);
    tbody.innerHTML = `<tr><td colspan="6" style="padding: 2rem; text-align: center; color: #ef4444;"><i class="lc lc-triangle-alert"></i> ${escapeHtml(t('mcp_pending.load_error', null, '대기 목록을 불러오지 못했습니다.'))}</td></tr>`;
  }
}
window.loadMcpPendingChanges = loadMcpPendingChanges;

function formatPreview(toolName, preview) {
  if (!preview) return '-';
  const emptyValueLabel = t('mcp_pending.empty_value', null, '(빈값)');

  if (toolName === 'bulk_update_book_metadata') {
    const rows = Object.entries(preview).slice(0, 5).map(([seriesName, fields]) => {
      const fieldSummary = Object.entries(fields).map(([field, diff]) =>
        `<div style="margin-top:0.2rem;"><b>${escapeHtml(field)}</b>: <span style="color:#f87171; text-decoration: line-through;">${escapeHtml(diff.before || emptyValueLabel)}</span> → <span style="color:#4ade80;">${escapeHtml(diff.after || emptyValueLabel)}</span></div>`
      ).join('');
      return `<div style="margin-bottom:0.5rem;"><b>${escapeHtml(seriesName)}</b>${fieldSummary}</div>`;
    }).join('');
    const remaining = Object.keys(preview).length - 5;
    return rows + (remaining > 0 ? `<div style="color: var(--app-text-muted);">${escapeHtml(t('mcp_pending.preview_more', { count: remaining }, `... 외 ${remaining}건 더`))}</div>` : '');
  }

  if (toolName === 'bulk_set_favorite') {
    const count = preview.book_count || 0;
    return escapeHtml(preview.is_favorite
      ? t('mcp_pending.preview_favorite_on', { count }, `${count}권을 즐겨찾기 등록`)
      : t('mcp_pending.preview_favorite_off', { count }, `${count}권을 즐겨찾기 해제`));
  }

  return `<pre style="white-space: pre-wrap; margin: 0; font-size: 0.78rem;">${escapeHtml(JSON.stringify(preview))}</pre>`;
}

function getToolLabel(toolName) {
  const labels = {
    bulk_update_book_metadata: `<i class="lc lc-pen"></i> ${escapeHtml(t('mcp_pending.tool_bulk_metadata', null, '메타데이터 일괄 수정'))}`,
    bulk_set_favorite: `<i class="fa-solid fa-star"></i> ${escapeHtml(t('mcp_pending.tool_bulk_favorite', null, '즐겨찾기 일괄 처리'))}`,
  };
  return labels[toolName] || escapeHtml(toolName);
}

function renderMcpPendingTable(changes) {
  const tbody = document.getElementById('mcp-pending-table-body');
  if (!tbody) return;

  if (changes.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="padding: 3rem; text-align: center; color: var(--app-text-muted);"><i class="lc lc-circle-check" style="font-size: 2rem; margin-bottom: 1rem; display: block; color: #22c55e;"></i>${escapeHtml(t('mcp_pending.empty', null, '대기 중인 제안이 없습니다.'))}</td></tr>`;
    return;
  }

  tbody.innerHTML = changes.map((change) => `
    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
      <td style="padding: 1rem; color: var(--app-text-muted);">${change.id}</td>
      <td style="padding: 1rem; color: var(--app-text-primary);">${getToolLabel(change.tool_name)}<br><span style="font-size: 0.75rem; color: var(--app-text-muted);">${escapeHtml(change.db_type)}</span></td>
      <td style="padding: 1rem; color: var(--app-text-primary);">${escapeHtml(change.target)}</td>
      <td style="padding: 1rem; color: var(--app-text-primary); font-size: 0.82rem; max-width: 420px;">${formatPreview(change.tool_name, change.preview)}</td>
      <td style="padding: 1rem; color: var(--app-text-muted); font-size: 0.82rem;">${escapeHtml(change.created_at)}</td>
      <td style="padding: 1rem;">
        <div style="display: flex; gap: 0.4rem;">
          <button class="action-btn" data-role="mcp-approve" data-change-id="${change.id}" style="padding: 0.35rem 0.7rem; background-color: rgba(34, 197, 94, 0.2); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 6px; color: #4ade80; font-weight: 600; cursor: pointer; white-space: nowrap;">
            <i class="lc lc-check"></i> ${escapeHtml(t('mcp_pending.btn_approve', null, '승인'))}
          </button>
          <button class="action-btn" data-role="mcp-reject" data-change-id="${change.id}" style="padding: 0.35rem 0.7rem; background-color: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; color: #fca5a5; font-weight: 600; cursor: pointer; white-space: nowrap;">
            <i class="lc lc-x"></i> ${escapeHtml(t('mcp_pending.btn_reject', null, '거부'))}
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

export async function approveMcpChange(changeId) {
  if (!confirm(t('mcp_pending.approve_confirm', { id: changeId }, `변경 ID ${changeId}를 승인하고 실제로 서재 DB에 반영하시겠습니까?`))) return;

  try {
    const res = await fetch(`/api/admin/mcp-pending-changes/${changeId}/approve`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert(t('mcp_pending.approve_success', null, '승인 및 반영이 완료되었습니다.'));
      loadMcpPendingChanges();
    } else {
      const errorMsg = data.error || t('mcp_pending.unknown_error', null, '알 수 없는 오류');
      alert(t('mcp_pending.approve_fail', { error: errorMsg }, `승인 실패: ${errorMsg}`));
    }
  } catch (err) {
    console.error('[MCP-Pending] 승인 오류:', err);
    alert(t('mcp_pending.approve_error', null, '승인 요청 중 오류가 발생했습니다.'));
  }
}
window.approveMcpChange = approveMcpChange;

export async function rejectMcpChange(changeId) {
  const note = prompt(t('mcp_pending.reject_reason_prompt', null, '거부 사유(선택, 비워도 됩니다):'), '') || '';
  if (!confirm(t('mcp_pending.reject_confirm', { id: changeId }, `변경 ID ${changeId}를 거부하시겠습니까? (DB에는 아무 것도 반영되지 않습니다)`))) return;

  try {
    const res = await fetch(`/api/admin/mcp-pending-changes/${changeId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    const data = await res.json();
    if (data.success) {
      alert(t('mcp_pending.reject_success', null, '거부되었습니다.'));
      loadMcpPendingChanges();
    } else {
      const errorMsg = data.error || t('mcp_pending.unknown_error', null, '알 수 없는 오류');
      alert(t('mcp_pending.reject_fail', { error: errorMsg }, `거부 실패: ${errorMsg}`));
    }
  } catch (err) {
    console.error('[MCP-Pending] 거부 오류:', err);
    alert(t('mcp_pending.reject_error', null, '거부 요청 중 오류가 발생했습니다.'));
  }
}
window.rejectMcpChange = rejectMcpChange;
