// fullscreen_controller.js - viewer fullscreen and mobile auto-fullscreen helpers

let _fullscreenSyncBound = false;

function getFullscreenElement() {
  return document.fullscreenElement || document.webkitFullscreenElement || null;
}

function getViewerModal() {
  return document.getElementById('media-viewer-modal');
}

function getFullscreenIcon() {
  return document.getElementById('fullscreen-icon');
}

export function isViewerInFullscreen() {
  return !!getFullscreenElement();
}

export function isLikelyMobileViewerContext() {
  const narrowViewport = window.matchMedia && window.matchMedia('(max-width: 1024px)').matches;
  const coarsePointer = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  const hasTouchPoints = (navigator.maxTouchPoints || 0) > 0;
  return !!(narrowViewport && (coarsePointer || hasTouchPoints));
}

export function tryAutoFullscreenOnOpen(modal = null) {
  const targetModal = modal || getViewerModal();
  if (!targetModal) return;
  if (!isLikelyMobileViewerContext()) return;
  if (isViewerInFullscreen()) return;

  const req = targetModal.requestFullscreen || targetModal.webkitRequestFullscreen;
  if (!req) return;

  try {
    const ret = req.call(targetModal, { navigationUI: 'hide' });
    if (ret && typeof ret.catch === 'function') {
      ret.catch(() => {});
    }
  } catch (e) {
    // Ignore: auto fullscreen may be blocked by browser gesture policy.
  }
}

export function exitFullscreenIfNeeded() {
  if (!isViewerInFullscreen()) return;

  if (document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  } else if (document.webkitExitFullscreen) {
    document.webkitExitFullscreen();
  }
}

export function syncViewerFullscreenState() {
  const modal = getViewerModal();
  const icon = getFullscreenIcon();
  if (!modal) return;

  if (isViewerInFullscreen()) {
    modal.classList.add('fullscreen-mode');
    if (icon) icon.className = 'fa-solid fa-compress';
  } else {
    modal.classList.remove('fullscreen-mode');
    if (icon) icon.className = 'fa-solid fa-expand';
  }
}

export function initFullscreenStateSync() {
  if (_fullscreenSyncBound) return;
  _fullscreenSyncBound = true;

  document.addEventListener('fullscreenchange', syncViewerFullscreenState);
  document.addEventListener('webkitfullscreenchange', syncViewerFullscreenState);
}

export function toggleFullscreenViewer() {
  const modal = getViewerModal();
  const icon = getFullscreenIcon();
  if (!modal) return;

  if (isViewerInFullscreen()) {
    exitFullscreenIfNeeded();
    modal.classList.remove('fullscreen-mode');
    if (icon) icon.className = 'fa-solid fa-expand';
    return;
  }

  const req = modal.requestFullscreen || modal.webkitRequestFullscreen;
  if (req) {
    try {
      const ret = req.call(modal, { navigationUI: 'hide' });
      if (ret && typeof ret.catch === 'function') {
        ret.catch(() => {
          // Fallback to CSS-only fullscreen class when API fails.
          modal.classList.add('fullscreen-mode');
          if (icon) icon.className = 'fa-solid fa-compress';
        });
      }
      modal.classList.add('fullscreen-mode');
      if (icon) icon.className = 'fa-solid fa-compress';
      return;
    } catch (e) {
      // Continue to CSS fallback below.
    }
  }

  modal.classList.add('fullscreen-mode');
  if (icon) icon.className = 'fa-solid fa-compress';
}
