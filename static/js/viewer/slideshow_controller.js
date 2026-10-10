// slideshow_controller.js - 만화/PDF 뷰어 슬라이드(자동 진행)
// 페이지 모드는 일정 간격으로 다음 페이지, 스크롤 모드는 일정 속도로 자동 스크롤한다.
// 권 끝에 닿으면 카운트다운 후 다음 권을 열고(전체화면 유지) 같은 방식으로 이어서 진행한다.
import { state } from '../state.js';
import { getActiveViewerInstance } from './lifecycle_controller.js';

const SUPPORTED_FORMATS = ['zip', 'cbz', 'imgdir', 'pdf'];
const INTERVAL_KEY = 'viewer_slideshow_interval';
const SPEED_KEY = 'viewer_slideshow_scroll_speed';
const INTERVAL_OPTIONS = [3, 5, 8, 10, 15, 30];
const DEFAULT_INTERVAL = 5;
const SPEED_PX_PER_SEC = { slow: 40, normal: 80, fast: 160 };
const DEFAULT_SPEED = 'normal';
// 스크롤 모드에서 바닥에 닿은 뒤 이만큼 머물러야 권 끝으로 본다 (늦게 로드되는 이미지로 길이가 늘어날 수 있음)
const SCROLL_END_HOLD_MS = 1500;
// 사용자가 직접 스크롤/터치하면 자동 스크롤을 잠깐 멈춘다
const SCROLL_USER_HOLD_MS = 2000;
const NEXT_VOLUME_COUNTDOWN_SEC = 5;
const PILL_DIM_DELAY_MS = 3000;

let running = false;
let paused = false;
let rafId = null;
let lastFrameTs = 0;
let pageDeadline = 0;
let scrollCarry = 0;
let bottomSince = 0;
let userHoldUntil = 0;
let goingToNextVolume = false;
let resumeAfterOpen = false;
let wakeLock = null;
let interactionBound = false;
let countdownTimer = null;
let pillDimTimer = null;

function t(key, params, fallback) {
  const text = window.i18n?.t?.(key, params || {});
  return (text && text !== key) ? text : fallback;
}

function toast(message, type = 'info') {
  if (typeof window.showToast === 'function') window.showToast(message, type);
}

export function isSlideshowSupportedFormat(fmt = state.currentViewerFormat) {
  return SUPPORTED_FORMATS.includes(String(fmt || '').toLowerCase());
}

export function isSlideshowRunning() {
  return running;
}

function readStorage(key) {
  try { return localStorage.getItem(key); } catch (e) { return null; }
}

function writeStorage(key, value) {
  try { localStorage.setItem(key, value); } catch (e) {}
}

function getIntervalSec() {
  const saved = parseInt(readStorage(INTERVAL_KEY), 10);
  return INTERVAL_OPTIONS.includes(saved) ? saved : DEFAULT_INTERVAL;
}

function getSpeedKey() {
  const saved = readStorage(SPEED_KEY);
  return Object.prototype.hasOwnProperty.call(SPEED_PX_PER_SEC, saved) ? saved : DEFAULT_SPEED;
}

export function setSlideshowInterval(value) {
  const sec = parseInt(value, 10);
  if (!INTERVAL_OPTIONS.includes(sec)) return;
  writeStorage(INTERVAL_KEY, String(sec));
  if (running) pageDeadline = performance.now() + sec * 1000;
  updatePill();
}

export function setSlideshowSpeed(value) {
  if (!Object.prototype.hasOwnProperty.call(SPEED_PX_PER_SEC, value)) return;
  writeStorage(SPEED_KEY, value);
  updatePill();
}

function isScrollMode() {
  return (readStorage('viewer_scroll_mode') || 'page') === 'scroll';
}

function getScrollContainer() {
  const fmt = String(state.currentViewerFormat || '').toLowerCase();
  if (fmt === 'pdf') return document.getElementById('pdf-render-area');
  return document.querySelector('#comic-viewer-container .comic-image-wrapper') || document.querySelector('.comic-image-wrapper');
}

function isElementShown(id) {
  const el = document.getElementById(id);
  return !!el && getComputedStyle(el).display !== 'none';
}

// 메뉴/다음 권 확인창이 떠 있거나 화면이 숨겨진 동안은 진행하지 않는다
function isBlocked(now) {
  if (paused || goingToNextVolume || document.hidden) return true;
  if (!isElementShown('media-viewer-modal')) return true;
  if (isElementShown('comic-overlay-menu')) return true;
  if (isElementShown('viewer-next-episode-modal')) return true;
  return now < userHoldUntil;
}

function isAtLastPage() {
  const inst = getActiveViewerInstance();
  return !!(inst && typeof inst.isAtLastPage === 'function' && inst.isAtLastPage());
}

function tick(now) {
  if (!running) return;
  rafId = requestAnimationFrame(tick);

  const dt = lastFrameTs ? Math.min(now - lastFrameTs, 100) : 0;
  lastFrameTs = now;

  if (isBlocked(now)) {
    // 멈춰 있던 동안은 넘김 간격을 다시 센다
    pageDeadline = now + getIntervalSec() * 1000;
    bottomSince = 0;
    return;
  }

  if (isScrollMode()) {
    const container = getScrollContainer();
    if (!container) return;
    const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 2;
    if (atBottom) {
      if (!bottomSince) bottomSince = now;
      if (now - bottomSince >= SCROLL_END_HOLD_MS) {
        bottomSince = 0;
        goToNextVolume();
      }
      return;
    }
    bottomSince = 0;
    // 일부 브라우저는 scrollTop의 소수점을 버리므로 1px 단위로 모아서 움직인다
    scrollCarry += SPEED_PX_PER_SEC[getSpeedKey()] * dt / 1000;
    if (scrollCarry >= 1) {
      const px = Math.floor(scrollCarry);
      scrollCarry -= px;
      container.scrollTop += px;
    }
    return;
  }

  if (now < pageDeadline) return;
  pageDeadline = now + getIntervalSec() * 1000;
  if (isAtLastPage()) {
    goToNextVolume();
    return;
  }
  const inst = getActiveViewerInstance();
  if (inst && typeof inst.nextPage === 'function') inst.nextPage();
}

function startLoop() {
  if (rafId) cancelAnimationFrame(rafId);
  lastFrameTs = 0;
  scrollCarry = 0;
  bottomSince = 0;
  pageDeadline = performance.now() + getIntervalSec() * 1000;
  rafId = requestAnimationFrame(tick);
}

function stopLoop() {
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
}

// ── 화면 꺼짐 방지 ──
async function acquireWakeLock() {
  if (!running || wakeLock || document.hidden) return;
  if (!navigator.wakeLock || typeof navigator.wakeLock.request !== 'function') return;
  try {
    wakeLock = await navigator.wakeLock.request('screen');
    wakeLock.addEventListener('release', () => { wakeLock = null; });
  } catch (e) {
    wakeLock = null;
  }
}

function releaseWakeLock() {
  if (!wakeLock) return;
  try { wakeLock.release(); } catch (e) {}
  wakeLock = null;
}

// ── 사용자 조작 감지: 수동 넘김은 간격을 다시 세고, 직접 스크롤하면 잠깐 멈춘다 ──
function onUserInteraction(event) {
  if (!running) return;
  if (event && event.isTrusted === false) return;
  if (event && event.target && typeof event.target.closest === 'function'
      && event.target.closest('#viewer-slideshow-pill, #viewer-slideshow-countdown')) {
    return;
  }
  const modal = document.getElementById('media-viewer-modal');
  if (!modal || !event || !modal.contains(event.target)) return;
  const now = performance.now();
  pageDeadline = now + getIntervalSec() * 1000;
  if (isScrollMode() && (event.type === 'wheel' || event.type === 'touchstart')) {
    userHoldUntil = now + SCROLL_USER_HOLD_MS;
  }
}

function bindInteractionTracking() {
  if (interactionBound) return;
  interactionBound = true;
  document.addEventListener('pointerdown', onUserInteraction, { capture: true, passive: true });
  document.addEventListener('touchstart', onUserInteraction, { capture: true, passive: true });
  document.addEventListener('wheel', onUserInteraction, { capture: true, passive: true });
  document.addEventListener('keydown', onUserInteraction, { capture: true });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && running) acquireWakeLock();
  });
}

// ── 실행 중 표시 (작은 컨트롤) ──
function getModal() {
  return document.getElementById('media-viewer-modal');
}

function ensurePill() {
  let pill = document.getElementById('viewer-slideshow-pill');
  if (pill) return pill;
  const modal = getModal();
  if (!modal) return null;
  pill = document.createElement('div');
  pill.id = 'viewer-slideshow-pill';
  pill.className = 'viewer-slideshow-pill';
  pill.innerHTML = `
    <button type="button" class="viewer-slideshow-pill-btn" data-slideshow="pause"><i class="fa-solid fa-pause"></i></button>
    <span class="viewer-slideshow-pill-label"></span>
    <button type="button" class="viewer-slideshow-pill-btn" data-slideshow="stop"><i class="fa-solid fa-xmark"></i></button>
  `;
  // 아래쪽 탭존/오버레이 토글로 이벤트가 새지 않게 막는다
  ['pointerdown', 'touchstart', 'mousedown'].forEach((type) => {
    pill.addEventListener(type, (e) => { e.stopPropagation(); wakePill(); }, { passive: true });
  });
  pill.addEventListener('click', (e) => {
    e.stopPropagation();
    e.preventDefault();
    const btn = e.target.closest('[data-slideshow]');
    if (!btn) return;
    if (btn.dataset.slideshow === 'pause') togglePause();
    else if (btn.dataset.slideshow === 'stop') stopSlideshow();
  });
  modal.appendChild(pill);
  return pill;
}

function wakePill() {
  const pill = document.getElementById('viewer-slideshow-pill');
  if (!pill) return;
  pill.classList.remove('dimmed');
  if (pillDimTimer) clearTimeout(pillDimTimer);
  pillDimTimer = setTimeout(() => pill.classList.add('dimmed'), PILL_DIM_DELAY_MS);
}

function updatePill() {
  const pill = document.getElementById('viewer-slideshow-pill');
  if (pill && running) {
    const icon = pill.querySelector('[data-slideshow="pause"] i');
    if (icon) icon.className = paused ? 'fa-solid fa-play' : 'fa-solid fa-pause';
    const label = pill.querySelector('.viewer-slideshow-pill-label');
    if (label) {
      label.textContent = isScrollMode()
        ? `${t('viewer.slideshow_scroll', null, '자동 스크롤')} · ${t(`viewer.slideshow_speed_${getSpeedKey()}`, null, getSpeedKey())}`
        : `${t('viewer.slideshow', null, '슬라이드')} · ${t('viewer.slideshow_seconds', { n: getIntervalSec() }, `${getIntervalSec()}초`)}`;
    }
  }
  syncSlideshowControls();
}

function showPill() {
  const pill = ensurePill();
  if (!pill) return;
  pill.style.display = 'flex';
  updatePill();
  wakePill();
}

function hidePill() {
  const pill = document.getElementById('viewer-slideshow-pill');
  if (pill) pill.style.display = 'none';
  if (pillDimTimer) clearTimeout(pillDimTimer);
  pillDimTimer = null;
}

// 오버레이(이동 탭)의 슬라이드 버튼/선택 상자 상태를 맞춘다
export function syncSlideshowControls() {
  const row = document.getElementById('overlay-slideshow-row');
  if (row) row.style.display = isSlideshowSupportedFormat() ? 'flex' : 'none';

  const icon = document.querySelector('#btn-slideshow-toggle i');
  const label = document.getElementById('slideshow-toggle-label');
  if (icon) icon.className = running ? 'fa-solid fa-stop' : 'fa-solid fa-play';
  if (label) label.textContent = running ? t('viewer.slideshow_stop', null, '슬라이드 끄기') : t('viewer.slideshow_start', null, '슬라이드');

  const intervalSelect = document.getElementById('viewer-slideshow-interval-select');
  if (intervalSelect) {
    if (!intervalSelect.options.length) {
      INTERVAL_OPTIONS.forEach((sec) => {
        const opt = document.createElement('option');
        opt.value = String(sec);
        opt.textContent = t('viewer.slideshow_interval_option', { n: sec }, `넘김 ${sec}초`);
        intervalSelect.appendChild(opt);
      });
    }
    intervalSelect.value = String(getIntervalSec());
  }

  const speedSelect = document.getElementById('viewer-slideshow-speed-select');
  if (speedSelect) {
    if (!speedSelect.options.length) {
      Object.keys(SPEED_PX_PER_SEC).forEach((key) => {
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = `${t('viewer.slideshow_scroll', null, '자동 스크롤')} ${t(`viewer.slideshow_speed_${key}`, null, key)}`;
        speedSelect.appendChild(opt);
      });
    }
    speedSelect.value = getSpeedKey();
  }
}

// ── 다음 권 이어 재생 ──
function removeCountdown() {
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = null;
  const el = document.getElementById('viewer-slideshow-countdown');
  if (el) el.remove();
}

function showCountdown(nextBook, onGo, onCancel) {
  removeCountdown();
  const modal = getModal();
  if (!modal) return;
  const el = document.createElement('div');
  el.id = 'viewer-slideshow-countdown';
  el.className = 'viewer-slideshow-countdown';
  el.innerHTML = `
    <div class="viewer-slideshow-countdown-card">
      <div class="viewer-slideshow-countdown-title"></div>
      <div class="viewer-slideshow-countdown-sub"></div>
      <div class="viewer-slideshow-countdown-actions">
        <button type="button" class="btn-overlay-fit" data-slideshow-countdown="go"></button>
        <button type="button" class="btn-overlay-fit" data-slideshow-countdown="cancel"></button>
      </div>
    </div>
  `;
  el.querySelector('.viewer-slideshow-countdown-title').textContent = t('viewer.slideshow_next_volume', { title: nextBook.title || '' }, `다음 권: ${nextBook.title || ''}`);
  el.querySelector('[data-slideshow-countdown="go"]').textContent = t('viewer.slideshow_go_now', null, '지금 이동');
  el.querySelector('[data-slideshow-countdown="cancel"]').textContent = t('common.cancel', null, '취소');
  const sub = el.querySelector('.viewer-slideshow-countdown-sub');

  let remaining = NEXT_VOLUME_COUNTDOWN_SEC;
  const renderRemaining = () => {
    sub.textContent = t('viewer.slideshow_next_in', { n: remaining }, `${remaining}초 후 이어서 재생합니다`);
  };
  renderRemaining();

  ['pointerdown', 'touchstart', 'mousedown'].forEach((type) => {
    el.addEventListener(type, (e) => e.stopPropagation(), { passive: true });
  });
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    e.preventDefault();
    const btn = e.target.closest('[data-slideshow-countdown]');
    if (!btn) return;
    removeCountdown();
    if (btn.dataset.slideshowCountdown === 'go') onGo();
    else onCancel();
  });

  modal.appendChild(el);
  countdownTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      removeCountdown();
      onGo();
      return;
    }
    renderRemaining();
  }, 1000);
}

async function goToNextVolume() {
  if (goingToNextVolume) return;
  goingToNextVolume = true;
  const currentBookId = state.activeBookId;
  try {
    const m = await import('../viewer_next_episode.js');
    const nextBook = await m.fetchNextBook(currentBookId);
    if (!running || String(state.activeBookId) !== String(currentBookId)) {
      goingToNextVolume = false;
      return;
    }
    if (!nextBook) {
      toast(t('viewer.slideshow_last_volume', null, '마지막 권입니다. 슬라이드를 마칩니다.'), 'info');
      stopSlideshow();
      return;
    }
    showCountdown(
      nextBook,
      () => {
        if (!running) return;
        resumeAfterOpen = true;
        goingToNextVolume = false;
        stopLoop();
        m.openNextBook(nextBook);
      },
      () => stopSlideshow(),
    );
  } catch (err) {
    console.error('[Viewer-Slideshow] next volume lookup failed:', err);
    stopSlideshow();
  }
}

// ── 시작/정지 ──
export function startSlideshow() {
  if (!isSlideshowSupportedFormat()) {
    toast(t('viewer.slideshow_unsupported', null, '슬라이드는 만화와 PDF에서만 쓸 수 있습니다.'), 'info');
    return;
  }
  bindInteractionTracking();
  running = true;
  paused = false;
  goingToNextVolume = false;
  userHoldUntil = 0;
  // 메뉴에서 켰다면 메뉴를 닫아 바로 진행되게 한다
  if (isElementShown('comic-overlay-menu') && typeof window.toggleComicOverlay === 'function') {
    window.toggleComicOverlay();
  }
  startLoop();
  acquireWakeLock();
  showPill();
}

export function stopSlideshow() {
  running = false;
  paused = false;
  goingToNextVolume = false;
  resumeAfterOpen = false;
  stopLoop();
  removeCountdown();
  releaseWakeLock();
  hidePill();
  syncSlideshowControls();
}

export function toggleSlideshow() {
  if (running) stopSlideshow();
  else startSlideshow();
}

function togglePause() {
  if (!running) return;
  paused = !paused;
  if (!paused) pageDeadline = performance.now() + getIntervalSec() * 1000;
  updatePill();
  wakePill();
}

// lifecycle_controller.closeMediaViewer()에서 호출. 다음 권으로 넘어가는 중이면 상태를 유지한다.
export function onSlideshowViewerClosing() {
  removeCountdown();
  if (resumeAfterOpen) {
    stopLoop();
    hidePill();
    return;
  }
  if (running) stopSlideshow();
}

// lifecycle_controller.openReader()에서 뷰어 초기화를 시작한 직후 호출.
export function onSlideshowViewerOpened(fmt, initPromise) {
  syncSlideshowControls();
  if (!resumeAfterOpen) return;
  resumeAfterOpen = false;
  if (!isSlideshowSupportedFormat(fmt)) {
    stopSlideshow();
    return;
  }
  Promise.resolve(initPromise)
    .catch(() => {})
    .then(() => {
      if (!running) return;
      startSlideshow();
    });
}

window.toggleViewerSlideshow = toggleSlideshow;
