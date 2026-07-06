export function getScrollMode() {
  return localStorage.getItem('viewer_scroll_mode') || 'page';
}

export function getEpubPageStep() {
  const pageStep = parseInt(localStorage.getItem('comic_page_step'), 10) || 1;
  return pageStep === 2 ? 2 : 1;
}

export function getReadingDirection() {
  return localStorage.getItem('comic_reading_direction') === 'rtl' ? 'rtl' : 'ltr';
}

export function getViewportSize(container) {
  const clientWidth = container ? container.clientWidth : 0;
  const clientHeight = container ? container.clientHeight : 0;
  let width = clientWidth || window.innerWidth;
  let height = clientHeight || window.innerHeight;

  if (window.visualViewport) {
    const vvWidth = Math.round(window.visualViewport.width || 0);
    const vvHeight = Math.round(window.visualViewport.height || 0);
    if (vvWidth > 0) {
      width = clientWidth > 0 ? Math.min(clientWidth, vvWidth) : vvWidth;
    }
    if (vvHeight > 0) {
      height = clientHeight > 0 ? Math.min(clientHeight, vvHeight) : vvHeight;
    }
  }

  return {
    width: Math.max(320, width),
    height: Math.max(240, height)
  };
}

export function getEffectivePageStep(viewportWidth, storedPageStep) {
  if (viewportWidth <= 600) return 1;
  return storedPageStep;
}

export function syncPageStepUI(step, forcedSinglePage) {
  const btn = document.getElementById('btn-comic-page-step');
  const label = document.getElementById('comic-page-step-label');

  if (btn) {
    btn.classList.toggle('active', step === 2 && !forcedSinglePage);
    btn.setAttribute('data-step', String(step));
    btn.title = forcedSinglePage
      ? '모바일 좁은 화면에서는 1장 보기만 지원됩니다'
      : (step === 2 ? '2장씩 보기' : '1장씩 보기');
  }

  if (label) {
    label.textContent = `${step}장`;
  }
}

export function resolveFontCSS(fontFamily) {
  if (fontFamily === 'gothic') {
    return "'Nanum Gothic', 'Malgun Gothic', sans-serif";
  }
  if (fontFamily === 'pretendard') {
    return "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif";
  }
  if (fontFamily !== 'batang') {
    return `'CustomFont_${fontFamily.replace(/\s+/g, '_')}', sans-serif`;
  }
  return "'KoPub Batang', 'Nanum Myeongjo', serif";
}
