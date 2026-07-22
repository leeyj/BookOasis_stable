import { state } from '../state.js';

let overlayVisibilityListenerBound = false;
let tocEntryRefs = [];
let activeTocIdx = -1;
let isTocPanelOpen = false;

function _debugToc() {
  // Debug hook reserved for temporary TOC troubleshooting.
}

function _teardownTocDebugWatchers() {
  // no-op
}

function _setupTocDebugWatchers() {
  // no-op
}

function _applyTocPanelState(container, shouldShowButton) {
  if (!container) return;
  if (!shouldShowButton) {
    container.style.display = 'none';
    container.style.right = '-320px';
    container.style.opacity = '0';
    container.style.visibility = 'hidden';
    container.style.pointerEvents = 'none';
    _debugToc('apply-panel-state:hidden-no-button', {
      shouldShowButton: false,
      shouldOpen: false,
    });
    return;
  }

  const shouldOpen = !!shouldShowButton && !!isTocPanelOpen;
  container.style.display = 'block';
  container.style.right = shouldOpen ? '0px' : '-320px';
  container.style.opacity = shouldOpen ? '1' : '0';
  container.style.visibility = shouldOpen ? 'visible' : 'hidden';
  container.style.pointerEvents = shouldOpen ? 'auto' : 'none';
  _debugToc('apply-panel-state', {
    shouldShowButton: !!shouldShowButton,
    shouldOpen,
  });
}

function _getTocHostElement() {
  return document.getElementById('media-viewer-modal') || document.body;
}

function _applyTocItemVisualState(li, anchorEl, isActive) {
  if (!li || !anchorEl) return;

  if (isActive) {
    li.style.background = 'rgba(168, 85, 247, 0.18)';
    li.style.border = '1px solid rgba(192, 132, 252, 0.45)';
    li.style.borderRadius = '8px';
    li.style.paddingTop = '6px';
    li.style.paddingBottom = '6px';
    anchorEl.style.opacity = '1';
    anchorEl.style.color = '#f5d0fe';
    anchorEl.style.fontWeight = '700';
  } else {
    li.style.background = 'transparent';
    li.style.border = '1px solid transparent';
    li.style.borderRadius = '8px';
    li.style.paddingTop = '';
    li.style.paddingBottom = '';
    anchorEl.style.opacity = '0.85';
    anchorEl.style.color = 'inherit';
    anchorEl.style.fontWeight = '400';
  }
}

function _resolveBestTocIndex(chapterIdx) {
  const target = Number.isFinite(chapterIdx) ? chapterIdx : parseInt(chapterIdx, 10);
  if (!Number.isFinite(target)) return -1;
  if (!Array.isArray(tocEntryRefs) || tocEntryRefs.length === 0) return -1;

  // 1) Exact chapter index match.
  const exact = tocEntryRefs.findIndex(ref => ref.chapterIdx === target);
  if (exact >= 0) return exact;

  // 2) Nearest previous chapter index.
  let best = -1;
  let bestChapter = -1;
  tocEntryRefs.forEach((ref, idx) => {
    if (ref.chapterIdx >= 0 && ref.chapterIdx <= target && ref.chapterIdx >= bestChapter) {
      best = idx;
      bestChapter = ref.chapterIdx;
    }
  });
  if (best >= 0) return best;

  // 3) If only future chapters exist, use the earliest one.
  let earliest = -1;
  let earliestChapter = Number.MAX_SAFE_INTEGER;
  tocEntryRefs.forEach((ref, idx) => {
    if (ref.chapterIdx >= 0 && ref.chapterIdx < earliestChapter) {
      earliest = idx;
      earliestChapter = ref.chapterIdx;
    }
  });
  return earliest;
}

export function highlightEpubTocChapter(chapterIdx, options = {}) {
  const resolvedIdx = _resolveBestTocIndex(chapterIdx);
  if (resolvedIdx < 0 || resolvedIdx >= tocEntryRefs.length) return;

  const shouldScroll = !!options.scrollIntoView;
  if (activeTocIdx === resolvedIdx && !shouldScroll) return;

  if (activeTocIdx >= 0 && activeTocIdx < tocEntryRefs.length) {
    const prev = tocEntryRefs[activeTocIdx];
    _applyTocItemVisualState(prev.li, prev.anchorEl, false);
  }

  const next = tocEntryRefs[resolvedIdx];
  _applyTocItemVisualState(next.li, next.anchorEl, true);
  activeTocIdx = resolvedIdx;

  if (shouldScroll && next.li && typeof next.li.scrollIntoView === 'function') {
    next.li.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

function syncEpubTocVisibility() {
  const container = document.getElementById('epub-toc-container');
  const btn = document.getElementById('epub-toc-btn');
  const overlayMenu = document.getElementById('comic-overlay-menu');
  // 오버레이는 navigation.js에서 inline style('flex'/'none')로만 토글한다.
  // style 값이 비어 있을 때를 열린 상태로 오인하지 않도록 엄격 비교한다.
  const isOverlayOpen = !!overlayMenu && overlayMenu.style.display === 'flex';
  const isEpub = (state.currentViewerFormat || '').toLowerCase() === 'epub';
  const shouldShow = isEpub && isOverlayOpen;

  if (btn) {
    btn.style.display = shouldShow ? 'flex' : 'none';
  }

  if (!shouldShow) {
    isTocPanelOpen = false;
  }
  _applyTocPanelState(container, shouldShow);
  _debugToc('sync-visibility', {
    isOverlayOpen,
    isEpub,
    shouldShow,
  });
}

function ensureOverlayVisibilityListener() {
  if (overlayVisibilityListenerBound) return;
  overlayVisibilityListenerBound = true;

  document.addEventListener('viewer-overlay-visibility-changed', (e) => {
    _debugToc('event:viewer-overlay-visibility-changed', {
      detail: e && e.detail ? e.detail : null,
    });
    syncEpubTocVisibility();
  });
  document.addEventListener('fullscreenchange', () => {
    isTocPanelOpen = false;
    _debugToc('event:fullscreenchange');
    syncEpubTocVisibility();
  });
  document.addEventListener('webkitfullscreenchange', () => {
    isTocPanelOpen = false;
    _debugToc('event:webkitfullscreenchange');
    syncEpubTocVisibility();
  });
}

export function renderEpubTocPanel({ tocList, txtChunks, onJumpToChapter }) {
  let container = document.getElementById('epub-toc-container');
  let btn = document.getElementById('epub-toc-btn');
  const hostEl = _getTocHostElement();

  ensureOverlayVisibilityListener();
  _debugToc('render-start', {
    tocCount: Array.isArray(tocList) ? tocList.length : -1,
    chunkCount: Array.isArray(txtChunks) ? txtChunks.length : -1,
  });

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
      opacity: 0;
      visibility: hidden;
      pointer-events: none;
      background: var(--bg-color, #1e1e1e);
      color: var(--text-color, #d4d4d4);
      box-shadow: -2px 0 12px rgba(0,0,0,0.5);
      transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease;
      z-index: 10008;
      overflow-y: auto;
      padding: 20px;
      box-sizing: border-box;
      border-left: 1px solid rgba(255,255,255,0.1);
    `;
    container.addEventListener('click', (e) => {
      e.stopPropagation();
    });
    hostEl.appendChild(container);
  } else if (container.parentElement !== hostEl) {
    hostEl.appendChild(container);
  }

  _setupTocDebugWatchers(container);

  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'epub-toc-btn';
    btn.innerHTML = '<i class="fas fa-list"></i>';
    btn.style.cssText = `
      position: fixed;
      top: calc(100px + env(safe-area-inset-top, 0px));
      right: calc(20px + env(safe-area-inset-right, 0px));
      z-index: 10009;
      background: rgba(0,0,0,0.6);
      color: white;
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 50%;
      width: 44px;
      height: 44px;
      cursor: pointer;
      display: none;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      backdrop-filter: blur(4px);
      touch-action: manipulation;
      transition: transform 0.2s, background 0.2s;
    `;
    btn.onmouseover = () => {
      btn.style.transform = 'scale(1.05)';
    };
    btn.onmouseout = () => {
      btn.style.transform = 'scale(1)';
    };
    let lastToggleAt = 0;
    const toggleFromButton = (e, source) => {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      const now = Date.now();
      if (now - lastToggleAt < 250) return;
      lastToggleAt = now;

      const overlayMenu = document.getElementById('comic-overlay-menu');
      const isOverlayOpen = !!overlayMenu && overlayMenu.style.display === 'flex';
      if (!isOverlayOpen) {
        _debugToc('btn-click-ignored-overlay-closed', { source });
        return;
      }
      isTocPanelOpen = !isTocPanelOpen;
      _debugToc('btn-click-toggle', { nextOpen: isTocPanelOpen, source });
      _applyTocPanelState(container, true);
    };
    btn.onclick = (e) => toggleFromButton(e, 'click');
    btn.addEventListener('touchend', (e) => {
      toggleFromButton(e, 'touchend');
    }, { passive: false });
    hostEl.appendChild(btn);
  } else if (btn.parentElement !== hostEl) {
    hostEl.appendChild(btn);
  }

  const headerEl = document.createElement('h3');
  headerEl.style.cssText = 'margin-top:0; margin-bottom:20px; font-weight:600; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;';
  headerEl.textContent = '목차';

  const ul = document.createElement('ul');
  ul.style.cssText = 'list-style:none; padding:0; margin:0; font-size:0.95rem;';
  tocEntryRefs = [];
  activeTocIdx = -1;

  const buildItem = (title, chapterIdx, anchor, paddingLeft, level = 1) => {
    const li = document.createElement('li');
    li.style.cssText = `padding-left:${paddingLeft}px; margin-bottom:12px; line-height:1.4;`;
    li.dataset.chapterIdx = String(chapterIdx);
    const a = document.createElement('a');
    a.href = '#';
    a.style.cssText = 'color:inherit; text-decoration:none; display:block; opacity:0.85; transition:opacity 0.2s;';
    a.style.touchAction = 'manipulation';
    a.textContent = title;
    a.addEventListener('mouseover', () => {
      a.style.opacity = '1';
    });
    a.addEventListener('mouseout', () => {
      a.style.opacity = '0.85';
    });
    let lastJumpAt = 0;
    let touchStartX = 0;
    let touchStartY = 0;
    let touchMoved = false;
    let suppressClickUntil = 0;
    const TOUCH_TAP_THRESHOLD = 10;
    const handleJump = (e, source) => {
      e.preventDefault();
      e.stopPropagation();
      const now = Date.now();
      if (now - lastJumpAt < 250) return;
      lastJumpAt = now;
      const isTopLevelChapter = Number(level || 1) <= 1;
      _debugToc('toc-item-jump', { chapterIdx, hasAnchor: !!anchor, source });
      onJumpToChapter(chapterIdx, anchor, {
        preferChapterStart: isTopLevelChapter,
      });
    };
    a.addEventListener('click', e => {
      if (Date.now() < suppressClickUntil) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      handleJump(e, 'click');
    });
    a.addEventListener('touchstart', e => {
      const touch = e.touches && e.touches[0];
      if (!touch) return;
      touchStartX = touch.clientX;
      touchStartY = touch.clientY;
      touchMoved = false;
    }, { passive: true });
    a.addEventListener('touchmove', e => {
      const touch = e.touches && e.touches[0];
      if (!touch) return;
      const dx = Math.abs(touch.clientX - touchStartX);
      const dy = Math.abs(touch.clientY - touchStartY);
      if (dx > TOUCH_TAP_THRESHOLD || dy > TOUCH_TAP_THRESHOLD) {
        touchMoved = true;
      }
    }, { passive: true });
    a.addEventListener('touchend', e => {
      if (touchMoved) {
        suppressClickUntil = Date.now() + 350;
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      handleJump(e, 'touchend');
    }, { passive: false });
    a.addEventListener('touchcancel', () => {
      touchMoved = false;
    }, { passive: true });
    li.appendChild(a);
    tocEntryRefs.push({
      chapterIdx: Number.isFinite(chapterIdx) ? chapterIdx : parseInt(chapterIdx, 10),
      li,
      anchorEl: a,
    });
    return li;
  };

  if (tocList && tocList.length > 0) {
    tocList.forEach(item => {
      ul.appendChild(buildItem(item.title, item.chapter_idx, item.anchor || '', (item.level - 1) * 16, item.level || 1));
    });
  } else {
    txtChunks.forEach((_, idx) => {
      ul.appendChild(buildItem(`청크 ${idx + 1}`, idx, '', 0));
    });
  }

  container.innerHTML = '';
  container.appendChild(headerEl);
  container.appendChild(ul);

  // EPUB 새 렌더 시 이전 열림 상태가 남지 않도록 항상 닫힌 상태로 초기화한다.
  isTocPanelOpen = false;
  _applyTocPanelState(container, false);
  _debugToc('render-end-reset-closed');

  syncEpubTocVisibility();
}

export function jumpToTxtTocChapter({
  chapterIdx,
  anchor,
  options,
  chunkCount,
  txtChunks,
  cancelPendingRestore,
  setCurrentChunkIdx,
  onActiveChapterChange,
  getScrollMode,
  getScrollWrapper,
  renderCurrentChunk,
  saveProgress,
  activeBookId,
}) {
  if (chapterIdx < 0 || chapterIdx >= chunkCount) return;

  if (typeof cancelPendingRestore === 'function') {
    cancelPendingRestore();
  }

  const findAnchorInElement = (rootEl, anchorId) => {
    if (!rootEl || !anchorId) return null;
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return rootEl.querySelector(`#${window.CSS.escape(anchorId)}`);
    }
    const safeAnchor = String(anchorId).replace(/"/g, '\\"');
    return rootEl.querySelector(`[id="${safeAnchor}"]`);
  };

  const container = document.getElementById('epub-toc-container');
  isTocPanelOpen = false;
  _applyTocPanelState(container, false);
  _debugToc('jump-chapter-close-toc', { chapterIdx, hasAnchor: !!anchor });

  setCurrentChunkIdx(chapterIdx);
  if (typeof onActiveChapterChange === 'function') {
    onActiveChapterChange(chapterIdx);
  }

  const scrollMode = getScrollMode();
  const isPageMode = scrollMode !== 'scroll';
  const preferChapterStart = !!(options && options.preferChapterStart);
  const overlayMenu = document.getElementById('comic-overlay-menu');
  const scrollWrapper = getScrollWrapper();

  console.log(`[EPUB-TOC-Jump] 챕터 점프 시도 - chapterIdx=${chapterIdx}, isLoaded=${txtChunks && txtChunks[chapterIdx] !== null}`);
  // 목차 클릭한 챕터가 미로드 상태(null)인 경우 즉시 fetch 후 렌더링
  if (state.currentViewerFormat === 'epub' && Array.isArray(txtChunks) && txtChunks[chapterIdx] === null) {
    console.log(`[EPUB-TOC-Jump] 챕터 ${chapterIdx} 미로드 상태(null) -> 비동기 fetch 요청`);
    fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${activeBookId}&chapter_idx=${chapterIdx}`)
      .then(res => res.json())
      .then(data => {
        const content = data.content || '<p>내용이 없습니다.</p>';
        txtChunks[chapterIdx] = content;

        const contentArea = document.getElementById('txt-content-area');
        if (contentArea) {
          const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${chapterIdx}"]`);
          console.log(`[EPUB-TOC-Jump] 챕터 ${chapterIdx} fetch 완료. chunkEl 발견: ${!!chunkEl}`);
          if (chunkEl) {
            chunkEl.innerHTML = content;
          }
        }

        jumpToTxtTocChapter({
          chapterIdx,
          anchor,
          options,
          chunkCount,
          txtChunks,
          cancelPendingRestore,
          setCurrentChunkIdx,
          onActiveChapterChange,
          getScrollMode,
          getScrollWrapper,
          renderCurrentChunk,
          saveProgress,
          activeBookId
        });
      })
      .catch(err => {
        console.error('[EPUB-TOC-Jump] Failed to fetch chapter:', err);
      });
    return;
  }

  let selectedChunkEl = null;
  if (scrollMode === 'scroll') {
    if (overlayMenu) {
      overlayMenu.dataset.skipInnerScrollRestore = 'true';
    }
    if (scrollWrapper) {
      const targetChunk = scrollWrapper.querySelector(`.txt-scroll-chunk[data-idx="${chapterIdx}"]`);
      selectedChunkEl = targetChunk || null;
      if (targetChunk) {
        const top = Math.max(0, targetChunk.offsetTop);
        scrollWrapper.scrollTo({ top, behavior: 'auto' });
      } else {
        const safeChunkCount = Math.max(1, chunkCount);
        const ratio = chapterIdx / safeChunkCount;
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
      }
      
      // TOC 점프 완료 후 점프한 챕터 주변(전후 10개 챕터) null 챕터 즉시 백그라운드 프리패치
      const neighbors = [];
      for (let offset = -10; offset <= 10; offset++) {
        if (offset !== 0) neighbors.push(chapterIdx + offset);
      }
      const validNeighbors = neighbors.filter(i => i >= 0 && i < chunkCount);
      validNeighbors.forEach(fIdx => {
        if (Array.isArray(txtChunks) && txtChunks[fIdx] === null) {
          txtChunks[fIdx] = 'LOADING_PENDING';
          fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${activeBookId}&chapter_idx=${fIdx}`)
            .then(r => r.json())
            .then(d => {
              const content = (d && d.content) ? d.content : '<p>내용이 없습니다.</p>';
              txtChunks[fIdx] = content;
              const contentArea = document.getElementById('txt-content-area');
              if (contentArea) {
                const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${fIdx}"]`);
                if (chunkEl) chunkEl.innerHTML = content;
              }
            })
            .catch(() => {
              txtChunks[fIdx] = null;
            });
        }
      });

      // 스크롤 이벤트 수동 트리거
      if (window.dispatchEvent) {
        scrollWrapper.dispatchEvent(new Event('scroll'));
      }
    }
  } else {
    renderCurrentChunk(true);
    if (scrollWrapper) {
      scrollWrapper.scrollLeft = 0;
      scrollWrapper.scrollTop = 0;
    }
  }

  saveProgress(activeBookId, chapterIdx, chunkCount);

  if (anchor && !preferChapterStart) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
      let targetEl = null;
      if (selectedChunkEl) {
        targetEl = findAnchorInElement(selectedChunkEl, anchor);
      }
      if (!targetEl) {
        targetEl = document.getElementById(anchor);
      }
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'auto', block: 'start', inline: 'start' });
      } else if (isPageMode) {
        // Fallback: ensure selected chapter is visible even if anchor id is missing.
        if (scrollWrapper) {
          scrollWrapper.scrollTo({ left: 0, top: 0, behavior: 'auto' });
        }
      }
      });
    });
  }
}

