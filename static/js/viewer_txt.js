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
const epubChapterFetchInFlight = new Set();
const epubChapterRetryState = new Map();

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
    epubChapterRetryState.clear();
    clearAnnotationState();
  }
};

import { showViewerLoading, hideViewerLoading, showViewerError, showToast } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { initPageStep, initReadingDirection, getComicReadingDirection } from './viewer/reader_settings.js';
import { getTxtPageAdvanceWidth, snapTxtPageScrollLeft, isTxtScrollLeftAtMaxPage, getTxtPageMaxScroll, applyTxtTwoPageTrailingSpacer, applyTxtImageMaxHeight } from './viewer/txt_page_utils.js';
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
import { renderEpubTocPanel, jumpToTxtTocChapter, highlightEpubTocChapter } from './viewer/txt_toc.js';
import { loadAnnotationsForBook, clearAnnotationState } from './viewer/annotation_state.js';
import { applyAnnotationsToAllRenderedChunks } from './viewer/annotation_render.js';
import { initAnnotationSelectionUI } from './viewer/annotation_ui.js';

import {
  clearEpubChapterRetryState,
  clampNumber,
  pickEpubStartIndex,
  syncActiveEpubToc as syncActiveEpubTocExt,
  preloadEpubChapterImages,
  requestEpubChapterContent as requestEpubChapterContentExt,
  getVisibleEpubPlaceholderIndexes as getVisibleEpubPlaceholderIndexesExt,
  scheduleVisibleEpubPlaceholderRecovery as scheduleVisibleEpubPlaceholderRecoveryExt,
  hydrateEpubChapterWindow as hydrateEpubChapterWindowExt,
  retryVisibleEpubPlaceholders as retryVisibleEpubPlaceholdersExt,
} from './viewer/epub_loader.js';

function syncActiveEpubToc(scrollIntoView = false) {
  syncActiveEpubTocExt(currentChunkIdx, scrollIntoView);
}

function requestEpubChapterContent(chapterIdx, options = {}) {
  return requestEpubChapterContentExt(txtChunks, chapterIdx, options);
}

function getVisibleEpubPlaceholderIndexes(maxCount = 10) {
  return getVisibleEpubPlaceholderIndexesExt(txtChunks, maxCount);
}

function scheduleVisibleEpubPlaceholderRecovery(delays = [50, 180, 450]) {
  scheduleVisibleEpubPlaceholderRecoveryExt(txtChunks, delays);
}

function hydrateEpubChapterWindow(centerIdx, radius = 10) {
  hydrateEpubChapterWindowExt(txtChunks, centerIdx, radius);
}

function retryVisibleEpubPlaceholders(maxCount = 8) {
  retryVisibleEpubPlaceholdersExt(txtChunks, maxCount);
}

// 스크롤/터치/리사이즈 런타임 리스너를 등록한다. EPUB과 일반 TXT 두 로딩 경로
// 모두에서 호출되어야 한다 — 예전에는 TXT 경로에만 있어서 EPUB 책은 브라우저
// 리사이즈 시 컬럼 폭이 갱신되지 않아 2페이지 모드가 1페이지처럼 깨지는 버그가 있었다.
function setupTxtViewerRuntimeListeners() {
  const contentArea = document.getElementById('txt-content-area');
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
      txtPendingRestoreTimer = setTimeout(() => {
        const ratio = currentChunkIdx / txtChunks.length;
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
        txtPendingRestoreTimer = null;
      }, 150);
    }

    let isTransitioning = false;
    let rAfPending = false;
    let scrollDebounceTimeout = null;

    const processScroll = () => {
      rAfPending = false;
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
      const isEpubMode = (state.currentViewerFormat === 'epub');

      // EPUB 스크롤 모드: 현재 화면 뷰포트 인근(전후 10개 챕터) null 챕터 선제 동적 로드
      if (isEpubMode) {
        hydrateEpubChapterWindow(newIdx, 10);
      }

      if (!txtScrollPreloadTriggered && ratio >= 0.9 && txtChunks.length > 1) {
        txtScrollPreloadTriggered = true;
        saveProgress(
          state.activeBookId,
          Math.min(txtChunks.length - 1, newIdx),
          txtChunks.length,
          isEpubMode ? { epub_session: { index: newIdx, percent: Math.round(ratio * 100) } } : null
        );
      }

      if (newIdx !== currentChunkIdx) {
        currentChunkIdx = newIdx;
        const pageInfo = document.getElementById('comic-overlay-page-info');
        if (pageInfo) {
          pageInfo.textContent = i18n.t('viewer.txt_chunk_info', {current: currentChunkIdx + 1, total: txtChunks.length});
        }
        syncActiveEpubToc();

        // EPUB 모드: 현재 감지된 챕터 및 이전/다음 챕터가 null이면 동적 로드
        if (isEpubMode) {
          const fetchList = [newIdx, newIdx - 1, newIdx + 1].filter(i => i >= 0 && i < txtChunks.length && (txtChunks[i] === null || txtChunks[i] === 'LOADING_PENDING'));
          fetchList.forEach(fIdx => {
            requestEpubChapterContent(fIdx);
          });
        }

        const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${newIdx}"]`);
        let fingerprint = '';
        if (targetChunk) {
          fingerprint = String(targetChunk.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180);
        }
        const epubSessionPayload = isEpubMode
          ? {
              epub_session: {
                index: newIdx,
                percent: Math.max(0, Math.min(100, Math.round(ratio * 100))),
                fingerprint: fingerprint || undefined
              }
            }
          : null;
        saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length, epubSessionPayload);
      }

      triggerNextEpisodeIfNeeded();

      // Debounce heavy operations (logActiveViewportText, saveDetailPosition, fine-grained progress)
      clearTimeout(scrollDebounceTimeout);
      scrollDebounceTimeout = setTimeout(() => {
        logActiveViewportText();
        saveDetailPosition();
        if (isEpubMode) {
          const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${currentChunkIdx}"]`);
          let fingerprint = '';
          if (targetChunk) {
            fingerprint = String(targetChunk.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180);
          }
          const epubSessionPayload = {
            epub_session: {
              index: currentChunkIdx,
              percent: Math.max(0, Math.min(100, Math.round(ratio * 100))),
              fingerprint: fingerprint || undefined
            }
          };
          saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length, epubSessionPayload);
        }
      }, 150);
    };

    const scrollHandler = () => {
      if (!rAfPending) {
        rAfPending = true;
        requestAnimationFrame(processScroll);
      }
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

  let lastWindowWidth = window.innerWidth;
  const handleResize = () => {
    const wrapper = document.getElementById('txt-scroll-wrapper');
    if (!wrapper) return;
    const mode = localStorage.getItem('viewer_scroll_mode') || 'page';

    const currentWidth = window.innerWidth;
    const widthChanged = Math.abs(currentWidth - lastWindowWidth) > 5;
    lastWindowWidth = currentWidth;

    if (mode === 'page') {
      const prevStepWidth = getTxtPageAdvanceWidth(wrapper);
      // 챕터 마지막의 짧은 페이지(스프레드)에 있을 때는 stepWidth 배수 기반 인덱스
      // 계산이 부정확할 수 있으므로(snapTxtPageScrollLeft와 동일한 문제), 그 경우
      // 인덱스 재구성 대신 "마지막 페이지였다"는 사실 자체를 보존한다.
      const wasAtLastPage = isTxtScrollLeftAtMaxPage(wrapper);
      const currentColumnIdx = Math.round(wrapper.scrollLeft / prevStepWidth);
      // Resize relayout should preserve current visual page, not stale saved localStorage position.
      applyTxtSettings({ previousMode: mode, skipSavedPositionRestore: true });
      const contentArea = document.getElementById('txt-content-area');
      applyTxtImageMaxHeight(wrapper, contentArea);
      applyTxtTwoPageTrailingSpacer(wrapper, contentArea);
      const newStepWidth = getTxtPageAdvanceWidth(wrapper);
      wrapper.scrollLeft = wasAtLastPage ? getTxtPageMaxScroll(wrapper) : currentColumnIdx * newStepWidth;
      snapTxtPageScrollLeft(wrapper);
      logActiveViewportText();
    } else {
      // In scroll mode, mobile address bar toggles change height only. Skip DOM re-render if width hasn't changed.
      if (!widthChanged) return;

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
}

export function initTxtViewer(bookId, initialPageIdx = 0) {
  console.log(`[Viewer-Txt] initTxtViewer - 콘텐츠 요청 중: bookId=${bookId}, initialPageIdx=${initialPageIdx}, format=${state.currentViewerFormat}`);
  const pane = document.getElementById('txt-viewer-container');
  const contentArea = document.getElementById('txt-content-area');
  if (!pane || !contentArea) return;
  pane.style.display = 'block';
  epubChapterRetryState.clear();

  loadAnnotationsForBook(bookId, state.currentLibraryType).then(() => {
    const contentArea = document.getElementById('txt-content-area');
    applyAnnotationsToAllRenderedChunks({
      contentArea,
      format: state.currentViewerFormat === 'epub' ? 'epub' : 'txt',
      txtChunks,
    });
  });
  initAnnotationSelectionUI(() => txtChunks);

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
  
  if (isEpub) {
    // ─── EPUB 초고속 렌더링: 1단계 /api/media/epub/meta 요청 (50ms) ───
    fetch(`/api/media/epub/meta?db_type=${state.currentLibraryType}&book_id=${bookId}`)
      .then(res => {
        if (!res.ok) throw new Error(i18n.t('viewer.error_txt_load'));
        return res.json();
      })
      .then(async meta => {
        const totalChapters = meta.total_chapters || 0;
        txtChunks = new Array(totalChapters).fill(null);
        
        const tocList = meta.toc || [];
        renderEpubToc(tocList);

        let startIdx = pickEpubStartIndex(totalChapters, initialPageIdx, null);

        let serverEpubSession = null;
        try {
          const stateRes = await fetch(`/api/media/progress-state?db_type=${state.currentLibraryType}&book_id=${bookId}&_ts=${Date.now()}`, {
            cache: 'no-store'
          });
          if (stateRes.ok) {
            const stateData = await stateRes.json();
            if (stateData && stateData.success && stateData.state && stateData.state.epub_session) {
              serverEpubSession = stateData.state.epub_session;
            }
          }
        } catch (_) {}

        if (serverEpubSession) {
          startIdx = pickEpubStartIndex(totalChapters, initialPageIdx, serverEpubSession);
        } else {
          const savedPosStr = localStorage.getItem(`viewer_last_pos_${bookId}`);
          if (savedPosStr) {
            try {
              const pos = JSON.parse(savedPosStr);
              if (pos && pos.chunkIdx !== undefined && pos.chunkIdx < totalChapters) {
                startIdx = pos.chunkIdx;
              }
            } catch(e) {}
          }
        }

        startIdx = Math.max(0, Math.min(totalChapters - 1, parseInt(startIdx, 10) || 0));
        currentChunkIdx = startIdx;

        // ─── 2단계: 현재 읽고 있는 챕터만 즉시 청크 스트리밍 렌더링 (0.01초) ───
        fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${bookId}&chapter_idx=${startIdx}`)
          .then(cRes => cRes.json())
          .then(cData => {
            hideViewerLoading();
            txtChunks[startIdx] = cData.content || '<p>내용이 없습니다.</p>';
            
            initReadingDirection();
            renderCurrentChunk(true);
            // scrollWrapper에 아직 scroll-mode-page 클래스가 안 붙어 있는 최초 오픈 시점이라,
            // previousMode를 안 넘기면 실제 설정이 '페이지(2장)' 모드여도 내부적으로
            // "scroll → page 모드 전환"으로 오판해 더블 rAF로 지연 적용된다. 그 사이
            // 컬럼 미설정 상태로 첫 페인트가 되어 1페이지 폭처럼 보이는 원인이 되므로,
            // 최초 렌더링임을 명시해 동기적으로 바로 적용되게 한다.
            applyTxtSettings({ previousMode: getViewerSettings().scrollMode });
            setupTxtViewerRuntimeListeners();

            // ─── 3단계: 이전/다음 챕터 백그라운드 프리패치 (전후 10개 챕터 확장) ───
            // hydrateEpubChapterWindow는 이제 반경 내 미로드 챕터를 배치 API 1회 호출로
            // 묶어서 요청하므로(서버에서 zip을 1번만 오픈), 반경을 키워도 zip 재오픈 부담이 없다.
            hydrateEpubChapterWindow(startIdx, 10);
          })
          .catch(err => {
            hideViewerLoading();
            showViewerError(i18n.t('viewer.error_txt_load'));
          });
      })
      .catch(err => {
        hideViewerLoading();
        showViewerError(i18n.t('viewer.error_txt_load'));
      });
    return;
  }

  const url = `/api/media/txt?db_type=${state.currentLibraryType}&book_id=${bookId}`;
  fetch(url)
    .then(res => {
      if (!res.ok) throw new Error(i18n.t('viewer.error_txt_load'));
      return res.text();
    })
    .then(async data => {
      hideViewerLoading();
      txtScrollPreloadTriggered = false;
      txtScrollNextEpisodeTriggered = false;

      fullText = data;
      txtChunks = chunkText(data, 4000);
      // TXT는 실제 목차(TOC)가 없지만, renderEpubToc([])의 폴백 경로(챕터 번호 나열)로
      // 여전히 패널을 띄운다 — 북마크 탭이 이 패널에 얹혀 있어서, 패널 자체를 없애면
      // TXT에서는 북마크 기능을 아예 쓸 수 없게 된다.
      renderEpubToc([]);

      let startIdx = initialPageIdx;

      // Cross-device resume: prefer server pointer / pages_read when available for both TXT and EPUB
      let serverEpubSession = null;
      let serverPagesRead = 0;
      try {
        const stateRes = await fetch(`/api/media/progress-state?db_type=${state.currentLibraryType}&book_id=${bookId}&_ts=${Date.now()}`, {
          cache: 'no-store'
        });
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          if (stateData && stateData.success && stateData.state) {
            if (stateData.state.epub_session) {
              serverEpubSession = stateData.state.epub_session;
            }
            if (typeof stateData.state.pages_read === 'number' && stateData.state.pages_read > 0) {
              serverPagesRead = stateData.state.pages_read;
            }
          }
        }
      } catch (_) {}

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

      if (serverPagesRead > 0) {
        startIdx = Math.max(0, serverPagesRead - 1);
        console.log(`[Viewer-Txt] Server progress-state fetched: chunk ${startIdx + 1}`);
      }

      if (isEpub && serverEpubSession) {
        startIdx = pickEpubStartIndex(txtChunks.length, serverPagesRead > 0 ? serverPagesRead : startIdx, serverEpubSession);

        // Fallback backup pointer: text fingerprint match.
        const fp = String(serverEpubSession.fingerprint || '').trim();
        if (fp) {
          const matchedIdx = txtChunks.findIndex(ch => stripHtml(ch).includes(fp));
          if (matchedIdx >= 0) {
            startIdx = matchedIdx;
          }
        }
      }

      if (isEpub && txtChunks.length > 0) {
        startIdx = Math.max(0, Math.min(txtChunks.length - 1, parseInt(startIdx, 10) || 0));
      }

      currentChunkIdx = startIdx;

      initReadingDirection();
      renderCurrentChunk(true);
      // 최초 오픈 시 previousMode 오판 방지 (위 스트리밍 경로와 동일한 이유)
      applyTxtSettings({ previousMode: getViewerSettings().scrollMode });

      setupTxtViewerRuntimeListeners();
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

function showTxtRestoreLoadingToast(msg = null) {
  const now = Date.now();
  if (now - txtRestoreToastAt < 300) return;
  txtRestoreToastAt = now;
  if (typeof showToast === 'function') {
    showToast(typeof msg === 'string' ? msg : '로딩중입니다', 'info');
  }
}

function renderCurrentChunk(initMode = false, onSettled) {
  const contentArea = document.getElementById('txt-content-area');
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  if (isEpub && (txtChunks[currentChunkIdx] === null || txtChunks[currentChunkIdx] === 'LOADING_PENDING')) {
    // 요청 시점의 챕터 번호를 고정 캡처합니다. currentChunkIdx는 이후 빠른 연속 페이지
    // 넘김으로 계속 바뀔 수 있는 가변 변수라, 응답을 그 변수로 다시 참조해서 쓰면
    // 엉뚱한(현재의) 슬롯에 데이터를 덮어쓰는 레이스가 발생합니다.
    const requestedIdx = currentChunkIdx;
    showViewerLoading(i18n.t("viewer.loading_txt_title"), i18n.t("viewer.loading_txt_sub"));

    const awaitChapter = (retriesLeft, isFirstAttempt) => {
      requestEpubChapterContent(requestedIdx, { force: isFirstAttempt, updateDom: false })
        .then(data => {
          if (data && typeof data === 'string') {
            txtChunks[requestedIdx] = data;
          } else if (retriesLeft > 0) {
            // null 응답은 같은 챕터를 이미 다른 호출이 fetch 중이라는 뜻(in-flight 중복 방지).
            // 빈 내용으로 성급하게 덮어쓰지 말고, 그 fetch가 채워줄 때까지 짧게 재확인한다.
            setTimeout(() => awaitChapter(retriesLeft - 1, false), 200);
            return;
          } else {
            txtChunks[requestedIdx] = '<p>내용이 없습니다.</p>';
          }
          hideViewerLoading();
          if (currentChunkIdx === requestedIdx) {
            renderCurrentChunk(initMode);
          }
        })
        .catch(err => {
          hideViewerLoading();
          showViewerError(i18n.t('viewer.error_txt_load'));
        });
    };

    awaitChapter(10, true);
    return;
  }

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

  applyAnnotationsToAllRenderedChunks({ contentArea, format: isEpub ? 'epub' : 'txt', txtChunks });
  applyDynamicParagraphStyles();
  applyTxtImageMaxHeight(scrollWrapper, contentArea);
  applyTxtTwoPageTrailingSpacer(scrollWrapper, contentArea);

  // 이미지가 로드되기 전에 위 계산이 끝나면(짧은 챕터에서 흔함) 홀/짝 판정이
  // 최종 레이아웃과 어긋난 채 고정될 수 있어, 이미지 로드 완료 후 재계산한다.
  const pendingImages = Array.from(contentArea.querySelectorAll('img')).filter(img => !img.complete);
  if (pendingImages.length) {
    let settled = false;
    let remaining = pendingImages.length;
    const recomputeWhenReady = () => {
      if (settled) return;
      remaining -= 1;
      if (remaining <= 0) {
        settled = true;
        applyTxtTwoPageTrailingSpacer(scrollWrapper, contentArea);
        if (typeof onSettled === 'function') onSettled();
      }
    };
    pendingImages.forEach(img => {
      img.addEventListener('load', recomputeWhenReady, { once: true });
      img.addEventListener('error', recomputeWhenReady, { once: true });
    });
    // 네트워크 문제 등으로 일부 이미지가 load/error 이벤트를 끝내 발생시키지
    // 않는 경우를 대비한 안전장치 — 무한 대기 방지.
    setTimeout(() => {
      if (!settled) {
        settled = true;
        applyTxtTwoPageTrailingSpacer(scrollWrapper, contentArea);
        if (typeof onSettled === 'function') onSettled();
      }
    }, 3000);
  } else if (typeof onSettled === 'function') {
    // 대기할 이미지가 없으면 이 시점에 이미 레이아웃이 최종 상태이므로 바로 콜백한다.
    onSettled();
  }

  // 모드 재전환 시 placeholder가 남아도 가시 범위 챕터를 즉시 재요청해 자동 복구한다.
  if (isEpub && scrollMode === 'scroll') {
    hydrateEpubChapterWindow(currentChunkIdx, 12);
    scheduleVisibleEpubPlaceholderRecovery();
  }

  updateTxtSeekBar();
  syncActiveEpubToc();
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

function persistTxtProgressSnapshot() {
  if (!state.activeBookId || !Array.isArray(txtChunks) || txtChunks.length === 0) return;

  // TXT는 첫 청크/첫 퍼센트 구간에서는 서버 progress가 0으로 남을 수 있으므로,
  // 같은 기기 재오픈용 세부 스크롤/페이지 위치를 닫기 직전에 반드시 갱신합니다.
  saveDetailPosition();

  const totalChunks = txtChunks.length;
  const safeChunkIdx = Math.max(0, Math.min(totalChunks - 1, currentChunkIdx));
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  if (!isEpub) {
    saveProgress(state.activeBookId, safeChunkIdx, totalChunks);
    return;
  }

  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  let snapshotIdx = safeChunkIdx;
  let snapshotPercent = totalChunks > 0 ? Math.round((safeChunkIdx / totalChunks) * 100) : 0;

  if (scrollMode === 'scroll' && scrollWrapper && contentArea) {
    const scrollHeight = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    const ratio = scrollHeight > 0 ? scrollWrapper.scrollTop / scrollHeight : 0;
    const chunks = contentArea.querySelectorAll('.txt-scroll-chunk');
    for (const chunk of chunks) {
      const idx = parseInt(chunk.getAttribute('data-idx'), 10);
      if (Number.isFinite(idx) && scrollWrapper.scrollTop >= chunk.offsetTop - 120) {
        snapshotIdx = idx;
      } else {
        break;
      }
    }
    snapshotPercent = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  }

  let fingerprint = '';
  if (contentArea) {
    const currentChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${snapshotIdx}"]`) || contentArea.querySelector('.txt-chunk, .epub-chunk');
    if (currentChunk) {
      fingerprint = String(currentChunk.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180);
    }
  }

  saveProgress(state.activeBookId, snapshotIdx, totalChunks, {
    epub_session: {
      index: snapshotIdx,
      percent: snapshotPercent,
      fingerprint: fingerprint || undefined
    }
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
        (name, url, target, fallbackFamily) => {
          import('./viewer_settings.js').then(m => {
            m.loadAndApplyCustomFont(name, url, target, fallbackFamily);
          });
        }
      );
    }
  });
}

export function prevTxtPage() {
  prevTxtPageAction({
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    getContentArea: () => document.getElementById('txt-content-area'),
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
    getTxtPageSnapInProgress: () => txtPageSnapInProgress,
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
    getTxtPageSnapInProgress: () => txtPageSnapInProgress,
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
  prepareForClose() {
    persistTxtProgressSnapshot();
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
  syncActiveEpubToc(true);
}

function jumpToChapter(chapterIdx, anchor, options = null) {
  jumpToTxtTocChapter({
    chapterIdx,
    anchor,
    options,
    chunkCount: txtChunks.length,
    txtChunks,
    cancelPendingRestore: cancelPendingTxtRestore,
    setCurrentChunkIdx: value => {
      currentChunkIdx = value;
    },
    getScrollMode: () => localStorage.getItem('viewer_scroll_mode') || 'page',
    getScrollWrapper: () => document.getElementById('txt-scroll-wrapper'),
    renderCurrentChunk,
    saveProgress,
    activeBookId: state.activeBookId,
    onActiveChapterChange: idx => {
      currentChunkIdx = idx;
      syncActiveEpubToc(true);
    }
  });
}

