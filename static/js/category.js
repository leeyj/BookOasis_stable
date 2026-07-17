// category.js – 카테고리(라이브러리) CRUD 및 우클릭 메뉴 관리 기능
import { state } from './state.js';
import * as api from './api.js';
import { selectCategory } from './tab_media_library.js';

/**
 * HTML 속성값에 삽입될 문자열의 특수문자를 이스케이프합니다.
 * 사용자가 카테고리 이름에 큰따옴표, 꺾쇠 등을 입력해도 DOM이 깨지지 않습니다.
 */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

let currentTargetLibrary = null; // 우클릭 대상 저장

const MAX_LIBRARY_NAME_LENGTH = 25;
const MAX_LIBRARY_PATHS = 20;
const MAX_LIBRARY_PATH_LINE_LENGTH = 1024;
const MAX_LIBRARY_PATH_TEXT_LENGTH = 8192;
const MAX_PATH_BROWSER_INPUT_LENGTH = 1024;

// 0. 라이브러리(카테고리) 목록 로드 및 사이드바 렌더링
export async function loadLibraries() {
  window.loadLibraries = loadLibraries;
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
      
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      const addBtnHtml = isAdmin 
        ? `<button onclick="event.stopPropagation(); triggerAddLibrary();" style="background: none; border: none; color: #a855f7; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: background 0.2s;" onmouseenter="this.style.background='rgba(168, 85, 247, 0.15)'" onmouseleave="this.style.background='none'" title="${i18n.t('category.add_new_tooltip')}">
            <i class="fa-solid fa-plus"></i>
          </button>`
        : '';
      
      let html = `<li class="menu-item ${state.currentLibraryId === 'home' ? 'active' : ''}" data-type="system" id="category-home" data-id="home" onclick="selectCategory('home')" style="display: flex; justify-content: space-between; align-items: center; box-sizing: border-box;">
        <span style="display: inline-flex; align-items: center; gap: 0.6rem;"><i class="fa-solid fa-house"></i> ${i18n.t('category.home')}</span>
        <div style="display: inline-flex; align-items: center; gap: 0.4rem;">
          <button id="btn-pin-categories" onclick="event.stopPropagation(); window.toggleCategoryOrderPin();" style="background: none; border: none; cursor: pointer; padding: 0.2rem 0.4rem; font-size: 0.9rem; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s; ${pinBtnStyle}" title="${pinTitle}">
            <i class="fa-solid fa-thumbtack"></i>
          </button>
          ${addBtnHtml}
        </div>
      </li>`;

      html += `<li class="menu-item ${state.currentLibraryId === 'history' ? 'active' : ''}" data-type="system" id="category-history" data-id="history" onclick="selectCategory('history')"><i class="fa-solid fa-clock-rotate-left"></i> ${i18n.t('category.history')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'favorite' ? 'active' : ''}" data-type="system" id="category-favorite" data-id="favorite" onclick="selectCategory('favorite')"><i class="fa-solid fa-star" style="color: #eab308;"></i> ${i18n.t('category.favorite')}</li>`;
      html += `<li class="menu-item ${state.currentLibraryId === 'plugins' ? 'active' : ''}" data-type="system" id="category-plugins" data-id="plugins" onclick="selectCategory('plugins')"><i class="fa-solid fa-puzzle-piece" style="color: #38bdf8;"></i> ${i18n.t('category.plugins')}</li>`;
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
          // HTML 속성값에 사용될 문자열 이스케이프 (큰따옴표, 꺾쇠 등 특수문자 방어)
          const safeName    = escapeHtml(lib.name || '');
          const safePath    = escapeHtml(lib.physical_path || '');
          const safeRclone  = escapeHtml(lib.rclone_rc_url || '');
          const safeIcon    = escapeHtml(lib.icon || 'fa-book');
          const safeColor   = escapeHtml(lib.color || '#94a3b8');
          const hideCover = Number(lib.hide_cover || 0) ? 1 : 0;
          html += `<li class="menu-item ${isActive}" data-type="custom" data-id="${lib.id}" data-name="${safeName}" data-path="${safePath}" data-remote="${lib.is_remote || 0}" data-rclone-url="${safeRclone}" data-icon="${safeIcon}" data-color="${safeColor}" data-hide-cover="${hideCover}" ${draggableAttr} onclick="selectCategory('${lib.id}')"><i class="fa-solid ${safeIcon}" style="color: ${safeColor};"></i> ${safeName}</li>`;
        });
      }
      sidebar.innerHTML = html;
      const activeItem = document.getElementById(`category-${state.currentLibraryId}`) || sidebar.querySelector(`[data-id="${state.currentLibraryId}"]`);
      state.currentLibraryHideCovers = !!(activeItem && activeItem.dataset && activeItem.dataset.type === 'custom' && activeItem.dataset.hideCover === '1');
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
  const isAdmin = state.currentUser && state.currentUser.role === 'admin';
  if (!isAdmin) {
    isEnabled = false;
  }
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;

  // 기존 인스턴스 정리
  if (sidebar._sortable) {
    sidebar._sortable.destroy();
    sidebar._sortable = null;
  }

  if (!isEnabled) return;

  if (typeof Sortable !== 'undefined') {
    sidebar._sortable = new Sortable(sidebar, {
      animation: 150,
      draggable: 'li[data-type="custom"]', // 커스텀 카테고리만 드래그 가능
      filter: 'li[data-type="system"]',    // 시스템 카테고리는 필터링
      preventOnFilter: false,
      onEnd: function (evt) {
        saveNewOrder();
      }
    });
  }
}
function saveNewOrder() {
  const sidebar = document.getElementById('sidebar-categories');
  if (!sidebar) return;
  const customItems = sidebar.querySelectorAll('li[data-type="custom"]');
  const order = Array.from(customItems).map(el => String(el.dataset.id));
  localStorage.setItem(`libraries_order_${state.currentLibraryType}`, JSON.stringify(order));
}

// 사이드바 및 외부 우클릭 바인딩
export function bindSidebarContextMenu() {
  const sidebar = document.querySelector('.library-sidebar');
  const contextMenu = document.getElementById('library-context-menu');

  if (sidebar) {
    sidebar.addEventListener('contextmenu', (e) => {
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      if (!isAdmin) return;
      
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

    sidebar.addEventListener('touchstart', (e) => {
      const isAdmin = state.currentUser && state.currentUser.role === 'admin';
      if (!isAdmin) return;

      const menuItem = e.target.closest('.menu-item');
      if (menuItem) {
        const type = menuItem.dataset.type;
        const id = menuItem.dataset.id;
        const name = menuItem.dataset.name;
        
        if (typeof window.handleLongPressTouchStart === 'function') {
          window.handleLongPressTouchStart(e, (x, y) => {
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
            showContextMenu(x, y);
          });
        }
      }
    }, { passive: true });

    sidebar.addEventListener('touchmove', (e) => {
      if (typeof window.handleLongPressTouchMove === 'function') {
        window.handleLongPressTouchMove(e);
      }
    }, { passive: true });

    sidebar.addEventListener('touchend', (e) => {
      if (typeof window.handleLongPressTouchEnd === 'function') {
        window.handleLongPressTouchEnd(e);
      }
    });

    sidebar.addEventListener('touchcancel', (e) => {
      if (typeof window.handleLongPressTouchEnd === 'function') {
        window.handleLongPressTouchEnd(e);
      }
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
  if (remoteEl) {
    remoteEl.checked = false;
    remoteEl.dispatchEvent(new Event('change'));
  }

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

  const hideCoverEl = document.getElementById('library-form-hide-cover');
  if (hideCoverEl) hideCoverEl.checked = false;

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
      // 원격 경로 경고 메시지 표시
      updateRemoteWarning();
      // 원격 경로 체크 시 VFS 자동 활성화
      if (e.target.checked) {
        enableVFSCheckForRemote();
      }
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

  // 아이콘 및 컬러 칩 데이터 바인딩
  const iconVal = document.querySelector(`[data-id="${id}"]`).dataset.icon || 'fa-book';
  const colorVal = document.querySelector(`[data-id="${id}"]`).dataset.color || '#94a3b8';
  
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

  const hideCoverVal = document.querySelector(`[data-id="${id}"]`).dataset.hideCover || '0';
  const hideCoverEl = document.getElementById('library-form-hide-cover');
  if (hideCoverEl) hideCoverEl.checked = (hideCoverVal === '1');

  // 체크박스 변경 감지 바인딩 (최초 1회)
  if (remoteEl && !remoteEl.dataset.listenerBound) {
    remoteEl.dataset.listenerBound = 'true';
    remoteEl.addEventListener('change', (e) => {
      if (rcloneGroup) rcloneGroup.style.display = e.target.checked ? 'block' : 'none';
      // 원격 경로 경고 메시지 표시
      updateRemoteWarning();
      // 원격 경로 체크 시 VFS 자동 활성화
      if (e.target.checked) {
        enableVFSCheckForRemote();
      }
    });
  }

  // 초기 경고 메시지 표시 여부 판단
  updateRemoteWarning();

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

    let result;
    if (isEdit) {
      result = await api.editLibrary(formData);
    } else {
      result = await api.addLibrary(formData);
    }

    if (result.success) {
      alert(result.message);
      closeLibraryModal();
      await loadLibraries();
      if (isEdit && String(state.currentLibraryId) === String(id)) {
        selectCategory(String(id), true);
      }
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


// ─── 경로 탐색 기능 (v0.6.6 신규) ───
let pathBrowserCurrentPath = '';

export function openPathBrowser() {
  const modal = document.getElementById('path-browser-modal');
  if (!modal) return;
  
  // 초기 경로 설정
  pathBrowserCurrentPath = '';
  
  modal.style.display = 'flex';
  refreshPathBrowser();
}

export function closePathBrowser() {
  const modal = document.getElementById('path-browser-modal');
  if (modal) modal.style.display = 'none';
}

export async function refreshPathBrowser() {
  const inputEl = document.getElementById('path-browser-input');
  if (inputEl) {
    const candidatePath = inputEl.value.trim();
    if (candidatePath.length > MAX_PATH_BROWSER_INPUT_LENGTH) {
      alert(`경로 입력은 최대 ${MAX_PATH_BROWSER_INPUT_LENGTH}자까지 허용됩니다.`);
      return;
    }
    pathBrowserCurrentPath = candidatePath || pathBrowserCurrentPath;
  }
  
  await loadPathBrowserItems();
}

export async function loadPathBrowserItems() {
  const listEl = document.getElementById('path-browser-list');
  const inputEl = document.getElementById('path-browser-input');
  
  if (!listEl) return;
  
  // UI 업데이트
  if (inputEl) inputEl.value = pathBrowserCurrentPath;
  listEl.innerHTML = '<div style="text-align: center; color: #94a3b8; padding: 2rem;">로딩 중...</div>';
  
  try {
    const params = new URLSearchParams();
    params.append('path', pathBrowserCurrentPath);
    
    const response = await fetch(`/api/media/browse-paths?${params.toString()}`);
    const data = await response.json();
    
    if (!data.success) {
      listEl.innerHTML = `<div style="color: #ef4444; padding: 1rem;">오류: ${data.error || '알 수 없는 오류'}</div>`;
      return;
    }
    
    const items = data.items || [];
    pathBrowserCurrentPath = data.currentPath || '';
    if (inputEl) inputEl.value = pathBrowserCurrentPath;
    
    if (items.length === 0) {
      listEl.innerHTML = '<div style="color: #94a3b8; padding: 1rem; text-align: center;">하위 디렉토리가 없습니다.</div>';
      return;
    }
    
    // 디렉토리 목록 렌더링
    listEl.innerHTML = '';
    items.forEach(item => {
      const itemEl = document.createElement('div');
      itemEl.style.cssText = `
        padding: 0.6rem 0.8rem;
        cursor: pointer;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        display: flex;
        align-items: center;
        gap: 0.6rem;
        transition: background 0.2s;
      `;
      itemEl.onmouseenter = () => itemEl.style.background = 'rgba(168, 85, 247, 0.1)';
      itemEl.onmouseleave = () => itemEl.style.background = 'none';
      itemEl.onclick = () => {
        pathBrowserCurrentPath = item.path;
        if (item.name !== '..') {
          loadPathBrowserItems();
        } else {
          loadPathBrowserItems();
        }
      };
      
      const icon = item.name === '..' ? 'fa-arrow-up' : 'fa-folder';
      itemEl.innerHTML = `
        <i class="fa-solid ${icon}" style="color: #a855f7; flex-shrink: 0;"></i>
        <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(item.name)}</span>
      `;
      listEl.appendChild(itemEl);
    });
    
  } catch (error) {
    console.error('[PathBrowser] 경로 탐색 오류:', error);
    listEl.innerHTML = `<div style="color: #ef4444; padding: 1rem;">오류: ${error.message || '경로를 불러올 수 없습니다.'}</div>`;
  }
}

export function selectPathFromBrowser() {
  const pathEl = document.getElementById('library-form-path');
  if (!pathEl) return;
  
  if (!pathBrowserCurrentPath) {
    alert('경로를 선택하세요.');
    return;
  }
  
  // 기존 경로 가져오기
  const existing = pathEl.value.trim();
  let newPaths = existing ? existing.split('\n').map(p => p.trim()).filter(p => p) : [];
  
  // 중복 체크
  if (!newPaths.includes(pathBrowserCurrentPath)) {
    newPaths.push(pathBrowserCurrentPath);
  }

  if (newPaths.length > MAX_LIBRARY_PATHS) {
    alert(`경로는 최대 ${MAX_LIBRARY_PATHS}개까지 입력할 수 있습니다.`);
    return;
  }
  if (newPaths.some(p => p.length > MAX_LIBRARY_PATH_LINE_LENGTH)) {
    alert(`각 경로는 최대 ${MAX_LIBRARY_PATH_LINE_LENGTH}자까지 허용됩니다.`);
    return;
  }
  const joined = newPaths.join('\n');
  if (joined.length > MAX_LIBRARY_PATH_TEXT_LENGTH) {
    alert(`경로 입력 길이는 최대 ${MAX_LIBRARY_PATH_TEXT_LENGTH}자까지 허용됩니다.`);
    return;
  }
  
  pathEl.value = joined;
  
  // 경로가 rclone/원격 마운트인지 자동 감지하여 is_remote 체크박스 업데이트
  detectAndUpdateRemoteFlag(pathBrowserCurrentPath);
  
  closePathBrowser();
}

function detectAndUpdateRemoteFlag(path) {
  // 경로가 rclone/네트워크 드라이브인지 자동 감지하여 is_remote 체크박스 업데이트
  // 사용자는 필요시 수동으로 조정 가능
  const isRemoteCheckbox = document.getElementById('library-form-remote');
  if (!isRemoteCheckbox) return;
  
  // 클라이언트 측 휴리스틱: rclone 마운트 경로 패턴 감지
  const pathLower = path.toLowerCase();
  const isLikelyRemote = 
    pathLower.includes('rclone') ||
    pathLower.includes('gdrive') ||
    pathLower.includes('onedrive') ||
    pathLower.includes('nas') ||
    pathLower.includes('network') ||
    pathLower.includes('vfs') ||
    /^[a-z]:\\\\?rclone/i.test(path) ||  // Windows: C:\rclone
    /^\/mnt\/(rclone|gdrive)/i.test(path); // Linux: /mnt/rclone
  
  // 자동 감지 결과를 체크박스에 반영 (사용자 수정 가능)
  isRemoteCheckbox.checked = isLikelyRemote;
  isRemoteCheckbox.dispatchEvent(new Event('change'));
}

// 글로벌 함수로 노출 (onclick 핸들러용)
if (typeof window !== 'undefined') {
  window.openPathBrowser = openPathBrowser;
  window.closePathBrowser = closePathBrowser;
  window.refreshPathBrowser = refreshPathBrowser;
  window.selectPathFromBrowser = selectPathFromBrowser;
}

// 원격 경로 경고 메시지 업데이트 함수
function updateRemoteWarning() {
  const remoteCheckbox = document.getElementById('library-form-remote');
  const warningEl = document.getElementById('library-form-remote-warning');
  if (!warningEl || !remoteCheckbox) return;
  
  if (remoteCheckbox.checked) {
    warningEl.style.display = 'block';
  } else {
    warningEl.style.display = 'none';
  }
}

// 원격 경로 체크 시 VFS 자동 활성화 함수
function enableVFSCheckForRemote() {
  // VFS 체크박스를 찾아 활성화
  // 라이브러리 설정 페이지의 VFS 체크박스를 찾음
  // 해당 라이브러리에 대한 VFS 체크박스를 활성화
  console.log('[VFS] Remote path selected - VFS should be enabled in scan settings');
}

export async function triggerMoveLibrary() {
  if (!currentTargetLibrary || currentTargetLibrary.type === 'system') return;
  
  const fromType = state.currentLibraryType;
  const toType = (fromType === 'general') ? 'adult' : 'general';
  
  const targetLabel = (toType === 'general') ? '일반도서' : '성인도서';
  const confirmMsg = `정말로 이 카테고리를 [${targetLabel}] 보관함으로 이동하시겠습니까?\n이동하는 동안 데이터베이스 정밀 이전 작업을 위해 전체 화면이 잠시 잠깁니다.`;
  if (!confirm(confirmMsg)) return;
  
  // 1. 모달창 닫기
  const modal = document.getElementById('library-form-modal');
  if (modal) modal.style.display = 'none';
  
  // 2. 전체 화면 잠금 오버레이 켜기
  const dimmer = document.getElementById('migration-dimmer-modal');
  if (dimmer) dimmer.style.display = 'flex';
  
  const formData = new FormData();
  formData.append('id', currentTargetLibrary.id);
  formData.append('from_type', fromType);
  formData.append('to_type', toType);
  
  // 창 닫기 및 이탈 방지 핸들러 등록
  const preventClose = (e) => {
    e.preventDefault();
    e.returnValue = ''; // 표준 브라우저 경고 팝업 활성화
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
      
      // 3. 목적지 탭으로 타입 변경
      state.currentLibraryType = toType;
      
      // 4. 일반 <-> 성인 토글 버튼 active 클래스 갱신
      document.querySelectorAll('.btn-toggle').forEach(btn => btn.classList.remove('active'));
      if (toType === 'general') {
        const btnGen = document.getElementById('btn-lib-general');
        if (btnGen) btnGen.classList.add('active');
      } else {
        const btnAd = document.getElementById('btn-lib-adult');
        if (btnAd) btnAd.classList.add('active');
      }
      
      // 5. 사이드바 및 화면 리셋
      await loadLibraries();
      selectCategory('home');
    } else {
      alert('이동 실패: ' + (data.error || '알 수 없는 오류'));
    }
  } catch (e) {
    console.error('이관 API 오류:', e);
    alert('서버 통신 실패 또는 타임아웃이 발생했습니다.');
  } finally {
    // 창 닫기 방지 핸들러 해제 및 딤 모달 끄기
    window.removeEventListener('beforeunload', preventClose);
    if (dimmer) dimmer.style.display = 'none';
  }
}

if (typeof window !== 'undefined') {
  window.triggerMoveLibrary = triggerMoveLibrary;
}


