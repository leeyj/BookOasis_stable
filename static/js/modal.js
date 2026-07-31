// modal.js – 도서 상세 인라인 뷰 진입점 (detail/ 서브모듈 Re-export & 전역 바인딩)

import { openBookDetail, goBackToList } from './detail/index.js';
import { detailVolumeViewState, applyDetailVolumeView, toggleDetailUnreadFilter, setDetailVolumeSort } from './detail/volume_controller.js';
import { toggleMetaEditMode, triggerCoverUpload, handleCoverUploadSelect, handleCoverDrop, saveManualMetadata, handleUnlockMetadataEvent } from './detail/metadata_editor.js';
import { showGlobalLoadingSpinner, hideGlobalLoadingSpinner, toggleBookFavorite, toggleSeriesFavorite, rescanBook, rescanMissingBooks, rescanSeries } from './detail/book_actions.js';

// ── Re-export Modules ──
export {
  openBookDetail,
  goBackToList,
  detailVolumeViewState,
  applyDetailVolumeView,
  toggleDetailUnreadFilter,
  setDetailVolumeSort,
  toggleMetaEditMode,
  triggerCoverUpload,
  handleCoverUploadSelect,
  handleCoverDrop,
  saveManualMetadata,
  handleUnlockMetadataEvent,
  showGlobalLoadingSpinner,
  hideGlobalLoadingSpinner,
  toggleBookFavorite,
  toggleSeriesFavorite,
  rescanBook,
  rescanMissingBooks,
  rescanSeries
};

// ── Global Window Bindings (HTML 및 인라인 이벤트 100% 하위 호환성 보장) ──
window.openBookDetail = openBookDetail;
window.goBackToList = goBackToList;
window.toggleDetailUnreadFilter = toggleDetailUnreadFilter;
window.setDetailVolumeSort = setDetailVolumeSort;

window.toggleBookFavorite = toggleBookFavorite;
window.toggleSeriesFavorite = toggleSeriesFavorite;

window.toggleMetaEditMode = toggleMetaEditMode;
window.triggerCoverUpload = triggerCoverUpload;
window.handleCoverUploadSelect = handleCoverUploadSelect;
window.handleCoverDrop = handleCoverDrop;
window.saveManualMetadata = saveManualMetadata;
window.handleUnlockMetadataEvent = handleUnlockMetadataEvent;

window.rescanBook = rescanBook;
window.rescanMissingBooks = rescanMissingBooks;
window.rescanSeries = rescanSeries;

window.showGlobalLoadingSpinner = showGlobalLoadingSpinner;
window.hideGlobalLoadingSpinner = hideGlobalLoadingSpinner;