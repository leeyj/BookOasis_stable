// Thin wrapper for backward compatibility — re-export modular EPUB viewer APIs
export {
  epubBook,
  epubTotalPages,
  initEpubViewer,
  clearEpubViewer,
  applyEpubSettings,
  changeEpubScrollMode,
  epubPrevPage,
  epubNextPage,
  syncEpubSeekBar,
  epubSliderInput,
  epubSliderChange,
  epubJumpToFirstPage,
  epubJumpToLastPage,
  EpubViewer
} from './viewer/epub/runtime.js';
