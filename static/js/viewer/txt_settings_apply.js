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
  const { theme, fontSize, fontFamily, scrollMode, lineHeight } = getViewerSettings();
  const isModeSwitch = previousMode !== scrollMode;

  // ── 앵커 캡처: DOM이 아직 이전 모드 상태일 때 즉시 수행해야 정확함 ──
  // runApply() 내부(double-rAF 후)에 두면 DOM이 이미 바뀌어 위치가 틀림
  let preservedAnchor = null;
  if (isModeSwitch) {
    const rawAnchor = getTxtAnchorInfo(previousMode);
    // anchorText가 공백/특수문자만으로 구성된 경우 복원이 불가능하므로 검증
    if (rawAnchor && rawAnchor.anchorText) {
      const nonWhitespace = rawAnchor.anchorText.replace(/\s/g, '');
      if (nonWhitespace.length >= 5) {
        preservedAnchor = rawAnchor;
      }
    }
    if (container) container.style.pointerEvents = 'none';
    if (typeof showRestoreLoadingToast === 'function') {
      showRestoreLoadingToast('보기 모드 전환 중...');
    }
    console.log('[Viewer-Txt] 앵커 캡처 완료 (전환 전):', preservedAnchor);
  }

  const runApply = () => {
    console.log('[Viewer-Txt] applyTxtSettings 전환 시작 - 현재 챕터:', savedChunkIdx);

    if (scrollWrapper.__txtScrollHandler) {
      scrollWrapper.removeEventListener('scroll', scrollWrapper.__txtScrollHandler);
    }

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

      scrollWrapper.style.height = `calc(100vh - ${80 + padTop + padBottom}px)`;
      scrollWrapper.style.marginTop = `${padTop + 40}px`;
      scrollWrapper.style.marginBottom = '40px';
      scrollWrapper.style.marginLeft = 'auto';
      scrollWrapper.style.marginRight = 'auto';
      scrollWrapper.style.paddingTop = '0';
      const pageStep = localStorage.getItem('comic_page_step') || '1';
      const removeCenterGap = (localStorage.getItem('remove_2page_center_gap') === '1');
      const pageGap = pageStep === '2' ? (removeCenterGap ? 0 : 40) : 0;

      const isMobileView = (window.innerWidth <= 768);
      if (isMobileView) {
        scrollWrapper.style.paddingLeft = `${padLeft}px`;
        scrollWrapper.style.paddingRight = `${padRight}px`;
        scrollWrapper.style.maxWidth = '100%';
      } else {
        scrollWrapper.style.paddingLeft = '0';
        scrollWrapper.style.paddingRight = '0';
        if (pageStep === '2') {
          scrollWrapper.style.maxWidth = `${Math.min(targetWidth, 1600)}px`;
        } else {
          scrollWrapper.style.maxWidth = `${Math.min(targetWidth, 800)}px`;
        }
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
      scrollWrapper.style.maxWidth = '850px';
      scrollWrapper.style.marginLeft = 'auto';
      scrollWrapper.style.marginRight = 'auto';
      scrollWrapper.style.padding = '0';
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
          showRestoreLoadingToast('위치 복원 중...');
          const timerId = setTimeout(() => {
            if (scrollMode === 'scroll') {
              scrollWrapper.scrollTop = pos.scrollTop;
              // 스크롤 오프셋 복원 후 눈에 보이는 챕터 주변(null) 동적 fetch
              if (window.dispatchEvent) {
                scrollWrapper.dispatchEvent(new Event('scroll'));
              }
            } else {
              scrollWrapper.scrollLeft = pos.scrollLeft;
              snapTxtPageScrollLeft(scrollWrapper);
            }
            setPendingRestoreTimer(null);
            if (container) container.style.pointerEvents = '';
            console.log(`[Viewer-Txt] 로컬 세부 위치 복원 성공 (left=${pos.scrollLeft}, top=${pos.scrollTop})`);
          }, 150);
          setPendingRestoreTimer(timerId);
          restored = true;
        }
      } catch (e) {}
    }

    if (!restored && isModeSwitch && preservedAnchor) {
      showRestoreLoadingToast('보기 모드 전환 중...');
      const timerId = setTimeout(() => {
        const ok = restoreTxtAnchorInfo(preservedAnchor);
        if (ok) {
          snapTxtPageScrollLeft(scrollWrapper);
          saveDetailPosition();
          console.log('[Viewer-Txt] 모드 전환 앵커 1차 복원 수행 완료');
        }
        
        // ── iOS WebKit Reflow 지연 방어: 2차 래치(Latch) 재검증 ──
        setTimeout(() => {
          if (scrollMode === 'scroll') {
            const currentScrollTop = scrollWrapper ? scrollWrapper.scrollTop : 0;
            // 1차 복원이 실패했거나 offsetTop 미계산으로 scrollTop 이 0에 불과한 경우 재조정
            if (!ok || currentScrollTop === 0) {
              const reOk = restoreTxtAnchorInfo(preservedAnchor);
              if (!reOk || (scrollWrapper && scrollWrapper.scrollTop === 0)) {
                const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${getCurrentChunkIdx()}"]`);
                if (targetChunk && targetChunk.offsetTop > 0) {
                  scrollWrapper.scrollTop = Math.max(0, targetChunk.offsetTop - 20);
                  console.log(`[Viewer-Txt][iOS SafeGuard] 2차 래치로 챕터 오프셋(${targetChunk.offsetTop}) 복원완료`);
                }
              }
            }
          }
          setPendingRestoreTimer(null);
          if (container) container.style.pointerEvents = '';
        }, 120);
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
            const ratio = getCurrentChunkIdx() / Math.max(1, getChunkCount());
            scrollWrapper.scrollTop = scrollWrapper.scrollHeight * ratio;
          }
          if (container) container.style.pointerEvents = '';
        }, 150);
      } else {
        scrollWrapper.scrollLeft = 0;
        snapTxtPageScrollLeft(scrollWrapper);
        if (container) container.style.pointerEvents = '';
      }
    }

    setTimeout(() => {
      if (container) container.style.pointerEvents = '';
      if (scrollWrapper.__txtScrollHandler) {
        scrollWrapper.addEventListener('scroll', scrollWrapper.__txtScrollHandler, { passive: true });
      }
    }, 300);
  };

  if (isModeSwitch) {
    // double-rAF: 첫 번째 rAF에서 토스트가 DOM에 등록되고,
    // 두 번째 rAF에서 실제로 화면에 Paint된 뒤 무거운 DOM 작업을 시작한다.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        runApply();
      });
    });
  } else {
    runApply();
  }
}
