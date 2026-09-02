// path_browser.js – 서버 물리 경로 탐색 모달 및 원격 경로/GDrive 연결 테스트
import { state } from '../state.js';

const MAX_LIBRARY_PATHS = 20;
const MAX_LIBRARY_PATH_LINE_LENGTH = 1024;
const MAX_LIBRARY_PATH_TEXT_LENGTH = 8192;
const MAX_PATH_BROWSER_INPUT_LENGTH = 1024;

let pathBrowserCurrentPath = '';

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function testGDriveLinks() {
  const pathEl = document.getElementById('library-form-path');
  const linksStr = pathEl ? pathEl.value : '';
  if (!linksStr.trim()) {
    if (typeof window.showToast === 'function') {
      window.showToast('테스트할 구글 드라이브 공유 링크를 입력해 주세요.', 'warning');
    } else {
      alert('테스트할 구글 드라이브 공유 링크를 입력해 주세요.');
    }
    return;
  }
  if (typeof window.showToast === 'function') {
    window.showToast('구글 드라이브 링크 연결 테스트 중...', 'info');
  }
  fetch('/api/category/test-gdrive-links', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ links: linksStr }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        if (typeof window.showToast === 'function') {
          window.showToast(`✅ ${data.message}`, 'success');
        } else {
          alert(`✅ ${data.message}`);
        }
      } else {
        if (typeof window.showToast === 'function') {
          window.showToast(`❌ ${data.error || '연결 실패'}`, 'error');
        } else {
          alert(`❌ ${data.error || '연결 실패'}`);
        }
      }
    })
    .catch(err => {
      if (typeof window.showToast === 'function') {
        window.showToast(`❌ 네트워크 오류: ${err.message}`, 'error');
      } else {
        alert(`❌ 네트워크 오류: ${err.message}`);
      }
    });
}

export async function loadGdriveCopyRemotes(selectedRemote = '') {
  const selectEl = document.getElementById('library-form-gdrive-copy-remote');
  const emptyEl = document.getElementById('library-form-gdrive-copy-remote-empty');
  if (!selectEl) return;

  try {
    const res = await fetch('/api/gdrive-copy/remotes');
    const data = await res.json();
    const remotes = (data && data.success && Array.isArray(data.remotes)) ? data.remotes.filter(r => r.usable) : [];

    selectEl.innerHTML = '<option value="">사용 안 함</option>' + remotes.map(r => {
      const safeName = escapeHtml(r.name);
      return `<option value="${safeName}"${r.name === selectedRemote ? ' selected' : ''}>${safeName}</option>`;
    }).join('');

    if (emptyEl) emptyEl.style.display = remotes.length === 0 ? 'block' : 'none';
  } catch (error) {
    console.error('[GdriveCopy] 리모트 목록 조회 오류:', error);
    if (emptyEl) {
      emptyEl.textContent = `리모트 목록을 불러오지 못했습니다: ${error.message || error}`;
      emptyEl.style.display = 'block';
    }
  }
}

/**
 * 서버의 OS 마운트 테이블(/proc/mounts, 우선) 또는 rclone RC의 mount/listmounts(폴백)로
 * 이 리모트가 실제로 마운트된 로컬 루트를 자동 감지해 "이 리모트의 로컬 마운트 루트"
 * 입력칸을 채운다. 관리자가 이미 아는 정보(서버가 스스로 알아낼 수 있는 정보)를 다시
 * 타이핑하지 않게 하려는 목적 — 실패하면 조용히 넘어가거나(silent=true, 자동 트리거 시)
 * 토스트로 알려준다(silent=false, 버튼 클릭 시).
 */
export function detectGdriveMountRoot(silent = false) {
  const mirrorInput = document.getElementById('library-form-gdrive-view-mirror-path');
  const rcloneUrlInput = document.getElementById('library-form-rclone-url');
  const remoteInput = document.getElementById('library-form-gdrive-copy-remote');
  if (!mirrorInput) return Promise.resolve(false);

  if (!remoteInput || !remoteInput.value) {
    if (!silent && typeof window.showToast === 'function') {
      window.showToast('먼저 연결할 리모트를 선택해 주세요.', 'warning');
    }
    return Promise.resolve(false);
  }

  // 카테고리 모달의 물리 경로는 공유 소스 링크라 매칭 기준으로 쓸 수 없다 — remote_name만
  // 으로 /proc/mounts를 조회하므로 물리 경로 없이도 감지가 가능하다.
  if (!silent && typeof window.showToast === 'function') {
    window.showToast('마운트 루트 감지 중...', 'info');
  }

  return fetch('/api/gdrive-copy/detect-mount-root', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: state.currentLibraryType,
      rclone_rc_url: rcloneUrlInput ? rcloneUrlInput.value : '',
      remote: remoteInput ? remoteInput.value : '',
    }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.success && data.mount_root) {
        mirrorInput.value = data.mount_root;
        mirrorInput.dispatchEvent(new Event('input', { bubbles: true }));
        if (!silent && typeof window.showToast === 'function') {
          window.showToast(`✅ 마운트 루트 감지됨: ${data.mount_root}`, 'success');
        }
        return true;
      }
      if (!silent && typeof window.showToast === 'function') {
        window.showToast(`❌ ${data.error || '자동 감지 실패 — 직접 입력해 주세요.'}`, 'error');
      }
      return false;
    })
    .catch(err => {
      if (!silent && typeof window.showToast === 'function') {
        window.showToast(`❌ 네트워크 오류: ${err.message}`, 'error');
      }
      return false;
    });
}

export function validateGdriveCopyTarget() {
  const remoteEl = document.getElementById('library-form-gdrive-copy-remote');
  const destPathEl = document.getElementById('library-form-gdrive-copy-dest-path');
  const remote = remoteEl ? remoteEl.value : '';
  const destPath = destPathEl ? destPathEl.value.trim() : '';

  if (!remote) {
    if (typeof window.showToast === 'function') {
      window.showToast('검증할 리모트를 선택해 주세요.', 'warning');
    } else {
      alert('검증할 리모트를 선택해 주세요.');
    }
    return;
  }

  if (typeof window.showToast === 'function') {
    window.showToast('대상 리모트/경로 검증 중...', 'info');
  }

  fetch('/api/gdrive-copy/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ remote, dest_path: destPath }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        const msg = `✅ 검증 성공 (계정: ${data.account_email || '알 수 없음'})`;
        if (typeof window.showToast === 'function') {
          window.showToast(msg, 'success');
        } else {
          alert(msg);
        }
      } else {
        if (typeof window.showToast === 'function') {
          window.showToast(`❌ ${data.error || '검증 실패'}`, 'error');
        } else {
          alert(`❌ ${data.error || '검증 실패'}`);
        }
      }
    })
    .catch(err => {
      if (typeof window.showToast === 'function') {
        window.showToast(`❌ 네트워크 오류: ${err.message}`, 'error');
      } else {
        alert(`❌ 네트워크 오류: ${err.message}`);
      }
    });
}

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
  listEl.innerHTML = '<div style="text-align: center; color: var(--app-text-muted); padding: 2rem;">로딩 중...</div>';
  
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
      listEl.innerHTML = '<div style="color: var(--app-text-muted); padding: 1rem; text-align: center;">하위 디렉토리가 없습니다.</div>';
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
        loadPathBrowserItems();
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

export function detectAndUpdateRemoteFlag(path) {
  const isRemoteCheckbox = document.getElementById('library-form-remote');
  if (!isRemoteCheckbox) return;
  
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
  
  isRemoteCheckbox.checked = isLikelyRemote;
  isRemoteCheckbox.dispatchEvent(new Event('change'));
}

export function updateRemoteWarning() {
  const remoteCheckbox = document.getElementById('library-form-remote');
  const warningEl = document.getElementById('library-form-remote-warning');
  if (!warningEl || !remoteCheckbox) return;
  
  if (remoteCheckbox.checked) {
    warningEl.style.display = 'block';
  } else {
    warningEl.style.display = 'none';
  }
}

export function enableVFSCheckForRemote() {
  console.log('[VFS] Remote path selected - VFS should be enabled in scan settings');
}
