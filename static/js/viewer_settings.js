// viewer_settings.js – 뷰어 테마 및 폰트 설정 제어 센터
import { state } from './state.js';

export const THEMES = {
  dark: {
    name: 'dark',
    background: '#0f172a',
    text: '#e2e8f0',
    heading: '#f8fafc',
    className: 'txt-reader-theme-dark'
  },
  light: {
    name: 'light',
    background: '#e2e8f0',
    text: '#0f172a',
    heading: '#020617',
    className: 'txt-reader-theme-light'
  }
};

// 1. 현재 설정 값 통합 획득
export function getViewerSettings() {
  // DB에서 로드된 시스템 설정 기반 Fallback 계산
  const defaultSizePx = state.systemSettings?.VIEWER_FONT_SIZE ? parseInt(state.systemSettings.VIEWER_FONT_SIZE, 10) : 18;
  const defaultSizeRem = (defaultSizePx / 16).toFixed(2); // px -> rem 변환
  
  const defaultFontFamily = state.systemSettings?.VIEWER_FONT_FAMILY || 'sans-serif';
  let fontMap = 'gothic'; // 기본 Nanum Gothic
  if (defaultFontFamily === 'serif') fontMap = 'batang';
  else if (defaultFontFamily === 'monospace') fontMap = 'monospace';
  else if (defaultFontFamily === 'sans-serif') fontMap = 'pretendard';

  const themeKey = localStorage.getItem('viewer_theme') || 'dark';
  const fontSize = parseFloat(localStorage.getItem('viewer_font_size') || defaultSizeRem);
  const fontFamily = localStorage.getItem('viewer_font_family') || fontMap;
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const lineHeight = parseFloat(localStorage.getItem('viewer_line_height') || '1.8');
  const paragraphSpacing = parseFloat(localStorage.getItem('viewer_paragraph_spacing') || '1.0');

  return {
    theme: THEMES[themeKey] || THEMES.dark,
    fontSize,
    fontFamily,
    scrollMode,
    lineHeight,
    paragraphSpacing
  };
}

// 2. 폰트 크기 변경 액션
export function updateFontSize(dir) {
  let size = parseFloat(localStorage.getItem('viewer_font_size') || '1.15');
  size += dir * 0.1;
  size = Math.max(0.8, Math.min(2.5, size));
  localStorage.setItem('viewer_font_size', size.toFixed(2));
  return size;
}

// 3. 테마 토글 액션
export function toggleTheme() {
  const current = localStorage.getItem('viewer_theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem('viewer_theme', next);
  return THEMES[next];
}

// 4. 행간 설정 저장
export function updateLineHeight(val) {
  localStorage.setItem('viewer_line_height', val);
}

// 5. 단락 간격 설정 저장
export function updateParagraphSpacing(val) {
  localStorage.setItem('viewer_paragraph_spacing', val);
}

// 📌 뷰어 공통 사용 가능 폰트 메타데이터 정의
export const VIEWER_FONTS = [
  { name: 'batang', url: '/static/fonts/KoPubWorldBatang_Pro_Medium.woff2' },
  { name: 'gothic', url: '/static/fonts/NanumGothic.woff2' },
  { name: 'pretendard', url: '/static/fonts/Pretendard-Regular.woff2' }
];

/**
 * 폰트 리소스를 동적으로 다운로드하여 Document.fonts에 등록하고 대상 엘리먼트에 적용합니다.
 * @param {string} fontName - 폰트 이름 키
 * @param {string} fontUrl - 폰트 woff2/woff 등 파일 다운로드 경로
 * @param {HTMLElement} element - 적용 대상 엘리먼트 (옵션)
 * @returns {Promise<string>} 로드 완료된 폰트 패밀리 이름
 */
export function loadAndApplyCustomFont(fontName, fontUrl, element) {
  const fontFaceName = `CustomFont_${fontName.replace(/\s+/g, '_')}`;
  
  // 이미 로드되었는지 브라우저 폰트 셋 확인
  let exists = false;
  for (let f of document.fonts.values()) {
    if (f.family === fontFaceName) {
      exists = true;
      break;
    }
  }
  
  if (exists) {
    if (element) {
      element.style.fontFamily = `'${fontFaceName}', sans-serif`;
    }
    return Promise.resolve(fontFaceName);
  }
  
  console.log(`[Viewer-Settings] Loading custom font: ${fontFaceName} from ${fontUrl}`);
  const fontFace = new FontFace(fontFaceName, `url("${fontUrl}")`);
  return fontFace.load().then(loadedFace => {
    document.fonts.add(loadedFace);
    if (element) {
      element.style.fontFamily = `'${fontFaceName}', sans-serif`;
    }
    return fontFaceName;
  }).catch(err => {
    console.error(`[Viewer-Settings] Failed to load custom font: ${fontName}`, err);
    // 실패 시 일반 폰트 패밀리 적용
    if (element) {
      element.style.fontFamily = fontName;
    }
    return fontName;
  });
}
