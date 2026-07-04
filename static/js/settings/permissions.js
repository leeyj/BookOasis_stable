// static/js/settings/permissions.js – 권한 관리 탭 모듈
import { state } from '../state.js';

export async function loadPermissionsMatrix() {
  const headerRow = document.getElementById('permissions-table-header');
  const tbody = document.getElementById('permissions-table-body');
  if (!headerRow || !tbody) return;

  const tLoading = window.i18n ? window.i18n.t('common.loading') : '불러오는 중...';
  const tError = window.i18n ? window.i18n.t('common.error') : '오류';
  const tCategoryCol = window.i18n ? window.i18n.t('settings.perm_col_category') : '카테고리 이름 (DB 구분)';
  const tAdultAllow = window.i18n ? window.i18n.t('settings.perm_adult_allow') : '성인도서 접근 허용';
  const tAdultBadge = window.i18n ? window.i18n.t('settings.perm_badge_adult') : '성인';
  const tGeneralBadge = window.i18n ? window.i18n.t('settings.perm_badge_general') : '일반';

  headerRow.innerHTML = `<th style="padding:1rem; text-align:center;">${tLoading}</th>`;
  tbody.innerHTML = '';

  try {
    const res = await fetch('/api/admin/permissions');
    const data = await res.json();

    if (!data.success) {
      headerRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tError}: ${data.error}</th>`;
      return;
    }

    const { users, categories, permissions } = data;

    // 1. Header 렌더링 (구조: [카테고리 (유형)] | [성인도서 허용] | [User 1] | [User 2] ...)
    let headerHTML = `
      <th style="padding:1rem; width:25%;">${tCategoryCol}</th>
    `;
    users.forEach(user => {
      headerHTML += `
        <th style="padding:1rem; text-align:center; min-width:100px;">
          <div style="font-weight:700; color:#fff;">${user.username}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">(${user.role})</div>
        </th>
      `;
    });
    headerRow.innerHTML = headerHTML;

    // 2. Body 렌더링 - 1행: 성인도서 권한 제어 행
    let adultRowHTML = `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.08); background:rgba(168,85,247,0.05);">
        <td style="padding:1rem; font-weight:700; color:#c084fc;">
          <i class="fa-solid fa-hand-holding-hand" style="margin-right:0.5rem;"></i>[${tAdultAllow}]
        </td>
    `;
    users.forEach(user => {
      const isChecked = user.has_adult_access === 1 ? 'checked' : '';
      // admin은 언제나 변경 불가능하고 항상 체크
      const isDisabled = user.username === 'admin' ? 'disabled' : '';
      adultRowHTML += `
        <td style="padding:1rem; text-align:center;">
          <input type="checkbox" class="permission-chk-adult" data-user-id="${user.id}" ${isChecked} ${isDisabled}
                 style="cursor:pointer; width:1.2rem; height:1.2rem; accent-color:#a855f7;">
        </td>
      `;
    });
    adultRowHTML += `</tr>`;

    // 3. Body 렌더링 - 카테고리별 접근 제어 행들
    let categoriesHTML = '';
    categories.forEach(cat => {
      let rowHTML = `
        <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
          <td style="padding:1rem; color:#fff;">
            <i class="fa-solid fa-folder" style="color:#94a3b8; margin-right:0.5rem;"></i>${cat.name}
          </td>
      `;

      users.forEach(user => {
        const key = `${cat.db_type}_${cat.id}`;
        const hasPerm = permissions[user.id] && permissions[user.id][key] !== undefined 
          ? permissions[user.id][key] 
          : true; // 기본값 허용
        
        const isChecked = hasPerm ? 'checked' : '';
        const isDisabled = user.username === 'admin' ? 'disabled' : '';

        rowHTML += `
          <td style="padding:1rem; text-align:center;">
            <input type="checkbox" class="permission-chk-category" 
                   data-user-id="${user.id}" data-library-id="${cat.id}" data-db-type="${cat.db_type}" 
                   ${isChecked} ${isDisabled}
                   style="cursor:pointer; width:1.1rem; height:1.1rem; accent-color:#10b981;">
          </td>
        `;
      });
      rowHTML += `</tr>`;
      categoriesHTML += rowHTML;
    });

    tbody.innerHTML = adultRowHTML + categoriesHTML;

    // 4. 이벤트 바인딩
    bindPermissionEvents();

  } catch (err) {
    const tServerErr = window.i18n ? window.i18n.t('settings.users_server_error') : '서버 요청 중 오류가 발생했습니다.';
    headerRow.innerHTML = `<th style="padding:1rem; color:#ef4444;">${tServerErr}</th>`;
    console.error(err);
  }
}

function bindPermissionEvents() {
  // 성인도서 권한 토글 이벤트
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
          e.target.checked = !hasAdultAccess; // 복원
        }
      } catch (err) {
        alert('네트워크 오류가 발생했습니다.');
        e.target.checked = !hasAdultAccess;
      }
    });
  });

  // 개별 카테고리 권한 토글 이벤트
  document.querySelectorAll('.permission-chk-category').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const userId = e.target.getAttribute('data-user-id');
      const libraryId = e.target.getAttribute('data-library-id');
      const dbType = e.target.getAttribute('data-db-type');
      const hasAccess = e.target.checked;

      try {
        const res = await fetch('/api/admin/permissions/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: parseInt(userId),
            library_id: parseInt(libraryId),
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

// 글로벌 바인딩
window.loadPermissionsMatrix = loadPermissionsMatrix;
