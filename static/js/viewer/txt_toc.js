import { state } from '../state.js';
import { viewerStorage } from './storage.js';
import { getTxtPageMaxScroll, snapTxtPageScrollLeft } from './txt_page_utils.js';

let overlayVisibilityListenerBound = false;
let tocEntryRefs = [];
let activeTocIdx = -1;
let isTocPanelOpen = false;
let activeTocTab = 'toc';
let bookmarksCache = [];
let bookmarksLoadedForBookId = null;
let currentOnJumpToChapter = null;
let lastKnownChunkIdx = 0;

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

  // 패널이 열려 있는 동안에는 토글 버튼이 원래 자리(패널 안쪽 상단)에 그대로 떠 있으면
  // 목차/북마크 리스트 내용(특히 오른쪽 정렬된 삭제 아이콘)을 가린다. 패널 폭(300px)만큼
  // 왼쪽으로 밀어 패널 바깥에 두면 겹치지 않으면서도 여전히 눌러서 닫을 수 있다.
  const btn = document.getElementById('epub-toc-btn');
  if (btn) {
    btn.style.right = shouldOpen
      ? 'calc(320px + env(safe-area-inset-right, 0px))'
      : 'calc(20px + env(safe-area-inset-right, 0px))';
  }

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
  // 목차(TOC) 항목 하나가 실제로는 여러 개의 하위 청크(스파인 파일)를 아우르는 경우가
  // 많아(예: "1장" 헤딩 하나가 청크 7~15를 모두 커버), TOC에서 역산한 activeTocIdx의
  // chapterIdx는 "가장 가까운 헤딩"일 뿐 실제 렌더링 중인 청크와 다를 수 있다. 북마크는
  // 반드시 이 함수가 매번 인자로 받는 진짜 청크 인덱스를 써야 한다 — TOC 역산값을 쓰면
  // 서로 다른 실제 청크가 같은 라벨로 저장되어 복원 시 엉뚱한(대개 훨씬 짧은) 청크로
  // 점프하는 버그가 생긴다.
  const resolvedChunkIdx = Number.isFinite(Number(chapterIdx)) ? Number(chapterIdx) : lastKnownChunkIdx;
  lastKnownChunkIdx = resolvedChunkIdx;

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
  const format = (state.currentViewerFormat || '').toLowerCase();
  // TXT는 실제 목차가 없지만 북마크 탭은 여전히 필요하므로 패널 자체는 EPUB과 동일하게 노출한다.
  const shouldShow = (format === 'epub' || format === 'txt') && isOverlayOpen;

  if (btn) {
    btn.style.display = shouldShow ? 'flex' : 'none';
  }

  if (!shouldShow) {
    isTocPanelOpen = false;
  }
  _applyTocPanelState(container, shouldShow);
  _debugToc('sync-visibility', {
    isOverlayOpen,
    format,
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
  currentOnJumpToChapter = onJumpToChapter;
  const currentFormat = (state.currentViewerFormat || '').toLowerCase();
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

  const tabsEl = document.createElement('div');
  tabsEl.style.cssText = 'display:flex; gap:6px; margin-bottom:16px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;';

  const makeTabBtn = (key, iconClass, label) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.tocTab = key;
    b.style.cssText = `
      flex: 1; display:flex; align-items:center; justify-content:center; gap:6px;
      background: transparent; border: none; border-radius: 6px; padding: 8px 6px;
      color: inherit; opacity: 0.65; cursor: pointer; font-size: 0.85rem; font-weight: 600;
      transition: background 0.2s, opacity 0.2s;
    `;
    b.innerHTML = `<i class="${iconClass}"></i><span>${label}</span>`;
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      setActiveTocTab(key);
    });
    return b;
  };
  const tocTabBtn = makeTabBtn('toc', 'fas fa-list', '목차');
  const bookmarkTabBtn = makeTabBtn('bookmarks', 'fas fa-bookmark', '북마크');
  // TXT는 실제 목차가 없다 — chunkText()로 임의 분할한 구간을 "N장"으로 나열하면
  // 사용자에게 진짜 챕터처럼 오인되어 혼란만 준다. TXT에서는 목차 탭 자체를 숨기고
  // 북마크 탭만 노출한다(내부적으로는 여전히 같은 구간 단위를 위치 추적에 사용).
  if (currentFormat !== 'txt') {
    tabsEl.appendChild(tocTabBtn);
  }
  tabsEl.appendChild(bookmarkTabBtn);

  const tocPanelEl = document.createElement('div');
  tocPanelEl.id = 'epub-toc-tab-toc';

  const bookmarkPanelEl = document.createElement('div');
  bookmarkPanelEl.id = 'epub-toc-tab-bookmarks';
  bookmarkPanelEl.style.display = 'none';

  function setActiveTocTab(key) {
    activeTocTab = key;
    tocPanelEl.style.display = key === 'toc' ? 'block' : 'none';
    bookmarkPanelEl.style.display = key === 'bookmarks' ? 'block' : 'none';
    [tocTabBtn, bookmarkTabBtn].forEach((b) => {
      const isActive = b.dataset.tocTab === key;
      b.style.opacity = isActive ? '1' : '0.65';
      b.style.background = isActive ? 'rgba(168, 85, 247, 0.18)' : 'transparent';
    });
    if (key === 'bookmarks') {
      fetchAndRenderBookmarks();
    }
  }

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
    // TXT는 실제 챕터가 아니라 chunkText()의 임의 분할 구간이므로 "N장"이 아니라
    // "책 위치 N"으로 표기한다 (EPUB에 목차가 없는 경우엔 그래도 진짜 스파인 챕터이므로
    // 기존 chapter_fallback 표기를 유지).
    const fallbackKey = currentFormat === 'txt' ? 'viewer.txt_position_fallback' : 'viewer.chapter_fallback';
    const fallbackDefault = currentFormat === 'txt' ? (n) => `책 위치 ${n}` : (n) => `${n}장`;
    txtChunks.forEach((_, idx) => {
      const fallbackTitle = (window.i18n && typeof window.i18n.t === 'function')
        ? window.i18n.t(fallbackKey, { num: idx + 1 })
        : fallbackDefault(idx + 1);
      ul.appendChild(buildItem(fallbackTitle, idx, '', 0));
    });
  }

  tocPanelEl.appendChild(ul);
  bookmarkPanelEl.appendChild(_buildBookmarkEmptyState());

  container.innerHTML = '';
  container.appendChild(tabsEl);
  container.appendChild(tocPanelEl);
  container.appendChild(bookmarkPanelEl);

  // EPUB 새 렌더(새 책)에서는 이전 탭/북마크 캐시 및 현재 청크 추적 상태가 남지 않도록 초기화한다.
  bookmarksCache = [];
  bookmarksLoadedForBookId = null;
  lastKnownChunkIdx = 0;
  setActiveTocTab(currentFormat === 'txt' ? 'bookmarks' : 'toc');

  // EPUB 새 렌더 시 이전 열림 상태가 남지 않도록 항상 닫힌 상태로 초기화한다.
  isTocPanelOpen = false;
  _applyTocPanelState(container, false);
  _debugToc('render-end-reset-closed');

  syncEpubTocVisibility();
}

function _buildBookmarkEmptyState() {
  const empty = document.createElement('p');
  empty.className = 'epub-bookmark-empty';
  empty.style.cssText = 'opacity:0.6; font-size:0.85rem; text-align:center; margin-top:24px;';
  empty.textContent = '저장된 북마크가 없습니다.';
  return empty;
}

function _formatBookmarkLabel(bookmark) {
  const label = (bookmark && bookmark.label) ? String(bookmark.label).trim() : '';
  if (label) return label;
  const idx = Number(bookmark && bookmark.chapter_idx);
  const isTxt = bookmark && bookmark.format === 'txt';
  const key = isTxt ? 'viewer.txt_position_fallback' : 'viewer.chapter_fallback';
  return (window.i18n && typeof window.i18n.t === 'function')
    ? window.i18n.t(key, { num: idx + 1 })
    : (isTxt ? `책 위치 ${idx + 1}` : `${idx + 1}장`);
}

async function fetchAndRenderBookmarks() {
  const bookmarkPanelEl = document.getElementById('epub-toc-tab-bookmarks');
  if (!bookmarkPanelEl) return;
  const bookId = state.activeBookId;
  const dbType = state.currentLibraryType;
  if (!bookId) return;

  if (bookmarksLoadedForBookId !== bookId) {
    try {
      const res = await fetch(`/api/v1/books/${bookId}/bookmarks?db_type=${dbType}`);
      const data = await res.json();
      bookmarksCache = (data && data.success && Array.isArray(data.bookmarks)) ? data.bookmarks : [];
      bookmarksLoadedForBookId = bookId;
    } catch (e) {
      console.error('[Bookmark] 목록 조회 실패:', e);
      bookmarksCache = [];
    }
  }

  _renderBookmarkListInto(bookmarkPanelEl, bookId, dbType);
}

function _renderBookmarkListInto(bookmarkPanelEl, bookId, dbType) {
  bookmarkPanelEl.innerHTML = '';

  if (!bookmarksCache.length) {
    bookmarkPanelEl.appendChild(_buildBookmarkEmptyState());
    return;
  }

  const ul = document.createElement('ul');
  ul.style.cssText = 'list-style:none; padding:0; margin:0; font-size:0.95rem;';

  bookmarksCache.forEach((bookmark) => {
    const li = document.createElement('li');
    li.style.cssText = 'display:flex; align-items:center; gap:8px; margin-bottom:12px; line-height:1.4;';

    const a = document.createElement('a');
    a.href = '#';
    a.style.cssText = 'flex:1; color:inherit; text-decoration:none; opacity:0.85; transition:opacity 0.2s;';
    a.textContent = _formatBookmarkLabel(bookmark);
    a.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const jumpOptions = {
        preferChapterStart: true,
        percent: Number.isFinite(Number(bookmark.percent)) ? Number(bookmark.percent) : 0,
      };
      if (typeof currentOnJumpToChapter === 'function') {
        currentOnJumpToChapter(Number(bookmark.chapter_idx), '', jumpOptions);
      }
    });

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.title = '북마크 삭제';
    delBtn.innerHTML = '<i class="fas fa-trash-can"></i>';
    delBtn.style.cssText = 'background:transparent; border:none; color:inherit; opacity:0.55; cursor:pointer; padding:4px; font-size:0.85rem;';
    delBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const res = await fetch(`/api/v1/bookmarks/${bookmark.id}?db_type=${dbType}`, { method: 'DELETE' });
        const data = await res.json();
        if (data && data.success) {
          bookmarksCache = bookmarksCache.filter((b) => Number(b.id) !== Number(bookmark.id));
          _renderBookmarkListInto(bookmarkPanelEl, bookId, dbType);
          if (typeof window.showToast === 'function') window.showToast('북마크가 삭제되었습니다.', 'success');
        } else if (typeof window.showToast === 'function') {
          window.showToast((data && data.error) || '북마크 삭제에 실패했습니다.', 'error');
        }
      } catch (err) {
        console.error('[Bookmark] 삭제 실패:', err);
      }
    });

    li.appendChild(a);
    li.appendChild(delBtn);
    ul.appendChild(li);
  });

  bookmarkPanelEl.appendChild(ul);
}

function _captureCurrentChapterPercent(chapterIdx) {
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!scrollWrapper) return 0;
  const scrollMode = viewerStorage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'scroll') {
    const contentArea = document.getElementById('txt-content-area');
    const chunkEl = contentArea && contentArea.querySelector(`.txt-scroll-chunk[data-idx="${chapterIdx}"]`);
    if (!chunkEl || !chunkEl.clientHeight) return 0;
    const within = scrollWrapper.scrollTop - chunkEl.offsetTop;
    return Math.max(0, Math.min(100, Math.round((within / chunkEl.clientHeight) * 100)));
  }

  const maxScroll = getTxtPageMaxScroll(scrollWrapper);
  if (!maxScroll) return 0;
  return Math.max(0, Math.min(100, Math.round((scrollWrapper.scrollLeft / maxScroll) * 100)));
}

function _waitForChapterImagesSettled(chapterIdx) {
  return new Promise((resolve) => {
    const contentArea = document.getElementById('txt-content-area');
    const scrollMode = viewerStorage.getItem('viewer_scroll_mode') || 'page';
    let scopeEl = contentArea;
    if (scrollMode === 'scroll' && contentArea) {
      scopeEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${chapterIdx}"]`) || contentArea;
    }
    if (!scopeEl) {
      resolve();
      return;
    }
    const pending = Array.from(scopeEl.querySelectorAll('img')).filter((img) => !img.complete);
    if (!pending.length) {
      resolve();
      return;
    }
    let settled = false;
    let remaining = pending.length;
    const done = () => {
      if (settled) return;
      remaining -= 1;
      if (remaining <= 0) {
        settled = true;
        resolve();
      }
    };
    pending.forEach((img) => {
      img.addEventListener('load', done, { once: true });
      img.addEventListener('error', done, { once: true });
    });
    setTimeout(() => {
      if (!settled) {
        settled = true;
        resolve();
      }
    }, 3000);
  });
}

export async function addBookmarkAtCurrentPosition() {
  const format = (state.currentViewerFormat || '').toLowerCase();
  if (format !== 'epub' && format !== 'txt') {
    if (typeof window.showToast === 'function') window.showToast('이 뷰어에서는 북마크를 지원하지 않습니다.', 'error');
    return;
  }
  if (activeTocIdx < 0 || activeTocIdx >= tocEntryRefs.length) {
    if (typeof window.showToast === 'function') window.showToast('현재 위치를 확인할 수 없습니다.', 'error');
    return;
  }

  const ref = tocEntryRefs[activeTocIdx];
  // 실제 저장/복원에는 TOC에서 역산한 ref.chapterIdx(가장 가까운 헤딩)가 아니라, 현재
  // 렌더링 중인 진짜 청크 인덱스(lastKnownChunkIdx)를 써야 한다 — 하나의 TOC 헤딩이
  // 여러 청크를 아우르는 경우 라벨(ref.chapterIdx)과 실제 위치가 어긋난다.
  const chapterIdx = lastKnownChunkIdx;
  const label = (ref.anchorEl && ref.anchorEl.textContent) ? ref.anchorEl.textContent.trim() : '';
  await _waitForChapterImagesSettled(chapterIdx);
  // 이미지 settle 이후에도 컬럼 레이아웃이 다음 프레임에야 최종 반영되므로 동일하게 2중 rAF로 대기.
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const percent = _captureCurrentChapterPercent(chapterIdx);
  const bookId = state.activeBookId;
  const dbType = state.currentLibraryType;

  try {
    const res = await fetch(`/api/v1/books/${bookId}/bookmarks?db_type=${dbType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, chapter_idx: chapterIdx, percent, label }),
    });
    const data = await res.json();
    if (data && data.success) {
      bookmarksCache.push({ id: data.bookmark_id, book_id: bookId, format, chapter_idx: chapterIdx, percent, label });
      bookmarksLoadedForBookId = bookId;
      if (activeTocTab === 'bookmarks') {
        const bookmarkPanelEl = document.getElementById('epub-toc-tab-bookmarks');
        if (bookmarkPanelEl) _renderBookmarkListInto(bookmarkPanelEl, bookId, dbType);
      }
      if (typeof window.showToast === 'function') window.showToast('북마크가 추가되었습니다.', 'success');
    } else if (typeof window.showToast === 'function') {
      window.showToast((data && data.error) || '북마크 추가에 실패했습니다.', 'error');
    }
  } catch (e) {
    console.error('[Bookmark] 추가 실패:', e);
    if (typeof window.showToast === 'function') window.showToast('북마크 추가에 실패했습니다.', 'error');
  }
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
  const restorePercent = (options && Number.isFinite(Number(options.percent)))
    ? Math.max(0, Math.min(100, Number(options.percent)))
    : null;
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
        const chapterTop = Math.max(0, targetChunk.offsetTop);
        const top = restorePercent !== null
          ? chapterTop + (restorePercent / 100) * targetChunk.clientHeight
          : chapterTop;
        scrollWrapper.scrollTo({ top, behavior: 'auto' });
      } else {
        const safeChunkCount = Math.max(1, chunkCount);
        const ratio = chapterIdx / safeChunkCount;
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
      }
      
      // TOC 점프 완료 후 점프한 챕터 주변(전후 10개 챕터) null 챕터 즉시 백그라운드 프리패치.
      // epub_loader.js의 requestEpubChaptersBatch를 재사용해 개별 요청 대신 배치 1회로 묶는다
      // (동적 import: epub_loader.js가 이 모듈을 정적으로 import하고 있어 순환 import를 피함).
      if (Array.isArray(txtChunks)) {
        const neighbors = [];
        for (let offset = -10; offset <= 10; offset++) {
          if (offset !== 0) neighbors.push(chapterIdx + offset);
        }
        const validNeighbors = neighbors.filter(i => i >= 0 && i < chunkCount);
        import('./epub_loader.js').then(m => m.requestEpubChaptersBatch(txtChunks, validNeighbors));
      }

      // 스크롤 이벤트 수동 트리거
      if (window.dispatchEvent) {
        scrollWrapper.dispatchEvent(new Event('scroll'));
      }
    }
  } else {
    const applyPagePercentRestore = () => {
      if (restorePercent === null || !scrollWrapper) return;
      // 2중 rAF로 이 콜백 프레임 자체의 레이아웃(컬럼 폭 재계산)이 완전히 반영된
      // 뒤에 스크롤을 적용한다 — onSettled가 이미지 로드/에러/3초 타임아웃 이후에
      // 불려도, applyTxtTwoPageTrailingSpacer가 막 갱신한 DOM의 최종 scrollWidth는
      // 다음 프레임에야 안정적으로 읽힌다.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const maxScroll = getTxtPageMaxScroll(scrollWrapper);
          if (maxScroll > 0) {
            scrollWrapper.scrollLeft = Math.round((restorePercent / 100) * maxScroll);
            snapTxtPageScrollLeft(scrollWrapper);
          }
        });
      });
    };

    renderCurrentChunk(true, applyPagePercentRestore);
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

