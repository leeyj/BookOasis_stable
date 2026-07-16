// Lightweight storage wrapper for safer viewer state persistence access.
export const viewerStorage = {
  getItem(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (e) {
      console.warn('[Viewer-Storage] getItem failed:', key, e);
      return null;
    }
  },
  setItem(key, value) {
    try {
      window.localStorage.setItem(key, value);
      return true;
    } catch (e) {
      console.warn('[Viewer-Storage] setItem failed:', key, e);
      return false;
    }
  },
  removeItem(key) {
    try {
      window.localStorage.removeItem(key);
      return true;
    } catch (e) {
      console.warn('[Viewer-Storage] removeItem failed:', key, e);
      return false;
    }
  }
};
