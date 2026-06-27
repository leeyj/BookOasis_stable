// static/js/settings/users.js – 사용자 관리 탭 모듈
import { state } from '../state.js';

export async function loadUsersList() {
  const tbody = document.getElementById('settings-users-list');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;"><i class="fa-solid fa-circle-notch fa-spin"></i> 사용자 목록 로드 중...</td></tr>';

  try {
    const res = await fetch(`/api/admin/users?type=${state.currentLibraryType}`);
    const data = await res.json();

    if (data.success) {
      if (data.users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;">등록된 사용자가 없습니다.</td></tr>';
        return;
      }

      tbody.innerHTML = data.users.map(user => {
        const isDefault = user.is_default_password === 1 
          ? '<span style="color:#f97316; font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> 미변경</span>' 
          : '<span style="color:#22c55e;"><i class="fa-solid fa-circle-check"></i> 변경완료</span>';

        const deleteBtn = user.username === 'admin' 
          ? '<span style="color:#64748b; font-size:0.8rem;">삭제불가</span>'
          : `<button onclick="deleteUser(${user.id}, '${user.username}')" class="btn-settings-action" style="background:#ef4444; color:#fff; border:none; padding:0.25rem 0.6rem; border-radius:4px; cursor:pointer;"><i class="fa-solid fa-trash-can"></i> 삭제</button>`;

        return `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:1rem;">${user.id}</td>
            <td style="padding:1rem; font-weight:700; color:#fff;">${user.username}</td>
            <td style="padding:1rem;"><span class="badge" style="background:rgba(168,85,247,0.1); color:#c084fc; border:1px solid rgba(168,85,247,0.2); padding:0.2rem 0.5rem; border-radius:4px; font-size:0.75rem;">${user.role}</span></td>
            <td style="padding:1rem; text-align:center;">${isDefault}</td>
            <td style="padding:1rem; text-align:center;">${deleteBtn}</td>
          </tr>
        `;
      }).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">조회 실패: ${data.error}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">서버 연결 오류</td></tr>';
    console.error(err);
  }
}

export function openAddUserModal() {
  const modal = document.getElementById('user-form-modal');
  if (modal) {
    modal.style.display = 'flex';
    document.getElementById('user-form-username').value = '';
    document.getElementById('user-form-password').value = '';
    document.getElementById('user-form-role').value = 'user';
  }
}

export function closeUserModal() {
  const modal = document.getElementById('user-form-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

export async function submitUserForm(e) {
  e.preventDefault();
  const username = document.getElementById('user-form-username').value.trim();
  const password = document.getElementById('user-form-password').value.trim();
  const role = document.getElementById('user-form-role').value;

  try {
    const res = await fetch(`/api/admin/users?type=${state.currentLibraryType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role })
    });
    const data = await res.json();

    if (data.success) {
      closeUserModal();
      loadUsersList();
    } else {
      alert(data.error || '사용자 등록 실패');
    }
  } catch (err) {
    alert('서버 요청 중 오류가 발생했습니다.');
    console.error(err);
  }
}

export async function deleteUser(userId, username) {
  if (!confirm(`사용자 "${username}" 계정을 정말로 삭제하시겠습니까?`)) return;

  try {
    const res = await fetch(`/api/admin/users/${userId}?type=${state.currentLibraryType}`, {
      method: 'DELETE'
    });
    const data = await res.json();

    if (data.success) {
      loadUsersList();
    } else {
      alert(data.error || '사용자 삭제 실패');
    }
  } catch (err) {
    alert('서버 요청 중 오류가 발생했습니다.');
    console.error(err);
  }
}

// 글로벌 등록 (인라인 핸들러 바인딩)
window.openAddUserModal = openAddUserModal;
window.closeUserModal = closeUserModal;
window.submitUserForm = submitUserForm;
window.deleteUser = deleteUser;
