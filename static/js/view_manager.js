// view_manager.js – 화면(뷰) 상태 제어 및 렌더링 영역 전환 매니저
import { state } from './state.js';
import { mountIndexScrollbar, unmountIndexScrollbar } from './index_scrollbar.js';
import { clearViewerReportAction, showViewerReportAction } from './viewer/report_problem.js';

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
  const pluginsView = document.getElementById('library-plugins-view');
  const customPluginView = document.getElementById('library-plugin-custom-view');
  const btnSort = document.getElementById('btn-lib-sort');

  console.log(`[View-Manager] Switching view to: ${viewName} (Current category: ${state.currentLibraryId})`);

  const libraryHeader = document.querySelector('.library-header');
  const searchCenter = document.querySelector('.library-search-center');
  const libraryControls = document.querySelector('.library-controls');
  const activeFilterBar = document.getElementById('active-filter-bar');
  // 검색창과 같은 줄에 있던 그룹모드가 별도 요소로 분리돼 있어 searchCenter와 함께 조율.
  // 세션탭(#library-type-toggle-group)은 "지금 어느 세션인지" 보여주는 유일한 지표라
  // 플러그인/설정 화면을 포함해 어떤 뷰에서도 숨기지 않는다 - 여기서 조율 대상에서 제외.
  const groupModeToggle = document.getElementById('group-mode-toggle-group');

  // 1. 모든 메인 뷰 컨테이너 숨김 초기화 (자식 뷰 겹침 방지 보장)
  const mainContent = document.querySelector('.library-main-content');
  if (mainContent) {
    Array.from(mainContent.children).forEach(child => {
      if (child.classList.contains('library-header') || child.id === 'active-filter-bar') return;
      child.style.display = 'none';
    });
  }

  if (dashboardView) dashboardView.style.display = 'none';
  if (gridView) gridView.style.display = 'none';
  if (detailView) detailView.style.display = 'none';
  if (settingsView) settingsView.style.display = 'none';
  if (pluginsView) pluginsView.style.display = 'none';
  if (customPluginView) customPluginView.style.display = 'none';
  
  unmountIndexScrollbar();

  // 상단 검색바/필터 컨트롤 숨김 조율 - 헤더 자체와 세션탭/환경설정·계정은 항상 유지
  if (viewName === 'plugin_custom' || viewName === 'settings' || viewName === 'plugins') {
    if (searchCenter) searchCenter.style.display = 'none';
    if (libraryControls) libraryControls.style.display = 'none';
    if (groupModeToggle) groupModeToggle.style.display = 'none';
    if (activeFilterBar) activeFilterBar.style.display = 'none';
  } else {
    // display 값을 하드코딩하지 않고 인라인 override를 제거 - 데스크톱(flex)/모바일(grid) 미디어쿼리별
    // 실제 레이아웃이 다르므로, 특정 값을 강제하면 좁은 화면에서 레이아웃이 깨진다.
    if (libraryHeader) libraryHeader.style.removeProperty('display');
    if (searchCenter) searchCenter.style.removeProperty('display');
    if (libraryControls) libraryControls.style.removeProperty('display');
    if (groupModeToggle) groupModeToggle.style.removeProperty('display');
  }

  // 2. 요청한 뷰 영역만 선택 활성화 및 정렬 버튼 조율
  switch (viewName) {
    case 'dashboard':
      if (dashboardView) dashboardView.style.display = 'flex';
      if (btnSort) btnSort.style.display = 'none';
      break;

    case 'plugin_custom':
      if (customPluginView) {
        customPluginView.style.display = 'block';
        customPluginView.style.width = '100%';
      }
      if (btnSort) btnSort.style.display = 'none';
      break;
      
    case 'grid':
      if (gridView) gridView.style.display = 'block';
      if (btnSort) {
        // 'history'(최근 읽은 도서), 'collection'(컬렉션), 'smart_rec'(스마트 추천), 'tts_ready'(음성 준비됨) 카테고리에서는 정렬 버튼을 노출하지 않고 그 외 보관함에서는 노출
        btnSort.style.display = (['history', 'collection', 'smart_rec', 'tts_ready'].includes(state.currentLibraryId)) ? 'none' : 'inline-flex';
      }
      if (['collection', 'smart_rec', 'tts_ready'].includes(state.currentLibraryId)) {
        const scrollSpinner = document.getElementById('infinite-scroll-spinner');
        if (scrollSpinner) scrollSpinner.style.display = 'none';
      }
      if (!['history', 'collection', 'smart_rec', 'tts_ready'].includes(state.currentLibraryId)) {
        mountIndexScrollbar();
      }
      break;
      
    case 'detail':
      if (detailView) detailView.style.display = 'block';
      break;
      
    case 'settings':
      if (settingsView) settingsView.style.display = 'flex';
      if (btnSort) btnSort.style.display = 'none';
      break;

    case 'plugins':
      if (pluginsView) pluginsView.style.display = 'flex';
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

export function showViewerLoading(message = i18n.t("viewer.loading_title_default"), subMessage = i18n.t("viewer.loading_sub_default")) {
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
  clearViewerReportAction();
}

export function hideViewerLoading() {
  const overlay = document.getElementById('viewer-common-overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
  clearViewerReportAction();
}

export function showViewerError(message = i18n.t("viewer.error_title_default"), subMessage = i18n.t("viewer.error_sub_default")) {
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
  // 오류 자리에 한 줄 조치: 일반 사용자 [관리자에게 알리기] / 관리자 [진단]
  showViewerReportAction(message, subMessage);
}

/**
 * ────────────────────────────────────────────────────────
 * 📌 공통 토스트 메시지 헬퍼 (Toast Message Alert)
 * ────────────────────────────────────────────────────────
 * @param {string} message - 토스트 노출 메시지
 * @param {string} type - 'success' | 'error' | 'info'
 * @param {{actionLabel?: string, onAction?: Function, duration?: number}} [options]
 *        actionLabel+onAction를 주면 토스트 오른쪽에 버튼 하나(예: 되돌리기)를 붙인다.
 */
export function showToast(message, type = 'success', options = {}) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%) translateY(20px);
      background: rgba(var(--app-panel-rgb), 0.95);
      border: 1px solid rgba(168, 85, 247, 0.5);
      color: var(--app-text-primary);
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

  // 이전 타이머 및 스타일 즉시 리셋 (토스트 중복/재호출 시 고착 방지)
  if (window.toastTimer) {
    clearTimeout(window.toastTimer);
    window.toastTimer = null;
  }

  container.innerHTML = `${iconHtml} <span>${message}</span>`;
  const hasAction = Boolean(options && options.actionLabel && typeof options.onAction === 'function');
  // 평소엔 클릭이 토스트를 통과하지만, 버튼이 있을 때만 눌릴 수 있게 한다.
  container.style.pointerEvents = hasAction ? 'auto' : 'none';
  if (hasAction) {
    const actionBtn = document.createElement('button');
    actionBtn.type = 'button';
    actionBtn.textContent = options.actionLabel;
    actionBtn.style.cssText = 'margin-left:0.4rem; padding:0.2rem 0.7rem; border-radius:999px; border:1px solid rgba(168, 85, 247, 0.6); background:transparent; color:inherit; font:inherit; font-size:0.82rem; cursor:pointer;';
    actionBtn.addEventListener('click', event => {
      event.stopPropagation();
      if (window.toastTimer) clearTimeout(window.toastTimer);
      window.toastTimer = null;
      container.style.opacity = '0';
      container.style.transform = 'translateX(-50%) translateY(20px)';
      container.style.pointerEvents = 'none';
      options.onAction();
    });
    container.appendChild(actionBtn);
  }
  container.style.opacity = '0';
  container.style.transform = 'translateX(-50%) translateY(20px)';
  
  // 브라우저 repaint 후 활성화
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      container.style.opacity = '1';
      container.style.transform = 'translateX(-50%) translateY(0)';
    });
  });

  // 3초 뒤 비활성화 (버튼이 있으면 누를 시간을 더 준다)
  const duration = Number(options && options.duration) || (hasAction ? 6000 : 3000);
  window.toastTimer = setTimeout(() => {
    container.style.opacity = '0';
    container.style.transform = 'translateX(-50%) translateY(20px)';
    container.style.pointerEvents = 'none';
  }, duration);
}

// 글로벌 노출
window.showToast = showToast;


