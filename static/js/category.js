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
  enableVFSCheckForRemote
} from './category/path_browser.js';

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
  enableVFSCheckForRemote
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
}
