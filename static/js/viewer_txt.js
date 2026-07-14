// viewer_txt.js – 텍스트 리더(TXT) 및 EPUB 뷰어 통합 로직
import { state } from './state.js';

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

import { showViewerLoading, hideViewerLoading, showViewerError, showToast } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { initPageStep, initReadingDirection } from './viewer/reader_settings.js';

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

function chunkText(text, chunkSize = 4000) {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    if (start + chunkSize >= text.length) {
      chunks.push(text.slice(start));
      break;
    }
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

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getTxtPageGapPx(scrollWrapper) {
  if (!scrollWrapper) return 0;
  const pageStep = localStorage.getItem('comic_page_step') || '1';
  if (pageStep !== '2') return 0;

  // In page mode, multi-column styles are applied to contentArea (not wrapper).
  const contentArea = document.getElementById('txt-content-area');
  const target = contentArea || scrollWrapper;
  const styles = window.getComputedStyle(target);
  const gap = parseFloat(styles.columnGap);
  return Number.isFinite(gap) ? gap : 0;
}

function getTxtPageAdvanceWidth(scrollWrapper) {
  if (!scrollWrapper) return 0;
  const base = Math.max(1, Math.floor(scrollWrapper.clientWidth));
  return base + getTxtPageGapPx(scrollWrapper);
}

function snapTxtPageScrollLeft(scrollWrapper) {
  if (!scrollWrapper) return;
  const stepWidth = getTxtPageAdvanceWidth(scrollWrapper);
  const maxScroll = Math.max(0, scrollWrapper.scrollWidth - scrollWrapper.clientWidth);
  const snapped = Math.min(maxScroll, Math.max(0, Math.round(scrollWrapper.scrollLeft / stepWidth) * stepWidth));
  scrollWrapper.scrollLeft = snapped;
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
  
  if (txtChunks.length === 0) {
    contentArea.textContent = i18n.t('viewer.txt_empty');
    return;
  }

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  if (isEpub) {
    contentArea.style.whiteSpace = 'normal';
    contentArea.style.wordBreak = 'break-word';
  } else {
    contentArea.style.whiteSpace = 'normal';
    contentArea.style.wordBreak = 'break-all';
  }

  const formatTxtToHtml = (rawText) => {
    return rawText
      .split('\n')
      .map(line => {
        const trimmed = line.trim();
        if (!trimmed) return '<p class="txt-paragraph txt-empty-line" style="margin: 0; min-height: 1rem;">&nbsp;</p>';
        return `<p class="txt-paragraph" style="margin: 0;">${escapeHtml(line)}</p>`;
      })
      .join('');
  };

  if (scrollMode === 'page') {
    if (isEpub) {
      contentArea.innerHTML = `<div class="txt-chunk epub-chunk" data-idx="${currentChunkIdx}" style="height: 100%; box-sizing: border-box;">${txtChunks[currentChunkIdx]}</div>`;
    } else {
      const htmlContent = formatTxtToHtml(txtChunks[currentChunkIdx]);
      contentArea.innerHTML = `<div class="txt-chunk" data-idx="${currentChunkIdx}" style="height: 100%; box-sizing: border-box;">${htmlContent}</div>`;
    }
  } else {
    if (initMode || !contentArea.querySelector('.txt-full-content')) {
      if (isEpub) {
        const wrapped = txtChunks.map((ch, idx) => `<div class="txt-scroll-chunk" data-idx="${idx}" style="margin-bottom: 3rem;">${ch}</div>`).join('');
        contentArea.innerHTML = `<div class="txt-full-content epub-full-content">${wrapped}</div>`;
      } else {
        const wrapped = txtChunks.map((ch, idx) => `<div class="txt-scroll-chunk" data-idx="${idx}" style="margin-bottom: 3rem;">${formatTxtToHtml(ch)}</div>`).join('');
        contentArea.innerHTML = `<div class="txt-full-content">${wrapped}</div>`;
      }
    }
  }
  
  applyDynamicParagraphStyles();
  updateTxtSeekBar();
  saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length);
}

function applyDynamicParagraphStyles() {
  const contentArea = document.getElementById('txt-content-area');
  if (!contentArea) return;

  const savedParagraphSpacing = localStorage.getItem('viewer_paragraph_spacing') || '1.0';
  const pSpacingRem = parseFloat(savedParagraphSpacing);
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';

  if (state.currentViewerFormat === 'epub') {
    contentArea.querySelectorAll('img').forEach(img => {
      img.style.maxHeight = scrollMode === 'page' ? '70vh' : '85vh';
      img.style.maxWidth = '100%';
      img.style.objectFit = 'contain';
    });
  }

  contentArea.querySelectorAll('p, div.txt-chunk > div, div.txt-full-content > div, h1, h2, h3, h4, h5, h6, blockquote, ul, ol, li, hr, ruby, rt, rp, sup, sub').forEach(el => {
    const tag = el.tagName.toLowerCase();
    if (tag.startsWith('h')) {
      el.style.marginBottom = `${pSpacingRem * 1.5}rem`;
      el.style.marginTop = '1.5rem';
      el.style.fontWeight = 'bold';
    } else if (tag === 'ul' || tag === 'ol') {
      el.style.marginTop = '0';
      el.style.marginBottom = `${pSpacingRem}rem`;
      el.style.paddingLeft = '1.4rem';
    } else if (tag === 'li') {
      el.style.marginTop = '0';
      el.style.marginBottom = `${Math.max(0.2, pSpacingRem * 0.45)}rem`;
    } else if (tag === 'blockquote') {
      el.style.marginTop = '0';
      el.style.marginBottom = `${pSpacingRem}rem`;
      el.style.paddingLeft = '0.9rem';
      el.style.borderLeft = '3px solid rgba(148, 163, 184, 0.45)';
      el.style.opacity = '0.95';
    } else if (tag === 'hr') {
      el.style.marginTop = `${pSpacingRem}rem`;
      el.style.marginBottom = `${pSpacingRem}rem`;
    } else {
      el.style.marginBottom = `${pSpacingRem}rem`;
      el.style.marginTop = '0';
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

function stripHtml(html) {
  if (!html) return '';
  return html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}

export function getTxtAnchorInfo(forcedMode = null) {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!scrollWrapper || !contentArea) return null;
  
  const scrollMode = forcedMode || localStorage.getItem('viewer_scroll_mode') || 'page';
  const isEpub = (state.currentViewerFormat === 'epub');

  if (scrollMode === 'scroll') {
    const cleanText = isEpub ? stripHtml(fullText) : fullText.replace(/\s+/g, ' ').trim();
    if (cleanText.length === 0) return null;

    const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    const ratio = maxScroll > 0 ? scrollWrapper.scrollTop / maxScroll : 0;
    const startIndex = Math.floor(cleanText.length * ratio);
    const anchorText = cleanText.substring(startIndex, startIndex + 30);

    return {
      chunkIdx: currentChunkIdx,
      anchorText: anchorText
    };
  } else {
    const rawChunk = txtChunks[currentChunkIdx] || '';
    const cleanText = isEpub ? stripHtml(rawChunk) : rawChunk.replace(/\s+/g, ' ').trim();
    if (cleanText.length === 0) return null;

    const maxScroll = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
    const ratio = maxScroll > 0 ? scrollWrapper.scrollLeft / maxScroll : 0;
    const startIndex = Math.floor(cleanText.length * ratio);
    const anchorText = cleanText.substring(startIndex, startIndex + 30);

    return {
      chunkIdx: currentChunkIdx,
      anchorText: anchorText
    };
  }
}

export function restoreTxtAnchorInfo(anchorInfo) {
  if (!anchorInfo || !anchorInfo.anchorText) return false;
  
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!scrollWrapper || !contentArea) return false;

  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const query = anchorInfo.anchorText;
  const targetChunkIdx = anchorInfo.chunkIdx !== undefined ? anchorInfo.chunkIdx : currentChunkIdx;

  let targetArea = contentArea;
  if (scrollMode === 'scroll') {
    const chunkContainer = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${targetChunkIdx}"]`);
    if (chunkContainer) targetArea = chunkContainer;
  } else {
    const chunkContainer = contentArea.querySelector(`.txt-chunk[data-idx="${targetChunkIdx}"]`);
    if (chunkContainer) targetArea = chunkContainer;
  }

  const elements = targetArea.querySelectorAll('p, div, li, blockquote, h1, h2, h3, h4, h5, h6');
  let matchedElem = null;

  for (let el of elements) {
    if (el.children.length === 0 || el.tagName === 'P') {
      const txt = el.textContent.replace(/\s+/g, ' ').trim();
      if (txt.includes(query)) {
        matchedElem = el;
        break;
      }
    }
  }

  if (!matchedElem) {
    for (let el of elements) {
      if (el.textContent.includes(query)) {
        matchedElem = el;
        break;
      }
    }
  }

  if (matchedElem) {
    if (scrollMode === 'scroll') {
      scrollWrapper.scrollTop = Math.max(0, matchedElem.offsetTop - 30);
      console.log(`[Viewer-Txt] DOM 매칭 앵커 복원 성공 (세로 scrollTop = ${scrollWrapper.scrollTop})`);
      return true;
    } else {
      const colWidth = getTxtPageAdvanceWidth(scrollWrapper);
      const pageIndex = Math.floor(matchedElem.offsetTop / scrollWrapper.clientHeight);
      scrollWrapper.scrollLeft = pageIndex * colWidth;
      console.log(`[Viewer-Txt] DOM 매칭 앵커 복원 성공 (가로 scrollLeft = ${scrollWrapper.scrollLeft})`);
      return true;
    }
  }

  const isEpub = (state.currentViewerFormat === 'epub');
  if (scrollMode === 'scroll') {
    const cleanText = isEpub ? stripHtml(fullText) : fullText.replace(/\s+/g, ' ').trim();
    
    let charOffset = 0;
    for (let i = 0; i < targetChunkIdx; i++) {
      const chunkText = isEpub ? stripHtml(txtChunks[i]) : txtChunks[i].replace(/\s+/g, ' ').trim();
      charOffset += chunkText.length;
    }

    const matchIndex = cleanText.indexOf(query, charOffset);
    if (matchIndex !== -1) {
      const ratio = matchIndex / cleanText.length;
      const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
      scrollWrapper.scrollTop = maxScroll * ratio;
      console.log(`[Viewer-Txt] Fallback 문자열 매핑 복원 성공 (세로 ratio=${ratio})`);
      return true;
    }
  } else {
    const rawChunk = txtChunks[targetChunkIdx] || '';
    const cleanText = isEpub ? stripHtml(rawChunk) : rawChunk.replace(/\s+/g, ' ').trim();
    const matchIndex = cleanText.indexOf(query);
    if (matchIndex !== -1) {
      const ratio = matchIndex / cleanText.length;
      const colWidth = getTxtPageAdvanceWidth(scrollWrapper);
      const maxScroll = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
      scrollWrapper.scrollLeft = Math.round((maxScroll * ratio) / colWidth) * colWidth;
      console.log(`[Viewer-Txt] Fallback 문자열 매핑 복원 성공 (가로 ratio=${ratio})`);
      return true;
    }
  }
  return false;
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

  const savedChunkIdx = currentChunkIdx;
  const previousMode = options.previousMode || (scrollWrapper.classList.contains('scroll-mode-page') ? 'page' : 'scroll');
  console.log(`[Viewer-Txt] applyTxtSettings 전환 시작 - 현재 챕터:`, savedChunkIdx);

  if (scrollWrapper && scrollWrapper.__txtScrollHandler) {
    scrollWrapper.removeEventListener('scroll', scrollWrapper.__txtScrollHandler);
  }

  const { theme, fontSize, fontFamily, scrollMode, lineHeight } = getViewerSettings();
  const isModeSwitch = previousMode !== scrollMode;
  const preservedAnchor = isModeSwitch ? getTxtAnchorInfo(previousMode) : null;

  container.className = `viewer-pane ${theme.className}`;
  contentArea.style.fontSize = `${fontSize}rem`;
  contentArea.style.lineHeight = lineHeight;

  if (scrollMode === 'page') {
    scrollWrapper.classList.add('scroll-mode-page');
    container.classList.add('scroll-mode-page');

    contentArea.style.paddingTop = '0';
    contentArea.style.paddingBottom = '0';
    contentArea.style.paddingLeft = '0';
    contentArea.style.paddingRight = '0';

    const padLeft = parseInt(localStorage.getItem('viewer_padding_left') || '20', 10);
    const padRight = parseInt(localStorage.getItem('viewer_padding_right') || '20', 10);
    const parentWidth = container ? container.clientWidth : window.innerWidth;
    const targetWidth = Math.floor(parentWidth - (padLeft + padRight));

    const pageStep = localStorage.getItem('comic_page_step') || '1';
    const pageGap = pageStep === '2' ? 40 : 0;
    if (pageStep === '2') {
      scrollWrapper.style.maxWidth = `${targetWidth}px`;
    } else {
      scrollWrapper.style.maxWidth = `${Math.min(targetWidth, 800)}px`;
    }

    const wrapperWidth = Math.max(1, Math.floor(scrollWrapper.clientWidth));
    const singleColWidth = pageStep === '2'
      ? Math.max(1, Math.floor((wrapperWidth - pageGap) / 2))
      : Math.max(1, wrapperWidth);

    // 다단(CSS Column) 정렬 설정을 부모가 아닌 자식(contentArea)에 부여하여 가로 스크롤 활성화
    contentArea.style.columnCount = pageStep === '2' ? '2' : '1';
    contentArea.style.columnGap = `${pageGap}px`;
    contentArea.style.columnWidth = `${singleColWidth}px`;
    contentArea.style.columnFill = 'auto';
    contentArea.style.height = '100%';

    scrollWrapper.style.columnCount = '';
    scrollWrapper.style.columnWidth = '';
    scrollWrapper.style.columnGap = '';
  } else {
    scrollWrapper.classList.remove('scroll-mode-page');
    container.classList.remove('scroll-mode-page');

    scrollWrapper.style.maxWidth = '';
    scrollWrapper.style.columnCount = '';
    scrollWrapper.style.columnWidth = '';
    scrollWrapper.style.columnGap = '';

    contentArea.style.columnCount = '';
    contentArea.style.columnWidth = '';
    contentArea.style.columnGap = '';
    contentArea.style.columnFill = '';
    contentArea.style.height = '';

    const padTop = parseInt(localStorage.getItem('viewer_padding_top') || '40', 10);
    const padBottom = parseInt(localStorage.getItem('viewer_padding_bottom') || '60', 10);
    const padLeft = parseInt(localStorage.getItem('viewer_padding_left') || '20', 10);
    const padRight = parseInt(localStorage.getItem('viewer_padding_right') || '20', 10);
    contentArea.style.paddingTop = `${padTop}px`;
    contentArea.style.paddingBottom = `${padBottom}px`;
    contentArea.style.paddingLeft = `${padLeft}px`;
    contentArea.style.paddingRight = `${padRight}px`;
  }

  applyFontFamilyToElement(contentArea, fontFamily);
  
  currentChunkIdx = savedChunkIdx;
  renderCurrentChunk(true);

  let restored = false;
  const skipSavedPositionRestore = !!options.skipSavedPositionRestore;
  const savedPosStr = localStorage.getItem(`viewer_last_pos_${state.activeBookId}`);
  if (!skipSavedPositionRestore && !isModeSwitch && savedPosStr) {
    try {
      const pos = JSON.parse(savedPosStr);
      if (pos && pos.chunkIdx === currentChunkIdx) {
        showTxtRestoreLoadingToast();
        txtPendingRestoreTimer = setTimeout(() => {
          if (scrollMode === 'scroll') {
            scrollWrapper.scrollTop = pos.scrollTop;
          } else {
            scrollWrapper.scrollLeft = pos.scrollLeft;
            snapTxtPageScrollLeft(scrollWrapper);
          }
          txtPendingRestoreTimer = null;
          console.log(`[Viewer-Txt] 로컬 세부 위치 복원 성공 (left=${pos.scrollLeft}, top=${pos.scrollTop})`);
        }, 150);
        restored = true;
      }
    } catch(e) {}
  }

  if (!restored && isModeSwitch && preservedAnchor) {
    showTxtRestoreLoadingToast();
    txtPendingRestoreTimer = setTimeout(() => {
      const ok = restoreTxtAnchorInfo(preservedAnchor);
      if (ok) {
        snapTxtPageScrollLeft(scrollWrapper);
        saveDetailPosition();
        console.log('[Viewer-Txt] 모드 전환 앵커 복원 성공');
      }
      txtPendingRestoreTimer = null;
    }, 150);
    restored = true;
  }

  if (!restored) {
    if (scrollMode === 'scroll') {
      setTimeout(() => {
        const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${currentChunkIdx}"]`);
        if (targetChunk) {
          scrollWrapper.scrollTop = Math.max(0, targetChunk.offsetTop - 20);
          console.log(`[Viewer-Txt] 챕터 오프셋 기준으로 스크롤 정렬 완료 (scrollTop = ${scrollWrapper.scrollTop})`);
        } else {
          const ratio = currentChunkIdx / txtChunks.length;
          scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
        }
      }, 150);
    } else {
      scrollWrapper.scrollLeft = 0;
      snapTxtPageScrollLeft(scrollWrapper);
    }
  }

  setTimeout(() => {
    if (scrollWrapper && scrollWrapper.__txtScrollHandler) {
      scrollWrapper.addEventListener('scroll', scrollWrapper.__txtScrollHandler, { passive: true });
    }
  }, 250);
}

function applyFontFamilyToElement(element, fontKey) {
  if (fontKey === 'batang') {
    element.style.fontFamily = "'KoPub Batang', 'Nanum Myeongjo', serif";
  } else if (fontKey === 'gothic') {
    element.style.fontFamily = "'Nanum Gothic', 'Malgun Gothic', sans-serif";
  } else if (fontKey === 'pretendard') {
    element.style.fontFamily = "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif";
  } else {
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
  cancelPendingTxtRestore();
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    snapTxtPageScrollLeft(scrollWrapper);
    if (scrollWrapper.scrollLeft <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        
        setTimeout(() => {
          scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
        }, 20);
        
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          saveDetailPosition();
        }, 80);
      }
    } else {
      const pageStepWidth = getTxtPageAdvanceWidth(scrollWrapper);
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = Math.max(0, (currentPageIdx - 1) * pageStepWidth);
      txtPageSnapInProgress = true;
      scrollWrapper.scrollTo({ left: targetScrollLeft, behavior: 'auto' });
      setTimeout(() => {
        snapTxtPageScrollLeft(scrollWrapper);
        logActiveViewportText();
        saveDetailPosition();
        txtPageSnapInProgress = false;
      }, 150);
    }
  } else {
    if (scrollWrapper.scrollTop <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        
        setTimeout(() => {
          scrollWrapper.scrollTop = scrollWrapper.scrollHeight;
        }, 20);
        
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          logActiveViewportText();
          saveDetailPosition();
        }, 80);
      }
    } else {
      scrollWrapper.scrollBy({ top: -scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
      setTimeout(() => {
        logActiveViewportText();
        saveDetailPosition();
      }, 350);
    }
  }
}

export function nextTxtPage() {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!scrollWrapper) return;
  cancelPendingTxtRestore();
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    snapTxtPageScrollLeft(scrollWrapper);
    const maxScrollLeft = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
    if (scrollWrapper.scrollLeft + 10 >= maxScrollLeft) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        
        setTimeout(() => {
          scrollWrapper.scrollLeft = 0;
          scrollWrapper.scrollTop = 0;
        }, 20);
        
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          saveDetailPosition();
        }, 80);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisodeDirect(state.activeBookId);
        });
      }
    } else {
      const pageStepWidth = getTxtPageAdvanceWidth(scrollWrapper);
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = (currentPageIdx + 1) * pageStepWidth;
      txtPageSnapInProgress = true;
      scrollWrapper.scrollTo({ left: targetScrollLeft, behavior: 'auto' });
      setTimeout(() => {
        snapTxtPageScrollLeft(scrollWrapper);
        logActiveViewportText();
        saveDetailPosition();
        txtPageSnapInProgress = false;
      }, 150);
    }
  } else {
    const maxScrollTop = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    if (scrollWrapper.scrollTop + 10 >= maxScrollTop) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        
        setTimeout(() => {
          scrollWrapper.scrollTop = 0;
          scrollWrapper.scrollLeft = 0;
        }, 20);
        
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          logActiveViewportText();
          saveDetailPosition();
        }, 80);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisodeDirect(state.activeBookId);
        });
      }
    } else {
      scrollWrapper.scrollBy({ top: scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
      setTimeout(() => {
        logActiveViewportText();
        saveDetailPosition();
      }, 350);
    }
  }
}

export function txtJumpToFirstPage() {
  cancelPendingTxtRestore();
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
  cancelPendingTxtRestore();
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
  cancelPendingTxtRestore();
  const targetIdx = Math.max(0, Math.min(txtChunks.length - 1, val - 1));
  if (currentChunkIdx !== targetIdx) {
    currentChunkIdx = targetIdx;
    
    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    const scrollWrapper = document.getElementById('txt-scroll-wrapper');
    if (scrollMode === 'scroll') {
      if (scrollWrapper) {
        const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
        const targetPercent = targetIdx / Math.max(1, txtChunks.length - 1);
        scrollWrapper.scrollTop = maxScroll * targetPercent;
        setTimeout(saveDetailPosition, 50);
      }
    } else {
      if (scrollWrapper) {
        scrollWrapper.scrollLeft = 0;
      }
      renderCurrentChunk();
      logActiveViewportText();
      saveDetailPosition();
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
    let container = document.getElementById('epub-toc-container');
    let btn = document.getElementById('epub-toc-btn');

    if (!container) {
        container = document.createElement('div');
        container.id = 'epub-toc-container';
        container.className = 'epub-toc-container';
        container.style.cssText = `
            position: fixed;
            top: 0;
            right: -320px;
            width: 300px;
            height: 100%;
            background: var(--bg-color, #1e1e1e);
            color: var(--text-color, #d4d4d4);
            box-shadow: -2px 0 12px rgba(0,0,0,0.5);
            transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 9999;
            overflow-y: auto;
            padding: 20px;
            box-sizing: border-box;
            border-left: 1px solid rgba(255,255,255,0.1);
        `;
        document.body.appendChild(container);
    }

    if (!btn) {
        btn = document.createElement('button');
        btn.id = 'epub-toc-btn';
        btn.innerHTML = '<i class="fas fa-list"></i>';
        btn.style.cssText = `
            position: fixed;
            top: 90px;
            right: 20px;
            z-index: 10000;
            background: rgba(0,0,0,0.6);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 50%;
            width: 44px;
            height: 44px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            backdrop-filter: blur(4px);
            transition: transform 0.2s, background 0.2s;
        `;
        btn.onmouseover = () => btn.style.transform = 'scale(1.05)';
        btn.onmouseout = () => btn.style.transform = 'scale(1)';
        btn.onclick = () => {
            const isClosed = container.style.right.startsWith('-');
            container.style.right = isClosed ? '0px' : '-320px';
        };
        document.body.appendChild(btn);
    }

    const headerEl = document.createElement('h3');
    headerEl.style.cssText = 'margin-top:0; margin-bottom:20px; font-weight:600; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;';
    headerEl.textContent = '목차';

    const ul = document.createElement('ul');
    ul.style.cssText = 'list-style:none; padding:0; margin:0; font-size:0.95rem;';

    const buildItem = (title, chapterIdx, anchor, paddingLeft) => {
        const li = document.createElement('li');
        li.style.cssText = `padding-left:${paddingLeft}px; margin-bottom:12px; line-height:1.4;`;
        const a = document.createElement('a');
        a.href = '#';
        a.style.cssText = 'color:inherit; text-decoration:none; display:block; opacity:0.85; transition:opacity 0.2s;';
        a.textContent = title;
        a.addEventListener('mouseover', () => { a.style.opacity = '1'; });
        a.addEventListener('mouseout', () => { a.style.opacity = '0.85'; });
        a.addEventListener('click', (e) => {
            e.preventDefault();
            jumpToChapter(chapterIdx, anchor);
        });
        li.appendChild(a);
        return li;
    };

    if (tocList && tocList.length > 0) {
        tocList.forEach(item => {
            ul.appendChild(buildItem(item.title, item.chapter_idx, item.anchor || '', (item.level - 1) * 16));
        });
    } else {
        txtChunks.forEach((_, idx) => {
            ul.appendChild(buildItem(`청크 ${idx + 1}`, idx, '', 0));
        });
    }

    container.innerHTML = '';
    container.appendChild(headerEl);
    container.appendChild(ul);
}

function jumpToChapter(chapterIdx, anchor) {
    if (chapterIdx < 0 || chapterIdx >= txtChunks.length) return;

    const container = document.getElementById('epub-toc-container');
    if (container) container.style.right = '-320px';

    currentChunkIdx = chapterIdx;

    const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
    if (scrollMode === 'scroll') {
        const scrollWrapper = document.getElementById('txt-scroll-wrapper');
        const ratio = currentChunkIdx / txtChunks.length;
        if (scrollWrapper) {
            scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
        }
    } else {
        renderCurrentChunk(true);
    }

    saveProgress(state.activeBookId, currentChunkIdx, txtChunks.length);

    if (anchor) {
        setTimeout(() => {
            const targetEl = document.getElementById(anchor);
            if (targetEl) {
                targetEl.scrollIntoView({ behavior: 'smooth' });
            }
        }, 100);
    }
}

