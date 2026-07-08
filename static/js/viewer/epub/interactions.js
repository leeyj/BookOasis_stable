function resolveHotZone(clientX, left, width) {
  const safeWidth = Math.max(1, width || 0);
  const ratio = (clientX - left) / safeWidth;
  if (ratio < 0.3) return 'left';
  if (ratio > 0.7) return 'right';
  return 'center';
}

function isInteractiveTarget(target) {
  return !!(target && target.closest && target.closest('a, button, input, select, textarea'));
}

export function bindRenderAreaClick({ renderArea, getScrollMode, goBackward, goForward, toggleOverlay }) {
  if (!renderArea || renderArea.dataset.epubClickBound === '1') return;

  renderArea.addEventListener('contextmenu', e => {
    if (getScrollMode() !== 'page') return;
    e.preventDefault();
    e.stopPropagation();
  }, true);

  renderArea.addEventListener('pointerdown', e => {
    if (getScrollMode() !== 'page') return;
    if (typeof e.button === 'number' && e.button === 2) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  let lastPointerHandledTs = 0;
  const handleRenderAreaTap = e => {
    if (typeof e.button === 'number' && e.button !== 0) return;

    const scrollMode = getScrollMode();
    const rect = renderArea.getBoundingClientRect();
    const zone = resolveHotZone(e.clientX, rect.left, rect.width);

    if (scrollMode === 'page') {
      // In page mode, edge taps should always navigate even when content has links.
      if (zone === 'left') {
        goBackward();
      } else if (zone === 'right') {
        goForward();
      } else if (!isInteractiveTarget(e.target) && typeof toggleOverlay === 'function') {
        toggleOverlay();
      }
      return;
    } else {
      // In scroll mode, allow center tap to toggle overlay
      if (zone === 'center' && !isInteractiveTarget(e.target) && typeof toggleOverlay === 'function') {
        toggleOverlay();
      }
    }
  };

  renderArea.addEventListener('pointerup', e => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    lastPointerHandledTs = Date.now();
    handleRenderAreaTap(e);
  }, true);

  // Capture phase helps when EPUB content scripts stop bubbling.
  renderArea.addEventListener('click', e => {
    // <a> 링크 이동으로 인한 백엔드 500 에러 차단 및 내부 스크롤 이동 연동 (Link Hijack)
    const anchor = e.target.closest('a');
    if (anchor) {
      const href = anchor.getAttribute('href');
      if (href && !href.startsWith('mailto:') && !href.startsWith('tel:')) {
        // 외부 웹링크(http://, https://)가 아닌 내부 상대 경로 링크인 경우 가로채기
        if (!/^(https?:|\/\/)/i.test(href)) {
          e.preventDefault();
          e.stopPropagation();
          console.log('[Viewer-Epub-Link] Hijacking link click:', href);

          if (href.startsWith('#')) {
            try {
              const targetEl = renderArea.querySelector(href);
              if (targetEl) {
                targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            } catch (err) {
              console.warn('[Viewer-Epub-Link] querySelector failed for ID:', href, err);
            }
          } else {
            const hashIdx = href.indexOf('#');
            const targetId = hashIdx !== -1 ? href.substring(hashIdx) : null;
            let found = false;

            if (targetId) {
              try {
                const targetEl = renderArea.querySelector(targetId);
                if (targetEl) {
                  targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  found = true;
                }
              } catch (_) {}
            }

            if (!found) {
              const cleanHref = href.split('#')[0].split('?')[0].split('/').pop();
              if (cleanHref) {
                const targetEl = renderArea.querySelector(`[data-href$="${cleanHref}"]`);
                if (targetEl) {
                  targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
              }
            }
          }
          return;
        }
      }
    }

    if (Date.now() - lastPointerHandledTs < 350) return;
    handleRenderAreaTap(e);
  }, true);

  renderArea.dataset.epubClickBound = '1';
}

export function bindRenditionInteractionHandlers({ rendition, getScrollMode, goBackward, goForward, toggleOverlay }) {
  if (!rendition || !rendition.hooks || !rendition.hooks.content) return;

  rendition.hooks.content.register(contents => {
    const doc = contents && contents.document;
    const win = contents && contents.window;
    if (!doc) return;

    let lastPointerHandledTs = 0;

    const handleContentTap = e => {
      if (typeof e.button === 'number' && e.button !== 0) return;

      const viewWidth = (win && win.innerWidth) ? win.innerWidth : window.innerWidth;
      const zone = resolveHotZone(e.clientX, 0, viewWidth);
      const scrollMode = getScrollMode();

      if (scrollMode === 'page') {
        // In page mode, edge taps should always navigate even when content has links.
        if (zone === 'left') {
          goBackward();
        } else if (zone === 'right') {
          goForward();
        } else if (!isInteractiveTarget(e.target) && typeof toggleOverlay === 'function') {
          toggleOverlay();
        }
      } else {
        // In scroll mode, allow center tap to toggle overlay
        if (zone === 'center' && !isInteractiveTarget(e.target) && typeof toggleOverlay === 'function') {
          toggleOverlay();
        }
      }
    };

    doc.addEventListener('pointerup', e => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      lastPointerHandledTs = Date.now();
      handleContentTap(e);
    }, true);

    doc.addEventListener('click', e => {
      // Avoid double-trigger when pointerup already handled this gesture.
      if (Date.now() - lastPointerHandledTs < 350) return;
      handleContentTap(e);
    }, true);

    doc.addEventListener('contextmenu', e => {
      if (getScrollMode() !== 'page') return;
      e.preventDefault();
      e.stopPropagation();
    }, true);

    doc.addEventListener('pointerdown', e => {
      if (getScrollMode() !== 'page') return;
      if (typeof e.button === 'number' && e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);

    doc.addEventListener('keydown', e => {
      if (getScrollMode() !== 'page') return;

      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        goForward();
        return;
      }

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goBackward();
      }
    });
  });
}
