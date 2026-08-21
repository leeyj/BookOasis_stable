// category.js – 카테고리 진입점 (category/ 서브모듈 Re-export & 전역 바인딩)

import { loadLibraries, toggleCategoryOrderPin, bindDragAndDropEvents, saveNewOrder } from './category/index.js';
import { currentTargetLibrary, setCurrentTargetLibrary, bindSidebarContextMenu, showContextMenu } from './category/context_menu.js';
import {
  triggerAddLibrary,
  triggerEditLibrary,
  triggerDeleteLibrary,
  triggerScanLibrary,
  triggerScanLibraryCovers,
  triggerCancelScanLibrary,
  closeLibraryModal,
  submitLibraryForm,
  triggerMoveLibrary,
  selectCategoryType,
  selectIconOption,
  selectColorOption
} from './category/crud_controller.js';
import {
  testGDriveLinks,
  openPathBrowser,
  closePathBrowser,
  refreshPathBrowser,
  loadPathBrowserItems,
  selectPathFromBrowser,
  detectAndUpdateRemoteFlag,
  updateRemoteWarning,
  enableVFSCheckForRemote,
  validateGdriveCopyTarget
} from './category/path_browser.js';
import {
  openGdriveCopyModal,
  closeGdriveCopyModal,
  submitGdriveCopyForm,
  triggerAddGdriveCopy
} from './category/gdrive_copy_modal.js';

// ── Re-export Modules ──
export {
  loadLibraries,
  toggleCategoryOrderPin,
  bindDragAndDropEvents,
  saveNewOrder,
  currentTargetLibrary,
  setCurrentTargetLibrary,
  bindSidebarContextMenu,
  showContextMenu,
  triggerAddLibrary,
  triggerEditLibrary,
  triggerDeleteLibrary,
  triggerScanLibrary,
  triggerScanLibraryCovers,
  triggerCancelScanLibrary,
  closeLibraryModal,
  submitLibraryForm,
  triggerMoveLibrary,
  selectCategoryType,
  selectIconOption,
  selectColorOption,
  testGDriveLinks,
  openPathBrowser,
  closePathBrowser,
  refreshPathBrowser,
  loadPathBrowserItems,
  selectPathFromBrowser,
  detectAndUpdateRemoteFlag,
  updateRemoteWarning,
  enableVFSCheckForRemote,
  validateGdriveCopyTarget,
  openGdriveCopyModal,
  closeGdriveCopyModal,
  submitGdriveCopyForm,
  triggerAddGdriveCopy
};

// ── Global Window Bindings (HTML 및 인라인 이벤트 100% 하위 호환성 보장) ──
if (typeof window !== 'undefined') {
  window.loadLibraries = loadLibraries;
  window.toggleCategoryOrderPin = toggleCategoryOrderPin;
  window.showContextMenu = showContextMenu;

  window.triggerAddLibrary = triggerAddLibrary;
  window.triggerEditLibrary = triggerEditLibrary;
  window.triggerDeleteLibrary = triggerDeleteLibrary;
  window.triggerScanLibrary = triggerScanLibrary;
  window.triggerScanLibraryCovers = triggerScanLibraryCovers;
  window.triggerCancelScanLibrary = triggerCancelScanLibrary;
  window.closeLibraryModal = closeLibraryModal;
  window.submitLibraryForm = submitLibraryForm;
  window.triggerMoveLibrary = triggerMoveLibrary;

  window.selectCategoryType = selectCategoryType;
  window.selectIconOption = selectIconOption;
  window.selectColorOption = selectColorOption;

  window.testGDriveLinks = testGDriveLinks;
  window.openPathBrowser = openPathBrowser;
  window.closePathBrowser = closePathBrowser;
  window.refreshPathBrowser = refreshPathBrowser;
  window.selectPathFromBrowser = selectPathFromBrowser;

  window.triggerAddGdriveCopy = triggerAddGdriveCopy;
}

function initCategoryModalDelegation() {
  if (typeof document === 'undefined' || window.__categoryModalDelegationBound) return;

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="library-modal-close"], [data-role="library-category-type"], [data-role="library-open-path-browser"], [data-role="library-test-gdrive"], [data-role="library-validate-gdrive-copy"], [data-role="library-icon-option"], [data-role="library-color-option"], [data-role="library-move"], [data-role="library-form-submit"], [data-role="path-browser-close"], [data-role="path-browser-refresh"], [data-role="path-browser-select"], [data-role="gdrive-copy-modal-close"], [data-role="gdrive-copy-submit"]')
      : null;
    if (!target) return;

    event.preventDefault();

    const role = target.getAttribute('data-role');
    if (role === 'library-modal-close') return closeLibraryModal();
    if (role === 'library-category-type') return selectCategoryType(target.getAttribute('data-type') || 'local');
    if (role === 'library-open-path-browser') return openPathBrowser();
    if (role === 'library-test-gdrive') return testGDriveLinks();
    if (role === 'library-validate-gdrive-copy') return validateGdriveCopyTarget();
    if (role === 'library-icon-option') return selectIconOption(target);
    if (role === 'library-color-option') return selectColorOption(target);
    if (role === 'library-move') return triggerMoveLibrary();
    if (role === 'library-form-submit') {
      console.log('[Category-Modal] [저장] 버튼 클릭 이벤트 감지됨');
      return submitLibraryForm(event);
    }
    if (role === 'path-browser-close') return closePathBrowser();
    if (role === 'path-browser-refresh') return refreshPathBrowser();
    if (role === 'path-browser-select') return selectPathFromBrowser();
    if (role === 'gdrive-copy-modal-close') return closeGdriveCopyModal();
    if (role === 'gdrive-copy-submit') return submitGdriveCopyForm(event);
  }, true);

  document.addEventListener('submit', (event) => {
    const form = event && event.target;
    if (!form) return;
    if (form.id === 'library-crud-form') {
      event.preventDefault();
      event.stopPropagation();
      console.log('[Category-Modal] library-crud-form submit 이벤트 가로챔 완료');
      submitLibraryForm(event);
      return;
    }
    if (form.id === 'gdrive-copy-form') {
      event.preventDefault();
      event.stopPropagation();
      submitGdriveCopyForm(event);
    }
  }, true);

  window.__categoryModalDelegationBound = true;
}

initCategoryModalDelegation();
