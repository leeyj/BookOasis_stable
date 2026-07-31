// book_actions.js – 도서/시리즈 즐겨찾기 토글 및 재스캔 액션 핸들러
import { state } from '../state.js';
import * as api from '../api.js';

// 전역 작업 차단 로딩 오버레이 헬퍼 (대량 삭제/긴 비동기 작업용)
export function showGlobalLoadingSpinner(message = '처리 중입니다. 잠시만 기다려 주세요...') {
  let overlay = document.getElementById('global-loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'global-loading-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(8px);
      z-index: 99999;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-family: inherit;
      pointer-events: auto;
    `;
    overlay.innerHTML = `
      <div style="background: rgba(30, 41, 59, 0.95); padding: 2rem 2.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); text-align: center; max-width: 90vw; width: 400px;">
        <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2.5rem; color: #a855f7; margin-bottom: 1.2rem;"></i>
        <div id="global-loading-overlay-msg" style="font-size: 1rem; font-weight: 600; color: #f8fafc; line-height: 1.5; word-break: keep-all;">${message}</div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.8rem;">작업이 진행되는 동안 잠시만 기다려 주세요</div>
      </div>
    `;
    document.body.appendChild(overlay);
  } else {
    const msgEl = document.getElementById('global-loading-overlay-msg');
    if (msgEl) msgEl.innerText = message;
    overlay.style.display = 'flex';
  }
}

export function hideGlobalLoadingSpinner() {
  const overlay = document.getElementById('global-loading-overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
}

export async function toggleBookFavorite(event, bookId, nextStatus, seriesName, libraryId) {
  if (event) event.stopPropagation();
  const res = await window.toggleFavoriteAction(bookId, nextStatus);
  if (res && res.success) {
    const statusText = nextStatus === 1 ? i18n.t('modal.fav_added') : i18n.t('modal.fav_removed');
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.fav_status', {statusText: statusText}), 'success');
    }
    if (typeof window.openBookDetail === 'function') {
      window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
    }
  } else {
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.fav_fail'), 'error');
    } else {
      alert(i18n.t('modal.fav_fail'));
    }
  }
}

export async function toggleSeriesFavorite(event, seriesName, currentStatus, libraryId) {
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
      if (typeof window.openBookDetail === 'function') {
        window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
      }
    }
  } catch (err) {
    console.error('시리즈 즐겨찾기 토글 실패:', err);
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('modal.series_fav_fail'), 'error');
    } else {
      alert(i18n.t('modal.series_fav_fail'));
    }
  }
}

export async function rescanBook(event, bookId, seriesName, libraryId) {
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
      setTimeout(() => {
        if (typeof window.openBookDetail === 'function') {
          window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
        }
      }, 1000);
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
}

export async function rescanMissingBooks(event, seriesName, libraryId) {
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
      setTimeout(() => {
        if (typeof window.openBookDetail === 'function') {
          window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
        }
      }, 1000);
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
}

export async function rescanSeries(event, seriesName, libraryId) {
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
      setTimeout(() => {
        if (typeof window.openBookDetail === 'function') {
          window.openBookDetail(null, seriesName, libraryId, state.detailRepresentativeBookId, state.detailDisplayTitle);
        }
      }, 1000);
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
}
