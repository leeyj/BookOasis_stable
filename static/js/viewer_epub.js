import { getViewerSettings } from './viewer_settings.js';
import { state } from './state.js';
import { closeMediaViewer } from './viewer.js';

export let epubBook = null;
export let epubRendition = null;

export function initEpubViewer(bookId) {
  if (typeof ePub === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/epubjs@0.3.88/dist/epub.min.js';
    script.onload = () => _doInitEpubViewer(bookId);
    script.onerror = (error) => {
      console.error('EPUB 라이브러리 로드 실패 상세 원인:', error);
      alert('EPUB 뷰어 라이브러리를 불러오지 못했습니다.\n네트워크 연결을 확인해 주세요.');
      closeMediaViewer();
    };
    document.head.appendChild(script);
    return;
  }
  _doInitEpubViewer(bookId);
}

import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

function _doInitEpubViewer(bookId) {
  console.log(`[Viewer-Epub] _doInitEpubViewer - EPUB 뷰어 초기화 시작: bookId=${bookId}`);
  const container = document.getElementById('epub-viewer-container');
  container.style.display = 'flex';
  const renderArea = document.getElementById('epub-render-area');
  renderArea.innerHTML = '';
  
  showViewerLoading("도서를 불러오는 중...", "EPUB 도서 파일을 읽어오고 있습니다.<br>잠시만 기다려 주세요.");
  
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
        }).catch(err => {
          console.error("[Viewer-Epub] epubBook ready 실패:", err);
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

        // 4. 페이지 이동(relocated) 시 진행률 저장 연동
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
        });

        epubRendition.display().catch(err => {
          console.error("[Viewer-Epub] display 렌더링 실패:", err);
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
      showViewerError("도서 파일을 불러오지 못했습니다.", err.message);
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
