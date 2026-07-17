// static/js/settings/users.js – 사용자 관리 탭 모듈
import { state } from '../state.js';

const MAX_USERNAME_LENGTH = 128;
const MAX_PASSWORD_LENGTH = 256;
const MIN_PASSWORD_LENGTH = 4;

export async function loadUsersList() {
  const tbody = document.getElementById('settings-users-list');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;"><i class="fa-solid fa-circle-notch fa-spin"></i> 사용자 목록 로드 중...</td></tr>';

  try {
    const res = await fetch(`/api/admin/users?type=${state.currentLibraryType}`);
    const data = await res.json();

    if (data.success) {
      if (data.users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#94a3b8;">${window.i18n ? window.i18n.t('settings.user_no_users') : '등록된 사용자가 없습니다.'}</td></tr>`;
        return;
      }

      tbody.innerHTML = data.users.map(user => {
        const isDefault = user.is_default_password === 1 
          ? `<span style="color:#f97316; font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> ${window.i18n ? window.i18n.t('settings.user_pwd_not_changed') : '초기 비밀번호'}</span>` 
          : `<span style="color:#22c55e;"><i class="fa-solid fa-circle-check"></i> ${window.i18n ? window.i18n.t('settings.user_pwd_changed') : '변경완료'}</span>`;

        const myUserId = Number(window.currentUser?.id || 0);
        const isSelf = Number(user.id) === myUserId;
        const deleteBtn = isSelf
          ? `<span style="color:#64748b; font-size:0.8rem;">${window.i18n ? window.i18n.t('settings.user_cannot_delete') : '삭제불가'}</span>`
          : `<button onclick="deleteUser(${user.id}, '${user.username}')" class="btn-settings-action" style="background:#ef4444; color:#fff; border:none; padding:0.25rem 0.6rem; border-radius:4px; cursor:pointer;"><i class="fa-solid fa-trash-can"></i> ${window.i18n ? window.i18n.t('settings.user_delete') : '삭제'}</button>`;

        const resetPwdBtn = user.role === 'admin'
          ? `<button onclick="openAdminChangePwdModal(${user.id})" class="btn-settings-action" style="background:#3b82f6; color:#fff; border:none; padding:0.25rem 0.6rem; border-radius:4px; cursor:pointer; margin-right:0.5rem;"><i class="fa-solid fa-key"></i> ${window.i18n ? window.i18n.t('settings.admin_change_pwd') : '비번 변경'}</button>`
          : `<button onclick="openResetPwdModal(${user.id})" class="btn-settings-action" style="background:#f59e0b; color:#fff; border:none; padding:0.25rem 0.6rem; border-radius:4px; cursor:pointer; margin-right:0.5rem;"><i class="fa-solid fa-unlock-keyhole"></i> ${window.i18n ? window.i18n.t('settings.user_reset_pwd') : '초기 비밀번호 재설정'}</button>`;

        return `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:1rem;">${user.id}</td>
            <td style="padding:1rem; font-weight:700; color:#fff;">${user.username}</td>
            <td style="padding:1rem;"><span class="badge" style="background:rgba(168,85,247,0.1); color:#c084fc; border:1px solid rgba(168,85,247,0.2); padding:0.2rem 0.5rem; border-radius:4px; font-size:0.75rem;">${user.role}</span></td>
            <td style="padding:1rem; text-align:center;">${isDefault}</td>
            <td style="padding:1rem; text-align:center;">${resetPwdBtn}${deleteBtn}</td>
          </tr>
        `;
      }).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${window.i18n ? window.i18n.t('settings.user_fetch_failed') : '조회 실패: '} ${data.error}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#ef4444;">${window.i18n ? window.i18n.t('settings.users_server_error') : '서버 요청 중 오류가 발생했습니다.'}</td></tr>`;
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
  const has_adult_access = document.getElementById('user-form-adult-access').checked;

  if (!username) {
    alert(i18n.t('settings.users_add_fail', {error: '사용자 아이디를 입력해 주세요.'}));
    return;
  }
  if (username.length > MAX_USERNAME_LENGTH) {
    alert(i18n.t('settings.users_add_fail', {error: `사용자 아이디는 최대 ${MAX_USERNAME_LENGTH}자까지 허용됩니다.`}));
    return;
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    alert(i18n.t('settings.users_add_fail', {error: `비밀번호는 최소 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`}));
    return;
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    alert(i18n.t('settings.users_add_fail', {error: `비밀번호는 최대 ${MAX_PASSWORD_LENGTH}자까지 허용됩니다.`}));
    return;
  }

  try {
    const res = await fetch(`/api/admin/users?type=${state.currentLibraryType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, role, has_adult_access })
    });
    const data = await res.json();

    if (data.success) {
      closeUserModal();
      loadUsersList();
    } else {
      alert(data.error ? i18n.t('settings.users_add_fail', {error: data.error}) : i18n.t('settings.users_add_fail', {error: ''}));
    }
  } catch (err) {
    alert(i18n.t('settings.users_server_error'));
    console.error(err);
  }
}

export async function deleteUser(userId, username) {
  if (!confirm(i18n.t('settings.users_del_confirm', {username: username}))) return;

  try {
    const res = await fetch(`/api/admin/users/${userId}?type=${state.currentLibraryType}`, {
      method: 'DELETE'
    });
    const data = await res.json();

    if (data.success) {
      loadUsersList();
    } else {
      alert(data.error ? i18n.t('settings.users_del_fail', {error: data.error}) : i18n.t('settings.users_del_fail', {error: ''}));
    }
  } catch (err) {
    alert(i18n.t('settings.users_server_error'));
    console.error(err);
  }
}

// 글로벌 등록 (인라인 핸들러 바인딩)
window.openAddUserModal = openAddUserModal;
window.closeUserModal = closeUserModal;
window.submitUserForm = submitUserForm;
window.deleteUser = deleteUser;

export function openResetPwdModal(userId) {
  const modal = document.getElementById('user-reset-pwd-modal');
  if (modal) {
    modal.style.display = 'flex';
    document.getElementById('reset-pwd-user-id').value = userId;
    document.getElementById('reset-pwd-new').value = '';
  }
}

export function closeResetPwdModal() {
  const modal = document.getElementById('user-reset-pwd-modal');
  if (modal) modal.style.display = 'none';
}

export async function submitResetPwdForm(e) {
  e.preventDefault();
  const userId = document.getElementById('reset-pwd-user-id').value;
  const newPassword = document.getElementById('reset-pwd-new').value.trim();

  if (newPassword.length < MIN_PASSWORD_LENGTH) {
    alert(`비밀번호는 최소 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`);
    return;
  }
  if (newPassword.length > MAX_PASSWORD_LENGTH) {
    alert(`비밀번호는 최대 ${MAX_PASSWORD_LENGTH}자까지 허용됩니다.`);
    return;
  }

  try {
    const res = await fetch(`/api/admin/users/${userId}/password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_password: newPassword })
    });
    const data = await res.json();
    if (data.success) {
      alert(data.message || '변경되었습니다.');
      closeResetPwdModal();
      loadUsersList();
    } else {
      alert(data.error || '오류가 발생했습니다.');
    }
  } catch (err) {
    alert(i18n.t('settings.users_server_error'));
    console.error(err);
  }
}

export function openAdminChangePwdModal(userId) {
  const modal = document.getElementById('admin-change-pwd-modal');
  if (modal) {
    modal.style.display = 'flex';
    document.getElementById('change-pwd-admin-id').value = userId;
    document.getElementById('change-pwd-current').value = '';
    document.getElementById('change-pwd-new').value = '';
  }
}

export function closeAdminChangePwdModal() {
  const modal = document.getElementById('admin-change-pwd-modal');
  if (modal) modal.style.display = 'none';
}

export async function submitAdminChangePwdForm(e) {
  e.preventDefault();
  const userId = document.getElementById('change-pwd-admin-id').value;
  const currentPassword = document.getElementById('change-pwd-current').value.trim();
  const newPassword = document.getElementById('change-pwd-new').value.trim();

  if (currentPassword.length > MAX_PASSWORD_LENGTH || newPassword.length > MAX_PASSWORD_LENGTH) {
    alert(`비밀번호는 최대 ${MAX_PASSWORD_LENGTH}자까지 허용됩니다.`);
    return;
  }
  if (newPassword.length < MIN_PASSWORD_LENGTH) {
    alert(`비밀번호는 최소 ${MIN_PASSWORD_LENGTH}자 이상이어야 합니다.`);
    return;
  }

  try {
    const res = await fetch(`/api/admin/users/${userId}/password`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
    const data = await res.json();
    if (data.success) {
      alert(data.message || '변경되었습니다.');
      closeAdminChangePwdModal();
      loadUsersList();
    } else {
      alert(data.error || '오류가 발생했습니다.');
    }
  } catch (err) {
    alert(i18n.t('settings.users_server_error'));
    console.error(err);
  }
}

window.openResetPwdModal = openResetPwdModal;
window.closeResetPwdModal = closeResetPwdModal;
window.submitResetPwdForm = submitResetPwdForm;
window.openAdminChangePwdModal = openAdminChangePwdModal;
window.closeAdminChangePwdModal = closeAdminChangePwdModal;
window.submitAdminChangePwdForm = submitAdminChangePwdForm;
