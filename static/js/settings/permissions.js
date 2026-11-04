// static/js/settings/permissions.js – 권한 관리 탭 모듈
let permissionSessionData = null;
let activePermissionSession = 'general';

// 체크박스 하나에서 /update, /bulk-update 등에 보낼 change 페이로드를 만든다
// (기존 개별 change 핸들러의 파싱 로직과 동일 - dbType==='plugin'이면 문자열 ID 그대로 유지)
function buildPermissionChangeFromCheckbox(chk, hasAccess) {
  const userIdRaw = chk.getAttribute('data-user-id');
  const libraryIdRaw = chk.getAttribute('data-library-id');
  const dbType = chk.getAttribute('data-db-type');

  const parsedUserId = parseInt(userIdRaw, 10);
  if (!Number.isFinite(parsedUserId)) return null;

  let payloadLibraryId;
  if (dbType === 'plugin') {
    payloadLibraryId = (libraryIdRaw || '').trim();
    if (!payloadLibraryId) return null;
  } else {
    const parsedLibraryId = parseInt(libraryIdRaw, 10);
    if (!Number.isFinite(parsedLibraryId)) return null;
    payloadLibraryId = parsedLibraryId;
  }

  return { user_id: parsedUserId, library_id: payloadLibraryId, has_access: hasAccess, target_db: dbType };
}

// entries: [{ chk, hasAccess, prevChecked }] - 여러 체크박스 변경을 요청 1건으로 묶어 전송하고,
// 실패한 항목만 되돌린다 (행/열 전체선택, 권한 복사가 공통으로 사용).
async function sendBulkPermissionChanges(entries) {
  const changes = [];
  const validEntries = [];
  entries.forEach(entry => {
    const change = buildPermissionChangeFromCheckbox(entry.chk, entry.hasAccess);
    if (change) {
      changes.push(change);
      validEntries.push(entry);
    }
  });
  if (!changes.length) return;

  try {
    const res = await fetch('/api/admin/permissions/bulk-update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes })
    });
    const data = await res.json();
    if (!data.success) {
      validEntries.forEach(entry => { entry.chk.checked = entry.prevChecked; });
      alert(i18n.t('settings.perm_change_failed', { error: data.error || i18n.t('settings.gen_unknown_error') }));
      return;
    }
    const errors = data.errors || [];
    if (errors.length) {
      errors.forEach(err => {
        const entry = validEntries[err.index];
        if (entry) entry.chk.checked = entry.prevChecked;
      });
      alert(i18n.t('settings.perm_bulk_partial_fail', { failed: errors.length, applied: data.applied || 0 }));
    }
  } catch (err) {
    validEntries.forEach(entry => { entry.chk.checked = entry.prevChecked; });
    alert(i18n.t('settings.perm_network_error'));
  }
}

// 체크박스 목록을 받아 전체선택/해제 상태를 뒤집고, 실제로 바뀐 것만 모아 배치 전송
function togglePermissionCheckboxGroup(checkboxes) {
  const list = Array.from(checkboxes);
  if (!list.length) return;
  const shouldCheck = !list.every(chk => chk.checked);

  const entries = [];
  list.forEach(chk => {
    if (chk.checked === shouldCheck) return;
    entries.push({ chk, hasAccess: shouldCheck, prevChecked: chk.checked });
    chk.checked = shouldCheck;
  });
  if (entries.length) sendBulkPermissionChanges(entries);
}

function closeCopyPermissionPanel() {
  document.querySelectorAll('.permission-copy-panel').forEach(p => p.remove());
}

function openCopyPermissionPanel(triggerBtn) {
  closeCopyPermissionPanel();

  const sourceUserId = triggerBtn.getAttribute('data-user-id');
  const table = triggerBtn.closest('table');
  if (!table || !permissionSessionData) return;

  const users = (permissionSessionData.users || [])
    .filter(u => u.username !== 'admin' && String(u.id) !== String(sourceUserId));
  if (!users.length) return;

  const panel = document.createElement('div');
  panel.className = 'permission-copy-panel';
  panel.style.cssText = 'position:absolute; z-index:1000; background: rgba(20,22,30,0.98); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:0.75rem; box-shadow:0 8px 24px rgba(0,0,0,0.4); min-width:200px; max-height:260px; overflow-y:auto;';

  const rect = triggerBtn.getBoundingClientRect();
  panel.style.top = `${rect.bottom + window.scrollY + 4}px`;
  panel.style.left = `${rect.left + window.scrollX}px`;

  const listHTML = users.map(u => `
    <label style="display:flex; align-items:center; gap:0.4rem; padding:0.2rem 0; color: var(--app-text-primary); font-size:0.85rem; cursor:pointer;">
      <input type="checkbox" class="permission-copy-target" value="${u.id}">
      <span>${u.username}</span>
    </label>
  `).join('');

  panel.innerHTML = `
    <div style="font-size:0.78rem; font-weight:700; margin-bottom:0.5rem; color: var(--app-text-primary);">${i18n.t('settings.perm_copy_target')}</div>
    ${listHTML}
    <button type="button" class="permission-copy-apply" style="margin-top:0.6rem; width:100%; padding:0.4rem; border-radius:6px; border:none; background: var(--app-accent, #a855f7); color:#fff; font-weight:700; cursor:pointer;">${i18n.t('settings.perm_apply')}</button>
  `;

  document.body.appendChild(panel);

  panel.querySelector('.permission-copy-apply').addEventListener('click', () => {
    const targetIds = Array.from(panel.querySelectorAll('.permission-copy-target:checked')).map(chk => chk.value);
    closeCopyPermissionPanel();
    if (!targetIds.length) return;
    applyPermissionCopy(table, sourceUserId, targetIds);
  });
}

function applyPermissionCopy(table, sourceUserId, targetUserIds) {
  const sourceCheckboxes = table.querySelectorAll(`.permission-chk-category[data-user-id="${sourceUserId}"]`);
  const entries = [];

  sourceCheckboxes.forEach(sourceChk => {
    const libraryId = sourceChk.getAttribute('data-library-id');
    const dbType = sourceChk.getAttribute('data-db-type');
    const hasAccess = sourceChk.checked;

    targetUserIds.forEach(targetUserId => {
      const targetChk = table.querySelector(
        `.permission-chk-category[data-user-id="${targetUserId}"][data-library-id="${libraryId}"][data-db-type="${dbType}"]`
      );
      if (!targetChk || targetChk.disabled || targetChk.checked === hasAccess) return;
      entries.push({ chk: targetChk, hasAccess, prevChecked: targetChk.checked });
      targetChk.checked = hasAccess;
    });
  });

  if (entries.length) {
    sendBulkPermissionChanges(entries);
  } else {
    alert(i18n.t('settings.perm_nothing_to_change'));
  }
}

function applyPermissionUserFilter(input) {
  const panel = input.closest('.permission-session-panel');
  const table = panel && panel.querySelector('table');
  if (!table) return;
  const term = input.value.trim().toLowerCase();

  table.querySelectorAll('th[data-username], td[data-username]').forEach(cell => {
    const match = !term || (cell.getAttribute('data-username') || '').toLowerCase().includes(term);
    cell.style.display = match ? '' : 'none';
  });
}

function applyPermissionCategoryFilter(input) {
  const panel = input.closest('.permission-session-panel');
  const table = panel && panel.querySelector('table');
  if (!table) return;
  const term = input.value.trim().toLowerCase();

  table.querySelectorAll('tbody tr[data-category-name]').forEach(row => {
    const match = !term || (row.getAttribute('data-category-name') || '').toLowerCase().includes(term);
    row.style.display = match ? '' : 'none';
  });
}

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

  document.addEventListener('click', (event) => {
    const colToggleBtn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.permission-col-toggle-all')
      : null;
    if (colToggleBtn) {
      event.preventDefault();
      const userId = colToggleBtn.getAttribute('data-user-id');
      const table = colToggleBtn.closest('table');
      if (table) {
        togglePermissionCheckboxGroup(table.querySelectorAll(`.permission-chk-category[data-user-id="${userId}"]:not(:disabled)`));
      }
      return;
    }

    const rowToggleBtn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.permission-row-toggle-all')
      : null;
    if (rowToggleBtn) {
      event.preventDefault();
      const libraryId = rowToggleBtn.getAttribute('data-library-id');
      const dbType = rowToggleBtn.getAttribute('data-db-type');
      const table = rowToggleBtn.closest('table');
      if (table) {
        togglePermissionCheckboxGroup(table.querySelectorAll(`.permission-chk-category[data-library-id="${libraryId}"][data-db-type="${dbType}"]:not(:disabled)`));
      }
      return;
    }

    const copyBtn = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.permission-copy-btn')
      : null;
    if (copyBtn) {
      event.preventDefault();
      event.stopPropagation();
      openCopyPermissionPanel(copyBtn);
      return;
    }

    const openPanel = document.querySelector('.permission-copy-panel');
    if (openPanel && !openPanel.contains(event.target)) {
      closeCopyPermissionPanel();
    }
  }, true);

  document.addEventListener('input', (event) => {
    if (event.target && event.target.classList && event.target.classList.contains('permission-user-filter')) {
      applyPermissionUserFilter(event.target);
    } else if (event.target && event.target.classList && event.target.classList.contains('permission-category-filter')) {
      applyPermissionCategoryFilter(event.target);
    }
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
  const downloadBody = document.getElementById('permissions-download-table-body');
  const contentRatingBody = document.getElementById('permissions-content-rating-table-body');
  const audiobookAccessBody = document.getElementById('permissions-audiobook-access-table-body');
  const videoAccessBody = document.getElementById('permissions-video-access-table-body');
  if (!generalHeaderRow || !generalBody || !adultBody || !audiobookHeaderRow || !audiobookBody || !videoHeaderRow || !videoBody || !downloadBody || !contentRatingBody) return;

  const tLoading = window.i18n ? window.i18n.t('common.loading') : '불러오는 중...';
  const tError = window.i18n ? window.i18n.t('common.error') : '오류';

  generalHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  audiobookHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  videoHeaderRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  generalBody.innerHTML = '';
  adultBody.innerHTML = '';
  audiobookBody.innerHTML = '';
  videoBody.innerHTML = '';
  downloadBody.innerHTML = '';
  contentRatingBody.innerHTML = '';

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
    if (audiobookAccessBody) audiobookAccessBody.innerHTML = renderMenuAccessBody(users, 'has_audiobook_access', 'audiobook', 'settings.perm_col_audiobook_access');
    if (videoAccessBody) videoAccessBody.innerHTML = renderMenuAccessBody(users, 'has_video_access', 'video', 'settings.perm_col_video_access');
    downloadBody.innerHTML = renderDownloadBody(users);
    contentRatingBody.innerHTML = renderContentRatingBody(users);

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
      // 서버 이름은 한국어 고정이라 번역 키(settings.perm_tab_<id>)를 먼저 쓰고, 키가 없는 세션만 서버 이름
      btn.textContent = i18n.t(`settings.perm_tab_${sessionId}`, {}, sessionTitleMap.get(sessionId));
    }
  });
}

function renderMatrixHeader(headerRow, users) {
  let headerHTML = `<th style="padding:1rem; width:25%;">${i18n.t('settings.perm_col_category_name')}</th>`;
  users.forEach(user => {
    const isAdmin = user.username === 'admin';
    headerHTML += `
      <th data-username="${user.username}" style="padding:1rem; text-align:center; min-width:100px;">
        <div style="font-weight:700; color: var(--app-text-primary);">${user.username}</div>
        <div style="font-size:0.75rem; color: var(--app-text-muted); margin-bottom:${isAdmin ? '0' : '0.4rem'};">(${user.role})</div>
        ${isAdmin ? '' : `
        <div style="display:flex; gap:0.3rem; justify-content:center; flex-wrap:wrap;">
          <button type="button" class="permission-col-toggle-all" data-user-id="${user.id}"
                  style="font-size:0.68rem; padding:0.15rem 0.5rem; border-radius:4px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.05); color: var(--app-text-muted); cursor:pointer;">${i18n.t('settings.perm_toggle_all')}</button>
          <button type="button" class="permission-copy-btn" data-user-id="${user.id}" title="${i18n.t('settings.perm_copy_title')}"
                  style="font-size:0.68rem; padding:0.15rem 0.5rem; border-radius:4px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.05); color: var(--app-text-muted); cursor:pointer;">
            <i class="lc lc-copy"></i>
          </button>
        </div>
        `}
      </th>
    `;
  });
  headerRow.innerHTML = headerHTML;
}

function renderMatrixBody(users, categories, permissions, targetDb) {
  return (categories || []).map(cat => {
    let rowHTML = `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);" data-category-name="${cat.name}">
        <td style="padding:1rem; color: var(--app-text-primary);">
          <i class="lc lc-folder" style="color: var(--app-text-muted); margin-right:0.5rem;"></i>${cat.name}
          <button type="button" class="permission-row-toggle-all" data-library-id="${cat.id}" data-db-type="${cat.db_type || targetDb}"
                  style="margin-left:0.5rem; font-size:0.65rem; padding:0.1rem 0.4rem; border-radius:4px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.05); color: var(--app-text-muted); cursor:pointer;">${i18n.t('settings.perm_toggle_all')}</button>
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
        <td data-username="${user.username}" style="padding:1rem; text-align:center;">
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
          <label style="display:inline-flex; align-items:center; gap:0.5rem; color:var(--app-accent-hover); font-weight:700;">
            <input type="checkbox" class="permission-chk-adult" data-user-id="${user.id}" ${isChecked} ${isDisabled}
                   style="cursor:pointer; width:1.2rem; height:1.2rem; accent-color:var(--app-accent);">
            <span>${i18n.t('settings.perm_col_adult_access')}</span>
          </label>
        </td>
      </tr>
    `;
  }).join('');
}

// 오디오북·영상 메뉴 전체 허용 스위치 (users.has_audiobook_access / has_video_access)
function renderMenuAccessBody(users, field, kind, labelKey) {
  return users.map(user => {
    const isChecked = Number(user[field]) === 1 ? 'checked' : '';
    const isDisabled = user.role === 'admin' ? 'disabled' : '';
    return `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="padding:0.9rem 1rem; color: var(--app-text-primary); font-weight:700;">${user.username}</td>
        <td style="padding:0.9rem 1rem; text-align:center; color: var(--app-text-muted);">${user.role}</td>
        <td style="padding:0.9rem 1rem; text-align:center;">
          <label style="display:inline-flex; align-items:center; gap:0.5rem; color:var(--app-accent-hover); font-weight:700;">
            <input type="checkbox" class="permission-chk-menu-access" data-kind="${kind}" data-user-id="${user.id}" ${isChecked} ${isDisabled}
                   style="cursor:pointer; width:1.2rem; height:1.2rem; accent-color:var(--app-accent);">
            <span>${i18n.t(labelKey)}</span>
          </label>
        </td>
      </tr>
    `;
  }).join('');
}

function renderDownloadBody(users) {
  return users.map(user => {
    const isChecked = user.has_download_access === 1 ? 'checked' : '';
    const isDisabled = user.username === 'admin' ? 'disabled' : '';
    return `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="padding:0.9rem 1rem; color: var(--app-text-primary); font-weight:700;">${user.username}</td>
        <td style="padding:0.9rem 1rem; text-align:center; color: var(--app-text-muted);">${user.role}</td>
        <td style="padding:0.9rem 1rem; text-align:center;">
          <label style="display:inline-flex; align-items:center; gap:0.5rem; color:var(--app-accent-hover); font-weight:700;">
            <input type="checkbox" class="permission-chk-download" data-user-id="${user.id}" ${isChecked} ${isDisabled}
                   style="cursor:pointer; width:1.2rem; height:1.2rem; accent-color:var(--app-accent);">
            <span>${i18n.t('settings.perm_col_download')}</span>
          </label>
        </td>
      </tr>
    `;
  }).join('');
}

function renderContentRatingBody(users) {
  return users.map(user => {
    const isAdmin = user.role === 'admin';
    const isDisabled = isAdmin ? 'disabled' : '';
    const currentLevel = isAdmin
      ? 20
      : Number(user.content_rating_max !== undefined && user.content_rating_max !== null ? user.content_rating_max : 18);
    return `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
        <td style="padding:0.9rem 1rem; color: var(--app-text-primary); font-weight:700;">${user.username}</td>
        <td style="padding:0.9rem 1rem; text-align:center; color: var(--app-text-muted);">${user.role}</td>
        <td style="padding:0.9rem 1rem; text-align:center;">
          <select class="permission-select-content-rating" data-user-id="${user.id}" ${isDisabled}
                  style="cursor:pointer; padding:0.4rem 0.7rem; border-radius:6px; border:1px solid rgba(255,255,255,0.15); background: rgba(var(--app-panel-rgb), 0.6); color: var(--app-text-primary); font-weight:700;">
            <option value="0" ${currentLevel === 0 ? 'selected' : ''}>${i18n.t('settings.perm_rating_all')}</option>
            <option value="15" ${currentLevel === 15 ? 'selected' : ''}>${i18n.t('settings.perm_rating_15')}</option>
            <option value="18" ${currentLevel === 18 ? 'selected' : ''}>${i18n.t('settings.perm_rating_18')}</option>
            <option value="19" ${currentLevel === 19 ? 'selected' : ''}>${i18n.t('settings.perm_rating_19')}</option>
            <option value="20" ${currentLevel === 20 ? 'selected' : ''}>${i18n.t('settings.perm_rating_20')}</option>
          </select>
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
          alert(i18n.t('settings.perm_change_failed', { error: data.error }));
          e.target.checked = !hasAdultAccess;
        }
      } catch (err) {
        alert(i18n.t('settings.perm_network_error'));
        e.target.checked = !hasAdultAccess;
      }
    });
  });

  document.querySelectorAll('.permission-chk-menu-access').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const userId = e.target.getAttribute('data-user-id');
      const kind = e.target.getAttribute('data-kind');
      const allowed = e.target.checked;
      const field = kind === 'video' ? 'has_video_access' : 'has_audiobook_access';

      try {
        const res = await fetch(`/api/admin/permissions/update-${kind}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: parseInt(userId), [field]: allowed })
        });
        const data = await res.json();
        if (!data.success) {
          alert(i18n.t('settings.perm_change_failed', { error: data.error }));
          e.target.checked = !allowed;
        }
      } catch (err) {
        alert(i18n.t('settings.perm_network_error'));
        e.target.checked = !allowed;
      }
    });
  });

  document.querySelectorAll('.permission-chk-download').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const userId = e.target.getAttribute('data-user-id');
      const hasDownloadAccess = e.target.checked;

      try {
        const res = await fetch('/api/admin/permissions/update-download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: parseInt(userId), has_download_access: hasDownloadAccess })
        });
        const data = await res.json();
        if (!data.success) {
          alert(i18n.t('settings.perm_change_failed', { error: data.error }));
          e.target.checked = !hasDownloadAccess;
        }
      } catch (err) {
        alert(i18n.t('settings.perm_network_error'));
        e.target.checked = !hasDownloadAccess;
      }
    });
  });

  document.querySelectorAll('.permission-select-content-rating').forEach(sel => {
    sel.addEventListener('change', async (e) => {
      const userId = e.target.getAttribute('data-user-id');
      const newLevel = e.target.value;
      const prevLevel = e.target.dataset.prevValue !== undefined ? e.target.dataset.prevValue : newLevel;

      try {
        const res = await fetch('/api/admin/permissions/update-content-rating', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: parseInt(userId), content_rating_max: parseInt(newLevel) })
        });
        const data = await res.json();
        if (!data.success) {
          alert(i18n.t('settings.perm_change_failed', { error: data.error }));
          e.target.value = prevLevel;
        } else {
          e.target.dataset.prevValue = newLevel;
        }
      } catch (err) {
        alert(i18n.t('settings.perm_network_error'));
        e.target.value = prevLevel;
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
        alert(i18n.t('settings.perm_change_failed', { error: i18n.t('settings.perm_bad_user_id') }));
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
          alert(i18n.t('settings.perm_change_failed', { error: data.error }));
          e.target.checked = !hasAccess;
        }
      } catch (err) {
        alert(i18n.t('settings.perm_network_error'));
        e.target.checked = !hasAccess;
      }
    });
  });
}

window.loadPermissionsMatrix = loadPermissionsMatrix;
window.switchPermissionSessionTab = switchPermissionSessionTab;
