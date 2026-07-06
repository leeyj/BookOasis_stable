// settings_trash.js - 휴지통(삭제 관리) 클라이언트 처리 로직

// 전역 탭 변경 감지기 등에서 호출될 수 있도록 로드 함수 노출
function loadTrashList() {
    const dbType = document.getElementById('trash-db-type').value;
    const body = document.getElementById('trash-list-body');
    const emptyState = document.getElementById('trash-empty-state');
    const selectAllCheckbox = document.getElementById('trash-select-all');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    body.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #94a3b8;"><i class="fa-solid fa-circle-notch fa-spin"></i> 목록 로딩 중...</td></tr>';
    emptyState.style.display = 'none';

    fetch('/api/admin/trash')
        .then(res => res.json())
        .then(data => {
            if (!data.success) {
                body.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">데이터 로드 실패: ${data.error}</td></tr>`;
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
                    <td style="padding: 0.75rem 1rem; font-weight: 500; color: #f1f5f9;">${escapeHtml(item.title)}</td>
                    <td style="padding: 0.75rem 1rem; color: #94a3b8; font-family: monospace; font-size: 0.775rem; word-break: break-all;">${escapeHtml(item.file_path)}</td>
                    <td style="padding: 0.75rem 1rem;"><span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.25); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem;">${escapeHtml(item.library_name)}</span></td>
                    <td style="padding: 0.75rem 1rem; color: #64748b; font-size: 0.8rem;">${item.deleted_at || '-'}</td>
                    <td style="padding: 0.75rem 1rem; text-align: center; display: flex; justify-content: center; gap: 0.35rem;">
                        <button class="btn btn-secondary" onclick="restoreSingleTrash(${item.id})" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-radius: 4px;">복구</button>
                        <button class="btn btn-danger-outline" onclick="deleteSingleTrash(${item.id})" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-radius: 4px;">삭제</button>
                    </td>
                </tr>
            `).join('');
        })
        .catch(err => {
            body.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">API 통신 오류: ${err.message}</td></tr>`;
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
        alert('복구할 항목을 하나 이상 선택해 주세요.');
        return;
    }
    restoreTrashBooks(ids);
}

function restoreTrashBooks(bookIds) {
    const dbType = document.getElementById('trash-db-type').value;
    
    if (!confirm(`${bookIds.length}권의 도서를 복구하시겠습니까? 복구 시 즉시 일반 도서 목록에 재노출됩니다.`)) {
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
            alert('복구 실패: ' + data.error);
        }
    })
    .catch(err => alert('오류: ' + err.message));
}

function deleteSingleTrash(bookId) {
    deleteTrashBooks([bookId]);
}

function deleteSelectedTrash() {
    const ids = getSelectedTrashIds();
    if (ids.length === 0) {
        alert('영구 삭제할 항목을 하나 이상 선택해 주세요.');
        return;
    }
    deleteTrashBooks(ids);
}

function deleteTrashBooks(bookIds) {
    const dbType = document.getElementById('trash-db-type').value;
    
    if (!confirm(`선택한 ${bookIds.length}권의 도서를 DB에서 영구 삭제하시겠습니까?\n이 작업은 되돌릴 수 없으며 독서 진척도 정보도 함께 삭제됩니다.`)) {
        return;
    }
    
    fetch('/api/admin/trash/empty', {
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
            alert('삭제 실패: ' + data.error);
        }
    })
    .catch(err => alert('오류: ' + err.message));
}

function emptyTrashAll() {
    const dbType = document.getElementById('trash-db-type').value;
    const dbLabel = dbType === 'general' ? '일반' : '성인';
    
    if (!confirm(`주의! 현재 ${dbLabel} 데이터베이스 휴지통 내의 모든 도서 데이터를 영구 삭제하시겠습니까?\n이 작업은 모든 읽기 상태와 기록을 완전히 삭제하며 되돌릴 수 없습니다.`)) {
        return;
    }
    
    fetch('/api/admin/trash/empty', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ db_type: dbType })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            loadTrashList();
        } else {
            alert('휴지통 비우기 실패: ' + data.error);
        }
    })
    .catch(err => alert('오류: ' + err.message));
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
