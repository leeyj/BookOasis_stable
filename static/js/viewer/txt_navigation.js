export function prevTxtPageAction(ctx) {
  const scrollWrapper = ctx.getScrollWrapper();
  if (!scrollWrapper) return;

  ctx.cancelPendingRestore();
  const scrollMode = ctx.getScrollMode();

  if (scrollMode === 'page') {
    // 챕터 경계를 넘는 전환(위 분기)은 기존에 이 가드를 전혀 쓰지 않았다.
    // 짧은 챕터(스크롤 폭이 좁아 maxScrollLeft가 거의 0)에 진입한 직후
    // 빠르게 다시 탭하면, 아직 innerHTML/scrollLeft 리셋이 끝나기 전(20ms
    // 타이머 대기 중) 상태로 재진입해 옛 scrollLeft 값을 새 챕터의(짧은)
    // scrollWidth 기준으로 판정 → 챕터를 건너뛰거나 같은 내용이 반복
    // 표시되는 원인이었다. 페이지 모드 전환 전체를 이 가드로 감싼다.
    if (ctx.getTxtPageSnapInProgress && ctx.getTxtPageSnapInProgress()) return;
    ctx.setTxtPageSnapInProgress(true);
    ctx.snapTxtPageScrollLeft(scrollWrapper);
    if (scrollWrapper.scrollLeft <= 10) {
      if (ctx.getCurrentChunkIdx() > 0) {
        ctx.setCurrentChunkIdx(ctx.getCurrentChunkIdx() - 1);
        scrollWrapper.style.scrollBehavior = 'auto';
        ctx.renderCurrentChunk();

        // 이미지가 많은 챕터는 20ms 안에 로딩/레이아웃이 끝나지 않을 수 있다.
        // 그 시점의 scrollWidth로 끝 페이지를 잡으면, 나중에 이미지이 마저
        // 로드되며 실제 콘텐츠가 더 넓어져도 스크롤 위치는 이미 고정되어
        // 진짜 마지막 페이지보다 훨씬 앞쪽에 멈추게 된다(이미지 로드 전 폭 기준).
        let chapterEndJumpDone = false;
        const finishJumpToChapterEnd = () => {
          if (chapterEndJumpDone) return;
          chapterEndJumpDone = true;
          scrollWrapper.scrollLeft = scrollWrapper.scrollWidth;
          scrollWrapper.style.scrollBehavior = '';
          ctx.saveDetailPosition();
          ctx.setTxtPageSnapInProgress(false);
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
      } else {
        ctx.setTxtPageSnapInProgress(false);
      }
    } else {
      const pageStepWidth = ctx.getTxtPageAdvanceWidth(scrollWrapper);
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = Math.max(0, (currentPageIdx - 1) * pageStepWidth);
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
    if (ctx.getTxtPageSnapInProgress && ctx.getTxtPageSnapInProgress()) return;
    ctx.setTxtPageSnapInProgress(true);
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
          ctx.setTxtPageSnapInProgress(false);
        }, 80);
      } else {
        ctx.setTxtPageSnapInProgress(false);
        ctx.handleNextEpisode();
      }
    } else {
      const currentPageIdx = Math.round(scrollWrapper.scrollLeft / pageStepWidth);
      const targetScrollLeft = Math.min(maxScrollLeft, (currentPageIdx + 1) * pageStepWidth);
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
