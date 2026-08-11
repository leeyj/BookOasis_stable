// fullscreen_controller.js - viewer fullscreen and mobile auto-fullscreen helpers
import { getViewerPlatformProfile, shouldShowMobileFullscreenButton } from './platform_profile.js';

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
  return !!getViewerPlatformProfile().isLikelyMobileContext;
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
  if (!isViewerInFullscreen()) return Promise.resolve();

  if (document.exitFullscreen) {
    return document.exitFullscreen().catch(() => {});
  } else if (document.webkitExitFullscreen) {
    try {
      document.webkitExitFullscreen();
    } catch (e) {
      // ignore
    }
    // webkitExitFullscreen는 Promise를 반환하지 않으므로,
    // 실제 전환이 끝날 만큼 짧게 대기한 뒤 다음 단계로 넘어간다.
    return new Promise((resolve) => setTimeout(resolve, 120));
  }
  return Promise.resolve();
}

export function isMobileDevice() {
  return !!getViewerPlatformProfile().isMobileDevice;
}

export function syncViewerFullscreenState() {
  const modal = getViewerModal();
  const icon = getFullscreenIcon();
  const mobileIcon = document.getElementById('overlay-mobile-fullscreen-icon');
  const mobileLabel = document.getElementById('overlay-mobile-fullscreen-label');
  const mobileBtn = document.getElementById('btn-overlay-fullscreen-mobile');
  if (!modal) return;

  if (mobileBtn) {
    mobileBtn.style.display = shouldShowMobileFullscreenButton() ? 'inline-flex' : 'none';
  }

  const inFullscreen = isViewerInFullscreen();
  if (inFullscreen) {
    modal.classList.add('fullscreen-mode');
    if (icon) icon.className = 'fa-solid fa-compress';
    if (mobileIcon) mobileIcon.className = 'fa-solid fa-compress';
    if (mobileLabel) mobileLabel.setAttribute('data-i18n', 'viewer.exit_fullscreen');
  } else {
    modal.classList.remove('fullscreen-mode');
    if (icon) icon.className = 'fa-solid fa-expand';
    if (mobileIcon) mobileIcon.className = 'fa-solid fa-expand';
    if (mobileLabel) mobileLabel.setAttribute('data-i18n', 'viewer.fullscreen');
  }

  if (window.i18n && typeof window.i18n.translateDOM === 'function') {
    window.i18n.translateDOM(modal);
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
