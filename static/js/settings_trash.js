// settings_trash.js - 휴지통(삭제 관리) 클라이언트 처리 로직

// ── 전체 화면 잠금 오버레이 제어 ────────────────────────────────
function _showTrashOverlay(msg) {
    const overlay = document.getElementById('trash-loading-overlay');
    const msgEl   = document.getElementById('trash-loading-overlay-msg');
    if (!overlay) return;
    if (msgEl && msg) msgEl.textContent = msg;
    overlay.style.display = 'flex';
}

function _hideTrashOverlay() {
    const overlay = document.getElementById('trash-loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

// window.showGlobalLoadingSpinner/hideGlobalLoadingSpinner는 detail/book_actions.js가 담당한다(modal.js 지연 바인딩).
// 예전엔 이 파일이 같은 전역을 휴지통 전용 오버레이로 덮어써, 로드 순서에 따라 카테고리 삭제 등 다른 화면의
// 스피너가 휴지통 오버레이로 바뀌었다. 휴지통은 아래 _show/_hideTrashOverlay를 직접 쓴다.

function initTrashDelegation() {
    if (window.__trashDelegationBound) return;

    document.addEventListener('click', (event) => {
        const target = event && event.target && typeof event.target.closest === 'function'
            ? event.target.closest('[data-role="trash-restore-selected"], [data-role="trash-delete-selected"], [data-role="trash-empty-all"], [data-role="trash-restore-single"], [data-role="trash-delete-single"]')
            : null;
        if (!target) return;

        event.preventDefault();

        const role = target.getAttribute('data-role');
        if (role === 'trash-restore-selected') return restoreSelectedTrash();
        if (role === 'trash-delete-selected') return deleteSelectedTrash();
        if (role === 'trash-empty-all') return emptyTrashAll();

        const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
        if (!Number.isFinite(bookId) || bookId <= 0) return;
        if (role === 'trash-restore-single') return restoreSingleTrash(bookId);
        if (role === 'trash-delete-single') return deleteSingleTrash(bookId);
    }, true);

    document.addEventListener('change', (event) => {
        const target = event && event.target;
        if (!target) return;
        if (target.matches && target.matches('[data-role="trash-db-type"]')) {
            loadTrashList();
            return;
        }
        if (target.matches && target.matches('[data-role="trash-select-all"]')) {
            toggleAllTrashCheckboxes(target);
        }
    }, true);

    window.__trashDelegationBound = true;
}

// 전역 탭 변경 감지기 등에서 호출될 수 있도록 로드 함수 노출
function loadTrashList() {
    initTrashDelegation();
    const dbType = document.getElementById('trash-db-type').value;
    const body = document.getElementById('trash-list-body');
    const emptyState = document.getElementById('trash-empty-state');
    const selectAllCheckbox = document.getElementById('trash-select-all');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    body.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--app-text-muted);"><i class="lc lc-loader-circle lc-spin"></i> ${i18n.t('settings.trash_loading')}</td></tr>`;
    emptyState.style.display = 'none';

    fetch('/api/admin/trash')
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                body.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">${i18n.t('settings.trash_load_failed', { error: data.error })}</td></tr>`;
                return;
            }

            const list = data[dbType] || [];
            if (list.length === 0) {
                body.innerHTML = '';
                emptyState.style.display = 'block';
                return;
            }

            body.innerHTML = list.map(item => `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.04); background: rgba(255,255,255,0.01); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.03)'" onmouseout="this.style.background='rgba(255,255,255,0.01)'">
                    <td style="padding: 0.75rem 1rem; text-align: center;">
                        <input type="checkbox" class="trash-item-checkbox" value="${item.id}" style="cursor: pointer; width: 14px; height: 14px; accent-color: #3b82f6;">
                    </td>
                    <td style="padding: 0.75rem 1rem; font-weight: 500; color: var(--app-text-primary);">${escapeHtml(item.title)}</td>
                    <td style="padding: 0.75rem 1rem; color: var(--app-text-muted); font-family: monospace; font-size: 0.775rem; word-break: break-all;">${escapeHtml(item.file_path)}</td>
                    <td style="padding: 0.75rem 1rem;"><span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.25); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem;">${escapeHtml(item.library_name)}</span></td>
                    <td style="padding: 0.75rem 1rem; color: var(--app-text-muted); font-size: 0.8rem;">${item.deleted_at || '-'}</td>
                    <td style="padding: 0.75rem 1rem; text-align: center; display: flex; justify-content: center; gap: 0.35rem;">
                        <button class="btn btn-secondary" data-role="trash-restore-single" data-book-id="${item.id}" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-radius: 4px;">${i18n.t('settings.trash_restore')}</button>
                        <button class="btn btn-danger-outline" data-role="trash-delete-single" data-book-id="${item.id}" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-radius: 4px;">${i18n.t('settings.trash_delete')}</button>
                    </td>
                </tr>
            `).join('');
        })
        .catch(err => {
            body.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">${i18n.t('settings.trash_api_error', { error: err.message })}</td></tr>`;
        });
}

function toggleAllTrashCheckboxes(master) {
    const checkboxes = document.querySelectorAll('.trash-item-checkbox');
    checkboxes.forEach(cb => cb.checked = master.checked);
}

function getSelectedTrashIds() {
    const checkboxes = document.querySelectorAll('.trash-item-checkbox:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.value));
}

function restoreSingleTrash(bookId) {
    restoreTrashBooks([bookId]);
}

function restoreSelectedTrash() {
    const ids = getSelectedTrashIds();
    if (ids.length === 0) {
        alert(i18n.t('settings.trash_select_to_restore'));
        return;
    }
    restoreTrashBooks(ids);
}

function restoreTrashBooks(bookIds) {
    const dbType = document.getElementById('trash-db-type').value;
    
    if (!confirm(i18n.t('settings.trash_restore_confirm', { count: bookIds.length }))) {
        return;
    }
    
    fetch('/api/admin/trash/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ db_type: dbType, book_ids: bookIds })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            loadTrashList();
        } else {
            alert(i18n.t('settings.trash_restore_failed', { error: data.error }));
        }
    })
    .catch(err => alert(i18n.t('settings.trash_error', { error: err.message })));
}

function deleteSingleTrash(bookId) {
    deleteTrashBooks([bookId]);
}

function deleteSelectedTrash() {
    const ids = getSelectedTrashIds();
    if (ids.length === 0) {
        alert(i18n.t('settings.trash_select_to_delete'));
        return;
    }
    deleteTrashBooks(ids);
}

function deleteTrashBooks(bookIds) {
    const dbType = document.getElementById('trash-db-type').value;
    
    if (!confirm(i18n.t('settings.trash_delete_confirm', { count: bookIds.length }))) {
        return;
    }

    // 오버레이 표시 — 삭제 완료 전 다른 클릭 차단
    _showTrashOverlay(i18n.t('settings.trash_deleting', { count: bookIds.length }));
    
    fetch('/api/admin/trash/empty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ db_type: dbType, book_ids: bookIds })
    })
    .then(res => res.json())
    .then(data => {
        _hideTrashOverlay();
        if (data.success) {
            alert(data.message);
            loadTrashList();
        } else {
            alert(i18n.t('settings.trash_delete_failed', { error: data.error }));
        }
    })
    .catch(err => {
        _hideTrashOverlay();
        alert(i18n.t('settings.trash_error', { error: err.message }));
    });
}

const TRASH_DB_LABELS = {
    general: 'header.general_books',
    adult: 'header.adult_books',
    audiobook: 'header.audiobooks',
    video: 'header.videos'
};

function emptyTrashAll() {
    const dbType = document.getElementById('trash-db-type').value;
    const dbLabel = TRASH_DB_LABELS[dbType] ? i18n.t(TRASH_DB_LABELS[dbType]) : dbType;
    
    if (!confirm(i18n.t('settings.trash_empty_confirm', { db: dbLabel }))) {
        return;
    }

    // 오버레이 표시 — 비우기 완료 전 다른 클릭 차단
    _showTrashOverlay(i18n.t('settings.trash_emptying'));

    fetch('/api/admin/trash/empty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ db_type: dbType })
    })
    .then(res => res.json())
    .then(data => {
        _hideTrashOverlay();
        if (data.success) {
            alert(data.message);
            loadTrashList();
        } else {
            alert(i18n.t('settings.trash_empty_failed', { error: data.error }));
        }
    })
    .catch(err => {
        _hideTrashOverlay();
        alert(i18n.t('settings.trash_error', { error: err.message }));
    });
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// 전역 노출 바인딩
window.loadTrashList = loadTrashList;
window.toggleAllTrashCheckboxes = toggleAllTrashCheckboxes;
window.restoreSingleTrash = restoreSingleTrash;
window.restoreSelectedTrash = restoreSelectedTrash;
window.deleteSingleTrash = deleteSingleTrash;
window.deleteSelectedTrash = deleteSelectedTrash;
window.emptyTrashAll = emptyTrashAll;

// 탭 스위처 바인딩 확인 및 초기화 지원
document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.switchSettingsTab === 'function') {
        const originalSwitchTab = window.switchSettingsTab;
        window.switchSettingsTab = function(tabName) {
            originalSwitchTab(tabName);
            if (tabName === 'trash') {
                loadTrashList();
            }
        };
    }
});

