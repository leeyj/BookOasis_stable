// viewer_txt.js – 텍스트 리더(TXT) 뷰어 로직
import { state } from './state.js';

let txtChunks = [];
let currentChunkIdx = 0;
let loadedChunks = { min: 0, max: 0 };
let fullText = '';
let resizeTimeout = null;
let activeResizeHandler = null;
let txtScrollPreloadTriggered = false;
let txtScrollNextEpisodeTriggered = false;

import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';

export function initTxtViewer(bookId, initialPageIdx = 0) {
  console.log(`[Viewer-Txt] initTxtViewer - TXT 콘텐츠 요청 중: bookId=${bookId}, initialPageIdx=${initialPageIdx}`);
  const pane = document.getElementById('txt-viewer-container');
  const contentArea = document.getElementById('txt-content-area');
  if (!pane || !contentArea) return;
  pane.style.display = 'block';
  
  // 기존 수동 상단 컨트롤 패널은 숨김 처리
  const txtCtrl = document.getElementById('txt-controls');
  if (txtCtrl) txtCtrl.style.display = 'none';
  
  showViewerLoading(i18n.t("viewer.loading_txt_title"), i18n.t("viewer.loading_txt_sub"));
  
  fetch(`/api/media/txt?db_type=${state.currentLibraryType}&book_id=${bookId}`)
    .then(res => res.ok ? res.text() : Promise.reject(i18n.t('viewer.error_txt_load')))
    .then(txt => {
      hideViewerLoading();
      fullText = txt;
      txtScrollPreloadTriggered = false;
      txtScrollNextEpisodeTriggered = false;
      // 대용량 텍스트 브라우저 렌더링 랙 방지를 위한 청크(페이지) 분할
      txtChunks = chunkText(txt, 4000);
      currentChunkIdx = initialPageIdx;
      
      // 렌더 및 세팅 적용
      renderCurrentChunk(true);
      applyTxtSettings();

      const scrollWrapper = document.getElementById('txt-scroll-wrapper');
      if (scrollWrapper) {
        if (scrollWrapper.__txtScrollHandler) {
          scrollWrapper.removeEventListener('scroll', scrollWrapper.__txtScrollHandler);
        }
        if (scrollWrapper.__txtTouchHandler) {
          scrollWrapper.removeEventListener('touchend', scrollWrapper.__txtTouchHandler);
          scrollWrapper.removeEventListener('touchcancel', scrollWrapper.__txtTouchHandler);
        }

        const triggerNextEpisodeIfNeeded = () => {
          const mode = localStorage.getItem('viewer_scroll_mode') || 'page';
          if (mode !== 'scroll') return;

          const scrollHeight = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
          if (scrollHeight <= 0) return;

          const ratio = scrollWrapper.scrollTop / scrollHeight;
          const newIdx = Math.min(txtChunks.length - 1, Math.max(0, Math.floor(ratio * txtChunks.length)));
          const isAtAbsoluteEnd = scrollWrapper.scrollTop + scrollWrapper.clientHeight >= scrollWrapper.scrollHeight - 15;
          if (!isAtAbsoluteEnd || isTransitioning || txtScrollNextEpisodeTriggered || newIdx < txtChunks.length - 1) return;

          isTransitioning = true;
          txtScrollNextEpisodeTriggered = true;
          import('./viewer_next_episode.js').then(m => {
            m.handleNextEpisode(state.activeBookId);
            setTimeout(() => { isTransitioning = false; }, 300);
          });
        };

        // 스크롤 모드 시 이전 진척도 스크롤 위치 복구
        const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
        if (scrollMode === 'scroll' && currentChunkIdx > 0 && txtChunks.length > 0) {
          setTimeout(() => {
            const ratio = currentChunkIdx / txtChunks.length;
            scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
          }, 150);
        }

        let isTransitioning = false;
        const scrollHandler = () => {
          const mode = localStorage.getItem('viewer_scroll_mode') || 'page';
          if (mode !== 'scroll') return;

          const scrollHeight = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
          if (scrollHeight <= 0) return;

          // 전체 텍스트 스크롤 비율 연산 기반으로 진척도 역산
          const ratio = scrollWrapper.scrollTop / scrollHeight;
          const newIdx = Math.min(txtChunks.length - 1, Math.max(0, Math.floor(ratio * txtChunks.length)));

          if (!txtScrollPreloadTriggered && ratio >= 0.9 && txtChunks.length > 1) {
            txtScrollPreloadTriggered = true;
            saveProgress(state.activeBookId, Math.min(txtChunks.length - 1, newIdx), txtChunks.length);
          }

          if (newIdx !== currentChunkIdx) {
            currentChunkIdx = newIdx;
            const pageInfo = document.getElementById('comic-overlay-page-info');
            if (pageInfo) {
              pageInfo.textContent = i18n.t('viewer.txt_chunk_info', {current: currentChunkIdx + 1, total: txtChunks.length});
            }
            saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length);
          }

          // 마지막 바닥 도달 시 다음 화 이동
          triggerNextEpisodeIfNeeded();
        };
        scrollWrapper.addEventListener('scroll', scrollHandler, { passive: true });
        scrollWrapper.__txtScrollHandler = scrollHandler;

        const touchHandler = () => {
          triggerNextEpisodeIfNeeded();
        };
        scrollWrapper.__txtTouchHandler = touchHandler;
        scrollWrapper.addEventListener('touchend', touchHandler, { passive: true });
        scrollWrapper.addEventListener('touchcancel', touchHandler, { passive: true });
      }

      // 윈도우 리사이즈 시 읽기 진행 위치 자동 계산 및 레이아웃 보정
      const handleResize = () => {
        const wrapper = document.getElementById('txt-scroll-wrapper');
        if (!wrapper) return;
        const mode = localStorage.getItem('viewer_scroll_mode') || 'page';

        if (mode === 'page') {
          // 1. 리사이즈 전 읽던 컬럼 번호 획득
          const currentColumnIdx = Math.round(wrapper.scrollLeft / (wrapper.clientWidth + 40));
          // 2. 너비/다단 세팅 재연산
          applyTxtSettings();
          // 3. 해당 컬럼 번호로 복원
          wrapper.scrollLeft = currentColumnIdx * (wrapper.clientWidth + 40);
        } else {
          // 세로 스크롤일 때는 비율 기준으로 스크롤바 높이 복원
          const beforeHeight = wrapper.scrollHeight - wrapper.clientHeight;
          const ratio = beforeHeight > 0 ? wrapper.scrollTop / beforeHeight : 0;
          applyTxtSettings();
          const afterHeight = wrapper.scrollHeight - wrapper.clientHeight;
          if (afterHeight > 0) {
            wrapper.scrollTop = afterHeight * ratio;
          }
        }
      };

      if (activeResizeHandler) {
        window.removeEventListener('resize', activeResizeHandler);
      }
      activeResizeHandler = () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(handleResize, 100);
      };
      window.addEventListener('resize', activeResizeHandler, { passive: true });
    })
    .catch((err) => {
      console.error('[Viewer-Txt] 로딩 에러 발생:', err);
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

function renderCurrentChunk(initMode = false) {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;
  
  if (txtChunks.length === 0) {
    contentArea.textContent = i18n.t('viewer.txt_empty');
    return;
  }

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'page') {
    contentArea.innerHTML = `<div class="txt-chunk" data-idx="${currentChunkIdx}" style="white-space: pre-wrap; margin-bottom: 2rem;">${txtChunks[currentChunkIdx]}</div>`;
  } else {
    // 스크롤 모드인 경우 텍스트 전체를 단 한 번만 통째로 렌더링
    if (initMode || !contentArea.querySelector('.txt-full-content')) {
      contentArea.innerHTML = `<div class="txt-full-content" style="white-space: pre-wrap; word-break: break-all; margin-bottom: 2rem;">${fullText}</div>`;
    }
  }
  
  // 시크바 및 배지 통합 업데이트
  updateTxtSeekBar();

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

    // 1장/2장(2단 분할) 보기 적용
    const pageStep = localStorage.getItem('comic_page_step') || '1';
    if (pageStep === '2') {
      scrollWrapper.style.maxWidth = '1600px';
      scrollWrapper.style.columnCount = '2';
      scrollWrapper.style.columnWidth = 'auto';
    } else {
      scrollWrapper.style.maxWidth = '800px';
      scrollWrapper.style.columnCount = '1';
      scrollWrapper.style.columnWidth = 'auto';
    }
  } else {
    scrollWrapper.classList.remove('scroll-mode-page');
    container.classList.remove('scroll-mode-page');

    // 스크롤 모드 스타일 초기화
    scrollWrapper.style.maxWidth = '';
    scrollWrapper.style.columnCount = '';
    scrollWrapper.style.columnWidth = '';
  }

  // 4. 폰트 종류 적용
  applyFontFamilyToElement(contentArea, fontFamily);

  // 5. 보기 모드 전환에 따른 콘텐츠 갱신 (initMode = true 강제 적용)
  renderCurrentChunk(true);

  // 6. 보기 모드 스위칭 시점에 읽던 진행 좌표 복구
  if (scrollMode === 'scroll') {
    if (currentChunkIdx > 0 && txtChunks.length > 0) {
      setTimeout(() => {
        const ratio = currentChunkIdx / txtChunks.length;
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
      }, 50);
    }
  } else {
    scrollWrapper.scrollLeft = 0;
  }
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
        scrollWrapper.style.scrollBehavior = 'auto'; // 애니메이션 일시 차단
        renderCurrentChunk();
        scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
        }, 50);
      }
    } else {
      const pageScrollWidth = scrollWrapper.clientWidth + 40;
      scrollWrapper.scrollBy({ left: -pageScrollWidth, behavior: 'auto' });
    }
  } else {
    // 세로 스크롤 모드인 경우
    if (scrollWrapper.scrollTop <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        scrollWrapper.style.scrollBehavior = 'auto'; // 애니메이션 일시 차단
        renderCurrentChunk();
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
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
        scrollWrapper.style.scrollBehavior = 'auto'; // 애니메이션 일시 차단
        renderCurrentChunk();
        scrollWrapper.scrollLeft = 0;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
        }, 50);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisode(state.activeBookId);
        });
      }
    } else {
      const pageScrollWidth = scrollWrapper.clientWidth + 40;
      scrollWrapper.scrollBy({ left: pageScrollWidth, behavior: 'auto' });
    }
  } else {
    // 세로 스크롤 모드인 경우
    const maxScrollTop = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    if (scrollWrapper.scrollTop + 10 >= maxScrollTop) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        scrollWrapper.style.scrollBehavior = 'auto'; // 애니메이션 일시 차단
        renderCurrentChunk();
        scrollWrapper.scrollTop = 0;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
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

export function txtJumpToFirstPage() {
  if (txtChunks.length > 0 && currentChunkIdx !== 0) {
    currentChunkIdx = 0;
    txtScrollPreloadTriggered = false;
    txtScrollNextEpisodeTriggered = false;
    renderCurrentChunk();
    const scrollWrapper = document.getElementById('txt-scroll-wrapper');
    if (scrollWrapper) {
      scrollWrapper.scrollTop = 0;
      scrollWrapper.scrollLeft = 0;
    }
  }
}

export function txtJumpToLastPage() {
  const lastIdx = Math.max(0, txtChunks.length - 1);
  if (txtChunks.length > 0 && currentChunkIdx !== lastIdx) {
    currentChunkIdx = lastIdx;
    txtScrollPreloadTriggered = true;
    renderCurrentChunk();
    const scrollWrapper = document.getElementById('txt-scroll-wrapper');
    if (scrollWrapper) {
      scrollWrapper.scrollTop = 0;
      scrollWrapper.scrollLeft = 0;
    }
  }
}

export function updateTxtSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  const startLabel = document.getElementById('seekbar-start-label');
  const endLabel = document.getElementById('seekbar-end-label');
  const pageInfo = document.getElementById('comic-overlay-page-info');

  if (!slider || txtChunks.length === 0) return;

  // 1. 슬라이더 속성 동기화 (1-indexed 기반)
  slider.min = "1";
  slider.max = String(txtChunks.length);
  slider.value = String(currentChunkIdx + 1);

  // 2. 텍스트 라벨 동기화
  if (startLabel) startLabel.textContent = "1";
  if (endLabel) endLabel.textContent = String(txtChunks.length);
  if (pageInfo) {
    pageInfo.textContent = `${currentChunkIdx + 1} / ${txtChunks.length}`;
  }
}

export function txtSliderInput(slider, val) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) {
    tooltip.textContent = val;
    tooltip.style.display = 'block';
  }
  const pageInfo = document.getElementById('comic-overlay-page-info');
  if (pageInfo) {
    pageInfo.textContent = `${val} / ${txtChunks.length}`;
  }
}

export function txtSliderChange(slider, val) {
  const targetIdx = Math.max(0, Math.min(txtChunks.length - 1, val - 1));
  if (currentChunkIdx !== targetIdx) {
    currentChunkIdx = targetIdx;
    
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode === 'scroll') {
      const scrollWrapper = document.getElementById('txt-scroll-wrapper');
      if (scrollWrapper) {
        const ratio = currentChunkIdx / txtChunks.length;
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
      }
    } else {
      renderCurrentChunk();
    }
  }
}

export const TxtViewer = {
  async init(bookId, initialPageIdx = 0) {
    return initTxtViewer(bookId, initialPageIdx);
  },
  destroy() {
    txtChunks = [];
    currentChunkIdx = 0;
    const contentArea = document.getElementById('txt-content-area');
    if (contentArea) contentArea.textContent = '';
    const pane = document.getElementById('txt-viewer-container');
    if (pane) pane.style.display = 'none';

    const scrollWrapper = document.getElementById('txt-scroll-wrapper');
    if (scrollWrapper && scrollWrapper.__txtScrollHandler) {
      scrollWrapper.removeEventListener('scroll', scrollWrapper.__txtScrollHandler);
      delete scrollWrapper.__txtScrollHandler;
    }
    if (scrollWrapper && scrollWrapper.__txtTouchHandler) {
      scrollWrapper.removeEventListener('touchend', scrollWrapper.__txtTouchHandler);
      scrollWrapper.removeEventListener('touchcancel', scrollWrapper.__txtTouchHandler);
      delete scrollWrapper.__txtTouchHandler;
    }

    if (activeResizeHandler) {
      window.removeEventListener('resize', activeResizeHandler);
      activeResizeHandler = null;
    }
    clearTimeout(resizeTimeout);
  },
  prevPage() {
    prevTxtPage();
  },
  nextPage() {
    nextTxtPage();
  },
  jumpTo(target) {
    if (target === 'first') {
      txtJumpToFirstPage();
    } else if (target === 'last') {
      txtJumpToLastPage();
    }
  },
  applySettings(options) {
    applyTxtSettings();
  }
};
