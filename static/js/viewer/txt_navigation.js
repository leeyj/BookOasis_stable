export function prevTxtPageAction(ctx) {
  const scrollWrapper = ctx.getScrollWrapper();
  if (!scrollWrapper) return;

  ctx.cancelPendingRestore();
  const scrollMode = ctx.getScrollMode();

  if (scrollMode === 'page') {
    ctx.snapTxtPageScrollLeft(scrollWrapper);
    if (scrollWrapper.scrollLeft <= 10) {
      if (ctx.getCurrentChunkIdx() > 0) {
        ctx.setCurrentChunkIdx(ctx.getCurrentChunkIdx() - 1);
        scrollWrapper.style.scrollBehavior = 'auto';
        ctx.renderCurrentChunk();

        // 이미지가 많은 챕터는 20ms 안에 로딩/레이아웃이 끝나지 않을 수 있다.
        // 그 시점의 scrollWidth로 끝 페이지를 잡으면, 나중에 이미지가 마저
        // 로드되며 실제 콘텐츠가 더 넓어져도 스크롤 위치는 이미 고정되어
        // 진짜 마지막 페이지보다 훨씬 앞쪽에 멈추게 된다(이미지 로드 전 폭 기준).
        let chapterEndJumpDone = false;
        const finishJumpToChapterEnd = () => {
          if (chapterEndJumpDone) return;
          chapterEndJumpDone = true;
          scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
          scrollWrapper.style.scrollBehavior = '';
          ctx.saveDetailPosition();
        };

        setTimeout(() => {
          const contentArea = ctx.getContentArea ? ctx.getContentArea() : null;
          const pendingImages = contentArea
            ? Array.from(contentArea.querySelectorAll('img')).filter(img => !img.complete)
            : [];
          if (!pendingImages.length) {
            finishJumpToChapterEnd();
            return;
          }
          let remaining = pendingImages.length;
          const onImageSettled = () => {
            remaining -= 1;
            if (remaining <= 0) finishJumpToChapterEnd();
          };
          pendingImages.forEach(img => {
            img.addEventListener('load', onImageSettled, { once: true });
            img.addEventListener('error', onImageSettled, { once: true });
          });
          // 이미지 로드가 끝내 완료 이벤트를 못 보내는 경우를 대비한 안전장치.
          setTimeout(finishJumpToChapterEnd, 3000);
        }, 20);
      }
    } else {
      const pageStepWidth = ctx.getTxtPageAdvanceWidth(scrollWrapper);
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = Math.max(0, (currentPageIdx - 1) * pageStepWidth);
      ctx.setTxtPageSnapInProgress(true);
      scrollWrapper.scrollTo({ left: targetScrollLeft, behavior: 'auto' });
      setTimeout(() => {
        ctx.snapTxtPageScrollLeft(scrollWrapper);
        ctx.logActiveViewportText();
        ctx.saveDetailPosition();
        ctx.setTxtPageSnapInProgress(false);
      }, 150);
    }
    return;
  }

  if (scrollWrapper.scrollTop <= 10) {
    if (ctx.getCurrentChunkIdx() > 0) {
      ctx.setCurrentChunkIdx(ctx.getCurrentChunkIdx() - 1);
      scrollWrapper.style.scrollBehavior = 'auto';
      ctx.renderCurrentChunk();

      setTimeout(() => {
        scrollWrapper.scrollTop = scrollWrapper.scrollHeight;
      }, 20);

      setTimeout(() => {
        scrollWrapper.style.scrollBehavior = '';
        ctx.logActiveViewportText();
        ctx.saveDetailPosition();
      }, 80);
    }
  } else {
    scrollWrapper.scrollBy({ top: -scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
    setTimeout(() => {
      ctx.logActiveViewportText();
      ctx.saveDetailPosition();
    }, 350);
  }
}

export function nextTxtPageAction(ctx) {
  const scrollWrapper = ctx.getScrollWrapper();
  if (!scrollWrapper) return;

  ctx.cancelPendingRestore();
  const scrollMode = ctx.getScrollMode();

  if (scrollMode === 'page') {
    ctx.snapTxtPageScrollLeft(scrollWrapper);
    const pageStepWidth = ctx.getTxtPageAdvanceWidth(scrollWrapper);
    const maxScrollLeft = Math.max(0, scrollWrapper.scrollWidth - scrollWrapper.clientWidth);
    const snapTolerance = Math.max(30, pageStepWidth * 0.4);

    if (scrollWrapper.scrollLeft + snapTolerance >= maxScrollLeft) {
      if (ctx.getCurrentChunkIdx() < ctx.getChunkCount() - 1) {
        ctx.setCurrentChunkIdx(ctx.getCurrentChunkIdx() + 1);
        scrollWrapper.style.scrollBehavior = 'auto';
        ctx.renderCurrentChunk();

        setTimeout(() => {
          scrollWrapper.scrollLeft = 0;
          scrollWrapper.scrollTop = 0;
        }, 20);

        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          ctx.saveDetailPosition();
        }, 80);
      } else {
        ctx.handleNextEpisode();
      }
    } else {
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = Math.min(maxScrollLeft, (currentPageIdx + 1) * pageStepWidth);
      ctx.setTxtPageSnapInProgress(true);
      scrollWrapper.scrollTo({ left: targetScrollLeft, behavior: 'auto' });
      setTimeout(() => {
        ctx.snapTxtPageScrollLeft(scrollWrapper);
        ctx.logActiveViewportText();
        ctx.saveDetailPosition();
        ctx.setTxtPageSnapInProgress(false);
      }, 150);
    }
    return;
  }

  const maxScrollTop = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
  if (scrollWrapper.scrollTop + 10 >= maxScrollTop) {
    if (ctx.getCurrentChunkIdx() < ctx.getChunkCount() - 1) {
      ctx.setCurrentChunkIdx(ctx.getCurrentChunkIdx() + 1);
      scrollWrapper.style.scrollBehavior = 'auto';
      ctx.renderCurrentChunk();

      setTimeout(() => {
        scrollWrapper.scrollTop = 0;
        scrollWrapper.scrollLeft = 0;
      }, 20);

      setTimeout(() => {
        scrollWrapper.style.scrollBehavior = '';
        ctx.logActiveViewportText();
        ctx.saveDetailPosition();
      }, 80);
    } else {
      ctx.handleNextEpisode();
    }
  } else {
    scrollWrapper.scrollBy({ top: scrollWrapper.clientHeight * 0.9, behavior: 'smooth' });
    setTimeout(() => {
      ctx.logActiveViewportText();
      ctx.saveDetailPosition();
    }, 350);
  }
}

export function txtJumpToFirstPageAction(ctx) {
  ctx.cancelPendingRestore();
  const scrollWrapper = ctx.getScrollWrapper();

  if (ctx.getChunkCount() > 0 && ctx.getCurrentChunkIdx() !== 0) {
    ctx.setCurrentChunkIdx(0);
    ctx.setTxtScrollPreloadTriggered(false);
    ctx.setTxtScrollNextEpisodeTriggered(false);
    ctx.renderCurrentChunk();
  }

  // Even if already on chunk 0, reset the in-chapter scroll position.
  if (scrollWrapper) {
    scrollWrapper.scrollTop = 0;
    scrollWrapper.scrollLeft = 0;
  }
}

export function txtJumpToLastPageAction(ctx) {
  ctx.cancelPendingRestore();
  const lastIdx = Math.max(0, ctx.getChunkCount() - 1);
  if (ctx.getChunkCount() > 0 && ctx.getCurrentChunkIdx() !== lastIdx) {
    ctx.setCurrentChunkIdx(lastIdx);
    ctx.setTxtScrollPreloadTriggered(true);
    ctx.renderCurrentChunk();
    const scrollWrapper = ctx.getScrollWrapper();
    if (scrollWrapper) {
      scrollWrapper.scrollTop = 0;
      scrollWrapper.scrollLeft = 0;
    }
  }
}

export function txtSliderInputAction({ val, chunkCount }) {
  const tooltip = document.getElementById('seekbar-tooltip');
  if (tooltip) {
    tooltip.textContent = val;
    tooltip.style.display = 'block';
  }
  const pageInfo = document.getElementById('comic-overlay-page-info');
  if (pageInfo) {
    pageInfo.textContent = `${val} / ${chunkCount}`;
  }
}

export function txtSliderChangeAction(ctx, val) {
  ctx.cancelPendingRestore();
  const targetIdx = Math.max(0, Math.min(ctx.getChunkCount() - 1, val - 1));
  if (ctx.getCurrentChunkIdx() !== targetIdx) {
    ctx.setCurrentChunkIdx(targetIdx);

    const scrollMode = ctx.getScrollMode();
    const scrollWrapper = ctx.getScrollWrapper();
    if (scrollMode === 'scroll') {
      const overlayMenu = document.getElementById('comic-overlay-menu');
      if (overlayMenu) {
        overlayMenu.dataset.skipInnerScrollRestore = 'true';
      }
      if (scrollWrapper) {
        const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
        const targetPercent = targetIdx / Math.max(1, ctx.getChunkCount() - 1);
        scrollWrapper.scrollTop = maxScroll * targetPercent;
        setTimeout(ctx.saveDetailPosition, 50);
      }
    } else {
      if (scrollWrapper) {
        scrollWrapper.scrollLeft = 0;
      }
      ctx.renderCurrentChunk();
      ctx.logActiveViewportText();
      ctx.saveDetailPosition();
    }
  }
}
