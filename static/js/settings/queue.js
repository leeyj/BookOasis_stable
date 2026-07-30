// settings/queue.js - 스캔 대기열(Queue) 상태 조회 및 관리 모듈

window.queueRefreshInterval = null;

export async function loadQueueStatus() {
    try {
        const response = await fetch(`/api/media/system/queue?_ts=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) throw new Error('API Response Error');
        const data = await response.json();
        
        if (data.success && data.queue) {
            renderQueueTable(data.queue);
        } else {
            console.error("Queue data load failed:", data.error);
        }
    } catch (error) {
        console.error("Failed to fetch queue status", error);
        const tbody = document.getElementById('queue-table-body');
        if (tbody) {
            tbody.innerHTML = `<tr data-queue-error="true"><td colspan="5" style="padding: 2rem; text-align: center; color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i> ${window.i18n ? window.i18n.t('queue.load_error') : '대기열 정보를 불러오지 못했습니다.'}</td></tr>`;
        }
    }
}
window.loadQueueStatus = loadQueueStatus;

function getQueueTaskTypeName(type, t) {
    if (type === 'library_scan') return `<span style="color: #60a5fa;"><i class="fa-solid fa-folder-tree"></i> ${t('queue.type_lib')}</span>`;
    if (type === 'cover_scan') return `<span style="color: #4ade80;"><i class="fa-solid fa-image"></i> ${t('queue.type_cover')}</span>`;
    if (type === 'lazy_scan') return `<span style="color: #c084fc;"><i class="fa-solid fa-moon"></i> ${t('queue.type_lazy')}</span>`;
    return type;
}

function getQueueStageBadge(task, t) {
    if (task.role === 'pending') {
        return `
            <span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 4px; background-color: rgba(255, 255, 255, 0.1); color: #cbd5e1; font-size: 0.85rem;">
                <i class="fa-solid fa-hourglass-half"></i> ${t('queue.status_pending')}
            </span>
        `;
    }

    if (task.stage === 'vfs_refresh') {
        return `
            <span style="display: inline-flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 6px 12px; border-radius: 6px; background-color: rgba(59, 130, 246, 0.15); color: #60a5fa; font-size: 0.82rem; font-weight: 600; line-height: 1.3; text-align: center; width: 100%; box-sizing: border-box;">
                <span><i class="fa-solid fa-spinner fa-spin"></i> ${t('queue.status_running')}</span>
                <span style="font-size: 0.72rem; opacity: 0.85;">(${t('queue.status_vfs') || 'VFS 갱신'})</span>
            </span>
        `;
    }

    if (task.stage === 'book_scan' || task.stage === 'db_scan') {
        return `
            <span style="display: inline-flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 6px 12px; border-radius: 6px; background-color: rgba(168, 85, 247, 0.15); color: #c084fc; font-size: 0.82rem; font-weight: 600; line-height: 1.3; text-align: center; width: 100%; box-sizing: border-box;">
                <span><i class="fa-solid fa-spinner fa-spin"></i> ${t('queue.status_running')}</span>
                <span style="font-size: 0.72rem; opacity: 0.85;">(${t('queue.status_books') || t('queue.status_scan') || '도서 스캔'})</span>
            </span>
        `;
    }

    return `
        <span style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 6px; background-color: rgba(59, 130, 246, 0.15); color: #60a5fa; font-size: 0.82rem; font-weight: 600; justify-content: center; width: 100%; box-sizing: border-box;">
            <i class="fa-solid fa-spinner fa-spin"></i> ${t('queue.status_running')}
        </span>
    `;
}

function getQueueCancelButton(task, t) {
    if (task.role === 'running' && task.type === 'library_scan' && task.kwargs && task.kwargs.library_id) {
        const libId = task.kwargs.library_id;
        const dbType = task.kwargs.db_type || 'general';
        return `
            <button class="action-btn" onclick="cancelRunningScan(${libId}, '${dbType}')" style="margin-left: 8px; padding: 2px 6px; background-color: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 4px; color: #fca5a5; font-size: 0.75rem; cursor: pointer; transition: all 0.2s; white-space: nowrap; display: inline-flex; align-items: center; gap: 4px;">
                <i class="fa-solid fa-circle-stop"></i> ${t('queue.btn_cancel') || '취소'}
            </button>
        `;
    }

    if (task.role === 'pending' && task.key) {
        return `
            <button class="action-btn" onclick="cancelWaitingScan('${task.key}')" style="margin-left: 8px; padding: 2px 6px; background-color: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 4px; color: #fca5a5; font-size: 0.72rem; cursor: pointer; transition: all 0.2s; white-space: nowrap;">
                ${t('queue.btn_cancel') || '취소'}
            </button>
        `;
    }

    return '';
}

function normalizeQueueRows(queueData) {
    const rows = [];
    if (queueData.running) {
        rows.push({ ...queueData.running, role: 'running', domKey: `running:${queueData.running.key || 'active'}` });
    }
    (queueData.pending || []).forEach((task, idx) => {
        rows.push({ ...task, role: 'pending', domKey: `pending:${task.key || idx}` });
    });
    return rows;
}

function buildQueueRowInnerHtml(task, index, t) {
    const statusHtml = getQueueStageBadge(task, t);
    const cancelButton = getQueueCancelButton(task, t);

    if (task.role === 'running') {
        return `
            <td style="padding: 1rem; color: #e2e8f0;">${index}</td>
            <td style="padding: 1rem;">${statusHtml}</td>
            <td style="padding: 1rem; color: #e2e8f0;">${getQueueTaskTypeName(task.type, t)}</td>
            <td style="padding: 1rem; color: #f8fafc; font-weight: 500;">${task.library_name || t('queue.system')}</td>
            <td style="padding: 1rem; color: #94a3b8; font-size: 0.85rem; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                <span>시작: ${task.started_at || '-'}</span>
                ${cancelButton}
            </td>
        `;
    }

    return `
        <td style="padding: 1rem; color: #94a3b8;">${index}</td>
        <td style="padding: 1rem; display: flex; align-items: center; gap: 8px;">${statusHtml}${cancelButton}</td>
        <td style="padding: 1rem; color: #e2e8f0;">${getQueueTaskTypeName(task.type, t)}</td>
        <td style="padding: 1rem; color: #e2e8f0;">${task.library_name || t('queue.system')}</td>
        <td style="padding: 1rem; color: #94a3b8; font-size: 0.85rem;">등록: ${task.enqueued_at || '-'}</td>
    `;
}

function applyQueueRowStyle(row, task) {
    if (task.role === 'running') {
        row.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
        row.style.backgroundColor = 'rgba(59, 130, 246, 0.05)';
    } else {
        row.style.borderBottom = '1px solid rgba(255, 255, 255, 0.05)';
        row.style.backgroundColor = '';
    }
}

function renderQueueTable(queueData) {
    const tbody = document.getElementById('queue-table-body');
    if (!tbody) return;

    const t = window.i18n ? window.i18n.t.bind(window.i18n) : (key) => key;

    const rows = normalizeQueueRows(queueData);
    if (rows.length === 0) {
        tbody.innerHTML = `<tr data-queue-empty="true"><td colspan="5" style="padding: 3rem; text-align: center; color: #94a3b8;"><i class="fa-solid fa-check-circle" style="font-size: 2rem; margin-bottom: 1rem; display: block; color: #22c55e;"></i>${t('queue.empty')}</td></tr>`;
        return;
    }

    // 이전 로딩/오류 행처럼 관리 대상이 아닌 고정 행은 먼저 제거한다.
    tbody.querySelectorAll('tr:not([data-queue-key]):not([data-queue-empty])').forEach(row => row.remove());

    const existingRows = new Map();
    tbody.querySelectorAll('tr[data-queue-key]').forEach(row => {
        existingRows.set(row.dataset.queueKey, row);
    });

    tbody.querySelectorAll('tr[data-queue-empty]').forEach(row => row.remove());

    const activeKeys = new Set();
    rows.forEach((task, idx) => {
        activeKeys.add(task.domKey);

        let row = existingRows.get(task.domKey);
        if (!row) {
            row = document.createElement('tr');
            row.dataset.queueKey = task.domKey;
        }

        applyQueueRowStyle(row, task);

        const nextInnerHtml = buildQueueRowInnerHtml(task, idx + 1, t);
        if (row.innerHTML !== nextInnerHtml) {
            row.innerHTML = nextInnerHtml;
        }

        const currentRowAtIndex = tbody.children[idx];
        if (currentRowAtIndex !== row) {
            tbody.insertBefore(row, currentRowAtIndex || null);
        }
    });

    Array.from(tbody.querySelectorAll('tr[data-queue-key]')).forEach(row => {
        if (!activeKeys.has(row.dataset.queueKey)) {
            row.remove();
        }
    });
}

export async function cancelRunningScan(libraryId, dbType) {
    const confirmMsg = window.i18n ? window.i18n.t('queue.cancel_confirm') : "진행 중인 스캔 작업을 강제 중단하시겠습니까?";
    if (!confirm(confirmMsg)) return;

    try {
        const formData = new FormData();
        formData.append('type', dbType);
        
        const response = await fetch(`/api/media/libraries/${libraryId}/cancel-scan`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadQueueStatus();
        } else {
            alert((window.i18n ? window.i18n.t('queue.cancel_fail') : "취소 실패: ") + data.error);
        }
    } catch (error) {
        console.error("Scan cancel error", error);
        alert(window.i18n ? window.i18n.t('queue.cancel_error') : "취소 요청 중 오류가 발생했습니다.");
    }
}
window.cancelRunningScan = cancelRunningScan;

export async function cancelWaitingScan(taskId) {
    const confirmMsg = window.i18n ? window.i18n.t('queue.cancel_waiting_confirm') : "대기열의 작업을 취소하시겠습니까?";
    if (!confirm(confirmMsg)) return;

    try {
        const response = await fetch(`/api/media/system/queue/cancel?task_id=${encodeURIComponent(taskId)}`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadQueueStatus();
        } else {
            alert((window.i18n ? window.i18n.t('queue.cancel_fail') : "취소 실패: ") + data.error);
        }
    } catch (error) {
        console.error("Cancel waiting scan error", error);
        alert(window.i18n ? window.i18n.t('queue.cancel_error') : "작업 취소 요청 중 오류가 발생했습니다.");
    }
}
window.cancelWaitingScan = cancelWaitingScan;

export async function clearQueue() {
    const msg = window.i18n ? window.i18n.t('queue.clear_confirm') : "대기 중인 모든 스캔 작업을 삭제하시겠습니까?\n(현재 실행 중인 작업은 중단되지 않습니다.)";
    
    if (!confirm(msg)) return;
    
    try {
        const response = await fetch('/api/media/system/queue/clear', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadQueueStatus();
        } else {
            alert((window.i18n ? window.i18n.t('queue.clear_fail') : "삭제 실패: ") + data.error);
        }
    } catch (error) {
        console.error("Queue clear error", error);
        alert(window.i18n ? window.i18n.t('queue.clear_error') : "삭제 요청 중 오류가 발생했습니다.");
    }
}
window.clearQueue = clearQueue;
