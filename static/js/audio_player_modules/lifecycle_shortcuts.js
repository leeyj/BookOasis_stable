// lifecycle_shortcuts.js - 전역 단축키/라이프사이클 저장 이벤트 전담

function isTextInputFocused() {
  const active = document.activeElement;
  const activeTag = (active && active.tagName) ? active.tagName.toUpperCase() : '';
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || !!(active && active.isContentEditable);
}

export function initAudioLifecycleAndShortcuts(deps) {
  if (window.__audioLifecycleAndShortcutsBound) return;

  const {
    isModalOpen,
    isAudioActive,
    onEscape,
    onTogglePlay,
    onSkipBackward,
    onSkipForward,
    onPageHide,
    onBeforeUnload,
    onVisibilityHidden,
    onVisibilityVisible
  } = deps;

  window.addEventListener('keydown', (e) => {
    const modalOpen = !!isModalOpen();
    const audioActive = !!isAudioActive();

    if (modalOpen && e.key === 'Escape') {
      e.preventDefault();
      onEscape();
      return;
    }

    if (!modalOpen && !audioActive) return;
    if (isTextInputFocused()) return;

    const key = String(e.key || '').toLowerCase();

    // '<' / '>'는 키보드 레이아웃에 따라 ',' / '.' 키로 들어올 수 있어 둘 다 허용한다.
    if (key === 's') {
      e.preventDefault();
      onTogglePlay();
    } else if (key === '<' || key === ',') {
      e.preventDefault();
      onSkipBackward();
    } else if (key === '>' || key === '.') {
      e.preventDefault();
      onSkipForward();
    }
  });

  window.addEventListener('pagehide', () => {
    onPageHide();
  });

  window.addEventListener('beforeunload', () => {
    onBeforeUnload();
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      onVisibilityHidden();
    } else if (document.visibilityState === 'visible') {
      onVisibilityVisible();
    }
  });

  window.__audioLifecycleAndShortcutsBound = true;
}
