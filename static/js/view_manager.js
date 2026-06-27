// view_manager.js – 화면(뷰) 상태 제어 및 렌더링 영역 전환 매니저
import { state } from './state.js';

/**
 * ────────────────────────────────────────────────────────
 * 📌 시스템 통합 뷰 매니저 (화면 전환 단일 통로)
 * ────────────────────────────────────────────────────────
 * @param {string} viewName - 활성화할 뷰 영역 ('dashboard' | 'grid' | 'detail')
 */
export function switchActiveView(viewName) {
  const dashboardView = document.getElementById('library-dashboard-view');
  const gridView = document.getElementById('books-grid-view');
  const detailView = document.getElementById('book-detail-view');
  const settingsView = document.getElementById('library-settings-view');
  const btnSort = document.getElementById('btn-lib-sort');

  console.log(`[View-Manager] Switching view to: ${viewName} (Current category: ${state.currentLibraryId})`);

  // 1. 모든 메인 뷰 컨테이너 숨김 초기화
  if (dashboardView) dashboardView.style.display = 'none';
  if (gridView) gridView.style.display = 'none';
  if (detailView) detailView.style.display = 'none';
  if (settingsView) settingsView.style.display = 'none';

  // 2. 요청한 뷰 영역만 선택 활성화 및 정렬 버튼 조율
  switch (viewName) {
    case 'dashboard':
      if (dashboardView) dashboardView.style.display = 'flex';
      if (btnSort) btnSort.style.display = 'none';
      break;
      
    case 'grid':
      if (gridView) gridView.style.display = 'block';
      if (btnSort) {
        // 'history'(최근 읽은 도서) 카테고리에서는 정렬 버튼을 노출하지 않고 그 외 보관함에서는 노출
        btnSort.style.display = (state.currentLibraryId === 'history') ? 'none' : 'inline-flex';
      }
      break;
      
    case 'detail':
      if (detailView) detailView.style.display = 'block';
      break;
      
    case 'settings':
      if (settingsView) settingsView.style.display = 'flex';
      if (btnSort) btnSort.style.display = 'none';
      break;
      
    default:
      console.warn(`[View-Manager] Unknown viewName requested: ${viewName}`);
  }
}

/**
 * ────────────────────────────────────────────────────────
 * 📌 공통 뷰어 로딩 및 에러 처리기
 * ────────────────────────────────────────────────────────
 */

export function showViewerLoading(message = "다운로드 중...", subMessage = "Google Drive에서 파일을 가져오고 있습니다.<br>잠시만 기다려 주세요.") {
  const overlay = document.getElementById('viewer-common-overlay');
  const spinner = document.getElementById('viewer-common-spinner');
  const textEl = document.getElementById('viewer-common-text');
  const subEl = document.getElementById('viewer-common-sub');
  const closeBtn = document.getElementById('viewer-common-close-btn');

  if (overlay) {
    overlay.style.display = 'flex';
    if (spinner) spinner.style.display = 'block';
    if (textEl) textEl.innerHTML = message;
    if (subEl) {
      subEl.style.display = 'block';
      subEl.innerHTML = subMessage;
    }
    if (closeBtn) closeBtn.style.display = 'none'; // 로딩 중에는 닫기 버튼 가림
  }
}

export function hideViewerLoading() {
  const overlay = document.getElementById('viewer-common-overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
}

export function showViewerError(message = "도서 파일을 불러오지 못했습니다.", subMessage = "네트워크 상태 및 파일 존재 여부를 확인해 주세요.") {
  const overlay = document.getElementById('viewer-common-overlay');
  const spinner = document.getElementById('viewer-common-spinner');
  const textEl = document.getElementById('viewer-common-text');
  const subEl = document.getElementById('viewer-common-sub');
  const closeBtn = document.getElementById('viewer-common-close-btn');

  if (overlay) {
    overlay.style.display = 'flex';
    if (spinner) spinner.style.display = 'none'; // 에러 시 스피너 숨김
    if (textEl) textEl.innerHTML = `<span style="color: #ef4444;">${message}</span>`;
    if (subEl) {
      subEl.style.display = 'block';
      subEl.innerHTML = subMessage;
    }
    if (closeBtn) closeBtn.style.display = 'block'; // 에러 시 닫기 버튼 활성화
  }
}

/**
 * ────────────────────────────────────────────────────────
 * 📌 공통 토스트 메시지 헬퍼 (Toast Message Alert)
 * ────────────────────────────────────────────────────────
 * @param {string} message - 토스트 노출 메시지
 * @param {string} type - 'success' | 'error' | 'info'
 */
export function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%) translateY(20px);
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(168, 85, 247, 0.5);
      color: #fff;
      padding: 0.75rem 1.5rem;
      border-radius: 50px;
      font-size: 0.9rem;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5), 0 0 15px rgba(168, 85, 247, 0.25);
      z-index: 99999;
      opacity: 0;
      transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
      pointer-events: none;
      display: flex;
      align-items: center;
      gap: 0.6rem;
    `;
    document.body.appendChild(container);
  }

  // 아이콘 결정
  let iconHtml = '<i class="fa-solid fa-circle-check" style="color: #eab308; font-size: 1.05rem;"></i>';
  if (type === 'error') {
    iconHtml = '<i class="fa-solid fa-circle-xmark" style="color: #ef4444; font-size: 1.05rem;"></i>';
  } else if (type === 'info') {
    iconHtml = '<i class="fa-solid fa-circle-info" style="color: #3b82f6; font-size: 1.05rem;"></i>';
  }

  container.innerHTML = `${iconHtml} <span>${message}</span>`;
  
  // 브라우저 렌더링 동기화 후 활성화
  setTimeout(() => {
    container.style.opacity = '1';
    container.style.transform = 'translateX(-50%) translateY(0)';
  }, 10);

  // 이전 타이머 정리
  if (window.toastTimer) clearTimeout(window.toastTimer);
  
  // 2초 뒤 비활성화
  window.toastTimer = setTimeout(() => {
    container.style.opacity = '0';
    container.style.transform = 'translateX(-50%) translateY(20px)';
  }, 2000);
}

// 글로벌 노출
window.showToast = showToast;


