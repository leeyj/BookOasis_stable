export async function activateRenditionPageMode({
  renderArea,
  ratio,
  themeSettings,
  book,
  getViewportSize,
  getEpubPageStep,
  getEffectivePageStep,
  syncPageStepUI,
  currentRendition,
  destroyRendition,
  bindRenditionInteractionHandlers,
  getScrollMode,
  goBackward,
  goForward,
  toggleOverlay,
  ensureLocations,
  locationsChars,
  applyRenditionTheme,
  safeRenditionDisplay,
  currentLocationCfi,
  currentLocationHref,
  setCurrentLocation,
  setRenditionAtEnd,
  updateProgressPercent,
  isRunCurrent
}) {
  if (!renderArea || !renderArea.isConnected) return currentRendition;
  if (!isRunCurrent()) return currentRendition;

  const { theme, fontCSS, fontSize, lineHeight, paragraphSpacing } = themeSettings;
  const { width, height } = getViewportSize(renderArea);
  const pageStep = getEffectivePageStep(width, getEpubPageStep());
  const forcedSinglePage = pageStep === 1 && getEpubPageStep() === 2;
  syncPageStepUI(pageStep, forcedSinglePage);

  renderArea.innerHTML = '';
  const host = document.createElement('div');
  host.id = 'epub-rendition-host';
  host.style.width = '100%';
  host.style.height = '100%';
  host.style.background = theme.background;
  renderArea.appendChild(host);

  if (currentRendition) {
    await destroyRendition();
  }

  if (!renderArea || !renderArea.isConnected) return null;
  if (!isRunCurrent()) return null;

  const rendition = book.renderTo(host, {
    width,
    height,
    flow: 'paginated',
    manager: 'default',
    spread: pageStep === 2 ? 'always' : 'none',
    minSpreadWidth: pageStep === 2 ? 0 : 99999
  });

  rendition.hooks.content.register(function(contents) {
    const customFonts = window.customFonts || [];
    let styleContent = '';
    customFonts.forEach(f => {
      const fontFaceName = `CustomFont_${f.name.replace(/\s+/g, '_')}`;
      styleContent += `@font-face { font-family: '${fontFaceName}'; src: url("${f.url}"); }\n`;
    });
    if (styleContent) {
      const style = contents.document.createElement('style');
      style.innerHTML = styleContent;
      contents.document.head.appendChild(style);
    }
  });

  bindRenditionInteractionHandlers({
    rendition,
    getScrollMode,
    goBackward,
    goForward,
    toggleOverlay
  });

  rendition.on('relocated', async location => {
    const cfi = location && location.start ? location.start.cfi : null;
    const href = location && location.start ? location.start.href : null;
    const index = (location && location.start && Number.isInteger(location.start.index)) ? location.start.index : null;
    setCurrentLocation({ cfi, href, index });
    setRenditionAtEnd(!!(location && location.atEnd));

    try {
      // locations가 완전히 생성되기 전까지는 강제로 0%로 초기화되는 것을 막아 기존 세션 복원율을 온존시킵니다.
      if (cfi && book.locations && book.locations.length) {
        const ratioFromCfi = book.locations.percentageFromCfi(cfi);
        if (Number.isFinite(ratioFromCfi) && ratioFromCfi >= 0) {
          updateProgressPercent(ratioFromCfi * 100);
          return;
        }
      }

      ensureLocations(book, locationsChars).then(() => {
        if (cfi && book.locations && book.locations.length) {
          const ratioFromCfi = book.locations.percentageFromCfi(cfi);
          if (Number.isFinite(ratioFromCfi) && ratioFromCfi >= 0) {
            updateProgressPercent(ratioFromCfi * 100);
          }
        }
      }).catch(() => {});
    } catch (_) {
      // ignore
    }
  });

  applyRenditionTheme(rendition, theme, fontCSS, fontSize, lineHeight, paragraphSpacing);

  try {
    await ensureLocations(book, locationsChars);
  } catch (err) {
    console.warn('[Viewer-Epub] locations generation failed:', err);
  }

  if (!isRunCurrent()) return rendition;

  if (currentLocationCfi) {
    await safeRenditionDisplay(rendition, currentLocationCfi);
  } else if (currentLocationHref) {
    await safeRenditionDisplay(rendition, currentLocationHref);
  } else if (ratio !== null && ratio !== undefined) {
    const safeRatio = Math.min(0.999, Math.max(0, ratio));
    let cfi = null;
    try {
      cfi = book.locations && book.locations.length
        ? book.locations.cfiFromPercentage(safeRatio)
        : null;
    } catch (err) {
      console.warn('[Viewer-Epub] cfiFromPercentage failed:', err);
    }
    await safeRenditionDisplay(rendition, cfi);
  } else {
    await safeRenditionDisplay(rendition, null);
  }

  return rendition;
}
