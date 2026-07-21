// modal.js – 도서 상세 인라인 뷰 관리 (모달 제거, 그리드↔상세 전환)
import { state } from './state.js';
import * as api from './api.js';
import { switchActiveView } from './view_manager.js';
import { renderDetailHeader, renderVolumesList, renderRecommendList } from './detail_render.js';

// 그리드 뷰 → 상세 뷰 전환
export async function openBookDetail(event, seriesName, libraryId, representativeBookId = null, displayTitle = '') {
  const detailView = document.getElementById('book-detail-view');
  if (!detailView) return;

  const safeSeriesName = seriesName || '';
  const safeDisplayTitle = String(displayTitle || '').trim() || safeSeriesName;
  // 전달된 libraryId가 없으면 현재 상태값을 사용하되, 대시보드 시스템성 값이면 'all'로 대체 처리
  const activeLibId = libraryId || state.currentLibraryId || 'all';

  // 현재 리스트 스크롤 위치 저장 (복귀 시 사용)
  state.scrollPositions = state.scrollPositions || {};
  try {
    state.scrollPositions[activeLibId] = window.pageYOffset || document.documentElement.scrollTop || 0;
  } catch (e) {
    // 접근이 실패하면 무시
    console.warn('[detail] failed to capture scroll position', e);
  }

  // 로딩 표시
  detailView.innerHTML = `
    <button class="btn-back-to-list" onclick="goBackToList()">
      <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
    </button>
    <div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('modal.loading_detail')}</div>
  `;
  switchActiveView('detail');

  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, activeLibId, safeSeriesName, representativeBookId);

    if (data.success) {
      const meta = data.meta;
      const books = data.books || [];
      const actualLibraryId = (books.length > 0 && books[0].library_id) ? books[0].library_id : activeLibId;
      state.detailSeriesName = safeSeriesName;
      state.detailLibraryId = actualLibraryId;
      state.detailRepresentativeBookId = representativeBookId || (books.length > 0 ? books[0].id : null);
      state.detailDisplayTitle = safeDisplayTitle;

      // 컴포넌트 렌더러 모듈 호출
      const headerHtml = renderDetailHeader(meta, books, safeSeriesName, actualLibraryId, safeDisplayTitle);
      const volumesSectionHtml = renderVolumesList(books, safeSeriesName, actualLibraryId, state.currentLibraryType || 'general');

      detailView.innerHTML = `
        <button class="btn-back-to-list" onclick="goBackToList()">
          <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
        </button>
        ${headerHtml}
        ${volumesSectionHtml}
      `;

      // 메타데이터 비동기 로드 추천 후보군 검색
      const triggerRecommendSearch = () => {
        const recSection = document.getElementById('meta-recommend-section');
        const recList = document.getElementById('recommend-candidates-list');
        if (recSection && recList) {
          recSection.style.display = 'block';
          recList.innerHTML = `<div style="font-size:0.75rem; color:#64748b;"><i class="fa-solid fa-circle-notch fa-spin"></i> 추천 후보를 찾는 중...</div>`;
          api.fetchMetaRecommend(state.currentLibraryType, seriesName).then(res => {
            if (res.success && res.recommends && res.recommends.length > 0) {
              recList.innerHTML = renderRecommendList(res.recommends, seriesName);

              // 적용 버튼 클릭 이벤트 바인딩
              recList.querySelectorAll('.btn-apply-meta').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                  const sourceBookId = e.target.dataset.sourceId;
                  const confirmApply = confirm(i18n.t('modal.copy_confirm', {seriesName: seriesName}));
                  if (!confirmApply) return;

                  e.target.disabled = true;
                  e.target.innerText = i18n.t('modal.applying');

                  const formData = new FormData();
                  formData.append('type', state.currentLibraryType);
                  formData.append('target_series', safeSeriesName);
                  formData.append('target_library_id', actualLibraryId);
                  formData.append('source_book_id', sourceBookId);

                  try {
                    const copyRes = await api.copyMetadata(formData);
                    if (copyRes.success) {
                      alert(copyRes.message);
                      openBookDetail(null, safeSeriesName, actualLibraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
                    } else {
                      alert(i18n.t('modal.apply_fail', {error: copyRes.error}));
                      e.target.disabled = false;
                      e.target.innerText = '이 정보로 채우기';
                    }
                  } catch (err) {
                    console.error('메타데이터 복사 오류:', err);
                    alert(i18n.t('modal.server_error'));
                    e.target.disabled = false;
                    e.target.innerText = '이 정보로 채우기';
                  }
                });
              });
            } else {
              recList.innerHTML = `<div style="font-size:0.75rem; color:#64748b;">${i18n.t('modal.no_recommend')}</div>`;
            }
          }).catch(err => {
            console.error('추천 데이터 로드 실패:', err);
            recList.innerHTML = `<div style="font-size:0.75rem; color:#ef4444;">${i18n.t('modal.recommend_fail')}</div>`;
          });
        }
      };

      // 메타데이터가 공란이거나 기본 설명일 때 자동 트리거 분기
      const isMetaEmpty = !meta.summary || meta.summary === '등록된 설명이 없습니다.';
      if (isMetaEmpty) {
        triggerRecommendSearch();
      } else {
        const btnManual = document.getElementById('btn-manual-meta-search');
        if (btnManual) {
          btnManual.style.display = 'inline-block';
          btnManual.addEventListener('click', () => {
            btnManual.style.display = 'none';
            triggerRecommendSearch();
          });
        }
      }

      // 히스토리 해시가 #detail이 아닌 경우 상태 푸시, 이미 #detail인데 상태가 유실된 경우 상태 보정 (URL에 상세 정보 쿼리파라미터 포함)
      const repIdForHistory = state.detailRepresentativeBookId || '';
      const displayTitleForHistory = state.detailDisplayTitle || '';
      const detailHash = `#detail?series=${encodeURIComponent(safeSeriesName)}&libraryId=${actualLibraryId}${repIdForHistory ? `&repBookId=${encodeURIComponent(repIdForHistory)}` : ''}${displayTitleForHistory ? `&displayTitle=${encodeURIComponent(displayTitleForHistory)}` : ''}`;
      if (!window.location.hash.startsWith('#detail')) {
        history.pushState({ view: 'detail', series: safeSeriesName, libraryId: actualLibraryId, repBookId: repIdForHistory || null, displayTitle: displayTitleForHistory || null }, '', detailHash);
      } else {
        history.replaceState({ view: 'detail', series: safeSeriesName, libraryId: actualLibraryId, repBookId: repIdForHistory || null, displayTitle: displayTitleForHistory || null }, '', detailHash);
      }

      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      detailView.innerHTML = `
        <button class="btn-back-to-list" onclick="goBackToList()">
          <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
        </button>
        <div class="loading-spinner">${i18n.t('modal.load_detail_fail', {error: data.error || ''})}</div>
      `;
    }
  } catch (e) {
    console.error('[detail] openBookDetail 에러:', e);
    detailView.innerHTML = `
      <button class="btn-back-to-list" onclick="goBackToList()">
        <i class="fa-solid fa-arrow-left"></i> ${i18n.t('modal.go_back')}
      </button>
      <div class="loading-spinner">${i18n.t('modal.load_detail_error')}</div>
    `;
  }
}

// 상세 뷰 → 그리드 뷰/대시보드 복귀
export function goBackToList(triggerBack = true) {
  if (state.currentLibraryId === 'home') {
    switchActiveView('dashboard');
  } else {
    switchActiveView('grid');
  }

  // 상세에서 돌아올 때 저장된 스크롤 위치가 있으면 복원
  try {
    const saved = state.scrollPositions && state.scrollPositions[state.currentLibraryId];
    if (typeof saved !== 'undefined' && saved !== null) {
      // 뷰 전환 렌더링이 완료될 시간을 약간 둔 후 복원
      setTimeout(() => {
        window.scrollTo({ top: saved, behavior: 'auto' });
      }, 50);
      // 복원 후 캐시 정리
      delete state.scrollPositions[state.currentLibraryId];
    }
  } catch (e) {
    console.warn('[goBackToList] failed to restore scroll', e);
  }
  // 수동 목록으로 돌아가기 버튼을 누른 경우에만 브라우저 히스토리 스택 원상복구
  if (triggerBack && window.location.hash.startsWith('#detail')) {
    history.back();
  }
}

window.toggleBookFavorite = async (event, bookId, nextStatus, seriesName, libraryId) => {
  if (event) event.stopPropagation();
  const res = await window.toggleFavoriteAction(bookId, nextStatus);
  if (res && res.success) {
    const statusText = nextStatus === 1 ? i18n.t('modal.fav_added') : i18n.t('modal.fav_removed');
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.fav_status', {statusText: statusText}), 'success');
    }
    openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
  } else {
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.fav_fail'), 'error');
    } else {
      alert(i18n.t('modal.fav_fail'));
    }
  }
};

window.toggleSeriesFavorite = async (event, seriesName, currentStatus, libraryId) => {
  if (event) event.stopPropagation();
  try {
    const data = await api.fetchMediaDetail(
      state.currentLibraryType,
      libraryId || state.currentLibraryId,
      seriesName,
      state.detailRepresentativeBookId
    );
    if (data.success && data.books && data.books.length > 0) {
      const nextStatus = currentStatus === 1 ? 0 : 1;
      const promises = data.books.map(b => window.toggleFavoriteAction(b.id, nextStatus));
      await Promise.all(promises);
      const statusText = nextStatus === 1 ? i18n.t('modal.fav_added') : i18n.t('modal.fav_removed');
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('modal.series_fav_status', {seriesName: seriesName, statusText: statusText}), 'success');
      }
      openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
    }
  } catch (err) {
    console.error('시리즈 즐겨찾기 토글 실패:', err);
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.series_fav_fail'), 'error');
    } else {
      alert(i18n.t('modal.series_fav_fail'));
    }
  }
};

window.toggleMetaEditMode = () => {
  const viewEl = document.getElementById('detail-header-meta-view');
  const editEl = document.getElementById('detail-header-meta-edit');
  const overlayBtn = document.getElementById('cover-upload-overlay-btn');
  const btnEdit = document.querySelector('.btn-edit-toggle');

  if (viewEl && editEl) {
    const isEdit = editEl.style.display !== 'none';
    if (isEdit) {
      editEl.style.display = 'none';
      viewEl.style.display = 'flex';
      if (overlayBtn) overlayBtn.classList.remove('editable');
      if (btnEdit) btnEdit.style.display = 'inline-flex';
    } else {
      editEl.style.display = 'flex';
      viewEl.style.display = 'none';
      if (overlayBtn) overlayBtn.classList.add('editable');
      if (btnEdit) btnEdit.style.display = 'none';
    }
  }
};

window.triggerCoverUpload = (event) => {
  if (event) event.stopPropagation();
  const fileInput = document.getElementById('cover-upload-file-input');
  if (fileInput) fileInput.click();
};

window.handleCoverUploadSelect = (event) => {
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
};

window.handleCoverDrop = (event) => {
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
};

window.saveManualMetadata = async (seriesName) => {
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
      if (typeof window.showToast === 'function') {
        window.showToast(res.message || i18n.t('modal.meta_updated'), 'success');
      } else {
        alert(res.message || i18n.t('modal.meta_updated'));
      }
      openBookDetail(null, seriesName, state.detailLibraryId || state.currentLibraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
    } else {
      alert(i18n.t('modal.update_fail', {error: res.error}));
    }
  } catch (err) {
    console.error('수동 메타 수정 오류:', err);
    alert(i18n.t('modal.server_error'));
  }
};

/**
 * rescanBook — 단일 도서 즉시 재스캔 실행
 * total_pages=0 또는 커버 없는 볼륨 카드의 "다시 스캔" 버튼에서 호출됩니다.
 */
window.rescanBook = async (event, bookId, seriesName, libraryId) => {
  if (event) event.stopPropagation();

  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('modal.scanning')}`;

  try {
    const formData = new FormData();
    formData.append('type', state.currentLibraryType);

    const res = await fetch(`/api/media/books/${bookId}/scan`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('modal.scan_done'), 'success');
      }
      // 1초 후 상세 화면 새로고침 (토스트 메시지 표시 시간 확보)
      setTimeout(() => openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle), 1000);
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('modal.scan_fail', {error: data.error || ''}), 'error');
      } else {
        alert(i18n.t('modal.scan_fail', {error: data.error || ''}));
      }
    }
  } catch (err) {
    console.error('[rescanBook] 오류:', err);
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (typeof window.showToast === 'function') {
      window.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  }
};
window.rescanMissingBooks = async (event, seriesName, libraryId) => {
  if (event) event.stopPropagation();

  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('modal.scanning')}`;

  try {
    const missingCards = Array.from(document.querySelectorAll('.volume-card[data-page-missing="1"]'));
    const bookIds = missingCards
      .map(card => parseInt(card.dataset.bookId, 10))
      .filter(id => !Number.isNaN(id));

    if (bookIds.length === 0) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('detail.no_missing_page_books'), 'info');
      }
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      return;
    }

    const errors = [];
    for (const bookId of bookIds) {
      try {
        const res = await api.scanSingleBook(state.currentLibraryType, bookId);
        if (!res.success) {
          errors.push(`ID:${bookId} ${res.error || 'unknown error'}`);
        }
      } catch (scanErr) {
        errors.push(`ID:${bookId} ${scanErr.message || scanErr}`);
      }
    }

    if (errors.length === 0) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('modal.scan_done'), 'success');
      }
      setTimeout(() => openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle), 1000);
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      const message = i18n.t('modal.scan_fail', {error: errors.join('; ')});
      if (typeof window.showToast === 'function') {
        window.showToast(message, 'error');
      } else {
        alert(message);
      }
    }
  } catch (err) {
    console.error('[rescanMissingBooks] 오류:', err);
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (typeof window.showToast === 'function') {
      window.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  }
};

window.rescanSeries = async (event, seriesName, libraryId) => {
  if (event) event.stopPropagation();

  const btn = event.currentTarget;
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('modal.scanning')}`;

  try {
    const cards = Array.from(document.querySelectorAll('.volume-card'));
    const bookIds = cards
      .map(card => parseInt(card.dataset.bookId, 10))
      .filter(id => !Number.isNaN(id));

    if (bookIds.length === 0) {
      if (typeof window.showToast === 'function') {
        window.showToast('재스캔할 도서가 없습니다.', 'info');
      }
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      return;
    }

    const errors = [];
    for (const bookId of bookIds) {
      try {
        const res = await api.scanSingleBook(state.currentLibraryType, bookId);
        if (!res.success) {
          errors.push(`ID:${bookId} ${res.error || 'unknown error'}`);
        }
      } catch (scanErr) {
        errors.push(`ID:${bookId} ${scanErr.message || scanErr}`);
      }
    }

    if (errors.length === 0) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('modal.scan_done'), 'success');
      }
      setTimeout(() => openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle), 1000);
    } else {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      const message = i18n.t('modal.scan_fail', {error: errors.join('; ')});
      if (typeof window.showToast === 'function') {
        window.showToast(message, 'error');
      } else {
        alert(message);
      }
    }
  } catch (err) {
    console.error('[rescanSeries] 오류:', err);
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    if (typeof window.showToast === 'function') {
      window.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  }
};