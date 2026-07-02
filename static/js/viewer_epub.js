import { getViewerSettings } from './viewer_settings.js';
import { state } from './state.js';
import { closeMediaViewer } from './viewer.js';

export let epubBook = null;
export let epubRendition = null;
export let epubTotalPages = 0;

export function initEpubViewer(bookId, pagesRead, totalPages) {
  if (typeof ePub === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/epubjs@0.3.88/dist/epub.min.js';
    script.onload = () => _doInitEpubViewer(bookId, pagesRead, totalPages);
    script.onerror = (error) => {
      console.error('EPUB 라이브러리 로드 실패 상세 원인:', error);
      alert(i18n.t('viewer.epub_lib_fail'));
      closeMediaViewer();
    };
    document.head.appendChild(script);
    return;
  }
  _doInitEpubViewer(bookId, pagesRead, totalPages);
}

import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

async function _doInitEpubViewer(bookId, pagesRead, totalPages) {
  console.log(`[Viewer-Epub] _doInitEpubViewer - EPUB 뷰어 초기화 시작: bookId=${bookId}, totalPages=${totalPages}`);
  const container = document.getElementById('epub-viewer-container');
  container.style.display = 'flex';
  const renderArea = document.getElementById('epub-render-area');
  renderArea.innerHTML = '';
  
  epubTotalPages = totalPages || 0;
  
  // 뷰어 진입 시 totalPages가 0이면 백엔드 API를 통해 동적 계산 시도 (DB 동기화용)
  if (epubTotalPages === 0) {
    try {
      showViewerLoading('페이지 정보 동기화 중...');
      const libType = state.currentLibraryType || 'general';
      const res = await fetch(`/api/media/books/${bookId}/info?type=${libType}`);
      const data = await res.json();
      if (data.success && data.total_pages > 0) {
        epubTotalPages = data.total_pages;
      }
    } catch (e) {
      console.warn('[Viewer-Epub] 동적 페이지 로딩 실패:', e);
    }
  }

  showViewerLoading(i18n.t("viewer.loading_epub_title") || "EPUB 준비 중", i18n.t("viewer.loading_epub_sub") || "잠시만 기다려 주세요...");
  
  const url = `/api/media/pdf?db_type=${state.currentLibraryType}&book_id=${bookId}&_cb=${new Date().getTime()}&ext=.epub`;
  console.log(`[Viewer-Epub] EPUB 바이너리 수동 Fetch 시도 url: ${url}`);

  fetch(url)
    .then(res => {
      if (!res.ok) throw new Error(`HTTP 에러: ${res.status}`);
      return res.arrayBuffer();
    })
    .then(buffer => {
      console.log(`[Viewer-Epub] EPUB 바이너리 수신 완료. 크기: ${buffer.byteLength} bytes`);
      hideViewerLoading();

      try {
        epubBook = ePub(buffer);
        
        epubBook.opened.then(() => {
          console.log("[Viewer-Epub] epubBook opened 성공");
        }).catch(err => {
          console.error("[Viewer-Epub] epubBook opened 실패:", err);
        });

        epubBook.ready.then(() => {
          console.log("[Viewer-Epub] epubBook ready 완료 - 책 정보:", epubBook.package.metadata);
          // 퍼센트 탐색을 위한 locations 사전 생성 (글자 수 기준 1600자)
          return epubBook.locations.generate(1600);
        }).then((locations) => {
          console.log("[Viewer-Epub] Locations 생성 완료. 슬라이더 연동 준비 끝");
          syncEpubSeekBar();
          
          if (pagesRead > 0 && pagesRead <= 100) {
            const percentage = pagesRead / 100;
            const cfi = epubBook.locations.cfiFromPercentage(percentage);
            if (cfi) {
              console.log(`[Viewer-Epub] Jumping to saved location: ${pagesRead}%`);
              return epubRendition.display(cfi);
            }
          }
          return epubRendition.display();
        }).catch(err => {
          console.error("[Viewer-Epub] epubBook ready 또는 locations 생성/렌더링 실패:", err);
          epubRendition.display().catch(e => console.error("[Viewer-Epub] Fallback display 실패:", e));
        });

        // 1. 초기 렌더링 옵션 빌드
        const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
        const renderOptions = { width: '100%', height: '100%' };
        if (scrollMode === 'page') {
          renderOptions.manager = 'default';
          renderOptions.flow = 'paginated';
          renderOptions.spread = 'always';
        } else {
          renderOptions.manager = 'continuous';
          renderOptions.flow = 'scrolled-doc';
        }

        epubRendition = epubBook.renderTo('epub-render-area', renderOptions);

        // 2. 훅 등록 (사용자 정의 폰트 인젝션)
        registerEpubHooks();

        // 3. 설정 반영
        applyEpubSettings();

        // 4. 페이지 이동(relocated) 시 진행률 저장 및 시크바 동기화 연동
        epubRendition.on('relocated', (location) => {
          console.log("[Viewer-Epub] Relocated to location:", location);
          
          let pageIdx = 0;
          let totalPages = 100; // epub.js 특성상 고정 100분율로 0-100 계산

          if (location && location.start) {
            const percentage = epubBook.locations.percentageFromCfi(location.start.cfi);
            if (percentage >= 0) {
              pageIdx = Math.round(percentage * 100);
            }
          }
          saveProgress(state.activeBookId, pageIdx, totalPages);
          syncEpubSeekBar(); // 뷰어 스크롤 이동 시 시크바 썸 위치 최신화
        });


        document.getElementById('epub-prev').onclick = epubPrevPage;
        document.getElementById('epub-next').onclick = epubNextPage;
      } catch (e) {
        console.error("[Viewer-Epub] EPUB 뷰어 생성 중 예외 발생:", e);
      }
    })
    .catch(err => {
      console.error("[Viewer-Epub] EPUB 파일 로드 실패:", err);
      hideViewerLoading();
      showViewerError(i18n.t("viewer.error_epub_title"), err.message);
    });
}

export function registerEpubHooks() {
  if (!epubRendition) return;

  epubRendition.hooks.content.register(function(contents) {
    console.log("[Viewer-Epub] Injecting custom fonts to EPUB iframe content...");
    const doc = contents.document;
    const style = doc.createElement('style');
    style.id = 'epub-custom-fonts-style';
    
    let fontStyles = '';
    const customFonts = window.customFonts || [];
    customFonts.forEach(font => {
      const fontFaceName = `CustomFont_${font.name.replace(/\s+/g, '_')}`;
      fontStyles += `
        @font-face {
          font-family: '${fontFaceName}';
          src: url('${font.url}');
        }
      `;
    });
    
    style.textContent = fontStyles;
    doc.head.appendChild(style);
  });
}

export function applyEpubSettings() {
  if (!epubRendition) return;

  const { theme, fontSize, fontFamily } = getViewerSettings();

  // 폰트 정의
  let fontCSS = "'KoPub Batang', 'Nanum Myeongjo', serif";
  if (fontFamily === 'gothic') {
    fontCSS = "'Nanum Gothic', 'Malgun Gothic', sans-serif";
  } else if (fontFamily === 'pretendard') {
    fontCSS = "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif";
  } else if (fontFamily !== 'batang') {
    fontCSS = `'CustomFont_${fontFamily.replace(/\s+/g, '_')}', sans-serif`;
  }

  // 부모 DOM 컨테이너 배경 동기화
  const container = document.getElementById('epub-viewer-container');
  const renderArea = document.getElementById('epub-render-area');
  if (container) container.style.setProperty('background-color', theme.background, 'important');
  if (renderArea) renderArea.style.setProperty('background-color', theme.background, 'important');

  // epub.js 테마 및 스타일 설정
  epubRendition.themes.default({
    'body': { 
      'color': `${theme.text} !important`, 
      'background-color': `${theme.background} !important`,
      'font-family': `${fontCSS} !important`,
      'font-size': `${fontSize}rem !important`
    },
    'p': { 
      'color': `${theme.text} !important`, 
      'line-height': '1.8 !important',
      'font-family': `${fontCSS} !important`
    },
    'span': { 
      'color': `${theme.text} !important`,
      'font-family': `${fontCSS} !important`
    },
    'div': { 
      'color': `${theme.text} !important`,
      'font-family': `${fontCSS} !important`,
      'background-color': 'transparent !important'
    },
    'h1': { 'color': `${theme.heading} !important`, 'font-family': `${fontCSS} !important` },
    'h2': { 'color': `${theme.heading} !important`, 'font-family': `${fontCSS} !important` },
    'h3': { 'color': `${theme.heading} !important`, 'font-family': `${fontCSS} !important` }
  });

  epubRendition.themes.fontSize(`${fontSize * 100}%`);
}

export function changeEpubScrollMode(scrollMode) {
  if (!epubBook || !epubRendition) return;

  // 현재 위치 백업
  let currentLocation = null;
  const visible = epubRendition.currentLocation();
  if (visible && visible.start) {
    currentLocation = visible.start.cfi;
  }

  console.log(`[Viewer-Epub] Re-rendering EPUB with scrollMode=${scrollMode}, cfi=${currentLocation}`);

  // 기존 rendition 정리
  epubRendition.destroy();

  // 신규 렌더링 옵션 빌드
  const renderOptions = { width: '100%', height: '100%' };
  if (scrollMode === 'page') {
    renderOptions.manager = 'default';
    renderOptions.flow = 'paginated';
    renderOptions.spread = 'always';
  } else {
    renderOptions.manager = 'continuous';
    renderOptions.flow = 'scrolled-doc';
  }

  epubRendition = epubBook.renderTo('epub-render-area', renderOptions);
  
  // 훅 및 세팅 재적용
  registerEpubHooks();
  applyEpubSettings();

  epubRendition.display(currentLocation || undefined).catch(err => {
    console.error("[Viewer-Epub] 리렌더링 display 복구 실패:", err);
  });
}

export function epubPrevPage() {
  if (epubRendition) epubRendition.prev();
}

export function epubNextPage() {
  if (!epubRendition) return;
  const currentLoc = epubRendition.currentLocation();
  epubRendition.next().then(() => {
    const newLoc = epubRendition.currentLocation();
    if (currentLoc && newLoc && currentLoc.start.cfi === newLoc.start.cfi) {
      import('./viewer_next_episode.js').then(m => {
        m.handleNextEpisode(state.activeBookId);
      });
    }
  }).catch(() => {
    import('./viewer_next_episode.js').then(m => {
      m.handleNextEpisode(state.activeBookId);
    });
  });
}

export function clearEpubViewer() {
  if (epubBook) {
    epubBook.destroy();
    epubBook = null;
    epubRendition = null;
  }
}
// ==========================================
// 시크바 (슬라이더) 컨트롤 (EPUB용: % 기반)
// ==========================================
function getEpubPercentage() {
  if (!epubBook || !epubRendition || !epubRendition.location) return 0;
  const cfi = epubRendition.location.start?.cfi;
  if (!cfi) return 0;
  const p = epubBook.locations.percentageFromCfi(cfi);
  return (p && p >= 0) ? Math.round(p * 100) : 0;
}

export function syncEpubSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  if (!slider) return;
  slider.min = 0;
  slider.max = 100;
  const val = getEpubPercentage();
  slider.value = val;
  
  const endLabel = document.getElementById('seekbar-end-label');
  if (endLabel) endLabel.textContent = '100%';
  
  const badge = document.getElementById('comic-overlay-page-info');
  if (badge) badge.textContent = `${val}%`;
}

export function epubSliderInput(slider, val) {
  // 드래그 중: 툴팁에 % 표시
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) {
    tooltip.textContent = `${val}%`;
    tooltip.style.display = 'block';
    
    // 툴팁 위치 계산 (viewer_comic과 유사)
    const min = parseInt(slider.min, 10) || 0;
    const max = parseInt(slider.max, 10) || 100;
    const trackWidth = slider.offsetWidth;
    const percent = (val - min) / (max - min);
    const thumbOffset = percent * trackWidth;
    tooltip.style.left = `calc(${thumbOffset}px - 14px)`;
  }
  
  const badge = document.getElementById('comic-overlay-page-info');
  if (badge) badge.textContent = `${val}%`;
}

export function epubSliderChange(slider, val) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) tooltip.style.display = 'none';

  if (!epubBook || !epubRendition) return;
  const percentage = val / 100;
  const cfi = epubBook.locations.cfiFromPercentage(percentage);
  if (cfi) {
    epubRendition.display(cfi);
  }
}

export function epubJumpToFirstPage() {
  if (epubRendition) epubRendition.display(0);
}

export function epubJumpToLastPage() {
  if (!epubBook || !epubRendition) return;
  const cfi = epubBook.locations.cfiFromPercentage(1.0);
  if (cfi) epubRendition.display(cfi);
}
