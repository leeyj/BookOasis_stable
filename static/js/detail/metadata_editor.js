// metadata_editor.js – 메타데이터 수동 편집, 표지 업로드/드롭, 추천 정보 적용, 잠금/해제
import { state } from '../state.js';
import * as api from '../api.js';

export function toggleMetaEditMode() {
  const viewEl = document.getElementById('detail-header-meta-view');
  const editEl = document.getElementById('detail-header-meta-edit');
  const fullRowEl = document.getElementById('detail-header-full-row');
  const overlayBtn = document.getElementById('cover-upload-overlay-btn');
  const btnEdit = document.querySelector('.btn-edit-toggle');

  if (viewEl && editEl) {
    const isEdit = editEl.style.display !== 'none';
    if (isEdit) {
      editEl.style.display = 'none';
      viewEl.style.display = 'flex';
      if (fullRowEl) fullRowEl.style.display = '';
      if (overlayBtn) overlayBtn.classList.remove('editable');
      if (btnEdit) btnEdit.style.display = 'inline-flex';
    } else {
      editEl.style.display = 'flex';
      viewEl.style.display = 'none';
      if (fullRowEl) fullRowEl.style.display = 'none';
      if (overlayBtn) overlayBtn.classList.add('editable');
      if (btnEdit) btnEdit.style.display = 'none';
    }
  }
}

export function triggerCoverUpload(event) {
  if (event) event.stopPropagation();
  const fileInput = document.getElementById('cover-upload-file-input');
  if (fileInput) fileInput.click();
}

export function handleCoverUploadSelect(event) {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const previewImg = document.getElementById('detail-cover-img-preview');
      if (previewImg) {
        previewImg.src = e.target.result;
      }
    };
    reader.readAsDataURL(file);
  }
}

export function handleCoverDrop(event) {
  event.preventDefault();
  event.stopPropagation();

  // 편집 모드가 활성화되어 있을 때만 드롭 승인
  const editEl = document.getElementById('detail-header-meta-edit');
  if (!editEl || editEl.style.display === 'none') {
    return;
  }

  const files = event.dataTransfer.files;
  if (files && files.length > 0) {
    const file = files[0];
    if (file.type.startsWith('image/')) {
      const fileInput = document.getElementById('cover-upload-file-input');
      if (fileInput) {
        // DataTransfer 객체를 통해 드롭된 파일을 Input 요소에 강제 매핑 바인딩
        const container = new DataTransfer();
        container.items.add(file);
        fileInput.files = container.files;

        // 미리보기 이미지 갱신
        const reader = new FileReader();
        reader.onload = (e) => {
          const previewImg = document.getElementById('detail-cover-img-preview');
          if (previewImg) {
            previewImg.src = e.target.result;
          }
        };
        reader.readAsDataURL(file);
        console.log('[CoverDrop] 드래그 앤 드롭 표지 파일 바인딩 완료:', file.name);
      }
    } else {
      alert(i18n.t('modal.only_image'));
    }
  }
}

export async function saveManualMetadata(seriesName) {
  const seriesAlias = document.getElementById('edit-series-alias-input') ? document.getElementById('edit-series-alias-input').value.trim() : '';
  const author = document.getElementById('edit-author-input').value.trim();
  const isbn = document.getElementById('edit-isbn-input').value.trim();
  const publisher = document.getElementById('edit-publisher-input').value.trim();
  const link = document.getElementById('edit-link-input').value.trim();
  const summary = document.getElementById('edit-summary-input').value.trim();
  const genre = document.getElementById('edit-genre-input').value.trim();
  const tags = document.getElementById('edit-tags-input').value.trim();
  const fileInput = document.getElementById('cover-upload-file-input');
  const coverFile = fileInput && fileInput.files ? fileInput.files[0] : null;

  const formData = new FormData();
  formData.append('type', state.currentLibraryType);
  formData.append('series', seriesName);
  formData.append('series_alias', seriesAlias);
  formData.append('author', author);
  formData.append('isbn', isbn);
  formData.append('publisher', publisher);
  formData.append('summary', summary);
  formData.append('link', link);
  formData.append('genre', genre);
  formData.append('tags', tags);
  if (coverFile) {
    formData.append('cover_image', coverFile);
  }

  try {
    const res = await api.editMediaDetail(formData);
    if (res.success) {
      if (fileInput) fileInput.value = '';
      if (typeof window.showToast === 'function') {
        window.showToast(res.message || i18n.t('modal.meta_updated'), 'success');
      } else {
        alert(res.message || i18n.t('modal.meta_updated'));
      }
      if (typeof window.openBookDetail === 'function') {
        window.openBookDetail(null, seriesName, state.detailLibraryId || state.currentLibraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
      }
    } else {
      alert(i18n.t('modal.update_fail', {error: res.error}));
    }
  } catch (err) {
    console.error('수동 메타 수정 오류:', err);
    alert(i18n.t('modal.server_error'));
  }
}

export async function handleUnlockMetadataEvent(event, seriesName, libraryId, bookId) {
  if (event) event.stopPropagation();
  if (!confirm('이 시리즈/도서의 메타데이터 잠금을 해제하시겠습니까?\n해제 후 스캔 시 메타데이터 및 커버가 다시 자동 업데이트됩니다.')) {
    return;
  }
  if (typeof window.showGlobalLoadingSpinner === 'function') {
    window.showGlobalLoadingSpinner('메타데이터 잠금을 해제하는 중입니다...');
  }
  try {
    const res = await api.unlockMetadata(state.currentLibraryType, seriesName, libraryId, bookId);
    if (typeof window.hideGlobalLoadingSpinner === 'function') {
      window.hideGlobalLoadingSpinner();
    }
    if (res && res.success) {
      if (typeof window.showToast === 'function') {
        window.showToast('메타데이터 잠금이 해제되었습니다.');
      } else {
        alert('메타데이터 잠금이 해제되었습니다.');
      }
      if (typeof window.openBookDetail === 'function') {
        window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
      }
      if (typeof window.loadBooksList === 'function') {
        window.loadBooksList(false);
      }
    } else {
      alert(`잠금 해제 실패: ${res.error || '오류가 발생했습니다.'}`);
    }
  } catch (e) {
    if (typeof window.hideGlobalLoadingSpinner === 'function') {
      window.hideGlobalLoadingSpinner();
    }
    console.error('unlockMetadata 에러:', e);
    alert('잠금 해제 처리 중 오류가 발생했습니다.');
  }
}
