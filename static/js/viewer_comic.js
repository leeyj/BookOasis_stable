// viewer_comic.js – 만화 ZIP 뷰어 로직
import { state } from './state.js';
import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

export let comicFitMode = 'height'; // 기본: 높이에 맞추기
export let comicCurrentPage = 0;
export let comicTotalPages = 0;
let comicLoadingTimer = null;
let observer = null;
let isScrollingToTarget = false;

export function initComicViewer(bookId, pagesRead, totalPages) {
  console.log(`[Viewer-Comic] initComicViewer - 읽은 페이지: ${pagesRead}, 전체 페이지: ${totalPages}`);
  document.getElementById('comic-viewer-container').style.display = 'flex';
  document.getElementById('comic-fit-controls').style.display = 'flex';
  
  comicCurrentPage = pagesRead > 0 ? pagesRead - 1 : 0;
  comicTotalPages = totalPages;
  
  applyComicFitMode();
  loadComicPage();
}

// 만화 이미지 맞추기 모드 전환
export function setComicFitMode(mode) {
  comicFitMode = mode;
  const btnHeight = document.getElementById('btn-fit-height');
  const btnWidth = document.getElementById('btn-fit-width');
  if (btnHeight) btnHeight.classList.toggle('active', mode === 'height');
  if (btnWidth) btnWidth.classList.toggle('active', mode === 'width');

  const btnOverlayHeight = document.getElementById('btn-overlay-fit-height');
  const btnOverlayWidth = document.getElementById('btn-overlay-fit-width');
  if (btnOverlayHeight) btnOverlayHeight.classList.toggle('active', mode === 'height');
  if (btnOverlayWidth) btnOverlayWidth.classList.toggle('active', mode === 'width');

  applyComicFitMode();
}

export function applyComicFitMode() {
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (!wrapper) return;
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  
  wrapper.classList.remove('fit-height', 'fit-width', 'scroll-mode');
  wrapper.classList.add(comicFitMode === 'width' ? 'fit-width' : 'fit-height');
  
  if (scrollMode === 'scroll') {
    wrapper.classList.add('scroll-mode');
  }
}

export function loadComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (!wrapper) return;

  if (observer) {
    observer.disconnect();
    observer = null;
  }

  if (scrollMode === 'scroll') {
    console.log(`[Viewer-Comic] 스크롤 모드 로드 시작 - 현재 페이지: ${comicCurrentPage}`);
    showViewerLoading("도서 준비 중...", "만화 이미지를 세로 연속 스크롤 모드로 로드하고 있습니다.");

    wrapper.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const imgElements = [];

    for (let i = 0; i < comicTotalPages; i++) {
      const img = document.createElement('img');
      img.className = 'comic-scroll-img';
      img.dataset.index = i;
      img.alt = `Page ${i + 1}`;
      img.loading = 'lazy';
      
      img.src = `/api/media/stream?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&page_idx=${i}`;
      
      fragment.appendChild(img);
      imgElements.push(img);
    }
    
    wrapper.appendChild(fragment);
    hideViewerLoading();

    const observerOptions = {
      root: wrapper,
      rootMargin: '0px',
      threshold: 0.3
    };

    observer = new IntersectionObserver((entries) => {
      if (isScrollingToTarget) return;
      
      let bestEntry = null;
      let maxRatio = 0;

      entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio > maxRatio) {
          maxRatio = entry.intersectionRatio;
          bestEntry = entry;
        }
      });

      if (bestEntry) {
        const pageIdx = parseInt(bestEntry.target.dataset.index, 10);
        if (pageIdx !== comicCurrentPage) {
          comicCurrentPage = pageIdx;
          updatePageInfo();
          saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
        }
      }
    }, observerOptions);

    imgElements.forEach(img => observer.observe(img));

    isScrollingToTarget = true;
    setTimeout(() => {
      const targetImg = imgElements[comicCurrentPage];
      if (targetImg) {
        targetImg.scrollIntoView({ block: 'start' });
      }
      setTimeout(() => {
        isScrollingToTarget = false;
      }, 300);
    }, 100);

    updatePageInfo();

  } else {
    let imgEl = document.getElementById('comic-page-img');
    if (!imgEl) {
      wrapper.innerHTML = '<img id="comic-page-img" src="" alt="Comic Page">';
      imgEl = document.getElementById('comic-page-img');
    } else {
      wrapper.innerHTML = '';
      wrapper.appendChild(imgEl);
    }

    console.log(`[Viewer-Comic] 페이지 모드 로드 시작 - page_idx=${comicCurrentPage}`);

    if (comicLoadingTimer) {
      clearTimeout(comicLoadingTimer);
      comicLoadingTimer = null;
    }

    const delayStr = localStorage.getItem('comic_loading_delay');
    const delay = (delayStr !== null) ? parseInt(delayStr, 10) : 300;

    comicLoadingTimer = setTimeout(() => {
      imgEl.style.opacity = '0';
      showViewerLoading("다운로드 중...", "Google Drive에서 만화 이미지를 가져오고 있습니다.<br>잠시만 기다려 주세요.");
    }, delay);

    imgEl.onload = () => {
      console.log(`[Viewer-Comic] 만화 이미지 로드 성공: page_idx=${comicCurrentPage}`);
      if (comicLoadingTimer) {
        clearTimeout(comicLoadingTimer);
        comicLoadingTimer = null;
      }
      hideViewerLoading();
      imgEl.style.opacity = '1';
      
      if (comicCurrentPage === 0) {
        const aspectRatio = imgEl.naturalWidth / imgEl.naturalHeight;
        if (aspectRatio < 0.7) {
          setComicFitMode('width');
        } else {
          setComicFitMode('height');
        }
      }

      preloadNextPages();
    };

    imgEl.onerror = () => {
      console.error(`[Viewer-Comic] 만화 이미지 로드 실패: page_idx=${comicCurrentPage}`);
      if (comicLoadingTimer) {
        clearTimeout(comicLoadingTimer);
        comicLoadingTimer = null;
      }
      showViewerError("이미지 로드에 실패했습니다.", "서버 연결 및 인터넷 상태를 확인해 주세요.");
      imgEl.style.opacity = '1';
    };

    imgEl.src = `/api/media/stream?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&page_idx=${comicCurrentPage}`;
    
    updatePageInfo();
    saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
  }
}

function updatePageInfo() {
  const infoEl = document.getElementById('comic-page-info');
  const textInfo = `${comicCurrentPage + 1} / ${comicTotalPages || '?'}`;
  if (infoEl) infoEl.textContent = textInfo;
  
  const overlayInfoEl = document.getElementById('comic-overlay-page-info');
  if (overlayInfoEl) overlayInfoEl.textContent = textInfo;

  const overlayTitleEl = document.getElementById('overlay-title-text');
  if (overlayTitleEl) overlayTitleEl.textContent = document.getElementById('viewer-title-text').textContent;
}

// Kavita 스타일 오버레이 메뉴 토글
export function toggleComicOverlay() {
  const menu = document.getElementById('comic-overlay-menu');
  if (!menu) return;
  menu.style.display = (menu.style.display === 'none') ? 'flex' : 'none';
}

// 처음부터 보기
export function jumpToFirstPage() {
  comicCurrentPage = 0;
  loadComicPage();
  toggleComicOverlay();
}

// 읽음 완료 처리 (진척도를 마지막 페이지로 강제 세팅)
export function markAsCompleted() {
  if (comicTotalPages > 0) {
    comicCurrentPage = comicTotalPages - 1;
    loadComicPage();
    
    // 즉시 진척도 동기 전송 (Alert 블로킹으로 인한 누수 차단)
    saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
    import('./viewer_progress.js').then(m => {
      m.flushProgress();
    });

    alert('완독 처리되었습니다.');
    toggleComicOverlay();
  }
}

export function nextComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'scroll') {
    if (comicCurrentPage < comicTotalPages - 1) {
      isScrollingToTarget = true;
      comicCurrentPage++;
      const targetImg = document.querySelector(`.comic-scroll-img[data-index="${comicCurrentPage}"]`);
      if (targetImg) {
        targetImg.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      updatePageInfo();
      saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
      setTimeout(() => { isScrollingToTarget = false; }, 500);
    } else {
      import('./viewer_next_episode.js').then(m => {
        m.handleNextEpisode(state.activeBookId);
      });
    }
  } else {
    if (comicCurrentPage < comicTotalPages - 1) {
      comicCurrentPage++;
      loadComicPage();
    } else {
      import('./viewer_next_episode.js').then(m => {
        m.handleNextEpisode(state.activeBookId);
      });
    }
  }
}

export function prevComicPage() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'scroll') {
    if (comicCurrentPage > 0) {
      isScrollingToTarget = true;
      comicCurrentPage--;
      const targetImg = document.querySelector(`.comic-scroll-img[data-index="${comicCurrentPage}"]`);
      if (targetImg) {
        targetImg.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      updatePageInfo();
      saveProgress(state.activeBookId, comicCurrentPage, comicTotalPages);
      setTimeout(() => { isScrollingToTarget = false; }, 500);
    }
  } else {
    if (comicCurrentPage > 0) {
      comicCurrentPage--;
      loadComicPage();
    }
  }
}

// 다음 2개 페이지 이미지 비동기 프리로드 헬퍼
function preloadNextPages() {
  const preloadCount = 2;
  for (let i = 1; i <= preloadCount; i++) {
    const nextIdx = comicCurrentPage + i;
    if (nextIdx < comicTotalPages) {
      const preloadImg = new Image();
      preloadImg.src = `/api/media/stream?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&page_idx=${nextIdx}`;
    }
  }
}

