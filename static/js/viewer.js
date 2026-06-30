// viewer.js – 미디어 뷰어 라이프사이클 및 단축키 코어 조율기
import { state } from './state.js';
import { initComicViewer, nextComicPage, prevComicPage, setComicFitMode, toggleComicOverlay, markAsCompleted } from './viewer_comic.js';
import { initTxtViewer, prevTxtPage, nextTxtPage, applyTxtSettings } from './viewer_txt.js';
import { initPdfViewer, nextPdfPage, prevPdfPage, clearPdfViewer } from './viewer_pdf.js';
import { initEpubViewer, clearEpubViewer, epubPrevPage, epubNextPage, applyEpubSettings, changeEpubScrollMode } from './viewer_epub.js';
import { updateFontSize, toggleTheme } from './viewer_settings.js';

// 사용자 정의 폰트 목록 로드 및 드롭다운 바인딩
export function loadCustomFontsList() {
  fetch('/api/media/fonts')
    .then(res => res.json())
    .then(data => {
      if (data.success && data.fonts) {
        window.customFonts = data.fonts;
        console.log("[Viewer-Fonts] Custom fonts loaded: ", window.customFonts);
        
        const select = document.getElementById('viewer-font-select');
        if (select) {
          // 기존 기본 옵션만 남기고 초기화
          select.innerHTML = `
            <option value="batang">KoPub 바탕</option>
            <option value="gothic">나눔고딕</option>
            <option value="pretendard">Pretendard</option>
          `;
          data.fonts.forEach(font => {
            const opt = document.createElement('option');
            opt.value = font.name;
            opt.textContent = font.name;
            select.appendChild(opt);
          });
          
          // 현재 선택된 폰트 복원
          const savedFont = localStorage.getItem('viewer_font_family') || 'batang';
          select.value = savedFont;
        }
      }
    })
    .catch(err => console.error("[Viewer-Fonts] Failed to fetch custom fonts list:", err));
}

// openReader: 포맷별 뷰어 디스패치 초기화
export function openReader(bookId, format, title, pagesRead, totalPages) {
  console.log(`[Viewer-Core] openReader 시작 - Book ID: ${bookId}, Format: ${format}, Title: ${title}`);
  state.activeBookId = bookId;
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;
  
  // Stacking Context(쌓임 맥락) 왜곡으로 인한 레이아웃 밀림 방지를 위해 body 바로 하위로 이동
  if (viewerModal.parentNode !== document.body) {
    document.body.appendChild(viewerModal);
  }
  
  viewerModal.style.display = 'flex';
  document.getElementById('viewer-title-text').textContent = title;

  // 뷰어 모달을 연 경우, 히스토리 스택에 #viewer 상태를 추가
  if (window.location.hash !== '#viewer') {
    history.pushState({ view: 'viewer', bookId, libraryId: state.currentLibraryId }, '', '#viewer');
  }
  
  // 브라우저 자체의 스크롤바 완전 격리 (이중 스크롤 방지)
  document.body.style.overflow = 'hidden';

  // 새 만화 로드 시 오버레이 메뉴를 숨김 상태로 초기화
  const overlayMenu = document.getElementById('comic-overlay-menu');
  if (overlayMenu) overlayMenu.style.display = 'none';

  // 모든 뷰어 영역 및 컨트롤 숨김
  document.querySelectorAll('.viewer-pane').forEach(p => p.style.display = 'none');
  document.getElementById('txt-controls').style.display = 'none';
  document.getElementById('comic-fit-controls').style.display = 'none';

  // 공용 오버레이 조작 패널 분기 제어
  const overlayComicFit = document.getElementById('overlay-comic-fit-group');
  const overlayTxtControls = document.getElementById('overlay-txt-controls-group');
  if (overlayComicFit) overlayComicFit.style.display = 'none';
  if (overlayTxtControls) overlayTxtControls.style.display = 'none';

  // 폰트 목록 갱신 및 UI 상태 동기화
  loadCustomFontsList();
  
  const savedFont = localStorage.getItem('viewer_font_family') || 'batang';
  const select = document.getElementById('viewer-font-select');
  if (select) select.value = savedFont;
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const btnPage = document.getElementById('btn-scroll-page');
  const btnScroll = document.getElementById('btn-scroll-continuous');
  if (scrollMode === 'page') {
    if (btnPage) btnPage.classList.add('active');
    if (btnScroll) btnScroll.classList.remove('active');
  } else {
    if (btnPage) btnPage.classList.remove('active');
    if (btnScroll) btnScroll.classList.add('active');
  }

  const fmt = format.toLowerCase();
  state.currentViewerFormat = fmt;
  if (fmt === 'zip' || fmt === 'cbz') {
    if (overlayComicFit) overlayComicFit.style.display = 'flex';
    initComicViewer(bookId, pagesRead, totalPages).then(() => {
      initViewerSeekBar();
    });
  } else if (fmt === 'txt') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_text') || '텍스트 보기';
    initTxtViewer(bookId);
  } else if (fmt === 'pdf') {
    initPdfViewer(bookId, pagesRead, totalPages);
  } else if (fmt === 'epub') {
    if (overlayTxtControls) overlayTxtControls.style.display = 'flex';
    document.getElementById('comic-overlay-page-info').textContent = i18n.t('viewer.view_epub') || 'EPUB 보기';
    initEpubViewer(bookId, totalPages);
    initViewerSeekBar();
  } else {
    alert(i18n.t('viewer.unsupported_format'));
    closeMediaViewer();
  }
}

export function closeMediaViewer(triggerBack = true, isTransitioning = false) {
  const viewerModal = document.getElementById('media-viewer-modal');
  if (!viewerModal) return;
  
  if (!isTransitioning) {
    viewerModal.classList.remove('fullscreen-mode');
    viewerModal.style.display = 'none';
    document.getElementById('fullscreen-icon').className = 'fa-solid fa-expand';
    // 브라우저 스크롤 복원
    document.body.style.overflow = '';
  }

  // 포맷별 정리 함수 위임 호출
  clearEpubViewer();
  clearPdfViewer();

  // 대기 중인 진척도 저장 예약 건 즉시 동기화(Flush) 및 메인 뷰 데이터 리로드
  import('./viewer_progress.js').then(m => {
    const flushPromise = m.flushProgress();
    if (m.resetPreloadState) m.resetPreloadState();

    const reloadData = () => {
      console.log("[Viewer-Core] DB Progress flush 완료. 화면 데이터 갱신을 실행합니다.");
      if (state.currentLibraryId === 'home') {
        import('./dashboard.js').then(d => d.loadDashboardData());
      } else if (state.currentLibraryId === 'history') {
        import('./book_list.js').then(b => b.loadReadingHistory());
      }
      
      // 도서 상세 화면이 노출되어 있는 경우 상세 영역도 실시간 리렌더링
      const detailView = document.getElementById('book-detail-view');
      if (detailView && detailView.style.display !== 'none') {
        const titleEl = detailView.querySelector('.book-detail-title');
        if (titleEl) {
          const seriesName = titleEl.textContent.replace(i18n.t('detail.edit_info'), '').trim();
          import('./modal.js').then(mod => {
            mod.openBookDetail(null, seriesName, state.currentLibraryId);
          });
        }
      }
    };

    if (flushPromise && typeof flushPromise.then === 'function') {
      flushPromise.then(() => reloadData());
    } else {
      reloadData();
    }
  });

  // 수동 닫기 버튼을 누른 경우에만 브라우저 히스토리 스택 원상복구
  if (triggerBack && !isTransitioning && window.location.hash === '#viewer') {
    history.back();
  }
}

export function toggleFullscreenViewer() {
  const modal = document.getElementById('media-viewer-modal');
  const icon = document.getElementById('fullscreen-icon');
  const isFullscreen = modal.classList.contains('fullscreen-mode');
  if (isFullscreen) {
    modal.classList.remove('fullscreen-mode');
    icon.className = 'fa-solid fa-expand';
  } else {
    modal.classList.add('fullscreen-mode');
    icon.className = 'fa-solid fa-compress';
  }
}

// 이전 페이지 통합 조율
export function prevPage() {
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    prevComicPage();
  } else if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    prevPdfPage();
  } else if (document.getElementById('epub-viewer-container').style.display !== 'none') {
    epubPrevPage();
  } else if (document.getElementById('txt-viewer-container').style.display !== 'none') {
    prevTxtPage();
  }
}

// 다음 페이지 통합 조율
export function nextPage() {
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    nextComicPage();
  } else if (document.getElementById('pdf-viewer-container').style.display !== 'none') {
    nextPdfPage();
  } else if (document.getElementById('epub-viewer-container').style.display !== 'none') {
    epubNextPage();
  } else if (document.getElementById('txt-viewer-container').style.display !== 'none') {
    nextTxtPage();
  }
}

// 키보드 단축키 초기화 (F, ESC, ArrowLeft/Right, Space)
export function initKeyboardListener() {
  document.addEventListener('keydown', e => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;
    switch (e.key) {
      case 'f':
      case 'F':
        e.preventDefault();
        toggleFullscreenViewer();
        break;
      case 'Escape':
        if (viewerModal.classList.contains('fullscreen-mode')) {
          toggleFullscreenViewer();
        } else {
          closeMediaViewer();
        }
        break;
      case 'ArrowRight':
      case ' ':
        e.preventDefault();
        nextPage();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        prevPage();
        break;
    }
  });

  // 마우스 휠 리스너 함께 초기화
  initWheelListener();
}

let wheelLock = false;

// 마우스 휠 이벤트 리스너 통합 조율 (핫스팟으로 막힌 휠 복원 및 페이지 모드 연속 전환 차단)
export function initWheelListener() {
  const hotspot = document.getElementById('common-viewer-hotspot');
  if (!hotspot) return;

  hotspot.addEventListener('wheel', e => {
    const viewerModal = document.getElementById('media-viewer-modal');
    if (!viewerModal || viewerModal.style.display !== 'flex') return;

    const isComic = document.getElementById('comic-viewer-container').style.display !== 'none';
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    const isComicScroll = isComic && scrollMode === 'scroll';
    const isComicWidth = isComic && document.querySelector('.comic-image-wrapper') && document.querySelector('.comic-image-wrapper').classList.contains('fit-width');
    const isTxt = document.getElementById('txt-viewer-container').style.display !== 'none';
    const isPdf = document.getElementById('pdf-viewer-container').style.display !== 'none';
    const isEpub = document.getElementById('epub-viewer-container').style.display !== 'none';

    // 1. 만화 뷰어 스크롤/웹툰 모드, PDF 뷰어, 텍스트 뷰어 세로 스크롤 모드일 경우 -> 휠 스크롤 직접 위임 전달
    if (isComicScroll || isComicWidth || isPdf || (isTxt && scrollMode === 'scroll')) {
      let targetScrollEl = null;
      if (isComicScroll || isComicWidth) {
        targetScrollEl = document.querySelector('.comic-image-wrapper');
      } else if (isTxt) {
        targetScrollEl = document.getElementById('txt-scroll-wrapper');
      } else if (isPdf) {
        targetScrollEl = document.getElementById('pdf-render-area');
      }

      if (targetScrollEl) {
        targetScrollEl.scrollBy({
          top: e.deltaY,
          behavior: 'auto'
        });
        e.preventDefault();
        return;
      }
    }

    // 2. EPUB 세로 스크롤 모드일 경우 -> 내부 iframe으로 휠 스크롤 전파
    if (isEpub && scrollMode === 'scroll') {
      const iframe = document.querySelector('#epub-render-area iframe');
      if (iframe && iframe.contentWindow) {
        iframe.contentWindow.scrollBy(0, e.deltaY);
        e.preventDefault();
        return;
      }
    }

    // 3. 페이지 전환 모드 (만화 height 맞춤, TXT 가로 페이지, EPUB 가로 페이지 등)
    if (scrollMode === 'page' || (isComic && !isComicWidth)) {
      e.preventDefault();
      if (wheelLock) return;

      if (e.deltaY > 30) {
        wheelLock = true;
        nextPage();
        setTimeout(() => { wheelLock = false; }, 600);
      } else if (e.deltaY < -30) {
        wheelLock = true;
        prevPage();
        setTimeout(() => { wheelLock = false; }, 600);
      }
    }
  }, { passive: false });
}

// 공통 환경 설정 트리거 함수
export function changeFontSize(dir) {
  updateFontSize(dir);
  applyTxtSettings();
  applyEpubSettings();
}

export function toggleReaderTheme() {
  toggleTheme();
  applyTxtSettings();
  applyEpubSettings();
}

// HTML 인라인 이벤트 연동을 위해 글로벌 윈도우 객체에 바인딩
window.onViewerFontChange = function(value) {
  console.log(`[Viewer-Core] Font family changed to: ${value}`);
  localStorage.setItem('viewer_font_family', value);
  applyTxtSettings();
  applyEpubSettings();
};

window.setScrollMode = function(mode) {
  console.log(`[Viewer-Core] Scroll mode changed to: ${mode}`);
  localStorage.setItem('viewer_scroll_mode', mode);
  
  const btnPage = document.getElementById('btn-scroll-page');
  const btnScroll = document.getElementById('btn-scroll-continuous');
  if (mode === 'page') {
    if (btnPage) btnPage.classList.add('active');
    if (btnScroll) btnScroll.classList.remove('active');
  } else {
    if (btnPage) btnPage.classList.remove('active');
    if (btnScroll) btnScroll.classList.add('active');
  }
  
  // 만화책 뷰어가 활성화되어 있는 경우, 스크롤 모드를 적용하여 다시 렌더링
  if (document.getElementById('comic-viewer-container').style.display !== 'none') {
    import('./viewer_comic.js').then(m => {
      m.applyComicFitMode();
      m.loadComicPage();
    });
  }
  
  applyTxtSettings();
  changeEpubScrollMode(mode);
};

// ==========================================
// 시크바 통합 이벤트 라우터
// ==========================================
let _viewerSeekbarInited = false;

function initViewerSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  if (!slider) return;

  if (_viewerSeekbarInited) return;
  _viewerSeekbarInited = true;

  slider.addEventListener('input', (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;
    
    if (fmt === 'zip' || fmt === 'cbz') {
      import('./viewer_comic.js').then(m => m.comicSliderInput(slider, val));
    } else if (fmt === 'epub') {
      import('./viewer_epub.js').then(m => m.epubSliderInput(slider, val));
    }
  });

  slider.addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;
    
    if (fmt === 'zip' || fmt === 'cbz') {
      import('./viewer_comic.js').then(m => m.comicSliderChange(slider, val));
    } else if (fmt === 'epub') {
      import('./viewer_epub.js').then(m => m.epubSliderChange(slider, val));
    }
  });
}

export function viewerJumpToFirst() {
  const fmt = state.currentViewerFormat;
  if (fmt === 'zip' || fmt === 'cbz') {
    import('./viewer_comic.js').then(m => m.comicJumpToFirstPage());
  } else if (fmt === 'epub') {
    import('./viewer_epub.js').then(m => m.epubJumpToFirstPage());
  }
}

export function viewerJumpToLast() {
  const fmt = state.currentViewerFormat;
  if (fmt === 'zip' || fmt === 'cbz') {
    import('./viewer_comic.js').then(m => m.comicJumpToLastPage());
  } else if (fmt === 'epub') {
    import('./viewer_epub.js').then(m => m.epubJumpToLastPage());
  }
}

window.viewerJumpToFirst = viewerJumpToFirst;
window.viewerJumpToLast = viewerJumpToLast;
window.prevPage = prevPage;
window.nextPage = nextPage;
window.toggleTheme = toggleReaderTheme;

// 최초 로드 시 사용자 폰트 사전 로딩
loadCustomFontsList();

// 글로벌 핸들러 노출에 사용될 함수 재내보내기 (Re-export)
export { toggleComicOverlay, markAsCompleted, setComicFitMode, nextComicPage, prevComicPage, nextPdfPage, prevPdfPage, epubPrevPage, epubNextPage, prevTxtPage, nextTxtPage, initViewerSeekBar };
