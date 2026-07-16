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

        setTimeout(() => {
          scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
        }, 20);

        setTimeout(() => {
          scrollWrapper.style.scrollBehavior = '';
          ctx.saveDetailPosition();
        }, 80);
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
    const maxScrollLeft = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
    if (scrollWrapper.scrollLeft + 10 >= maxScrollLeft) {
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
      const pageStepWidth = ctx.getTxtPageAdvanceWidth(scrollWrapper);
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = (currentPageIdx + 1) * pageStepWidth;
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
  if (ctx.getChunkCount() > 0 && ctx.getCurrentChunkIdx() !== 0) {
    ctx.setCurrentChunkIdx(0);
    ctx.setTxtScrollPreloadTriggered(false);
    ctx.setTxtScrollNextEpisodeTriggered(false);
    ctx.renderCurrentChunk();
    const scrollWrapper = ctx.getScrollWrapper();
    if (scrollWrapper) {
      scrollWrapper.scrollTop = 0;
      scrollWrapper.scrollLeft = 0;
    }
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
