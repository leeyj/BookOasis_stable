export function createNoSectionRecovery(getReadableSpineItems) {
  let lastWarnTs = 0;

  function normalizeHref(href) {
    if (!href) return '';
    return String(href).split('#')[0];
  }

  function isNoSectionFoundError(err) {
    const msg = err && err.message ? String(err.message) : '';
    return msg.toLowerCase().includes('no section found');
  }

  function warnNoSectionThrottled(prefix, err) {
    const now = Date.now();
    if (now - lastWarnTs < 2000) return;
    lastWarnTs = now;
    console.warn(prefix, err);
  }

  function hasRenderableLocation(rendition) {
    if (!rendition || typeof rendition.currentLocation !== 'function') return false;
    try {
      const loc = rendition.currentLocation();
      const start = loc && loc.start ? loc.start : null;
      if (!start) return false;
      if (start.cfi) return true;
      if (start.href) return true;
      if (Number.isInteger(start.index)) return true;
      return false;
    } catch {
      return false;
    }
  }

  async function displaySpineItemByHref(rendition, item) {
    if (!rendition || !item || !item.href) return false;
    try {
      await rendition.display(item.href);
      return true;
    } catch {
      return false;
    }
  }

  async function fallbackDisplayFromSpine(rendition, fromEnd = false) {
    const items = getReadableSpineItems();
    if (!items.length) return false;

    const ordered = fromEnd ? [...items].reverse() : items;
    for (const item of ordered) {
      const ok = await displaySpineItemByHref(rendition, item);
      if (ok) return true;
    }
    return false;
  }

  async function displayAdjacentSpine(rendition, direction) {
    const items = getReadableSpineItems();
    if (!items.length || !rendition) return false;

    const loc = rendition.currentLocation && rendition.currentLocation();
    const currentHref = normalizeHref(loc && loc.start ? loc.start.href : null);

    let currentPos = -1;
    if (currentHref) {
      currentPos = items.findIndex(item => normalizeHref(item && item.href) === currentHref);
    }

    if (currentPos < 0) {
      const currentIndex = loc && loc.start && Number.isInteger(loc.start.index) ? loc.start.index : null;
      if (currentIndex === null) return false;
      currentPos = Math.min(Math.max(0, currentIndex), items.length - 1);
    }

    if (direction === 'next') {
      for (let i = currentPos + 1; i < items.length; i += 1) {
        const ok = await displaySpineItemByHref(rendition, items[i]);
        if (ok) return true;
      }
      return false;
    }

    for (let i = currentPos - 1; i >= 0; i -= 1) {
      const ok = await displaySpineItemByHref(rendition, items[i]);
      if (ok) return true;
    }
    return false;
  }

  async function safeRenditionDisplay(rendition, target) {
    if (!rendition) return;

    try {
      if (target) {
        await rendition.display(target);
        if (hasRenderableLocation(rendition)) return;
      }
      await rendition.display();
      if (hasRenderableLocation(rendition)) return;
    } catch (err) {
      if (isNoSectionFoundError(err)) {
        warnNoSectionThrottled('[Viewer-Epub] rendition display fallback(No Section):', err);
      } else {
        console.warn('[Viewer-Epub] rendition display fallback:', err);
      }
    }

    try {
      await rendition.display();
      if (hasRenderableLocation(rendition)) return;
    } catch (err) {
      if (!isNoSectionFoundError(err)) {
        console.warn('[Viewer-Epub] rendition display(default) failed:', err);
      }
    }

    const recovered = await fallbackDisplayFromSpine(rendition, false);
    if (!recovered) {
      warnNoSectionThrottled('[Viewer-Epub] rendition could not recover from No Section Found', null);
    }
  }

  return {
    isNoSectionFoundError,
    fallbackDisplayFromSpine,
    displayAdjacentSpine,
    safeRenditionDisplay,
    warnNoSectionThrottled
  };
}
