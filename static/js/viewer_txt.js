// viewer_txt.js – 텍스트 리더(TXT) 및 EPUB 뷰어 통합 로직
import { state } from './state.js';
import { viewerStorage } from './viewer/storage.js';

// Route all storage access through a wrapper for safer future refactors.
const localStorage = viewerStorage;

let txtChunks = [];
let currentChunkIdx = 0;
let loadedChunks = { min: 0, max: 0 };
let fullText = '';
let resizeTimeout = null;
let activeResizeHandler = null;
let txtScrollPreloadTriggered = false;
let txtScrollNextEpisodeTriggered = false;
let txtPageSnapTimeout = null;
let txtPageSnapInProgress = false;
let txtPendingRestoreTimer = null;
let txtRestoreToastAt = 0;

// Phase-1 runtime state object for incremental modularization.
export const txtRuntimeState = {
  get txtChunks() {
    return txtChunks;
  },
  set txtChunks(value) {
    txtChunks = value;
  },
  get currentChunkIdx() {
    return currentChunkIdx;
  },
  set currentChunkIdx(value) {
    currentChunkIdx = value;
  },
  get loadedChunks() {
    return loadedChunks;
  },
  set loadedChunks(value) {
    loadedChunks = value;
  },
  get fullText() {
    return fullText;
  },
  set fullText(value) {
    fullText = value;
  },
  get txtScrollPreloadTriggered() {
    return txtScrollPreloadTriggered;
  },
  set txtScrollPreloadTriggered(value) {
    txtScrollPreloadTriggered = value;
  },
  get txtScrollNextEpisodeTriggered() {
    return txtScrollNextEpisodeTriggered;
  },
  set txtScrollNextEpisodeTriggered(value) {
    txtScrollNextEpisodeTriggered = value;
  },
  reset() {
    txtChunks = [];
    currentChunkIdx = 0;
    loadedChunks = { min: 0, max: 0 };
    fullText = '';
    txtScrollPreloadTriggered = false;
    txtScrollNextEpisodeTriggered = false;
  }
};

import { showViewerLoading, hideViewerLoading, showViewerError, showToast } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { initPageStep, initReadingDirection } from './viewer/reader_settings.js';
import { getTxtPageAdvanceWidth, snapTxtPageScrollLeft } from './viewer/txt_page_utils.js';
import { chunkText, formatTxtToHtml, stripHtml } from './viewer/txt_text_utils.js';
import { renderTxtChunkView, applyTxtParagraphStyles } from './viewer/txt_render.js';
import { getTxtAnchorInfoByMode, restoreTxtAnchorInfoByMode } from './viewer/txt_anchor_utils.js';
import { applyTxtSettingsCore, applyFontFamilyToElement as applyTxtFontFamily } from './viewer/txt_settings_apply.js';
import {
  prevTxtPageAction,
  nextTxtPageAction,
  txtJumpToFirstPageAction,
  txtJumpToLastPageAction,
  txtSliderInputAction,
  txtSliderChangeAction,
} from './viewer/txt_navigation.js';
import { renderEpubTocPanel, jumpToTxtTocChapter } from './viewer/txt_toc.js';

export function initTxtViewer(bookId, initialPageIdx = 0) {
  console.log(`[Viewer-Txt] initTxtViewer - 콘텐츠 요청 중: bookId=${bookId}, initialPageIdx=${initialPageIdx}, format=${state.currentViewerFormat}`);
  const pane = document.getElementById('txt-viewer-container');
  const contentArea = document.getElementById('txt-content-area');
  if (!pane || !contentArea) return;
  pane.style.display = 'block';
  
  // 뷰어 여백(Padding) 설정 동적 적용
  import('./viewer/viewer_padding.js').then(m => {
    const padTop = localStorage.getItem('viewer_padding_top') || '40';
    const padBottom = localStorage.getItem('viewer_padding_bottom') || '60';
    const padLeft = localStorage.getItem('viewer_padding_left') || '20';
    const padRight = localStorage.getItem('viewer_padding_right') || '20';
    m.applyViewerPaddingRealtime('novel', 'top', padTop);
    m.applyViewerPaddingRealtime('novel', 'bottom', padBottom);
    m.applyViewerPaddingRealtime('novel', 'left', padLeft);
    m.applyViewerPaddingRealtime('novel', 'right', padRight);
  }).catch(e => {
    console.error('[Viewer-Txt] Failed to dynamically load viewer_padding.js:', e);
  });
  
  const txtCtrl = document.getElementById('txt-controls');
  if (txtCtrl) txtCtrl.style.display = 'none';
  
  showViewerLoading(i18n.t("viewer.loading_txt_title"), i18n.t("viewer.loading_txt_sub"));
  
  const isEpub = (state.currentViewerFormat === 'epub');
  const url = isEpub 
    ? `/api/media/epub?db_type=${state.currentLibraryType}&book_id=${bookId}`
    : `/api/media/txt?db_type=${state.currentLibraryType}&book_id=${bookId}`;

  fetch(url)
    .then(res => {
      if (!res.ok) throw new Error(i18n.t('viewer.error_txt_load'));
      return isEpub ? res.json() : res.text();
    })
    .then(data => {
      hideViewerLoading();
      txtScrollPreloadTriggered = false;
      txtScrollNextEpisodeTriggered = false;

      if (isEpub) {
        const chapters = data.chapters || [];
        txtChunks = chapters.map(ch => ch.content);
        fullText = txtChunks.join('<hr class="epub-chapter-divider" style="border: none; border-top: 1px dashed rgba(255,255,255,0.15); margin: 3rem 0;"/>');
        
        const tocList = data.toc || [];
        renderEpubToc(tocList);
      } else {
        fullText = data;
        txtChunks = chunkText(data, 4000);
        renderEpubToc([]); // Fallback for TXT
      }

      let startIdx = initialPageIdx;
      const savedPosStr = localStorage.getItem(`viewer_last_pos_${bookId}`);
      if (savedPosStr) {
        try {
          const pos = JSON.parse(savedPosStr);
          if (pos && pos.chunkIdx !== undefined) {
            startIdx = pos.chunkIdx;
            console.log(`[Viewer-Txt] 로컬 저장소에서 챕터 인덱스 감지: ${startIdx}`);
          }
        } catch(e) {}
      }

      currentChunkIdx = startIdx;

      initReadingDirection();
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
            m.handleNextEpisodeDirect(state.activeBookId);
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
          if (mode === 'page') {
            if (txtPageSnapInProgress) return;
            clearTimeout(txtPageSnapTimeout);
            txtPageSnapTimeout = setTimeout(() => {
              txtPageSnapInProgress = true;
              snapTxtPageScrollLeft(scrollWrapper);
              txtPageSnapInProgress = false;
              logActiveViewportText();
              saveDetailPosition();
            }, 90);
            return;
          }

          if (mode !== 'scroll') return;

          const scrollHeight = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
          if (scrollHeight <= 0) return;

          const currentScroll = scrollWrapper.scrollTop;
          const chunks = contentArea.querySelectorAll('.txt-scroll-chunk');
          let detectedIdx = 0;
          
          for (let chunk of chunks) {
            const idx = parseInt(chunk.getAttribute('data-idx'));
            if (currentScroll >= chunk.offsetTop - 120) {
              detectedIdx = idx;
            } else {
              break;
            }
          }

          const newIdx = Math.min(txtChunks.length - 1, Math.max(0, detectedIdx));
          const ratio = scrollHeight > 0 ? scrollWrapper.scrollTop / scrollHeight : 0;

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

          logActiveViewportText();
          triggerNextEpisodeIfNeeded();
          saveDetailPosition();
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

      const handleResize = () => {
        const wrapper = document.getElementById('txt-scroll-wrapper');
        if (!wrapper) return;
        const mode = localStorage.getItem('viewer_scroll_mode') || 'page';

        if (mode === 'page') {
          const prevStepWidth = getTxtPageAdvanceWidth(wrapper);
          const currentColumnIdx = Math.round(wrapper.scrollLeft / prevStepWidth);
          // Resize relayout should preserve current visual page, not stale saved localStorage position.
          applyTxtSettings({ previousMode: mode, skipSavedPositionRestore: true });
          const newStepWidth = getTxtPageAdvanceWidth(wrapper);
          wrapper.scrollLeft = currentColumnIdx * newStepWidth;
          snapTxtPageScrollLeft(wrapper);
          logActiveViewportText();
        } else {
          const beforeHeight = wrapper.scrollHeight - wrapper.clientHeight;
          const ratio = beforeHeight > 0 ? wrapper.scrollTop / beforeHeight : 0;
          // Scroll mode resize also preserves ratio instead of restoring stale saved position.
          applyTxtSettings({ previousMode: mode, skipSavedPositionRestore: true });
          const afterHeight = wrapper.scrollHeight - wrapper.clientHeight;
          if (afterHeight > 0) {
            wrapper.scrollTop = afterHeight * ratio;
          }
          logActiveViewportText();
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

function cancelPendingTxtRestore() {
  if (txtPendingRestoreTimer) {
    clearTimeout(txtPendingRestoreTimer);
    txtPendingRestoreTimer = null;
  }
}

function showTxtRestoreLoadingToast() {
  const now = Date.now();
  if (now - txtRestoreToastAt < 700) return;
  txtRestoreToastAt = now;
  if (typeof showToast === 'function') {
    showToast('로딩중입니다', 'info');
  }
}

function renderCurrentChunk(initMode = false) {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  const rendered = renderTxtChunkView({
    contentArea,
    txtChunks,
    currentChunkIdx,
    scrollMode,
    isEpub,
    initMode,
    formatTxtToHtml,
    emptyText: i18n.t('viewer.txt_empty')
  });
  if (!rendered) return;

  applyDynamicParagraphStyles();
  updateTxtSeekBar();
  saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length);
}

function applyDynamicParagraphStyles() {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;
  applyTxtParagraphStyles({
    contentArea,
    localStorage,
    currentViewerFormat: state.currentViewerFormat
  });
}

import { getViewerSettings } from './viewer_settings.js';

export function logActiveViewportText() {
  try {
    const anchor = getTxtAnchorInfo();
    if (anchor && anchor.anchorText) {
      console.log(`[Viewer-Active-Text] 현재 화면 첫줄 감지: "${anchor.anchorText.trim()}" (챕터: ${anchor.chunkIdx})`);
    } else {
      console.log(`[Viewer-Active-Text] 현재 화면 첫줄 감지 실패 (null)`);
    }
  } catch (e) {
    console.error(`[Viewer-Active-Text] 감지 중 예외 발생:`, e);
  }
}

export function getTxtAnchorInfo(forcedMode = null) {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  const isEpub = (state.currentViewerFormat === 'epub');
  return getTxtAnchorInfoByMode({
    scrollWrapper,
    contentArea,
    forcedMode,
    storage: localStorage,
    isEpub,
    fullText,
    txtChunks,
    currentChunkIdx,
    stripHtml
  });
}

export function restoreTxtAnchorInfo(anchorInfo) {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  const isEpub = (state.currentViewerFormat === 'epub');
  const restored = restoreTxtAnchorInfoByMode({
    anchorInfo,
    scrollWrapper,
    contentArea,
    storage: localStorage,
    currentChunkIdx,
    getPageAdvanceWidth: getTxtPageAdvanceWidth,
    isEpub,
    fullText,
    txtChunks,
    stripHtml
  });

  if (restored) {
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode === 'scroll') {
      console.log(`[Viewer-Txt] 앵커 복원 성공 (세로 scrollTop = ${scrollWrapper ? scrollWrapper.scrollTop : 0})`);
    } else {
      console.log(`[Viewer-Txt] 앵커 복원 성공 (가로 scrollLeft = ${scrollWrapper ? scrollWrapper.scrollLeft : 0})`);
    }
  }

  return restored;
}

export function saveDetailPosition() {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (scrollWrapper && state.activeBookId) {
    const pos = {
      chunkIdx: currentChunkIdx,
      scrollLeft: scrollWrapper.scrollLeft,
      scrollTop: scrollWrapper.scrollTop
    };
    localStorage.setItem(`viewer_last_pos_${state.activeBookId}`, JSON.stringify(pos));
  }
}

export function applyTxtSettings(options = {}) {
  const container = document.getElementById('txt-viewer-container');
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!container || !scrollWrapper || !contentArea) return;

  clearTimeout(txtPageSnapTimeout);
  txtPageSnapInProgress = false;
  cancelPendingTxtRestore();

  applyTxtSettingsCore({
    options,
    container,
    scrollWrapper,
    contentArea,
    localStorage,
    getViewerSettings,
    getCurrentChunkIdx: () => currentChunkIdx,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getChunkCount: () => txtChunks.length,
    getActiveBookId: () => state.activeBookId,
    getTxtAnchorInfo,
    restoreTxtAnchorInfo,
    renderCurrentChunk,
    snapTxtPageScrollLeft,
    saveDetailPosition,
    showRestoreLoadingToast: showTxtRestoreLoadingToast,
    setPendingRestoreTimer: value => {
      txtPendingRestoreTimer = value;
    },
    applyFontFamily: (element, fontKey) => {
      applyTxtFontFamily(
        element,
        fontKey,
        window.customFonts || [],
        (name, url, target) => {
          import('./viewer_settings.js').then(m => {
            m.loadAndApplyCustomFont(name, url, target);
          });
        }
      );
    }
  });
}

export function prevTxtPage() {
  prevTxtPageAction({
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    cancelPendingRestore: cancelPendingTxtRestore,
    getScrollMode: () => localStorage.getItem('viewer_scroll_mode') || 'page',
    snapTxtPageScrollLeft,
    getTxtPageAdvanceWidth,
    getCurrentChunkIdx: () => currentChunkIdx,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getChunkCount: () => txtChunks.length,
    renderCurrentChunk,
    saveDetailPosition,
    logActiveViewportText,
    setTxtPageSnapInProgress: value => {
      txtPageSnapInProgress = value;
    },
    handleNextEpisode: () => {
      import('./viewer_next_episode.js').then(m => {
        m.handleNextEpisodeDirect(state.activeBookId);
      });
    },
    setTxtScrollPreloadTriggered: value => {
      txtScrollPreloadTriggered = value;
    },
    setTxtScrollNextEpisodeTriggered: value => {
      txtScrollNextEpisodeTriggered = value;
    }
  });
}

export function nextTxtPage() {
  nextTxtPageAction({
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    cancelPendingRestore: cancelPendingTxtRestore,
    getScrollMode: () => localStorage.getItem('viewer_scroll_mode') || 'page',
    snapTxtPageScrollLeft,
    getTxtPageAdvanceWidth,
    getCurrentChunkIdx: () => currentChunkIdx,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getChunkCount: () => txtChunks.length,
    renderCurrentChunk,
    saveDetailPosition,
    logActiveViewportText,
    setTxtPageSnapInProgress: value => {
      txtPageSnapInProgress = value;
    },
    handleNextEpisode: () => {
      import('./viewer_next_episode.js').then(m => {
        m.handleNextEpisodeDirect(state.activeBookId);
      });
    },
    setTxtScrollPreloadTriggered: value => {
      txtScrollPreloadTriggered = value;
    },
    setTxtScrollNextEpisodeTriggered: value => {
      txtScrollNextEpisodeTriggered = value;
    }
  });
}

export function txtJumpToFirstPage() {
  txtJumpToFirstPageAction({
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    cancelPendingRestore: cancelPendingTxtRestore,
    getCurrentChunkIdx: () => currentChunkIdx,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getChunkCount: () => txtChunks.length,
    renderCurrentChunk,
    setTxtScrollPreloadTriggered: value => {
      txtScrollPreloadTriggered = value;
    },
    setTxtScrollNextEpisodeTriggered: value => {
      txtScrollNextEpisodeTriggered = value;
    }
  });
}

export function txtJumpToLastPage() {
  txtJumpToLastPageAction({
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    cancelPendingRestore: cancelPendingTxtRestore,
    getCurrentChunkIdx: () => currentChunkIdx,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getChunkCount: () => txtChunks.length,
    renderCurrentChunk,
    setTxtScrollPreloadTriggered: value => {
      txtScrollPreloadTriggered = value;
    },
    setTxtScrollNextEpisodeTriggered: value => {
      txtScrollNextEpisodeTriggered = value;
    }
  });
}

export function updateTxtSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  const startLabel = document.getElementById('seekbar-start-label');
  const endLabel = document.getElementById('seekbar-end-label');
  const pageInfo = document.getElementById('comic-overlay-page-info');

  if (!slider || txtChunks.length === 0) return;

  slider.min = "1";
  slider.max = String(txtChunks.length);
  slider.value = String(currentChunkIdx + 1);

  if (startLabel) startLabel.textContent = "1";
  if (endLabel) endLabel.textContent = String(txtChunks.length);
  if (pageInfo) {
    pageInfo.textContent = `${currentChunkIdx + 1} / ${txtChunks.length}`;
  }
}

export function txtSliderInput(slider, val) {
  txtSliderInputAction({ val, chunkCount: txtChunks.length });
}

export function txtSliderChange(slider, val) {
  txtSliderChangeAction(
    {
      getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
      cancelPendingRestore: cancelPendingTxtRestore,
      getScrollMode: () => localStorage.getItem('viewer_scroll_mode') || 'page',
      getCurrentChunkIdx: () => currentChunkIdx,
      setCurrentChunkIdx: value => {
        currentChunkIdx = value;
      },
      getChunkCount: () => txtChunks.length,
      renderCurrentChunk,
      saveDetailPosition,
      logActiveViewportText
    },
    val
  );
}

export const TxtViewer = {
  async init(bookId, initialPageIdx = 0) {
    return initTxtViewer(bookId, initialPageIdx);
  },
  destroy() {
    txtRuntimeState.reset();
    clearTimeout(txtPageSnapTimeout);
    txtPageSnapInProgress = false;
    cancelPendingTxtRestore();
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
    
    const tocBtn = document.getElementById('epub-toc-btn');
    const tocContainer = document.getElementById('epub-toc-container');
    if (tocBtn) tocBtn.remove();
    if (tocContainer) tocContainer.remove();
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
    applyTxtSettings(options || {});
  }
};

function renderEpubToc(tocList) {
  renderEpubTocPanel({
    tocList,
    txtChunks,
    onJumpToChapter: jumpToChapter
  });
}

function jumpToChapter(chapterIdx, anchor) {
  jumpToTxtTocChapter({
    chapterIdx,
    anchor,
    chunkCount: txtChunks.length,
    setCurrentChunkIdx: value => {
    currentChunkIdx = value;
    },
    getScrollMode: () => localStorage.getItem('viewer_scroll_mode') || 'page',
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    renderCurrentChunk,
    saveProgress,
    activeBookId: state.activeBookId
  });
}

