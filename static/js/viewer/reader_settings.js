// reader_settings.js — 읽기 방향, 페이지 스텝, fit 모드, 스크롤 너비 관리
import { showViewerLoading, hideViewerLoading } from '../view_manager.js';

export let comicReadingDirection = 'ltr';
export let comicPageStep = 1;
export let comicFitMode = 'height';
export let comicScrollWidth = 800; // 스크롤 모드 이미지 너비 (px, 600~900, 50단위)

function getStoredComicReadingDirection() {
  const saved = localStorage.getItem('comic_reading_direction');
  return saved === 'rtl' ? 'rtl' : 'ltr';
}

export function setComicReadingDirection(direction) {
  comicReadingDirection = direction === 'rtl' ? 'rtl' : 'ltr';
  localStorage.setItem('comic_reading_direction', comicReadingDirection);
  syncComicReadingDirectionUI();
  return comicReadingDirection;
}

export function getComicReadingDirection() {
  return comicReadingDirection;
}

export function toggleComicReadingDirection() {
  const nextDirection = comicReadingDirection === 'rtl' ? 'ltr' : 'rtl';
  return setComicReadingDirection(nextDirection);
}

function getStoredComicPageStep() {
  const saved = parseInt(localStorage.getItem('comic_page_step'), 10);
  return saved === 2 ? 2 : 1;
}

export function setComicPageStep(step) {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  const safeStep = step === 2 ? 2 : 1;
  if (scrollMode === 'scroll') {
    comicPageStep = 1;
    localStorage.setItem('comic_page_step', '1');
    syncComicPageStepUI();
    return 1;
  }

  comicPageStep = safeStep;
  localStorage.setItem('comic_page_step', String(comicPageStep));
  syncComicPageStepUI();
  return comicPageStep;
}

export function getComicPageStep() {
  return comicPageStep;
}

export function toggleComicPageStep() {
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (scrollMode === 'scroll') {
    return setComicPageStep(1);
  }

  // Use persisted value as source of truth because this module can be loaded
  // before EPUB initializes page-step state, causing first-click no-op.
  const currentStep = getStoredComicPageStep();
  return setComicPageStep(currentStep === 2 ? 1 : 2);
}

function syncComicReadingDirectionUI() {
  const btn = document.getElementById('btn-comic-reading-direction');
  const label = document.getElementById('comic-reading-direction-label');
  if (btn) {
    btn.classList.toggle('active', comicReadingDirection === 'rtl');
    btn.setAttribute('data-direction', comicReadingDirection);
    btn.title = comicReadingDirection === 'rtl' ? '오른쪽→왼쪽 읽기' : '왼쪽→오른쪽 읽기';
  }
  if (label) {
    label.textContent = comicReadingDirection === 'rtl' ? '오른쪽→왼쪽' : '왼쪽→오른쪽';
  }
}

function syncComicPageStepUI() {
  const btn = document.getElementById('btn-comic-page-step');
  const label = document.getElementById('comic-page-step-label');
  const scrollMode = localStorage.getItem('viewer_scroll_mode') || 'page';
  if (btn) {
    btn.classList.toggle('active', comicPageStep === 2 && scrollMode !== 'scroll');
    btn.setAttribute('data-step', String(comicPageStep));
    btn.title = scrollMode === 'scroll' ? '스크롤 모드에서는 1장씩만 적용됩니다' : (comicPageStep === 2 ? '2장씩 보기' : '1장씩 보기');
  }
  if (label) {
    label.textContent = scrollMode === 'scroll' ? '1장' : `${comicPageStep}장`;
  }
}

export function initReadingDirection() {
  setComicReadingDirection(getStoredComicReadingDirection());
}

export function initPageStep() {
  setComicPageStep(getStoredComicPageStep());
}

export function setFitMode(mode) {
  comicFitMode = mode;
  syncFitUI();
}

export function getFitMode() { return comicFitMode; }

function syncFitUI() {
  const btnHeight = document.getElementById('btn-fit-height');
  const btnWidth = document.getElementById('btn-fit-width');
  if (btnHeight) btnHeight.classList.toggle('active', comicFitMode === 'height');
  if (btnWidth) btnWidth.classList.toggle('active', comicFitMode === 'width');

  const btnOverlayHeight = document.getElementById('btn-overlay-fit-height');
  const btnOverlayWidth = document.getElementById('btn-overlay-fit-width');
  if (btnOverlayHeight) btnOverlayHeight.classList.toggle('active', comicFitMode === 'height');
  if (btnOverlayWidth) btnOverlayWidth.classList.toggle('active', comicFitMode === 'width');
}

// ──────────────────────────────────────────────────
// 스크롤 모드 이미지 너비 설정 (600~900px, 50px 단위)
// ──────────────────────────────────────────────────

export function getScrollWidth() {
  return comicScrollWidth;
}

export function setScrollWidth(px) {
  const clamped = Math.round(Math.max(600, Math.min(900, Number(px))) / 50) * 50;
  comicScrollWidth = clamped;
  localStorage.setItem('comic_scroll_width', String(clamped));
  applyScrollWidth();
  syncScrollWidthUI();
  return clamped;
}

export function applyScrollWidth() {
  const wrapper = document.querySelector('.comic-image-wrapper');
  if (wrapper) {
    wrapper.style.setProperty('--comic-scroll-width', `${comicScrollWidth}px`);
  }
}

export function initScrollWidth() {
  const saved = parseInt(localStorage.getItem('comic_scroll_width'), 10);
  comicScrollWidth = (saved >= 600 && saved <= 900) ? Math.round(saved / 50) * 50 : 800;
  applyScrollWidth();
  syncScrollWidthUI();
}

function syncScrollWidthUI() {
  const slider = document.getElementById('comic-scroll-width-slider');
  const label  = document.getElementById('comic-scroll-width-label');
  if (slider) slider.value = comicScrollWidth;
  if (label)  label.textContent = `${comicScrollWidth}px`;
}
