// gdrive_copy_modal.js – 구글 드라이브 "복사해오기" 전용 모달 (실험적)
// 카테고리와 무관한 독립 동작이다 — 리모트 + 저장할 로컬 폴더만 있으면 실행된다.
// 복사해온 파일을 카테고리로 등록할지는 완료 후 사용자가 별도로 정한다
// (2026-08-23, "복사 전용 카테고리를 미리 만들어두게 강제할 이유가 없다"는 판단).
import { state } from '../state.js';

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function toast(msg, type = 'info') {
  if (typeof window.showToast === 'function') {
    window.showToast(msg, type);
  } else {
    alert(msg);
  }
}

async function loadRemotes() {
  const selectEl = document.getElementById('gdrive-copy-form-remote');
  const emptyEl = document.getElementById('gdrive-copy-form-remote-empty');
  if (!selectEl) return;

  try {
    const res = await fetch('/api/gdrive-copy/remotes');
    const data = await res.json();
    const remotes = (data && data.success && Array.isArray(data.remotes)) ? data.remotes.filter(r => r.usable) : [];

    selectEl.innerHTML = '<option value="">사용 안 함</option>' + remotes.map(r => {
      const safeName = escapeHtml(r.name);
      return `<option value="${safeName}">${safeName}</option>`;
    }).join('');

    if (emptyEl) emptyEl.style.display = remotes.length === 0 ? 'block' : 'none';
  } catch (error) {
    console.error('[GdriveCopyModal] 리모트 목록 조회 오류:', error);
    if (emptyEl) {
      emptyEl.textContent = `리모트 목록을 불러오지 못했습니다: ${error.message || error}`;
      emptyEl.style.display = 'block';
    }
  }
}

async function detectMountRootForCopyModal() {
  const remoteEl = document.getElementById('gdrive-copy-form-remote');
  const destPathEl = document.getElementById('gdrive-copy-form-dest-path');
  const rcloneUrlEl = document.getElementById('gdrive-copy-form-rclone-url');
  const hintEl = document.getElementById('gdrive-copy-form-dest-path-hint');
  if (!remoteEl || !remoteEl.value) {
    toast('먼저 연결할 리모트를 선택해 주세요.', 'warning');
    return;
  }
  if (!destPathEl || !destPathEl.value.trim()) {
    toast('먼저 저장할 로컬 폴더 경로를 입력해 주세요.', 'warning');
    return;
  }

  toast('마운트 루트 확인 중...', 'info');
  try {
    const res = await fetch('/api/gdrive-copy/detect-mount-root', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: state.currentLibraryType,
        physical_path: destPathEl.value.trim(),
        rclone_rc_url: rcloneUrlEl ? rcloneUrlEl.value : '',
        remote: remoteEl.value,
      }),
    });
    const data = await res.json();
    if (data.success && data.mount_root) {
      toast(`✅ 마운트 루트 확인됨: ${data.mount_root}`, 'success');
      if (hintEl) hintEl.textContent = `마운트 루트: ${data.mount_root} — Drive 쪽 목적지는 이 아래 상대경로로 자동 생성됩니다.`;
    } else {
      toast(`❌ ${data.error || '마운트 루트를 찾지 못했습니다 — 입력한 경로가 실제로 이 리모트가 마운트된 위치인지 확인해 주세요.'}`, 'error');
    }
  } catch (err) {
    toast(`❌ 네트워크 오류: ${err.message}`, 'error');
  }
}

export function openGdriveCopyModal() {
  const modal = document.getElementById('gdrive-copy-modal');
  const form = document.getElementById('gdrive-copy-form');
  if (!modal || !form) return;

  form.reset();
  loadRemotes();

  const detectBtn = document.querySelector('[data-role="gdrive-copy-detect-mount-root"]');
  if (detectBtn && !detectBtn.dataset.listenerBound) {
    detectBtn.dataset.listenerBound = 'true';
    detectBtn.addEventListener('click', detectMountRootForCopyModal);
  }

  modal.style.display = 'flex';
}

export function closeGdriveCopyModal() {
  const modal = document.getElementById('gdrive-copy-modal');
  if (modal) modal.style.display = 'none';
}

export async function submitGdriveCopyForm(event) {
  if (event) {
    event.preventDefault();
    if (typeof event.stopPropagation === 'function') event.stopPropagation();
  }

  const remote = document.getElementById('gdrive-copy-form-remote')?.value || '';
  const destLocalPath = document.getElementById('gdrive-copy-form-dest-path')?.value.trim() || '';
  const rcloneRcUrl = document.getElementById('gdrive-copy-form-rclone-url')?.value.trim() || '';
  const sourceLinks = document.getElementById('gdrive-copy-form-links')?.value.trim() || '';

  if (!remote) {
    toast('연결할 리모트를 선택해 주세요.', 'warning');
    return;
  }
  if (!destLocalPath) {
    toast('저장할 로컬 폴더 경로를 입력해 주세요.', 'warning');
    return;
  }
  if (!sourceLinks) {
    toast('구글 드라이브 공유 폴더 링크를 입력해 주세요.', 'warning');
    return;
  }

  const submitBtn = document.querySelector('#gdrive-copy-form [data-role="gdrive-copy-submit"]');
  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = '요청 중...';
    }

    const res = await fetch('/api/gdrive-copy/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: state.currentLibraryType,
        remote,
        dest_local_path: destLocalPath,
        rclone_rc_url: rcloneRcUrl,
        source_links: sourceLinks,
      }),
    });
    const data = await res.json();

    if (data.success) {
      closeGdriveCopyModal();
      toast('복사 작업을 시작했습니다. 진행 상태는 화면 하단 스캔 상태에서 확인할 수 있습니다.', 'success');
    } else {
      toast(`복사 시작 오류: ${data.error || '알 수 없는 오류'}`, 'error');
    }
  } catch (e) {
    toast(`서버 통신 예외: ${e && e.message ? e.message : String(e)}`, 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = '복사 시작';
    }
  }
}

export function triggerAddGdriveCopy() {
  openGdriveCopyModal();
}
