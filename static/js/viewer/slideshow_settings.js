// slideshow_settings.js - 자동 넘김(슬라이드) 간격/속도 값과 저장
// 뷰어(slideshow_controller.js)와 설정 > 뷰어 탭이 같이 쓰므로 범위 검증은 여기 한 곳에만 둔다.

export const INTERVAL_KEY = 'viewer_slideshow_interval';
export const SCROLL_PX_KEY = 'viewer_slideshow_scroll_px';
// 2.8.9~3.0.3의 느림/보통/빠름 저장값 - 처음 읽을 때 px/초로 바꾼다
const LEGACY_SPEED_KEY = 'viewer_slideshow_scroll_speed';
const LEGACY_SPEED_PX = { slow: 40, normal: 80, fast: 160 };

export const INTERVAL_MIN = 2;
export const INTERVAL_MAX = 120;
export const INTERVAL_DEFAULT = 5;
export const INTERVAL_PRESETS = [5, 10, 20, 30, 60];

export const SCROLL_PX_MIN = 10;
export const SCROLL_PX_MAX = 400;
export const SCROLL_PX_DEFAULT = 60;
export const SCROLL_PX_PRESETS = [30, 60, 100, 160];

function readStorage(storage, key) {
  try { return storage ? storage.getItem(key) : null; } catch (e) { return null; }
}

function writeStorage(storage, key, value) {
  try { if (storage) storage.setItem(key, value); } catch (e) {}
}

function defaultStorage() {
  try { return globalThis.localStorage || null; } catch (e) { return null; }
}

// 범위 밖이면 가장 가까운 끝값으로, 숫자가 아니면 null
function clampInt(value, min, max) {
  const n = Math.round(Number(value));
  if (value === null || value === '' || !Number.isFinite(n)) return null;
  return Math.min(max, Math.max(min, n));
}

export function normalizeInterval(value) {
  return clampInt(value, INTERVAL_MIN, INTERVAL_MAX);
}

export function normalizeScrollPx(value) {
  return clampInt(value, SCROLL_PX_MIN, SCROLL_PX_MAX);
}

export function getIntervalSec(storage = defaultStorage()) {
  return normalizeInterval(readStorage(storage, INTERVAL_KEY)) ?? INTERVAL_DEFAULT;
}

export function getScrollPxPerSec(storage = defaultStorage()) {
  const saved = normalizeScrollPx(readStorage(storage, SCROLL_PX_KEY));
  if (saved !== null) return saved;
  const legacy = LEGACY_SPEED_PX[readStorage(storage, LEGACY_SPEED_KEY)];
  if (legacy) {
    writeStorage(storage, SCROLL_PX_KEY, String(legacy));
    return legacy;
  }
  return SCROLL_PX_DEFAULT;
}

// 저장한 값(범위 보정 후)을 돌려준다. 숫자가 아니면 저장하지 않고 null
export function saveIntervalSec(value, storage = defaultStorage()) {
  const sec = normalizeInterval(value);
  if (sec === null) return null;
  writeStorage(storage, INTERVAL_KEY, String(sec));
  return sec;
}

export function saveScrollPxPerSec(value, storage = defaultStorage()) {
  const px = normalizeScrollPx(value);
  if (px === null) return null;
  writeStorage(storage, SCROLL_PX_KEY, String(px));
  return px;
}
