// gdrive_copy_modal.js – 구글 드라이브 "복사해오기" 전용 모달 (실험적)
// 대상 카테고리는 미리 "카테고리 추가/수정" 모달에서 서버사이드 복사 리모트/목적지 경로를
// 설정해둔 것 중에서 선택한다 — 이 모달에서는 소스 공유 링크만 추가로 입력한다.
import { state } from '../state.js';
import * as api from '../api.js';

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

async function loadEligibleLibraries() {
  const selectEl = document.getElementById('gdrive-copy-form-library');
  const emptyEl = document.getElementById('gdrive-copy-form-library-empty');
  const infoEl = document.getElementById('gdrive-copy-form-library-info');
  if (!selectEl) return;

  if (infoEl) infoEl.style.display = 'none';

  try {
    const data = await api.fetchLibraries(state.currentLibraryType);
    const libraries = (data && data.success && Array.isArray(data.libraries)) ? data.libraries : [];
    const eligible = libraries.filter(lib => lib.gdrive_copy_remote);

    selectEl.innerHTML = '<option value="">카테고리를 선택하세요</option>' + eligible.map(lib => {
      const safeName = escapeHtml(lib.name);
      const safeRemote = escapeHtml(lib.gdrive_copy_remote);
      return `<option value="${lib.id}" data-remote="${safeRemote}" data-dest-path="${escapeHtml(lib.gdrive_copy_dest_path || '')}" data-path="${escapeHtml(lib.physical_path || '')}">${safeName} (${safeRemote})</option>`;
    }).join('');

    if (emptyEl) emptyEl.style.display = eligible.length === 0 ? 'block' : 'none';
  } catch (error) {
    console.error('[GdriveCopyModal] 카테고리 목록 조회 오류:', error);
    if (emptyEl) {
      emptyEl.textContent = `카테고리 목록을 불러오지 못했습니다: ${error.message || error}`;
      emptyEl.style.display = 'block';
    }
  }
}

function updateLibraryInfo() {
  const selectEl = document.getElementById('gdrive-copy-form-library');
  const infoEl = document.getElementById('gdrive-copy-form-library-info');
  if (!selectEl || !infoEl) return;

  const option = selectEl.selectedOptions && selectEl.selectedOptions[0];
  if (!option || !option.value) {
    infoEl.style.display = 'none';
    return;
  }

  const remote = option.dataset.remote || '';
  const destPath = option.dataset.destPath || '';
  const localPath = option.dataset.path || '';
  infoEl.textContent = `리모트: ${remote}${destPath ? ` / ${destPath}` : ''} → 로컬: ${localPath}`;
  infoEl.style.display = 'block';
}

export function openGdriveCopyModal() {
  const modal = document.getElementById('gdrive-copy-modal');
  const form = document.getElementById('gdrive-copy-form');
  if (!modal || !form) return;

  form.reset();
  loadEligibleLibraries();

  const selectEl = document.getElementById('gdrive-copy-form-library');
  if (selectEl && !selectEl.dataset.listenerBound) {
    selectEl.dataset.listenerBound = 'true';
    selectEl.addEventListener('change', updateLibraryInfo);
  }
  const infoEl = document.getElementById('gdrive-copy-form-library-info');
  if (infoEl) infoEl.style.display = 'none';

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

  const libraryId = document.getElementById('gdrive-copy-form-library')?.value || '';
  const sourceLinks = document.getElementById('gdrive-copy-form-links')?.value.trim() || '';

  if (!libraryId) {
    alert('대상 카테고리를 선택해 주세요.');
    return;
  }
  if (!sourceLinks) {
    alert('구글 드라이브 공유 폴더 링크를 입력해 주세요.');
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
        library_id: libraryId,
        source_links: sourceLinks,
      }),
    });
    const data = await res.json();

    if (data.success) {
      closeGdriveCopyModal();
      toast('복사 작업을 시작했습니다. 진행 상태는 화면 하단 스캔 상태에서 확인할 수 있습니다.', 'success');
    } else {
      alert(`[복사 시작 오류]\n${data.error || '알 수 없는 오류'}`);
    }
  } catch (e) {
    alert(`[서버 통신 예외]\n${e && e.message ? e.message : String(e)}`);
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
