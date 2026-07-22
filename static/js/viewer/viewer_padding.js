// viewer_padding.js – 뷰어 내부 실시간 여백 조절 및 동적 패딩 적용 모듈
import { state } from '../state.js';

// 여백 상세 설정 패널 토글
export function toggleViewerPaddingPanel() {
  console.log('[Viewer-Padding] toggleViewerPaddingPanel called. Current Format:', state.currentViewerFormat);
  const panel = document.getElementById('viewer-padding-overlay-panel');
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (!panel) {
    console.error('[Viewer-Padding] #viewer-padding-overlay-panel not found in DOM');
    return;
  }

  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    console.log('[Viewer-Padding] Panel display set to block');
    // 모바일 겹침 방지: 여백 조절판이 열릴 때 오버레이 제어 메뉴를 일단 숨김
    if (overlayMenu) {
      overlayMenu.style.display = 'none';
    }
    initViewerPaddingPanel();
  } else {
    panel.style.display = 'none';
    console.log('[Viewer-Padding] Panel display set to none. Re-rendering viewer.');
    // 여백 조절판을 닫았을 때, 오버레이 메뉴를 복원
    if (overlayMenu) {
      overlayMenu.style.display = 'flex';
    }
    // 최종 닫히는 시점에 1회 완벽 리렌더링하여 좌표 찢어짐 원천 봉쇄!
    commitViewerPadding();
  }
}

// 뷰어 포맷에 따라 슬라이더 값 동기화 및 폼 그룹 노출
export function initViewerPaddingPanel() {
  console.log('[Viewer-Padding] initViewerPaddingPanel executing...');
  const isTxtOrEpub = (state.currentViewerFormat === 'epub' || state.currentViewerFormat === 'txt');
  
  const novelGroup = document.getElementById('quick-padding-novel-group');
  const comicGroup = document.getElementById('quick-padding-comic-group');
  
  if (isTxtOrEpub) {
    console.log('[Viewer-Padding] Detected TXT/EPUB novel mode.');
    if (novelGroup) novelGroup.style.display = 'flex';
    if (comicGroup) comicGroup.style.display = 'none';
    
    // 4방향 개별 소설 값 복원
    const padTop = localStorage.getItem('viewer_padding_top') || '40';
    const padBottom = localStorage.getItem('viewer_padding_bottom') || '60';
    const padLeft = localStorage.getItem('viewer_padding_left') || '20';
    const padRight = localStorage.getItem('viewer_padding_right') || '20';
    console.log(`[Viewer-Padding] Recovered Spacing: Top=${padTop}, Bottom=${padBottom}, Left=${padLeft}, Right=${padRight}`);
    
    const topSlider = document.getElementById('quick-novel-top-slider');
    const bottomSlider = document.getElementById('quick-novel-bottom-slider');
    const leftSlider = document.getElementById('quick-novel-left-slider');
    const rightSlider = document.getElementById('quick-novel-right-slider');
    
    if (topSlider) {
      topSlider.value = padTop;
      const valEl = document.getElementById('quick-novel-top-val');
      if (valEl) valEl.innerText = padTop;
    }
    if (bottomSlider) {
      bottomSlider.value = padBottom;
      const valEl = document.getElementById('quick-novel-bottom-val');
      if (valEl) valEl.innerText = padBottom;
    }
    if (leftSlider) {
      leftSlider.value = padLeft;
      const valEl = document.getElementById('quick-novel-left-val');
      if (valEl) valEl.innerText = padLeft;
    }
    if (rightSlider) {
      rightSlider.value = padRight;
      const valEl = document.getElementById('quick-novel-right-val');
      if (valEl) valEl.innerText = padRight;
    }
  } else {
    console.log('[Viewer-Padding] Detected Non-novel mode (Comic/PDF). Hiding groups.');
    if (novelGroup) novelGroup.style.display = 'none';
    if (comicGroup) comicGroup.style.display = 'none';
  }

  // 동적 슬라이더 이벤트 프로그램 바인딩
  bindPaddingSliders();
}

// 4방향 독립 슬라이더 이벤트 바인딩
function bindPaddingSliders() {
  console.log('[Viewer-Padding] bindPaddingSliders initiating binding...');
  const configs = [
    { id: 'quick-novel-top-slider', type: 'novel', side: 'top' },
    { id: 'quick-novel-bottom-slider', type: 'novel', side: 'bottom' },
    { id: 'quick-novel-left-slider', type: 'novel', side: 'left' },
    { id: 'quick-novel-right-slider', type: 'novel', side: 'right' }
  ];

  configs.forEach(c => {
    const el = document.getElementById(c.id);
    if (el) {
      if (!el.__paddingBound) {
        el.__paddingBound = true;
        el.addEventListener('input', (e) => {
          applyViewerPaddingRealtime(c.type, c.side, e.target.value);
        });
      }
    }
  });
}

// 실시간 조작 시에는 스토리지 캐시 및 라벨 값만 변경 (실시간 화면 뷰포트 흔들기 중단)
export function applyViewerPaddingRealtime(type, side, value) {
  if (type === 'novel') {
    if (side === 'top') localStorage.setItem('viewer_padding_top', value);
    else if (side === 'bottom') localStorage.setItem('viewer_padding_bottom', value);
    else if (side === 'left') localStorage.setItem('viewer_padding_left', value);
    else if (side === 'right') localStorage.setItem('viewer_padding_right', value);

    const valEl = document.getElementById(`quick-novel-${side}-val`);
    if (valEl) valEl.innerText = value;
    console.log(`[Viewer-Padding] Live Spacing Cache updated: ${side}=${value}px`);
  }
}

// [핵심 정답] 조절창이 완전히 닫힐 때 1회 물리 너비 결정 및 applyTxtSettings 새로고침 연계
export function commitViewerPadding() {
  console.log('[Viewer-Padding] commitViewerPadding - Applying final box styles.');
  const wrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!wrapper || !contentArea) {
    console.warn('[Viewer-Padding] Core Novel DOM elements not found.');
    return;
  }

  const padTop = parseInt(localStorage.getItem('viewer_padding_top') || '40', 10);
  const padBottom = parseInt(localStorage.getItem('viewer_padding_bottom') || '60', 10);
  const padLeft = parseInt(localStorage.getItem('viewer_padding_left') || '20', 10);
  const padRight = parseInt(localStorage.getItem('viewer_padding_right') || '20', 10);

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'page') {
    // 부모 너비를 가져와 정수 픽셀로 변형하여 가로폭 직접 인라인 덮어쓰기
    const container = document.getElementById('txt-viewer-container');
    const parentWidth = container ? container.clientWidth : window.innerWidth;
    const targetWidth = Math.floor(parentWidth - (padLeft + padRight));
    const pageStep = localStorage.getItem('comic_page_step') || '1';
    const maxAllowedWidth = pageStep === '2' ? Math.min(targetWidth, 1600) : Math.min(targetWidth, 800);

    wrapper.style.height = `calc(100vh - ${80 + padTop + padBottom}px)`;
    wrapper.style.marginTop = `${padTop + 40}px`;
    wrapper.style.maxWidth = `${maxAllowedWidth}px`;
    wrapper.style.marginLeft = 'auto';
    wrapper.style.marginRight = 'auto';
    wrapper.style.padding = '0';
    contentArea.style.padding = '0';
    console.log(`[Viewer-Padding] Wrapper maxWidth locked to integer: ${targetWidth}px`);
  } else {
    // 세로 스크롤 모드
    wrapper.style.height = '100%';
    wrapper.style.marginTop = '0';
    wrapper.style.maxWidth = '850px';
    wrapper.style.marginLeft = 'auto';
    wrapper.style.marginRight = 'auto';
    wrapper.style.padding = '0';

    contentArea.style.paddingTop = `${padTop}px`;
    contentArea.style.paddingBottom = `${padBottom}px`;
    contentArea.style.paddingLeft = `${padLeft}px`;
    contentArea.style.paddingRight = `${padRight}px`;
  }

  // 뷰어 설정 강제 갱신 리로딩 호출
  import('../viewer_txt.js').then(m => {
    m.applyTxtSettings();
  }).catch(e => {
    console.error('[Viewer-Padding] Failed to load viewer_txt.js:', e);
  });
}

// 윈도우 전역 함수 매핑
window.toggleViewerPaddingPanel = toggleViewerPaddingPanel;
window.applyViewerPaddingRealtime = applyViewerPaddingRealtime;
window.commitViewerPadding = commitViewerPadding;
