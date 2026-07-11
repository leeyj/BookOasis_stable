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
    console.log('[Viewer-Padding] Panel display set to none');
    // 여백 조절판을 닫았을 때, 오버레이 메뉴를 다시 복원하여 노출
    if (overlayMenu) {
      overlayMenu.style.display = 'flex';
    }
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
    console.log(`[Viewer-Padding] Recovered Novel Spacing - Top: ${padTop}px, Bottom: ${padBottom}px, Left: ${padLeft}px, Right: ${padRight}px`);
    
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
    console.log('[Viewer-Padding] Detected Non-novel mode (Comic/PDF). Hiding padding groups.');
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
      console.log(`[Viewer-Padding] Found slider element: ${c.id}`);
      if (!el.__paddingBound) {
        el.__paddingBound = true;
        el.addEventListener('input', (e) => {
          console.log(`[Viewer-Padding] Slider [${c.id}] input event captured. New Value: ${e.target.value}`);
          applyViewerPaddingRealtime(c.type, c.side, e.target.value);
        });
        console.log(`[Viewer-Padding] Successfully bound 'input' listener to ${c.id}`);
      } else {
        console.log(`[Viewer-Padding] Slider [${c.id}] already has __paddingBound mark`);
      }
    } else {
      console.warn('[Viewer-Padding] Slider element NOT found in DOM:', c.id);
    }
  });
}

// 4방향 개별 패딩/여백 계산 (가로 페이지 뷰일 때는 텍스트 박스 물리적 수축 제어로 글자 잘림 방지)
export function applyViewerPaddingRealtime(type, side, value) {
  console.log(`[Viewer-Padding] applyViewerPaddingRealtime. Type: ${type}, Side: ${side}, Value: ${value}`);
  if (type === 'novel') {
    // 1. 값 캐싱 업데이트
    if (side === 'top') localStorage.setItem('viewer_padding_top', value);
    else if (side === 'bottom') localStorage.setItem('viewer_padding_bottom', value);
    else if (side === 'left') localStorage.setItem('viewer_padding_left', value);
    else if (side === 'right') localStorage.setItem('viewer_padding_right', value);

    const valEl = document.getElementById(`quick-novel-${side}-val`);
    if (valEl) valEl.innerText = value;

    const wrapper = document.getElementById('txt-scroll-wrapper');
    const contentArea = document.getElementById('txt-content-area');
    if (!wrapper || !contentArea) {
      console.error('[Viewer-Padding] Core Novel DOM elements not found!');
      return;
    }

    const padTop = parseInt(localStorage.getItem('viewer_padding_top') || '40', 10);
    const padBottom = parseInt(localStorage.getItem('viewer_padding_bottom') || '60', 10);
    const padLeft = parseInt(localStorage.getItem('viewer_padding_left') || '20', 10);
    const padRight = parseInt(localStorage.getItem('viewer_padding_right') || '20', 10);

    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    console.log(`[Viewer-Padding] Current Scroll Mode: ${scrollMode}`);

    if (scrollMode === 'page') {
      // [페이지 모드]: 텍스트 박스 자체의 크기와 여백 오프셋을 직접 제어하여 글자 잘림 완전 차단 (진짜 물리 여백)
      wrapper.style.height = `calc(100vh - ${80 + padTop + padBottom}px)`; // 탑바(60px) + 안전마진(20px) + 여백
      wrapper.style.marginTop = `${padTop + 40}px`; // 탑바 고려 오프셋
      wrapper.style.maxWidth = `calc(100% - ${padLeft + padRight}px)`;
      wrapper.style.padding = '0'; // 물리 박스이므로 패딩은 0

      contentArea.style.padding = '0'; // 내측 패딩 소거
      console.log(`[Viewer-Padding] Physical Page Box resized: Height=calc(100vh - ${80+padTop+padBottom}px), MarginTop=${padTop+40}px, MaxWidth=calc(100% - ${padLeft+padRight}px)`);
    } else {
      // [스크롤 모드]: 세로 연속 흐름이므로 래퍼 크기는 복원하고 안쪽 패딩으로 자연스레 밀어내기
      wrapper.style.height = '100%';
      wrapper.style.marginTop = '0';
      wrapper.style.maxWidth = '100%';
      wrapper.style.padding = '0';

      contentArea.style.paddingTop = `${padTop}px`;
      contentArea.style.paddingBottom = `${padBottom}px`;
      contentArea.style.paddingLeft = `${padLeft}px`;
      contentArea.style.paddingRight = `${padRight}px`;
      console.log(`[Viewer-Padding] Scroll Mode paddings applied: Top=${padTop}px, Bottom=${padBottom}px, Left=${padLeft}px, Right=${padRight}px`);
    }
  }
}

// 윈도우 전역 함수 매핑
window.toggleViewerPaddingPanel = toggleViewerPaddingPanel;
window.applyViewerPaddingRealtime = applyViewerPaddingRealtime;
