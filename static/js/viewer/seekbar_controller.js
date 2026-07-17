// seekbar_controller.js - unified seekbar routing for comic/txt/epub/pdf
import { state } from '../state.js';

let viewerSeekbarInited = false;
const viewerModules = {
  comic: null,
  txt: null,
  pdf: null,
};

async function getViewerModule(fmt) {
  try {
    if (fmt === 'zip' || fmt === 'cbz' || fmt === 'imgdir') {
      if (!viewerModules.comic) viewerModules.comic = await import('../viewer_comic.js');
      return viewerModules.comic;
    }
    if (fmt === 'epub' || fmt === 'txt') {
      if (!viewerModules.txt) viewerModules.txt = await import('../viewer_txt.js');
      return viewerModules.txt;
    }
    if (fmt === 'pdf') {
      if (!viewerModules.pdf) viewerModules.pdf = await import('../viewer_pdf.js');
      return viewerModules.pdf;
    }
  } catch (err) {
    console.error(`[Viewer-Core] Failed to import module for format ${fmt}:`, err);
  }
  return null;
}

export function initViewerSeekBar() {
  const slider = document.getElementById('viewer-page-slider');
  if (!slider) return;

  if (viewerSeekbarInited) return;
  viewerSeekbarInited = true;

  const initialFmt = state.currentViewerFormat;
  if (initialFmt) {
    getViewerModule(initialFmt).catch(() => {});
  }

  slider.addEventListener('input', async (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;

    if (fmt === 'zip' || fmt === 'cbz' || fmt === 'imgdir') {
      const m = await getViewerModule(fmt);
      if (m) {
        const fn = m.comicSliderInput || (window && window.comicSliderInput);
        if (typeof fn === 'function') fn(slider, val);
      }
    } else if (fmt === 'epub' || fmt === 'txt') {
      const m = await getViewerModule(fmt);
      if (m) {
        const fn = m.txtSliderInput;
        if (typeof fn === 'function') fn(slider, val);
      }
    } else if (fmt === 'pdf') {
      const tooltip = document.getElementById('seekbar-tooltip');
      if (tooltip) {
        tooltip.textContent = val;
        tooltip.style.display = 'block';
      }
      const pageInfo = document.getElementById('comic-overlay-page-info');
      if (pageInfo) {
        pageInfo.textContent = `${val} / ${slider.max}`;
      }
    }
  });

  slider.addEventListener('change', async (e) => {
    const val = parseInt(e.target.value, 10);
    const fmt = state.currentViewerFormat;

    if (fmt === 'zip' || fmt === 'cbz' || fmt === 'imgdir') {
      const m = await getViewerModule(fmt);
      if (m) {
        const fn = m.comicSliderChange || (window && window.comicSliderChange);
        if (typeof fn === 'function') fn(slider, val);
      }
    } else if (fmt === 'epub' || fmt === 'txt') {
      const m = await getViewerModule(fmt);
      if (m) {
        const fn = m.txtSliderChange;
        if (typeof fn === 'function') fn(slider, val);
      }
    } else if (fmt === 'pdf') {
      const m = await getViewerModule(fmt);
      if (m) {
        const fn = m.pdfSliderChange || m.pdfJumpToPage || (window && window.pdfJumpToPage);
        if (typeof fn === 'function') fn(slider, val);
      }
    }
  });
}
