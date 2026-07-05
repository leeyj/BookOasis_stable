// viewer_txt.js – 텍스트 리더(TXT) 뷰어 로직
import { state } from './state.js';

let txtChunks = [];
let currentChunkIdx = 0;

import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

export function initTxtViewer(bookId) {
  console.log(`[Viewer-Txt] initTxtViewer - TXT 콘텐츠 요청 중: bookId=${bookId}`);
  const pane = document.getElementById('txt-viewer-container');
  const contentArea = document.getElementById('txt-content-area');
  pane.style.display = 'block';
  
  // 기존 수동 상단 컨트롤 패널은 숨김 처리
  const txtCtrl = document.getElementById('txt-controls');
  if (txtCtrl) txtCtrl.style.display = 'none';
  
  showViewerLoading(i18n.t("viewer.loading_txt_title"), i18n.t("viewer.loading_txt_sub"));
  
  fetch(`/api/media/txt?db_type=${state.currentLibraryType}&book_id=${bookId}`)
    .then(res => res.ok ? res.text() : Promise.reject(i18n.t('viewer.error_txt_load')))
    .then(txt => {
      hideViewerLoading();
      // 대용량 텍스트 브라우저 렌더링 랙 방지를 위한 청크(페이지) 분할
      txtChunks = chunkText(txt, 4000);
      currentChunkIdx = 0;
      renderCurrentChunk();
      applyTxtSettings();
    })
    .catch(() => {
      hideViewerLoading();
      showViewerError(i18n.t("viewer.error_txt_title"), i18n.t("viewer.error_txt_sub"));
    });
}

// 텍스트를 문맥 단락 기준으로 약 4,000자씩 분할
function chunkText(text, chunkSize = 4000) {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    if (start + chunkSize >= text.length) {
      chunks.push(text.slice(start));
      break;
    }
    // 단락 중간이 잘리지 않도록 줄바꿈 위치 기준 분할
    let end = start + chunkSize;
    const nextNewline = text.indexOf('\n', end);
    if (nextNewline !== -1 && nextNewline - end < 500) {
      end = nextNewline + 1;
    }
    chunks.push(text.slice(start, end));
    start = end;
  }
  return chunks;
}

function renderCurrentChunk() {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;
  
  if (txtChunks.length === 0) {
    contentArea.textContent = i18n.t('viewer.txt_empty');
    return;
  }
  
  contentArea.textContent = txtChunks[currentChunkIdx];
  
  // 공용 오버레이에 진행률 표시 업데이트
  const pageInfo = document.getElementById('comic-overlay-page-info');
  if (pageInfo) {
    pageInfo.textContent = i18n.t('viewer.txt_chunk_info', {current: currentChunkIdx + 1, total: txtChunks.length});
  }

  // 진척도 전송 예약
  saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length);
}

import { getViewerSettings } from './viewer_settings.js';

export function applyTxtSettings() {
  const container = document.getElementById('txt-viewer-container');
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!container || !scrollWrapper || !contentArea) return;

  const { theme, fontSize, fontFamily, scrollMode, lineHeight } = getViewerSettings();

  // 1. 테마 클래스 교체
  container.className = `viewer-pane ${theme.className}`;

  // 2. 폰트 크기 및 행간 적용 (rem)
  contentArea.style.fontSize = `${fontSize}rem`;
  contentArea.style.lineHeight = lineHeight;

  // 3. 스크롤 모드 적용
  if (scrollMode === 'page') {
    scrollWrapper.classList.add('scroll-mode-page');
    container.classList.add('scroll-mode-page');
  } else {
    scrollWrapper.classList.remove('scroll-mode-page');
    container.classList.remove('scroll-mode-page');
  }

  // 4. 폰트 종류 적용
  applyFontFamilyToElement(contentArea, fontFamily);
}

function applyFontFamilyToElement(element, fontKey) {
  if (fontKey === 'batang') {
    element.style.fontFamily = "'KoPub Batang', 'Nanum Myeongjo', serif";
  } else if (fontKey === 'gothic') {
    element.style.fontFamily = "'Nanum Gothic', 'Malgun Gothic', sans-serif";
  } else if (fontKey === 'pretendard') {
    element.style.fontFamily = "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif";
  } else {
    // 사용자 정의 폰트 검색
    const customFonts = window.customFonts || [];
    const found = customFonts.find(f => f.name === fontKey);
    if (found) {
      import('./viewer_settings.js').then(m => {
        m.loadAndApplyCustomFont(found.name, found.url, element);
      });
    } else {
      element.style.fontFamily = fontKey;
    }
  }
}

export function prevTxtPage() {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!scrollWrapper) return;
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    // 가로 스크롤 모드인 경우 (column-width: 800px + column-gap: 80px = 880px)
    if (scrollWrapper.scrollLeft <= 10) {
      // 이전 청크로 이동
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        renderCurrentChunk();
        // 이전 청크의 맨 마지막으로 스크롤 이동
        setTimeout(() => {
          scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
        }, 50);
      }
    } else {
      scrollWrapper.scrollBy({ left: -scrollWrapper.clientWidth, behavior: 'smooth' });
    }
  } else {
    // 세로 스크롤 모드인 경우
    if (scrollWrapper.scrollTop <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        renderCurrentChunk();
        setTimeout(() => {
          scrollWrapper.scrollTop = scrollWrapper.scrollHeight;
        }, 50);
      }
    } else {
      scrollWrapper.scrollBy({ top: -scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
    }
  }
}

export function nextTxtPage() {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!scrollWrapper) return;
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    // 가로 스크롤 모드인 경우 (column-width: 800px + column-gap: 80px = 880px)
    const maxScrollLeft = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
    if (scrollWrapper.scrollLeft + 10 >= maxScrollLeft) {
      // 다음 청크로 이동
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        renderCurrentChunk();
        setTimeout(() => {
          scrollWrapper.scrollLeft = 0;
        }, 50);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisode(state.activeBookId);
        });
      }
    } else {
      scrollWrapper.scrollBy({ left: scrollWrapper.clientWidth, behavior: 'smooth' });
    }
  } else {
    // 세로 스크롤 모드인 경우
    const maxScrollTop = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    if (scrollWrapper.scrollTop + 10 >= maxScrollTop) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        renderCurrentChunk();
        setTimeout(() => {
          scrollWrapper.scrollTop = 0;
        }, 50);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisode(state.activeBookId);
        });
      }
    } else {
      scrollWrapper.scrollBy({ top: scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
    }
  }
}
