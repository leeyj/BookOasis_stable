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
import { renderEpubTocPanel, jumpToTxtTocChapter, highlightEpubTocChapter } from './viewer/txt_toc.js';

function syncActiveEpubToc(scrollIntoView = false) {
  if ((state.currentViewerFormat || '').toLowerCase() !== 'epub') return;
  highlightEpubTocChapter(currentChunkIdx, { scrollIntoView });
}

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

        let startIdx = initialPageIdx;
        let serverEpubSession = null;
        try {
          const stateRes = await fetch(`/api/media/progress-state?db_type=${state.currentLibraryType}&book_id=${bookId}`);
          if (stateRes.ok) {
            const stateData = await stateRes.json();
            if (stateData && stateData.success && stateData.state && stateData.state.epub_session) {
              serverEpubSession = stateData.state.epub_session;
            }
          }
        } catch (_) {}

        const savedPosStr = localStorage.getItem(`viewer_last_pos_${bookId}`);
        if (savedPosStr) {
          try {
            const pos = JSON.parse(savedPosStr);
            if (pos && pos.chunkIdx !== undefined) {
              startIdx = pos.chunkIdx;
            }
          } catch(e) {}
        }

        if (serverEpubSession) {
          if (Number.isFinite(serverEpubSession.index)) {
            startIdx = Number(serverEpubSession.index);
          } else if (Number.isFinite(serverEpubSession.percent)) {
            startIdx = Math.round((Number(serverEpubSession.percent) / 100) * Math.max(0, totalChapters - 1));
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
            applyTxtSettings();

            // ─── 3단계: 이전/다음 챕터 백그라운드 프리패치 (전후 10개 챕터 확장) ───
            const prefetchIndices = [];
            for (let offset = 1; offset <= 10; offset++) {
              prefetchIndices.push(startIdx - offset);
              prefetchIndices.push(startIdx + offset);
            }
            const validPrefetchIndices = prefetchIndices.filter(i => i >= 0 && i < totalChapters);
            validPrefetchIndices.forEach(pIdx => {
              if (txtChunks[pIdx] === null) {
                txtChunks[pIdx] = 'LOADING_PENDING'; // 중복 fetch 방지
                fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${bookId}&chapter_idx=${pIdx}`)
                  .then(r => r.json())
                  .then(d => {
                    const content = (d && d.content) ? d.content : '<p>내용이 없습니다.</p>';
                    txtChunks[pIdx] = content;
                    const contentArea = document.getElementById('txt-content-area');
                    if (contentArea) {
                      const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${pIdx}"]`);
                      if (chunkEl) chunkEl.innerHTML = content;
                    }
                  })
                  .catch(() => {
                    txtChunks[pIdx] = null;
                  });
              }
            });
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
      const tocBtn = document.getElementById('epub-toc-btn');
      const tocContainer = document.getElementById('epub-toc-container');
      if (tocBtn) tocBtn.remove();
      if (tocContainer) tocContainer.remove();

      let startIdx = initialPageIdx;

      // Cross-device resume: prefer server pointer / pages_read when available for both TXT and EPUB
      let serverEpubSession = null;
      let serverPagesRead = 0;
      try {
        const stateRes = await fetch(`/api/media/progress-state?db_type=${state.currentLibraryType}&book_id=${bookId}`);
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
        if (Number.isFinite(serverEpubSession.index)) {
          startIdx = Number(serverEpubSession.index);
        } else if (Number.isFinite(serverEpubSession.percent)) {
          const byPercent = Math.round((Number(serverEpubSession.percent) / 100) * Math.max(0, txtChunks.length - 1));
          startIdx = byPercent;
        }

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
            const targetIndices = [];
            for (let offset = -10; offset <= 10; offset++) {
              targetIndices.push(newIdx + offset);
            }
            const validTargetIndices = targetIndices.filter(i => i >= 0 && i < txtChunks.length);
            validTargetIndices.forEach(fIdx => {
              if (txtChunks[fIdx] === null) {
                txtChunks[fIdx] = 'LOADING_PENDING';
                fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&chapter_idx=${fIdx}`)
                  .then(r => r.json())
                  .then(d => {
                    const content = (d && d.content) ? d.content : '<p>내용이 없습니다.</p>';
                    txtChunks[fIdx] = content;
                    const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${fIdx}"]`);
                    if (chunkEl) chunkEl.innerHTML = content;
                  })
                  .catch(err => {
                    txtChunks[fIdx] = null;
                  });
              }
            });
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
              const fetchList = [newIdx, newIdx - 1, newIdx + 1].filter(i => i >= 0 && i < txtChunks.length && txtChunks[i] === null);
              fetchList.forEach(fIdx => {
                fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&chapter_idx=${fIdx}`)
                  .then(r => r.json())
                  .then(d => {
                    if (d && d.content) {
                      txtChunks[fIdx] = d.content;
                      const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${fIdx}"]`);
                      if (chunkEl) chunkEl.innerHTML = d.content;
                    }
                  })
                  .catch(() => {});
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
          const currentColumnIdx = Math.round(wrapper.scrollLeft / prevStepWidth);
          // Resize relayout should preserve current visual page, not stale saved localStorage position.
          applyTxtSettings({ previousMode: mode, skipSavedPositionRestore: true });
          const newStepWidth = getTxtPageAdvanceWidth(wrapper);
          wrapper.scrollLeft = currentColumnIdx * newStepWidth;
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

function renderCurrentChunk(initMode = false) {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  if (isEpub && txtChunks[currentChunkIdx] === null) {
    showViewerLoading(i18n.t("viewer.loading_txt_title"), i18n.t("viewer.loading_txt_sub"));
    fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&chapter_idx=${currentChunkIdx}`)
      .then(res => res.json())
      .then(data => {
        hideViewerLoading();
        txtChunks[currentChunkIdx] = data.content || '<p>내용이 없습니다.</p>';
        renderCurrentChunk(initMode);
      })
      .catch(err => {
        hideViewerLoading();
        showViewerError(i18n.t('viewer.error_txt_load'));
      });
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

  applyDynamicParagraphStyles();
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

