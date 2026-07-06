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
      await ensureLocations(book, locationsChars);
      const ratioFromCfi = cfi ? book.locations.percentageFromCfi(cfi) : 0;
      updateProgressPercent((Number.isFinite(ratioFromCfi) ? ratioFromCfi : 0) * 100);
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

  if (ratio !== null && ratio !== undefined) {
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
  } else if (currentLocationCfi) {
    await safeRenditionDisplay(rendition, currentLocationCfi);
  } else if (currentLocationHref) {
    await safeRenditionDisplay(rendition, currentLocationHref);
  } else {
    await safeRenditionDisplay(rendition, null);
  }

  return rendition;
}
