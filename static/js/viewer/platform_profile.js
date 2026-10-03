// platform_profile.js - centralized platform/capability profile for viewer runtime

function getUserAgentText() {
  return String(navigator.userAgent || navigator.vendor || window.opera || '').toLowerCase();
}

function getBasePlatformFlags() {
  const ua = getUserAgentText();
  const isAndroid = /android/i.test(ua);
  const isIOS = /iphone|ipad|ipod/i.test(ua);
  const isMobileUA = isAndroid || isIOS || /mobile|tablet/i.test(ua);
  return { ua, isAndroid, isIOS, isMobileUA };
}

export function getViewerPlatformProfile() {
  const base = getBasePlatformFlags();
  const hasTouch = (navigator.maxTouchPoints || 0) > 0 || 'ontouchstart' in window;
  const isNarrowViewport = window.innerWidth <= 1024;
  const coarsePointer = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  const narrowMatch = !!(window.matchMedia && window.matchMedia('(max-width: 1024px)').matches);
  const hasTouchPoints = (navigator.maxTouchPoints || 0) > 0;

  return {
    ...base,
    hasTouch,
    isNarrowViewport,
    coarsePointer,
    narrowMatch,
    hasTouchPoints,
    isLikelyMobileContext: !!(narrowMatch && (coarsePointer || hasTouchPoints)),
    isMobileDevice: !!(base.isMobileUA || (hasTouch && isNarrowViewport)),
  };
}

export function shouldUseAndroidHotspotTouchFallback(profile = getViewerPlatformProfile()) {
  return !!(profile.isAndroid && profile.hasTouch);
}

// 기기 판별 대신 기능 지원으로 판단 - Windows 태블릿은 데스크톱 UA라 모바일로 안 잡히는데 F11도 누르기 어렵다.
// (iPhone Safari처럼 요소 전체화면을 지원하지 않으면 숨김)
export function shouldShowFullscreenButton() {
  return !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
}

export function shouldAutoFullscreenForFormat(format, profile = getViewerPlatformProfile()) {
  if (!profile.isLikelyMobileContext) return false;
  const fmt = String(format || '').toLowerCase();
  // Keep EPUB/TXT out of auto-fullscreen because they are sensitive to relayout on fullscreen exit.
  return ['zip', 'cbz', 'imgdir', 'pdf'].includes(fmt);
}
