// crud_controller.js – 카테고리 생성/수정/삭제, 스캔/중단, 보관함 이관 및 폼 UI 조작
import { state } from '../state.js';
import * as api from '../api.js';
import { selectCategory } from '../tab_media_library.js';
import { currentTargetLibrary } from './context_menu.js';
import { updateRemoteWarning, enableVFSCheckForRemote, loadGdriveCopyRemotes } from './path_browser.js';
import { loadVideoLibraryView } from '../video_library.js';

async function reloadLibrarySidebar() {
  if (state.currentLibraryType === 'video') {
    await loadVideoLibraryView();
  } else if (typeof window.loadLibraries === 'function') {
    await window.loadLibraries();
  }
}

const MAX_LIBRARY_NAME_LENGTH = 25;
const MAX_LIBRARY_PATHS = 20;
const MAX_LIBRARY_PATH_LINE_LENGTH = 1024;
const MAX_LIBRARY_PATH_TEXT_LENGTH = 8192;

function populateLibraryGroupSelect(selectedGroupId = '') {
  const select = document.getElementById('library-form-group-id');
  if (!select) return;
  const selected = selectedGroupId == null ? '' : String(selectedGroupId);
  select.innerHTML = '<option value="">미분류</option>' + (state.libraryGroups || []).map((group) => {
    const groupId = String(group.id);
    const safeName = String(group.name || '')
      .replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<option value="${groupId}"${groupId === selected ? ' selected' : ''}>${safeName}</option>`;
  }).join('');
  select.value = selected;
}

export async function triggerAddLibraryGroup() {
  const name = prompt('새 그룹 이름을 입력하세요.');
  if (name === null) return;
  const cleanName = name.trim();
  if (!cleanName || cleanName.length > 25) {
    alert('그룹 이름은 1~25자로 입력해 주세요.');
    return;
  }
  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('name', cleanName);
  const result = await api.addLibraryGroup(formData);
  if (!result.success) {
    alert(result.error || '그룹을 추가하지 못했습니다.');
    return;
  }
  await window.loadLibraries?.();
}

export async function triggerEditLibraryGroup(group) {
  const name = prompt('그룹 이름을 입력하세요.', group?.name || '');
  if (name === null) return;
  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('id', group.id);
  formData.append('name', name.trim());
  const result = await api.editLibraryGroup(formData);
  if (!result.success) {
    alert(result.error || '그룹 이름을 변경하지 못했습니다.');
    return;
  }
  await window.loadLibraries?.();
}

export async function triggerDeleteLibraryGroup(group) {
  if (!confirm(`'${group?.name || ''}' 그룹을 삭제할까요? 하위 카테고리는 미분류로 이동합니다.`)) return;
  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('id', group.id);
  const result = await api.deleteLibraryGroup(formData);
  if (!result.success) {
    alert(result.error || '그룹을 삭제하지 못했습니다.');
    return;
  }
  await window.loadLibraries?.();
}

export function triggerAddLibrary() {
  console.log('[Category-CRUD] triggerAddLibrary() 진입');
  const modal = document.getElementById('library-form-modal');
  const title = document.getElementById('library-modal-title');
  const form = document.getElementById('library-crud-form');
  
  console.log('[Category-CRUD] modal 검색 결과:', modal, 'form 검색 결과:', form);
  if (!modal || !form) {
    console.error('[Category-CRUD] Error: library-form-modal 또는 library-crud-form 엘리먼트를 찾을 수 없습니다.');
    return;
  }
  form.reset();
  document.getElementById('library-form-id').value = '';
  populateLibraryGroupSelect('');
  const remoteEl = document.getElementById('library-form-remote');
  if (remoteEl) {
    remoteEl.checked = false;
    remoteEl.dispatchEvent(new Event('change'));
  }
  updateAdvancedStatusDot(false);
  const advancedDetailsEl = document.getElementById('library-form-advanced-details');
  if (advancedDetailsEl) advancedDetailsEl.open = false;

  // 이동 버튼 숨김
  const moveBtn = document.getElementById('library-form-move-btn');
  if (moveBtn) moveBtn.style.display = 'none';

  // Rclone RC URL 초기화 및 숨김
  const rcloneUrlEl = document.getElementById('library-form-rclone-url');
  if (rcloneUrlEl) rcloneUrlEl.value = '';
  const rcloneGroup = document.getElementById('library-form-rclone-url-group');
  if (rcloneGroup) rcloneGroup.style.display = 'none';

  // 아이콘 및 컬러 칩 초기화
  const iconInput = document.getElementById('library-form-icon');
  if (iconInput) iconInput.value = 'fa-book';
  document.querySelectorAll('.category-icon-selector .icon-option').forEach(el => {
    if (el.dataset.icon === 'fa-book') el.classList.add('active');
    else el.classList.remove('active');
  });
  const colorInput = document.getElementById('library-form-color');
  if (colorInput) colorInput.value = '#94a3b8';
  document.querySelectorAll('.category-color-selector .color-option').forEach(el => {
    if (el.dataset.color === '#94a3b8') el.classList.add('active');
    else el.classList.remove('active');
  });
  updateAppearancePreview('fa-book', '#94a3b8');

  const hideCoverEl = document.getElementById('library-form-hide-cover');
  if (hideCoverEl) hideCoverEl.checked = false;

  const gdriveCopyDestPathEl = document.getElementById('library-form-gdrive-copy-dest-path');
  if (gdriveCopyDestPathEl) gdriveCopyDestPathEl.value = '';
  loadGdriveCopyRemotes('');

  selectCategoryType('local');

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
      updateRemoteWarning();
      updateAdvancedStatusDot(e.target.checked);
      if (e.target.checked) {
        enableVFSCheckForRemote();
      }
    });
  }

  if (title) {
    title.innerText = (window.i18n && typeof i18n.t === 'function') ? i18n.t('category.add_title') : '카테고리 추가';
  }
  console.log('[Category-CRUD] modal.style.display를 flex로 변경합니다. (이전값: ' + modal.style.display + ')');
  modal.style.display = 'flex';
}

export async function triggerEditLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  if (currentTargetLibrary.type === 'group') {
    await triggerEditLibraryGroup(currentTargetLibrary);
    return;
  }
  
  const modal = document.getElementById('library-form-modal');
  const title = document.getElementById('library-modal-title');
  const form = document.getElementById('library-crud-form');
  
  if (!modal || !form) return;

  // 이동 버튼 노출 및 텍스트 갱신
  const moveBtn = document.getElementById('library-form-move-btn');
  if (moveBtn) {
    moveBtn.style.display = 'block';
    if (state.currentLibraryType === 'general') {
      moveBtn.innerText = '성인도서로 이동';
    } else {
      moveBtn.innerText = '일반도서로 이동';
    }
  }
  
  const id = currentTargetLibrary.id;
  const name = currentTargetLibrary.name;
  const libraryItem = document.querySelector(`[data-type="custom"][data-id="${id}"]`);
 
  document.getElementById('library-form-id').value = id;
  document.getElementById('library-form-name').value = name;
  const groupIdVal = libraryItem?.dataset?.groupId || '';
  populateLibraryGroupSelect(groupIdVal);
  
  const pathVal = libraryItem?.dataset?.path || '';
  document.getElementById('library-form-path').value = pathVal;

  const categoryTypeVal = libraryItem?.dataset?.categoryType || 'local';
  selectCategoryType(categoryTypeVal);

  const isRemoteVal = libraryItem?.dataset?.remote || '0';
  const remoteEl = document.getElementById('library-form-remote');
  if (remoteEl) remoteEl.checked = (isRemoteVal === '1');
  updateAdvancedStatusDot(isRemoteVal === '1');
  const advancedDetailsEl = document.getElementById('library-form-advanced-details');
  if (advancedDetailsEl) advancedDetailsEl.open = (isRemoteVal === '1');

  // Rclone RC URL 바인딩 및 표시 토글
  const rcloneUrlVal = libraryItem?.dataset?.rcloneUrl || '';
  const rcloneUrlEl = document.getElementById('library-form-rclone-url');
  if (rcloneUrlEl) rcloneUrlEl.value = rcloneUrlVal;

  const rcloneGroup = document.getElementById('library-form-rclone-url-group');
  if (rcloneGroup) {
    rcloneGroup.style.display = (isRemoteVal === '1') ? 'block' : 'none';
  }

  // 서버사이드 복사 대상 리모트/목적지 경로 바인딩
  const gdriveCopyRemoteVal = libraryItem?.dataset?.gdriveCopyRemote || '';
  const gdriveCopyDestPathVal = libraryItem?.dataset?.gdriveCopyDestPath || '';
  const gdriveCopyDestPathEl = document.getElementById('library-form-gdrive-copy-dest-path');
  if (gdriveCopyDestPathEl) gdriveCopyDestPathEl.value = gdriveCopyDestPathVal;
  loadGdriveCopyRemotes(gdriveCopyRemoteVal);

  // 아이콘 및 컬러 칩 데이터 바인딩
  const iconVal = libraryItem?.dataset?.icon || 'fa-book';
  const colorVal = libraryItem?.dataset?.color || '#94a3b8';
  
  const iconInput = document.getElementById('library-form-icon');
  if (iconInput) iconInput.value = iconVal;
  document.querySelectorAll('.category-icon-selector .icon-option').forEach(el => {
    if (el.dataset.icon === iconVal) el.classList.add('active');
    else el.classList.remove('active');
  });

  const colorInput = document.getElementById('library-form-color');
  if (colorInput) colorInput.value = colorVal;
  document.querySelectorAll('.category-color-selector .color-option').forEach(el => {
    if (el.dataset.color === colorVal) el.classList.add('active');
    else el.classList.remove('active');
  });
  updateAppearancePreview(iconVal, colorVal);

  const hideCoverVal = libraryItem?.dataset?.hideCover || '0';
  const hideCoverEl = document.getElementById('library-form-hide-cover');
  if (hideCoverEl) hideCoverEl.checked = (hideCoverVal === '1');

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
      updateRemoteWarning();
      if (e.target.checked) {
        enableVFSCheckForRemote();
      }
    });
  }

  updateRemoteWarning();

  title.innerText = i18n.t('category.edit_title', {id: id});
  modal.style.display = 'flex';
}

export async function triggerDeleteLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  if (currentTargetLibrary.type === 'group') {
    await triggerDeleteLibraryGroup(currentTargetLibrary);
    return;
  }
  const confirmDel = confirm(i18n.t('category.delete_confirm', {name: currentTargetLibrary.name}));
  if (!confirmDel) return;

  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('id', currentTargetLibrary.id);

  if (typeof window.showGlobalLoadingSpinner === 'function') {
    window.showGlobalLoadingSpinner(`'${currentTargetLibrary.name}' 카테고리와 관련 도서 데이터를 안전하게 삭제 중입니다...\n잠시만 기다려 주세요.`);
  }

  try {
    const data = await api.deleteLibrary(formData);
    if (data.success) {
      if (typeof window.hideGlobalLoadingSpinner === 'function') {
        window.hideGlobalLoadingSpinner();
      }
      alert(data.message);
      await reloadLibrarySidebar();

      if (String(state.currentLibraryId) === String(currentTargetLibrary.id)) {
        selectCategory('history');
      }
    } else {
      if (typeof window.hideGlobalLoadingSpinner === 'function') {
        window.hideGlobalLoadingSpinner();
      }
      alert(i18n.t('category.delete_fail', {error: data.error}));
    }
  } catch (e) {
    if (typeof window.hideGlobalLoadingSpinner === 'function') {
      window.hideGlobalLoadingSpinner();
    }
    console.error('삭제 API 호출 오류:', e);
    alert(i18n.t('category.server_error'));
  }
}

export async function triggerScanLibrary(force = false) {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  const id = currentTargetLibrary.id;
  const name = currentTargetLibrary.name;
  const modeText = force ? i18n.t('category.force_scan_started', {name: name}) : i18n.t('category.scan_started', {name: name});

  try {
    const data = await api.triggerLibraryScan(state.currentLibraryType, id, force);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(modeText, 'success');
      } else {
        alert(`${modeText} : ${data.message}`);
      }
    } else {
      alert(i18n.t('category.scan_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('스캔 요청 중 오류 발생:', e);
    alert(i18n.t('category.server_error'));
  }
}

export async function triggerScanLibraryCovers() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  const id = currentTargetLibrary.id;
  const name = currentTargetLibrary.name;

  try {
    const data = await api.triggerLibraryCoversScan(state.currentLibraryType, id);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('category.cover_scan_started', {name: name}), 'success');
      } else {
        alert(`${i18n.t('category.cover_scan_started', {name: name})} : ${data.message}`);
      }
    } else {
      alert(i18n.t('category.scan_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('스캔 요청 중 오류 발생:', e);
    alert(i18n.t('category.server_error'));
  }
}

export async function triggerCancelScanLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  const id = currentTargetLibrary.id;
  const name = currentTargetLibrary.name;

  try {
    const data = await api.cancelLibraryScan(state.currentLibraryType, id);
    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('category.cancel_scan_req', {name: name}), 'info');
      } else {
        alert(data.message);
      }
    } else {
      alert(i18n.t('category.cancel_fail', {error: data.error}));
    }
  } catch (e) {
    console.error('중단 요청 중 오류 발생:', e);
    alert(i18n.t('category.server_error'));
  }
}

export function closeLibraryModal() {
  const modal = document.getElementById('library-form-modal');
  if (modal) modal.style.display = 'none';
}

export async function submitLibraryForm(event) {
  if (event) {
    event.preventDefault();
    if (typeof event.stopPropagation === 'function') event.stopPropagation();
  }
  console.log('[Category-CRUD] submitLibraryForm() 진입 완료. (페이지 새로고침 방지 적용)');
  const form = document.getElementById('library-crud-form');
  const formData = new FormData(form);

  const name = String(formData.get('name') || '').trim();
  const physicalPathRaw = String(formData.get('physical_path') || '').replace(/\r/g, '');
  const targetPaths = physicalPathRaw.split('\n').map(p => p.trim()).filter(Boolean);

  if (!name) {
    alert(i18n.t('category.name_required'));
    return;
  }
  if (name.length > MAX_LIBRARY_NAME_LENGTH) {
    alert(`카테고리 이름은 최대 ${MAX_LIBRARY_NAME_LENGTH}자까지 입력할 수 있습니다.`);
    return;
  }
  if (physicalPathRaw.length > MAX_LIBRARY_PATH_TEXT_LENGTH) {
    alert(`경로 입력 길이는 최대 ${MAX_LIBRARY_PATH_TEXT_LENGTH}자까지 허용됩니다.`);
    return;
  }
  if (targetPaths.length > MAX_LIBRARY_PATHS) {
    alert(`경로는 최대 ${MAX_LIBRARY_PATHS}개까지 입력할 수 있습니다.`);
    return;
  }
  if (targetPaths.some(p => p.length > MAX_LIBRARY_PATH_LINE_LENGTH)) {
    alert(`각 경로는 최대 ${MAX_LIBRARY_PATH_LINE_LENGTH}자까지 허용됩니다.`);
    return;
  }

  formData.append('type', state.currentLibraryType);
  
  const isRemoteChecked = document.getElementById('library-form-remote')?.checked;
  formData.set('is_remote', isRemoteChecked ? '1' : '0');
  const hideCoverChecked = document.getElementById('library-form-hide-cover')?.checked;
  formData.set('hide_cover', hideCoverChecked ? '1' : '0');

  const id = formData.get('id');
  const isEdit = !!id;

  try {
    const submitBtn = document.getElementById('library-form-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = i18n.t('category.processing');
    }

    const submitRequest = async (payload) => {
      if (isEdit) {
        return api.editLibrary(payload);
      }
      return api.addLibrary(payload);
    };

    let result = await submitRequest(formData);
    console.log('[Category-CRUD] API 저장 응답 결과:', result);

    if (result && result.needs_confirmation) {
      const confirmMsg = result.confirm_message || result.error || i18n.t('category.save_error', {error: ''});
      if (!confirm(confirmMsg)) {
        return;
      }
      formData.set('confirm_media_mismatch', '1');
      result = await submitRequest(formData);
      console.log('[Category-CRUD] 미디어 미스매치 확정 후 API 재요청 결과:', result);
    }

    if (result.success) {
      console.log('[Category-CRUD] 카테고리 저장 성공! 모달을 즉시 닫고 목록을 새로고침합니다.');
      closeLibraryModal();
      if (typeof showToast === 'function') {
        showToast(result.message, 'success');
      } else {
        alert(result.message);
      }
      await reloadLibrarySidebar();
      if (isEdit && String(state.currentLibraryId) === String(id)) {
        selectCategory(String(id), true);
      }
    } else {
      console.error('[Category-CRUD] 카테고리 저장 실패:', result ? result.error : '알 수 없는 오류');
      const errDetail = result && result.error ? result.error : '오류가 발생했습니다.';
      alert(`[카테고리 저장 오류]\n${errDetail}`);
    }
  } catch (e) {
    console.error('라이브러리 저장 예외 발생:', e);
    const errDetail = e && e.message ? e.message : String(e);
    alert(`[서버 통신/저장 예외]\n${errDetail}`);
  } finally {
    const submitBtn = document.getElementById('library-form-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = i18n.t('category.save');
    }
  }
}

export async function triggerMoveLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  
  const fromType = state.currentLibraryType;
  const toType = (fromType === 'general') ? 'adult' : 'general';
  
  const targetLabel = (toType === 'general') ? '일반도서' : '성인도서';
  const confirmMsg = `정말로 이 카테고리를 [${targetLabel}] 보관함으로 이동하시겠습니까?\n이동하는 동안 데이터베이스 정밀 이전 작업을 위해 전체 화면이 잠시 잠깁니다.`;
  if (!confirm(confirmMsg)) return;
  
  const modal = document.getElementById('library-form-modal');
  if (modal) modal.style.display = 'none';
  
  const dimmer = document.getElementById('migration-dimmer-modal');
  if (dimmer) dimmer.style.display = 'flex';
  
  const formData = new FormData();
  formData.append('id', currentTargetLibrary.id);
  formData.append('from_type', fromType);
  formData.append('to_type', toType);
  
  const preventClose = (e) => {
    e.preventDefault();
    e.returnValue = '';
  };
  window.addEventListener('beforeunload', preventClose);
  
  try {
    const response = await fetch('/api/media/libraries/move', {
      method: 'POST',
      body: formData
    });
    const data = await response.json();
    
    if (data.success) {
      alert(data.message || '카테고리가 성공적으로 이동되었습니다.');
      
      state.currentLibraryType = toType;
      
      document.querySelectorAll('.btn-toggle').forEach(btn => btn.classList.remove('active'));
      if (toType === 'general') {
        const btnGen = document.getElementById('btn-lib-general');
        if (btnGen) btnGen.classList.add('active');
      } else {
        const btnAd = document.getElementById('btn-lib-adult');
        if (btnAd) btnAd.classList.add('active');
      }
      
      if (typeof window.loadLibraries === 'function') {
        await window.loadLibraries();
      }
      selectCategory('home');
    } else {
      alert('이동 실패: ' + (data.error || '알 수 없는 오류'));
    }
  } catch (e) {
    console.error('이관 API 오류:', e);
    alert('서버 통신 실패 또는 타임아웃이 발생했습니다.');
  } finally {
    window.removeEventListener('beforeunload', preventClose);
    if (dimmer) dimmer.style.display = 'none';
  }
}

export function selectCategoryType(type) {
  document.querySelectorAll('.category-type-selector .category-type-btn').forEach(el => el.classList.remove('active'));
  const btn = document.querySelector(`.category-type-selector .category-type-btn[data-type="${type}"]`);
  if (btn) btn.classList.add('active');

  const typeInput = document.getElementById('library-form-category-type');
  if (typeInput) typeInput.value = type;

  const pathLabel = document.getElementById('library-form-path-label');
  const pathTextarea = document.getElementById('library-form-path');
  const btnBrowse = document.getElementById('btn-browse-paths');
  const btnTest = document.getElementById('btn-test-gdrive-links');
  const remoteRow = document.getElementById('library-form-remote-row');
  const rcloneGroup = document.getElementById('library-form-rclone-url-group');
  const gdriveCopyGroup = document.getElementById('library-form-gdrive-copy-group');

  if (type === 'gdrive') {
      if (pathLabel) pathLabel.textContent = (window.i18n && i18n.t('modal.gdrive_path_label')) || '구글 드라이브 공유 폴더 링크 (엔터로 여러 개 입력 가능)';
      if (pathTextarea) pathTextarea.placeholder = (window.i18n && i18n.t('modal.gdrive_path_placeholder')) || '예: https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I';
      if (btnBrowse) btnBrowse.style.display = 'none';
      if (btnTest) btnTest.style.display = 'inline-flex';
      if (remoteRow) remoteRow.style.display = 'none';
      if (rcloneGroup) rcloneGroup.style.display = 'none';
      if (gdriveCopyGroup) gdriveCopyGroup.style.display = 'none';
  } else {
      if (pathLabel) pathLabel.textContent = (window.i18n && i18n.t('modal.category_path_label')) || '서버 물리 경로 (엔터로 여러 개 입력 가능)';
      if (pathTextarea) pathTextarea.placeholder = '예: C:\\library\\fantasy\n/home/user/manga';
      if (btnBrowse) btnBrowse.style.display = 'inline-flex';
      if (btnTest) btnTest.style.display = 'none';
      if (remoteRow) remoteRow.style.display = 'flex';
      if (gdriveCopyGroup) gdriveCopyGroup.style.display = 'block';
  }
}

function updateAdvancedStatusDot(isRemoteChecked) {
  const dotEl = document.getElementById('library-form-advanced-status-dot');
  if (dotEl) dotEl.classList.toggle('active', !!isRemoteChecked);
}

function updateAppearancePreview(iconVal, colorVal) {
  const previewIconEl = document.getElementById('library-form-appearance-preview-icon');
  if (previewIconEl) previewIconEl.innerHTML = `<i class="fa-solid ${iconVal}"></i>`;
  const previewColorEl = document.getElementById('library-form-appearance-preview-color');
  if (previewColorEl) previewColorEl.style.backgroundColor = colorVal;
}

export function selectIconOption(element) {
  document.querySelectorAll('.category-icon-selector .icon-option').forEach(el => el.classList.remove('active'));
  element.classList.add('active');
  const iconInput = document.getElementById('library-form-icon');
  if (iconInput) iconInput.value = element.dataset.icon;
  updateAppearancePreview(element.dataset.icon, document.getElementById('library-form-color')?.value || '#94a3b8');
}

export function selectColorOption(element) {
  document.querySelectorAll('.category-color-selector .color-option').forEach(el => el.classList.remove('active'));
  element.classList.add('active');
  const colorInput = document.getElementById('library-form-color');
  if (colorInput) colorInput.value = element.dataset.color;
  updateAppearancePreview(document.getElementById('library-form-icon')?.value || 'fa-book', element.dataset.color);
}
