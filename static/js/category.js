// category.js – 카테고리(라이브러리) CRUD 및 우클릭 메뉴 관리 기능
import { state } from './state.js';
import * as api from './api.js';
import { selectCategory } from './tab_media_library.js';

let currentTargetLibrary = null; // 우클릭 대상 저장

// 0. 라이브러리(카테고리) 목록 로드 및 사이드바 렌더링
export async function loadLibraries() {
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;
  try {
    const data = await api.fetchLibraries(state.currentLibraryType);
    if (data.success) {
      const isPinned = localStorage.getItem('category_order_pinned') !== 'false'; // default true
      const pinBtnStyle = isPinned 
        ? "color: #a855f7; transform: none;" 
        : "color: #94a3b8; transform: rotate(45deg);";
      const pinTitle = isPinned ? i18n.t('category.pin_pinned') : i18n.t('category.pin_unpinned');
      
      let html = `<li class="menu-item ${state.currentLibraryId === 'home' ? 'active' : ''}" data-type="system" id="category-home" data-id="home" onclick="selectCategory('home')" style="display: flex; justify-content: space-between; align-items: center; box-sizing: border-box;">
        <span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid fa-house"></i> ${i18n.t('category.home')}</span>
        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
          <button id="btn-pin-categories" onclick="event.stopPropagation(); window.toggleCategoryOrderPin();" style="background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s; ${pinBtnStyle}" title="${pinTitle}">
            <i class="fa-solid fa-thumbtack"></i>
          </button>
          <button onclick="event.stopPropagation(); triggerAddLibrary();" style="background: none; border: none; color: #a855f7; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: background 0.2s;" onmouseenter="this.style.background='rgba(168, 85, 247, 0.15)'" onmouseleave="this.style.background='none'" title="${i18n.t('category.add_new_tooltip')}">
            <i class="fa-solid fa-plus"></i>
          </button>
        </div>
      </li>`;

      html += `<li class="menu-item ${state.currentLibraryId === 'history' ? 'active' : ''}" data-type="system" id="category-history" data-id="history" onclick="selectCategory('history')"><i class="fa-solid fa-clock-rotate-left"></i> ${i18n.t('category.history')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" id="category-favorite" data-id="favorite" onclick="selectCategory('favorite')"><i class="fa-solid fa-star" style="color: #eab308;"></i> ${i18n.t('category.favorite')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'all' ? 'active' : ''}" data-type="system" id="category-all" data-id="all" onclick="selectCategory('all')"><i class="fa-solid fa-layer-group"></i> ${i18n.t('category.all')}</li>`;
      
      if (data.libraries && data.libraries.length > 0) {
        // localStorage에서 순서 읽기
        const savedOrderStr = localStorage.getItem(`libraries_order_${state.currentLibraryType}`);
        if (savedOrderStr) {
          try {
            const savedOrder = JSON.parse(savedOrderStr);
            data.libraries.sort((a, b) => {
              let idxA = savedOrder.indexOf(String(a.id));
              let idxB = savedOrder.indexOf(String(b.id));
              if (idxA === -1) idxA = 9999;
              if (idxB === -1) idxB = 9999;
              return idxA - idxB;
            });
          } catch(e) {
            console.error('Error parsing library order:', e);
          }
        }

        data.libraries.forEach(lib => {
          const isActive = String(state.currentLibraryId) === String(lib.id) ? 'active' : '';
          const draggableAttr = !isPinned ? 'draggable="true"' : '';
          html += `<li class="menu-item ${isActive}" data-type="custom" data-id="${lib.id}" data-name="${lib.name}" data-path="${lib.physical_path || ''}" data-remote="${lib.is_remote || 0}" data-rclone-url="${lib.rclone_rc_url || ''}" ${draggableAttr} onclick="selectCategory('${lib.id}')"><i class="fa-solid fa-book"></i> ${lib.name}</li>`;
        });
      }
      sidebar.innerHTML = html;
      bindSidebarContextMenu();
      bindDragAndDropEvents(!isPinned);
    }
  } catch (e) {
    console.error('라이브러리 목록 로드 실패:', e);
  }
}

window.toggleCategoryOrderPin = () => {
  const isPinned = localStorage.getItem('category_order_pinned') !== 'false';
  localStorage.setItem('category_order_pinned', isPinned ? 'false' : 'true');
  loadLibraries();
};

function bindDragAndDropEvents(isEnabled) {
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar || !isEnabled) return;

  const items = sidebar.querySelectorAll('li[data-type="custom"]');
  let dragSrcEl = null;

  items.forEach(item => {
    item.addEventListener('dragstart', (e) => {
      dragSrcEl = item;
      e.dataTransfer.effectAllowed = 'move';
      item.classList.add('dragging');
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      
      const target = e.target.closest('li[data-type="custom"]');
      if (target && target !== dragSrcEl) {
        const rect = target.getBoundingClientRect();
        const next = (e.clientY - rect.top) / (rect.bottom - rect.top) > 0.5;
        sidebar.insertBefore(dragSrcEl, next ? target.nextSibling : target);
      }
    });

    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      saveNewOrder();
    });
  });

  function saveNewOrder() {
    const customItems = sidebar.querySelectorAll('li[data-type="custom"]');
    const order = Array.from(customItems).map(el => String(el.dataset.id));
    localStorage.setItem(`libraries_order_${state.currentLibraryType}`, JSON.stringify(order));
  }
}

// 사이드바 및 외부 우클릭 바인딩
export function bindSidebarContextMenu() {
  const sidebar = document.querySelector('.library-sidebar');
  const contextMenu = document.getElementById('library-context-menu');

  if (sidebar) {
    sidebar.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      
      const menuItem = e.target.closest('.menu-item');
      if (menuItem) {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;
        
        currentTargetLibrary = { id, name, type };

        if (type === 'system') {
          document.getElementById('ctx-edit-category').style.display = 'none';
          document.getElementById('ctx-delete-category').style.display = 'none';
          document.getElementById('ctx-scan-category').style.display = 'none';
          if (document.getElementById('ctx-force-scan-category')) {
            document.getElementById('ctx-force-scan-category').style.display = 'none';
          }
          if (document.getElementById('ctx-scan-covers-category')) {
            document.getElementById('ctx-scan-covers-category').style.display = 'none';
          }
          if (document.getElementById('ctx-cancel-scan-category')) {
            document.getElementById('ctx-cancel-scan-category').style.display = 'none';
          }
        } else {
          document.getElementById('ctx-edit-category').style.display = 'block';
          document.getElementById('ctx-delete-category').style.display = 'block';
          document.getElementById('ctx-scan-category').style.display = 'block';
          if (document.getElementById('ctx-force-scan-category')) {
            document.getElementById('ctx-force-scan-category').style.display = 'block';
          }
          if (document.getElementById('ctx-scan-covers-category')) {
            document.getElementById('ctx-scan-covers-category').style.display = 'block';
          }
          if (document.getElementById('ctx-cancel-scan-category')) {
            document.getElementById('ctx-cancel-scan-category').style.display = 'block';
          }
        }
      } else {
        currentTargetLibrary = null;
        document.getElementById('ctx-edit-category').style.display = 'none';
        document.getElementById('ctx-delete-category').style.display = 'none';
        document.getElementById('ctx-scan-category').style.display = 'none';
        if (document.getElementById('ctx-force-scan-category')) {
          document.getElementById('ctx-force-scan-category').style.display = 'none';
        }
        if (document.getElementById('ctx-scan-covers-category')) {
          document.getElementById('ctx-scan-covers-category').style.display = 'none';
        }
        if (document.getElementById('ctx-cancel-scan-category')) {
          document.getElementById('ctx-cancel-scan-category').style.display = 'none';
        }
      }

      showContextMenu(e.clientX, e.clientY);
    });
  }

  // 문서 클릭 시 컨텍스트 메뉴 닫기
  document.addEventListener('click', () => {
    if (contextMenu) contextMenu.style.display = 'none';
  });
}

export function showContextMenu(x, y) {
  const contextMenu = document.getElementById('library-context-menu');
  if (!contextMenu) return;
  
  // 임시 표시하여 높이 측정
  contextMenu.style.display = 'block';
  const menuHeight = contextMenu.offsetHeight || 180;
  const menuWidth = contextMenu.offsetWidth || 160;
  
  // 뷰포트 경계 검사 및 조정
  let targetY = y + window.scrollY;
  let targetX = x + window.scrollX;
  
  if (y + menuHeight > window.innerHeight) {
    targetY = (y - menuHeight) + window.scrollY;
    // 음수가 되지 않도록 최소 한계 보정
    if (targetY < window.scrollY) targetY = window.scrollY;
  }
  
  if (x + menuWidth > window.innerWidth) {
    targetX = (x - menuWidth) + window.scrollX;
  }
  
  contextMenu.style.left = `${targetX}px`;
  contextMenu.style.top = `${targetY}px`;
}

// ─── CRUD 트리거 ───
export function triggerAddLibrary() {
  const modal = document.getElementById('library-form-modal');
  const title = document.getElementById('library-modal-title');
  const form = document.getElementById('library-crud-form');
  
  if (!modal || !form) return;
  form.reset();
  document.getElementById('library-form-id').value = '';
  const remoteEl = document.getElementById('library-form-remote');
  if (remoteEl) remoteEl.checked = false;

  // Rclone RC URL 초기화 및 숨김
  const rcloneUrlEl = document.getElementById('library-form-rclone-url');
  if (rcloneUrlEl) rcloneUrlEl.value = '';
  const rcloneGroup = document.getElementById('library-form-rclone-url-group');
  if (rcloneGroup) rcloneGroup.style.display = 'none';

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
    });
  }

  title.innerText = i18n.t('category.add_title');
  modal.style.display = 'flex';
}

export async function triggerEditLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  
  const modal = document.getElementById('library-form-modal');
  const title = document.getElementById('library-modal-title');
  const form = document.getElementById('library-crud-form');
  
  if (!modal || !form) return;
  
  const id = currentTargetLibrary.id;
  const name = currentTargetLibrary.name;
 
  document.getElementById('library-form-id').value = id;
  document.getElementById('library-form-name').value = name;
  
  const pathVal = document.querySelector(`[data-id="${id}"]`).dataset.path || '';
  document.getElementById('library-form-path').value = pathVal;

  const isRemoteVal = document.querySelector(`[data-id="${id}"]`).dataset.remote || '0';
  const remoteEl = document.getElementById('library-form-remote');
  if (remoteEl) remoteEl.checked = (isRemoteVal === '1');

  // Rclone RC URL 바인딩 및 표시 토글
  const rcloneUrlVal = document.querySelector(`[data-id="${id}"]`).dataset.rcloneUrl || '';
  const rcloneUrlEl = document.getElementById('library-form-rclone-url');
  if (rcloneUrlEl) rcloneUrlEl.value = rcloneUrlVal;

  const rcloneGroup = document.getElementById('library-form-rclone-url-group');
  if (rcloneGroup) {
    rcloneGroup.style.display = (isRemoteVal === '1') ? 'block' : 'none';
  }

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
    });
  }

  title.innerText = i18n.t('category.edit_title', {id: id});
  modal.style.display = 'flex';
}

export async function triggerDeleteLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  const confirmDel = confirm(i18n.t('category.delete_confirm', {name: currentTargetLibrary.name}));
  if (!confirmDel) return;

  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('id', currentTargetLibrary.id);

  try {
    const data = await api.deleteLibrary(formData);
    if (data.success) {
      alert(data.message);
      // 삭제 완료 후 즉각 사이드바 카테고리 목록 다시 렌더링
      await loadLibraries();
      
      // 만약 방금 지운 카테고리를 현재 활성화하여 보고 있었던 경우, 안전하게 최근 읽은 도서 뷰로 전환
      if (String(state.currentLibraryId) === String(currentTargetLibrary.id)) {
        selectCategory('history');
      }
    } else {
      alert(i18n.t('category.delete_fail', {error: data.error}));
    }
  } catch (e) {
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
  event.preventDefault();
  const form = document.getElementById('library-crud-form');
  const formData = new FormData(form);
  formData.append('type', state.currentLibraryType);
  
  const isRemoteChecked = document.getElementById('library-form-remote')?.checked;
  formData.set('is_remote', isRemoteChecked ? '1' : '0');

  const id = formData.get('id');
  const isEdit = !!id;

  try {
    const submitBtn = document.getElementById('library-form-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = i18n.t('category.processing');
    }

    let result;
    if (isEdit) {
      result = await api.editLibrary(formData);
    } else {
      result = await api.addLibrary(formData);
    }

    if (result.success) {
      alert(result.message);
      closeLibraryModal();
      loadLibraries();
    } else {
      alert(i18n.t('category.save_error', {error: result.error}));
    }
  } catch (e) {
    console.error('라이브러리 저장 실패:', e);
    alert(i18n.t('category.save_server_error'));
  } finally {
    const submitBtn = document.getElementById('library-form-submit-btn');
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = i18n.t('category.save');
    }
  }
}


