export function applyFontFamilyToElement(element, fontKey, customFonts, loadAndApplyCustomFont) {
  if (fontKey === 'batang') {
    element.style.fontFamily = "'KoPub Batang', 'Nanum Myeongjo', serif";
  } else if (fontKey === 'gothic') {
    element.style.fontFamily = "'Nanum Gothic', 'Malgun Gothic', sans-serif";
  } else if (fontKey === 'pretendard') {
    element.style.fontFamily = "'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif";
  } else {
    const found = (customFonts || []).find(f => f.name === fontKey);
    if (found) {
      loadAndApplyCustomFont(found.name, found.url, element);
    } else {
      element.style.fontFamily = fontKey;
    }
  }
}

export function applyTxtSettingsCore(ctx) {
  const {
    options,
    container,
    scrollWrapper,
    contentArea,
    localStorage,
    getViewerSettings,
    getCurrentChunkIdx,
    setCurrentChunkIdx,
    getChunkCount,
    getActiveBookId,
    getTxtAnchorInfo,
    restoreTxtAnchorInfo,
    renderCurrentChunk,
    snapTxtPageScrollLeft,
    saveDetailPosition,
    showRestoreLoadingToast,
    setPendingRestoreTimer,
    applyFontFamily,
  } = ctx;

  const savedChunkIdx = getCurrentChunkIdx();
  const previousMode = options.previousMode || (scrollWrapper.classList.contains('scroll-mode-page') ? 'page' : 'scroll');
  console.log('[Viewer-Txt] applyTxtSettings 전환 시작 - 현재 챕터:', savedChunkIdx);

  if (scrollWrapper.__txtScrollHandler) {
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

    const padTop = parseInt(localStorage.getItem('viewer_padding_top') || '40', 10);
    const padBottom = parseInt(localStorage.getItem('viewer_padding_bottom') || '60', 10);
    const padLeft = parseInt(localStorage.getItem('viewer_padding_left') || '20', 10);
    const padRight = parseInt(localStorage.getItem('viewer_padding_right') || '20', 10);
    const parentWidth = container ? container.clientWidth : window.innerWidth;
    const targetWidth = Math.floor(parentWidth - (padLeft + padRight));

    // Page mode also needs top/bottom spacing at init time.
    // Previously this was only applied via commitViewerPadding() when closing the spacing panel.
    scrollWrapper.style.height = `calc(100vh - ${80 + padTop + padBottom}px)`;
    scrollWrapper.style.marginTop = `${padTop + 40}px`;
    scrollWrapper.style.marginBottom = '40px';
    scrollWrapper.style.marginLeft = 'auto';
    scrollWrapper.style.marginRight = 'auto';
    scrollWrapper.style.padding = '0';

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

    scrollWrapper.style.height = '100%';
    scrollWrapper.style.margin = '0';
    scrollWrapper.style.padding = '0';
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

  applyFontFamily(contentArea, fontFamily);

  setCurrentChunkIdx(savedChunkIdx);
  renderCurrentChunk(true);

  let restored = false;
  const skipSavedPositionRestore = !!options.skipSavedPositionRestore;
  const savedPosStr = localStorage.getItem(`viewer_last_pos_${getActiveBookId()}`);
  if (!skipSavedPositionRestore && !isModeSwitch && savedPosStr) {
    try {
      const pos = JSON.parse(savedPosStr);
      if (pos && pos.chunkIdx === getCurrentChunkIdx()) {
        showRestoreLoadingToast();
        const timerId = setTimeout(() => {
          if (scrollMode === 'scroll') {
            scrollWrapper.scrollTop = pos.scrollTop;
          } else {
            scrollWrapper.scrollLeft = pos.scrollLeft;
            snapTxtPageScrollLeft(scrollWrapper);
          }
          setPendingRestoreTimer(null);
          console.log(`[Viewer-Txt] 로컬 세부 위치 복원 성공 (left=${pos.scrollLeft}, top=${pos.scrollTop})`);
        }, 150);
        setPendingRestoreTimer(timerId);
        restored = true;
      }
    } catch (e) {}
  }

  if (!restored && isModeSwitch && preservedAnchor) {
    showRestoreLoadingToast();
    const timerId = setTimeout(() => {
      const ok = restoreTxtAnchorInfo(preservedAnchor);
      if (ok) {
        snapTxtPageScrollLeft(scrollWrapper);
        saveDetailPosition();
        console.log('[Viewer-Txt] 모드 전환 앵커 복원 성공');
      }
      setPendingRestoreTimer(null);
    }, 150);
    setPendingRestoreTimer(timerId);
    restored = true;
  }

  if (!restored) {
    if (scrollMode === 'scroll') {
      setTimeout(() => {
        const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${getCurrentChunkIdx()}"]`);
        if (targetChunk) {
          scrollWrapper.scrollTop = Math.max(0, targetChunk.offsetTop - 20);
          console.log(`[Viewer-Txt] 챕터 오프셋 기준으로 스크롤 정렬 완료 (scrollTop = ${scrollWrapper.scrollTop})`);
        } else {
          const ratio = getCurrentChunkIdx() / getChunkCount();
          scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
        }
      }, 150);
    } else {
      scrollWrapper.scrollLeft = 0;
      snapTxtPageScrollLeft(scrollWrapper);
    }
  }

  setTimeout(() => {
    if (scrollWrapper.__txtScrollHandler) {
      scrollWrapper.addEventListener('scroll', scrollWrapper.__txtScrollHandler, { passive: true });
    }
  }, 250);
}
