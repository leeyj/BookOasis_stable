// static/js/settings/permissions.js – 권한 관리 탭 모듈
let permissionSessionData = null;
let activePermissionSession = 'general';

function initPermissionDelegation() {
  if (window.__permissionDelegationBound) return;

  document.addEventListener('click', (event) => {
    const tabButton = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.permission-session-tab[data-permission-session]')
      : null;
    if (!tabButton) return;

    event.preventDefault();
    const sessionId = tabButton.getAttribute('data-permission-session') || 'general';
    switchPermissionSessionTab(sessionId);
  }, true);

  window.__permissionDelegationBound = true;
}

export async function loadPermissionsMatrix() {
  initPermissionDelegation();
  const generalHeaderRow = document.getElementById('permissions-table-header');
  const generalBody = document.getElementById('permissions-table-body');
  const adultBody = document.getElementById('permissions-adult-table-body');
  const audiobookHeaderRow = document.getElementById('permissions-audiobook-table-header');
  const audiobookBody = document.getElementById('permissions-audiobook-table-body');
  const videoHeaderRow = document.getElementById('permissions-video-table-header');
  const videoBody = document.getElementById('permissions-video-table-body');
  if (!generalHeaderRow || !generalBody || !adultBody || !audiobookHeaderRow || !audiobookBody || !videoHeaderRow || !videoBody) return;

  const tLoading = window.i18n ? window.i18n.t('common.loading') : '불러오는 중...';
  const tError = window.i18n ? window.i18n.t('common.error') : '오류';

  generalHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  audiobookHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  videoHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  generalBody.innerHTML = '';
  adultBody.innerHTML = '';
  audiobookBody.innerHTML = '';
  videoBody.innerHTML = '';

  try {
    const res = await fetch('/api/admin/permissions');
    const data = await res.json();

    if (!data.success) {
      generalHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tError}: ${data.error}</th>`;
      audiobookHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tError}: ${data.error}</th>`;
      videoHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tError}: ${data.error}</th>`;
      return;
    }

    permissionSessionData = data;
    renderSessionTabs(data.sessions || []);

    const users = data.users || [];
    const generalMatrix = data.matrices?.general || { categories: [], permissions: {} };
    const audiobookMatrix = data.matrices?.audiobook || { categories: [], permissions: {} };
    const videoMatrix = data.matrices?.video || { categories: [], permissions: {} };

    renderMatrixHeader(generalHeaderRow, users);
    renderMatrixHeader(audiobookHeaderRow, users);
    renderMatrixHeader(videoHeaderRow, users);
    generalBody.innerHTML = renderMatrixBody(users, generalMatrix.categories, generalMatrix.permissions, 'general');
    audiobookBody.innerHTML = renderMatrixBody(users, audiobookMatrix.categories, audiobookMatrix.permissions, 'audiobook');
    videoBody.innerHTML = renderMatrixBody(users, videoMatrix.categories, videoMatrix.permissions, 'video');
    adultBody.innerHTML = renderAdultBody(users);

    bindPermissionEvents();
    switchPermissionSessionTab(activePermissionSession);
  } catch (err) {
    const tServerErr = window.i18n ? window.i18n.t('settings.users_server_error') : '서버 요청 중 오류가 발생했습니다.';
    generalHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tServerErr}</th>`;
    audiobookHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tServerErr}</th>`;
    videoHeaderRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tServerErr}</th>`;
    console.error(err);
  }
}

function renderSessionTabs(sessions) {
  const sessionTitleMap = new Map((sessions || []).map(session => [session.id, session.title]));
  document.querySelectorAll('.permission-session-tab').forEach(btn => {
    const sessionId = btn.getAttribute('data-permission-session');
    if (sessionTitleMap.has(sessionId)) {
      btn.textContent = sessionTitleMap.get(sessionId);
    }
  });
}

function renderMatrixHeader(headerRow, users) {
  let headerHTML = '<th style="padding:1rem; width:25%;">카테고리 이름</th>';
  users.forEach(user => {
    headerHTML += `
      <th style="padding:1rem; text-align:center; min-width:100px;">
        <div style="font-weight:700; color: var(--app-text-primary);">${user.username}</div>
        <div style="font-size:0.75rem; color: var(--app-text-muted);">(${user.role})</div>
      </th>
    `;
  });
  headerRow.innerHTML = headerHTML;
}

function renderMatrixBody(users, categories, permissions, targetDb) {
  return (categories || []).map(cat => {
    let rowHTML = `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="padding:1rem; color: var(--app-text-primary);">
          <i class="fa-solid fa-folder" style="color: var(--app-text-muted); margin-right:0.5rem;"></i>${cat.name}
        </td>
    `;

    users.forEach(user => {
      const key = `${targetDb}_${cat.id}`;
      const permissionTargetDb = cat.db_type || targetDb;
      const hasPerm = permissions[user.id] && permissions[user.id][key] !== undefined
        ? permissions[user.id][key]
        : true;
      const isDisabled = user.username === 'admin' ? 'disabled' : '';
      const accentColor = targetDb === 'audiobook' ? '#10b981' : '#10b981';

      rowHTML += `
        <td style="padding:1rem; text-align:center;">
          <input type="checkbox" class="permission-chk-category"
                 data-user-id="${user.id}" data-library-id="${cat.id}" data-db-type="${permissionTargetDb}"
                 ${hasPerm ? 'checked' : ''} ${isDisabled}
                 style="cursor:pointer; width:1.1rem; height:1.1rem; accent-color:${accentColor};">
        </td>
      `;
    });

    rowHTML += `</tr>`;
    return rowHTML;
  }).join('');
}

function renderAdultBody(users) {
  return users.map(user => {
    const isChecked = user.has_adult_access === 1 ? 'checked' : '';
    const isDisabled = user.username === 'admin' ? 'disabled' : '';
    return `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="padding:0.9rem 1rem; color: var(--app-text-primary); font-weight:700;">${user.username}</td>
        <td style="padding:0.9rem 1rem; text-align:center; color: var(--app-text-muted);">${user.role}</td>
        <td style="padding:0.9rem 1rem; text-align:center;">
          <label style="display:inline-flex; align-items:center; gap:0.5rem; color:#c084fc; font-weight:700;">
            <input type="checkbox" class="permission-chk-adult" data-user-id="${user.id}" ${isChecked} ${isDisabled}
                   style="cursor:pointer; width:1.2rem; height:1.2rem; accent-color:#a855f7;">
            <span>성인 서재 접근 허용</span>
          </label>
        </td>
      </tr>
    `;
  }).join('');
}

export function switchPermissionSessionTab(sessionId) {
  activePermissionSession = sessionId || 'general';

  document.querySelectorAll('.permission-session-tab').forEach(btn => {
    const isActive = btn.getAttribute('data-permission-session') === activePermissionSession;
    btn.classList.toggle('active', isActive);
    btn.style.background = isActive ? 'rgba(168,85,247,0.18)' : 'rgba(255,255,255,0.03)';
    btn.style.color = isActive ? '#fff' : '#cbd5e1';
  });

  document.querySelectorAll('.permission-session-panel').forEach(panel => {
    panel.style.display = panel.id === `permission-session-${activePermissionSession}` ? 'block' : 'none';
  });
}

function bindPermissionEvents() {
  document.querySelectorAll('.permission-chk-adult').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const userId = e.target.getAttribute('data-user-id');
      const hasAdultAccess = e.target.checked;

      try {
        const res = await fetch('/api/admin/permissions/update-adult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: parseInt(userId), has_adult_access: hasAdultAccess })
        });
        const data = await res.json();
        if (!data.success) {
          alert('변경에 실패했습니다: ' + data.error);
          e.target.checked = !hasAdultAccess;
        }
      } catch (err) {
        alert('네트워크 오류가 발생했습니다.');
        e.target.checked = !hasAdultAccess;
      }
    });
  });

  document.querySelectorAll('.permission-chk-category').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const userIdRaw = e.target.getAttribute('data-user-id');
      const libraryIdRaw = e.target.getAttribute('data-library-id');
      const dbType = e.target.getAttribute('data-db-type');
      const hasAccess = e.target.checked;

      const parsedUserId = parseInt(userIdRaw, 10);
      if (!Number.isFinite(parsedUserId)) {
        alert('변경에 실패했습니다: user_id 값이 올바르지 않습니다.');
        e.target.checked = !hasAccess;
        return;
      }

      let payloadLibraryId;
      if (dbType === 'plugin') {
        payloadLibraryId = (libraryIdRaw || '').trim();
      } else {
        const parsedLibraryId = parseInt(libraryIdRaw, 10);
        payloadLibraryId = Number.isFinite(parsedLibraryId) ? parsedLibraryId : null;
      }

      try {
        const res = await fetch('/api/admin/permissions/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: parsedUserId,
            library_id: payloadLibraryId,
            has_access: hasAccess,
            target_db: dbType
          })
        });
        const data = await res.json();
        if (!data.success) {
          alert('변경에 실패했습니다: ' + data.error);
          e.target.checked = !hasAccess;
        }
      } catch (err) {
        alert('네트워크 오류가 발생했습니다.');
        e.target.checked = !hasAccess;
      }
    });
  });
}

window.loadPermissionsMatrix = loadPermissionsMatrix;
window.switchPermissionSessionTab = switchPermissionSessionTab;
