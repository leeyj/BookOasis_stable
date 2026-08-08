/* search_shortcut_manager.js – 검색 창 포커싱, 단축키(Alt+`) 및 미디어 타입 핫키 전담 모듈 */
import { filterBooks } from './book_list.js';
import { switchLibraryType } from './library_type_toggle.js';

let searchShortcutConfig = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };

export function focusLibrarySearchInput() {
  const searchInput = document.getElementById('library-search');
  if (!searchInput) return;
  searchInput.focus();
  searchInput.select();
}

export function applySearchShortcutSetting() {
  const savedRaw = localStorage.getItem('settings_search_shortcut');
  if (savedRaw) {
    try {
      searchShortcutConfig = JSON.parse(savedRaw);
    } catch (e) {
      console.error('[Shortcut] 단축키 파싱 실패:', e);
    }
  } else {
    searchShortcutConfig = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };
  }

  const searchInput = document.getElementById('library-search');
  if (searchInput) {
    const displayShortcut = searchShortcutConfig ? searchShortcutConfig.display : 'Alt + `';
    const fallbackText = `제목·시리즈·별칭 / 작가:작가명 (단축키: ${displayShortcut})`;
    let translatedPlaceholder = (window.i18n && typeof window.i18n.t === 'function')
      ? window.i18n.t('header.search_placeholder', { shortcut: displayShortcut }, fallbackText)
      : fallbackText;
    if (translatedPlaceholder === 'header.search_placeholder') {
      translatedPlaceholder = fallbackText;
    }
    searchInput.setAttribute('placeholder', translatedPlaceholder);
    const titleLabel = (window.i18n && typeof window.i18n.t === 'function')
      ? window.i18n.t('settings.search_shortcut_label', '검색 단축키 설정')
      : '검색 단축키 설정';
    searchInput.setAttribute('title', `${titleLabel}: ${displayShortcut}`);
  }
}

export function initLibrarySearchShortcut() {
  if (window.__librarySearchShortcutBound) return;

  applySearchShortcutSetting();

  window.addEventListener('bookoasis_language_changed', () => {
    applySearchShortcutSetting();
  });

  document.addEventListener('keydown', (e) => {
    if (document.getElementById('btn-record-shortcut')?.innerText === '입력 대기...') return;

    const savedRaw = localStorage.getItem('settings_search_shortcut');
    let currentShortcut = null;
    try {
      currentShortcut = savedRaw ? JSON.parse(savedRaw) : null;
    } catch (err) {
      currentShortcut = null;
    }

    const cfg = currentShortcut || searchShortcutConfig;
    const matchCtrl = !!cfg.ctrlKey === !!e.ctrlKey;
    const matchAlt = !!cfg.altKey === !!e.altKey;
    const matchShift = !!cfg.shiftKey === !!e.shiftKey;
    const matchMeta = !!cfg.metaKey === !!e.metaKey;

    let matchKey = false;
    if (cfg.code && e.code) {
      matchKey = cfg.code === e.code;
    } else if (cfg.key && e.key) {
      matchKey = cfg.key.toLowerCase() === e.key.toLowerCase();
    }

    if (matchCtrl && matchAlt && matchShift && matchMeta && matchKey) {
      e.preventDefault();
      focusLibrarySearchInput();
    }
  });

  window.__librarySearchShortcutBound = true;
}

export function handleLibrarySearchAction() {
  const searchInput = document.getElementById('library-search');
  if (!searchInput) return;

  const hasQuery = !!String(searchInput.value || '').trim();
  if (hasQuery) {
    searchInput.value = '';
    if (typeof window.filterBooks === 'function') window.filterBooks();
    else filterBooks();
    focusLibrarySearchInput();
    return;
  }

  if (document.activeElement !== searchInput) {
    focusLibrarySearchInput();
  } else {
    if (typeof window.filterBooks === 'function') window.filterBooks();
    else filterBooks();
  }
}

export function handleLibrarySearchKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    if (typeof window.filterBooks === 'function') window.filterBooks();
    else filterBooks();
  } else if (event.key === 'Escape') {
    const searchInput = document.getElementById('library-search');
    if (searchInput) {
      searchInput.value = '';
      if (typeof window.filterBooks === 'function') window.filterBooks();
      else filterBooks();
      searchInput.blur();
    }
  }
}

export function initLibraryTypeHotkeys() {
  if (window.__libraryTypeHotkeysBound) return;

  document.addEventListener('keydown', async (e) => {
    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (['input', 'textarea', 'select'].includes(tag) || activeEl?.isContentEditable) return;
    if (e.ctrlKey || e.altKey || e.metaKey) return;

    const key = e.key;
    if (!['1', '2', '3'].includes(key)) return;

    e.preventDefault();
    const switchFn = window.switchLibraryType || switchLibraryType;
    if (key === '1') {
      await switchFn('general');
    } else if (key === '2') {
      await switchFn('adult');
    } else if (key === '3') {
      await switchFn('audiobook');
    }
  });

  window.__libraryTypeHotkeysBound = true;
}

window.focusLibrarySearchInput = focusLibrarySearchInput;
window.applySearchShortcutSetting = applySearchShortcutSetting;
window.handleLibrarySearchAction = handleLibrarySearchAction;
window.handleLibrarySearchKeydown = handleLibrarySearchKeydown;
