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

import { showViewerLoading, hideViewerLoading, showViewerError } from './view_manager.js';
import { saveProgress } from './viewer_progress.js';
import { initPageStep, initReadingDirection } from './viewer/reader_settings.js';

export function initTxtViewer(bookId, initialPageIdx = 0) {
  console.log(`[Viewer-Txt] initTxtViewer - 콘텐츠 요청 중: bookId=${bookId}, initialPageIdx=${initialPageIdx}, format=${state.currentViewerFormat}`);
  const pane = document.getElementById('txt-viewer-container');
  const contentArea = document.getElementById('txt-content-area');
  if (!pane || !contentArea) return;
  pane.style.display = 'block';
  
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
      } else {
        fullText = data;
        txtChunks = chunkText(data, 4000);
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
      
      initPageStep();
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
          const currentColumnIdx = Math.round(wrapper.scrollLeft / (wrapper.clientWidth + 40));
          applyTxtSettings();
          wrapper.scrollLeft = currentColumnIdx * (wrapper.clientWidth + 40);
          logActiveViewportText();
        } else {
          const beforeHeight = wrapper.scrollHeight - wrapper.clientHeight;
          const ratio = beforeHeight > 0 ? wrapper.scrollTop / beforeHeight : 0;
          applyTxtSettings();
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
      contentArea.innerHTML = `<div class="txt-chunk epub-chunk" data-idx="${currentChunkIdx}" style="margin-bottom: 2rem;">${txtChunks[currentChunkIdx]}</div>`;
    } else {
      const htmlContent = formatTxtToHtml(txtChunks[currentChunkIdx]);
      contentArea.innerHTML = `<div class="txt-chunk" data-idx="${currentChunkIdx}" style="margin-bottom: 2rem;">${htmlContent}</div>`;
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

  contentArea.querySelectorAll('p, div.txt-chunk > div, div.txt-full-content > div, h1, h2, h3, h4, h5, h6').forEach(el => {
    const tag = el.tagName.toLowerCase();
    if (tag.startsWith('h')) {
      el.style.marginBottom = `${pSpacingRem * 1.5}rem`;
      el.style.marginTop = '1.5rem';
      el.style.fontWeight = 'bold';
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

export function getTxtAnchorInfo() {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!scrollWrapper || !contentArea) return null;
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
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

  const elements = targetArea.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6');
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
      const colWidth = scrollWrapper.clientWidth + 40;
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
      const colWidth = scrollWrapper.clientWidth + 40;
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

export function applyTxtSettings() {
  const container = document.getElementById('txt-viewer-container');
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  const contentArea = document.getElementById('txt-content-area');
  if (!container || !scrollWrapper || !contentArea) return;

  const savedChunkIdx = currentChunkIdx;
  console.log(`[Viewer-Txt] applyTxtSettings 전환 시작 - 현재 챕터:`, savedChunkIdx);

  if (scrollWrapper && scrollWrapper.__txtScrollHandler) {
    scrollWrapper.removeEventListener('scroll', scrollWrapper.__txtScrollHandler);
  }

  const { theme, fontSize, fontFamily, scrollMode, lineHeight } = getViewerSettings();

  container.className = `viewer-pane ${theme.className}`;
  contentArea.style.fontSize = `${fontSize}rem`;
  contentArea.style.lineHeight = lineHeight;

  if (scrollMode === 'page') {
    scrollWrapper.classList.add('scroll-mode-page');
    container.classList.add('scroll-mode-page');

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

    scrollWrapper.style.maxWidth = '';
    scrollWrapper.style.columnCount = '';
    scrollWrapper.style.columnWidth = '';
  }

  applyFontFamilyToElement(contentArea, fontFamily);
  
  currentChunkIdx = savedChunkIdx;
  renderCurrentChunk(true);

  // 로컬 세부 위치 복원 처리
  let restored = false;
  const savedPosStr = localStorage.getItem(`viewer_last_pos_${state.activeBookId}`);
  if (savedPosStr) {
    try {
      const pos = JSON.parse(savedPosStr);
      if (pos && pos.chunkIdx === currentChunkIdx) {
        setTimeout(() => {
          if (scrollMode === 'scroll') {
            scrollWrapper.scrollTop = pos.scrollTop;
          } else {
            scrollWrapper.scrollLeft = pos.scrollLeft;
          }
          console.log(`[Viewer-Txt] 로컬 세부 위치 복원 성공 (left=${pos.scrollLeft}, top=${pos.scrollTop})`);
        }, 150);
        restored = true;
      }
    } catch(e) {}
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
    }
  }

  // 리스너 바인딩 딜레이 적용
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
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    if (scrollWrapper.scrollLeft <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          saveDetailPosition();
        }, 50);
      }
    } else {
      const pageScrollWidth = scrollWrapper.clientWidth + 40;
      scrollWrapper.scrollBy({ left: -pageScrollWidth, behavior: 'auto' });
      setTimeout(() => {
        logActiveViewportText();
        saveDetailPosition();
      }, 100);
    }
  } else {
    if (scrollWrapper.scrollTop <= 10) {
      if (currentChunkIdx > 0) {
        currentChunkIdx--;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          logActiveViewportText();
          saveDetailPosition();
        }, 50);
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
  
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'page') {
    const maxScrollLeft = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
    if (scrollWrapper.scrollLeft + 10 >= maxScrollLeft) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        scrollWrapper.scrollLeft = 0;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          saveDetailPosition();
        }, 50);
      } else {
        import('./viewer_next_episode.js').then(m => {
          m.handleNextEpisodeDirect(state.activeBookId);
        });
      }
    } else {
      const pageScrollWidth = scrollWrapper.clientWidth + 40;
      scrollWrapper.scrollBy({ left: pageScrollWidth, behavior: 'auto' });
      setTimeout(() => {
        logActiveViewportText();
        saveDetailPosition();
      }, 100);
    }
  } else {
    const maxScrollTop = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    if (scrollWrapper.scrollTop + 10 >= maxScrollTop) {
      if (currentChunkIdx < txtChunks.length - 1) {
        currentChunkIdx++;
        scrollWrapper.style.scrollBehavior = 'auto';
        renderCurrentChunk();
        scrollWrapper.scrollTop = 0;
        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          logActiveViewportText();
          saveDetailPosition();
        }, 50);
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
