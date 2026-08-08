// mini_player_ui.js - 미니 플레이어 UI/드래그/뷰 모드 전담

export function createMiniPlayerUiController(deps) {
  const {
    getCurrentViewMode,
    setCurrentViewMode,
    getAudiobookData,
    getCurrentTrackIndex,
    getAudioInstance,
    getEffectiveTrackDuration,
    updatePlaybackToggleButtons
  } = deps;

  const AUDIO_MINI_BAR_POS_KEY = 'audio_mini_bar_pos_v1';
  const AUDIO_MINI_BAR_COLLAPSED_KEY_BASE = 'audio_mini_bar_collapsed_v2';

  let miniBarDragBound = false;
  let miniBarDragSuppressClickUntil = 0;
  let audioExpandGuardUntil = 0;
  let miniBarCollapsed = false;
  let miniTrackListRenderKey = '';
  let miniTrackListActiveId = null;

  const miniBarDragState = {
    dragging: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    originLeft: 0,
    originTop: 0,
    moved: false
  };

  function getConfiguredMiniPlayerMode() {
    const raw = (typeof window !== 'undefined' && window.__audioMiniPlayerMode)
      ? String(window.__audioMiniPlayerMode)
      : 'mini';
    return raw === 'right_dock' ? 'right_dock' : 'mini';
  }

  function isRightDockMiniPlayerMode() {
    return getConfiguredMiniPlayerMode() === 'right_dock';
  }

  function isRightDockDimEnabled() {
    return !!(typeof window !== 'undefined' && window.__audioRightDockDimEnabled);
  }

  function formatTrackLength(track) {
    if (!track) return '';
    if (track.time_str && typeof track.time_str === 'string') return track.time_str;

    const raw = Number(track.duration || track.total_duration || 0);
    if (!Number.isFinite(raw) || raw <= 0) return '';

    const sec = Math.floor(raw % 60);
    const min = Math.floor((raw / 60) % 60);
    const hour = Math.floor(raw / 3600);
    if (hour > 0) {
      return `${hour}:${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }
    return `${min}:${String(sec).padStart(2, '0')}`;
  }

  function applyMiniTrackItemVisual(item, active) {
    if (!item) return;
    item.style.background = active ? 'rgba(56, 189, 248, 0.16)' : 'rgba(255,255,255,0.03)';
    item.style.borderColor = active ? 'rgba(56, 189, 248, 0.55)' : 'rgba(255,255,255,0.08)';
    item.style.color = active ? '#e0f2fe' : '#cbd5e1';
  }

  function clampPct(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, n));
  }

  function updateMiniTrackProgressBars(trackListEl, tracks, meta, currentTrack) {
    if (!trackListEl || !Array.isArray(tracks) || tracks.length === 0) return;

    const currentIdx = getCurrentTrackIndex();
    const audioInstance = getAudioInstance();
    const currentTrackId = currentTrack ? Number(currentTrack.id || 0) : 0;

    const items = trackListEl.querySelectorAll('[data-role="audio-chapter-track"]');
    items.forEach((item) => {
      const bar = item.querySelector('[data-mini-track-progress-fill="1"]');
      if (!bar) return;

      const itemTrackId = Number(item.getAttribute('data-track-id') || '0');
      const itemIdx = tracks.findIndex((t) => Number(t && t.id ? t.id : 0) === itemTrackId);
      if (itemIdx < 0) {
        bar.style.width = '0%';
        return;
      }

      const track = tracks[itemIdx] || null;
      let pct = 0;

      if (currentTrackId > 0 && itemTrackId === currentTrackId) {
        const duration = getEffectiveTrackDuration() || Number(track && (track.duration || track.total_duration) || 0);
        const cur = audioInstance ? Number(audioInstance.currentTime || 0) : Number(meta && meta.current_time || 0);
        pct = duration > 0 ? (cur / duration) * 100 : 0;
      } else if (Number(track && track.is_track_completed) === 1) {
        pct = 100;
      } else if (Number.isFinite(Number(track && track.track_progress_pct))) {
        pct = Number(track.track_progress_pct || 0);
      } else if (itemIdx < currentIdx) {
        pct = 100;
      } else if (track && Number.isFinite(Number(track.pages_read))) {
        pct = Number(track.pages_read);
      }

      bar.style.width = `${clampPct(pct).toFixed(2)}%`;
    });
  }

  function renderMiniTrackList(trackListEl, tracks, currentTrack) {
    if (!trackListEl) return;

    const trackCount = Array.isArray(tracks) ? tracks.length : 0;
    const renderKey = `${trackCount}:${tracks.map((t) => t && t.id).join(',')}`;
    const currentTrackId = currentTrack ? Number(currentTrack.id || 0) : 0;
    const needsRebuild = miniTrackListRenderKey !== renderKey;

    if (needsRebuild) {
      trackListEl.innerHTML = '';

      tracks.forEach((track, idx) => {
        const trackId = Number(track && track.id ? track.id : 0);
        if (!trackId) return;

        const trackNo = Number(track.track_number) > 0 ? Number(track.track_number) : (idx + 1);
        const title = String(track.title || `Track ${trackNo}`);
        const durationText = formatTrackLength(track);

        const item = document.createElement('button');
        item.type = 'button';
        item.setAttribute('data-role', 'audio-chapter-track');
        item.setAttribute('data-track-id', String(trackId));
        item.style.width = '100%';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.justifyContent = 'space-between';
        item.style.gap = '0.5rem';
        item.style.padding = '0.44rem 0.56rem 0.42rem 0.56rem';
        item.style.borderRadius = '9px';
        item.style.border = '1px solid rgba(255,255,255,0.08)';
        item.style.marginBottom = '0.36rem';
        item.style.cursor = 'pointer';
        item.style.fontSize = '0.78rem';
        item.style.textAlign = 'left';
        item.style.flexDirection = 'column';
        item.style.alignItems = 'stretch';

        const topRow = document.createElement('div');
        topRow.style.display = 'flex';
        topRow.style.alignItems = 'center';
        topRow.style.justifyContent = 'space-between';
        topRow.style.gap = '0.5rem';

        const left = document.createElement('span');
        left.style.minWidth = '0';
        left.style.flex = '1';
        left.style.whiteSpace = 'nowrap';
        left.style.overflow = 'hidden';
        left.style.textOverflow = 'ellipsis';
        left.textContent = `${trackNo}. ${title}`;

        const right = document.createElement('span');
        right.style.flexShrink = '0';
        right.style.fontSize = '0.7rem';
        right.style.opacity = '0.84';
        right.textContent = durationText || '-';

        topRow.appendChild(left);
        topRow.appendChild(right);

        const progressRail = document.createElement('div');
        progressRail.style.width = '100%';
        progressRail.style.height = '3px';
        progressRail.style.marginTop = '0.32rem';
        progressRail.style.borderRadius = '999px';
        progressRail.style.background = 'rgba(148, 163, 184, 0.22)';
        progressRail.style.overflow = 'hidden';

        const progressFill = document.createElement('div');
        progressFill.setAttribute('data-mini-track-progress-fill', '1');
        progressFill.style.width = '0%';
        progressFill.style.height = '100%';
        progressFill.style.borderRadius = '999px';
        progressFill.style.background = 'linear-gradient(90deg, #22d3ee 0%, #38bdf8 100%)';
        progressFill.style.transition = 'width 0.16s linear';

        progressRail.appendChild(progressFill);
        item.appendChild(topRow);
        item.appendChild(progressRail);
        trackListEl.appendChild(item);
      });

      miniTrackListRenderKey = renderKey;
      miniTrackListActiveId = null;
    }

    if (miniTrackListActiveId === currentTrackId) return;

    const items = trackListEl.querySelectorAll('[data-role="audio-chapter-track"]');
    items.forEach((item) => {
      const itemTrackId = Number(item.getAttribute('data-track-id') || '0');
      const isActive = currentTrackId > 0 && itemTrackId === currentTrackId;
      applyMiniTrackItemVisual(item, isActive);
    });

    miniTrackListActiveId = currentTrackId;
  }

  function getCollapsedStateStorageKey() {
    return `${AUDIO_MINI_BAR_COLLAPSED_KEY_BASE}_${getConfiguredMiniPlayerMode()}`;
  }

  function isMiniBarFeatureEnabled() {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(min-width: 1024px)').matches;
  }

  function isMiniBarDragEnabled() {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    if (isRightDockMiniPlayerMode()) return false;
    return isMiniBarFeatureEnabled();
  }

  function saveMiniBarPosition(left, top) {
    try {
      const payload = { left: Math.round(Number(left) || 12), top: Math.round(Number(top) || 12) };
      localStorage.setItem(AUDIO_MINI_BAR_POS_KEY, JSON.stringify(payload));
    } catch (e) {}
  }

  function saveMiniBarCollapsedState(collapsed) {
    try {
      localStorage.setItem(getCollapsedStateStorageKey(), collapsed ? '1' : '0');
    } catch (e) {}
  }

  function loadMiniBarCollapsedState() {
    try {
      return localStorage.getItem(getCollapsedStateStorageKey()) === '1';
    } catch (e) {
      return false;
    }
  }

  function loadMiniBarPosition() {
    try {
      const raw = localStorage.getItem(AUDIO_MINI_BAR_POS_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !Number.isFinite(parsed.left) || !Number.isFinite(parsed.top)) return null;
      return { left: parsed.left, top: parsed.top };
    } catch (e) {
      return null;
    }
  }

  function clampMiniBarToViewport(miniBar) {
    if (!miniBar) return;
    const rect = miniBar.getBoundingClientRect();
    const maxLeft = Math.max(0, window.innerWidth - rect.width - 8);
    const maxTop = Math.max(0, window.innerHeight - rect.height - 8);
    const nextLeft = Math.min(Math.max(rect.left, 8), maxLeft);
    const nextTop = Math.min(Math.max(rect.top, 8), maxTop);
    miniBar.style.left = `${nextLeft}px`;
    miniBar.style.top = `${nextTop}px`;
  }

  function resetMiniBarPosition(miniBar) {
    if (!miniBar) return;
    if (isRightDockMiniPlayerMode()) {
      miniBar.style.left = '';
      miniBar.style.right = '12px';
      miniBar.style.top = 'calc(12px + env(safe-area-inset-top, 0px))';
      miniBar.style.bottom = '12px';
      return;
    }
    miniBar.style.left = '12px';
    miniBar.style.right = '';
    miniBar.style.bottom = '';
    miniBar.style.top = 'calc(12px + env(safe-area-inset-top, 0px))';
  }

  function applySavedMiniBarPosition(miniBar) {
    if (!miniBar) return;
    if (isRightDockMiniPlayerMode()) {
      resetMiniBarPosition(miniBar);
      return;
    }
    const saved = loadMiniBarPosition();
    if (!saved) {
      resetMiniBarPosition(miniBar);
      return;
    }
    miniBar.style.left = `${saved.left}px`;
    miniBar.style.top = `${saved.top}px`;
    clampMiniBarToViewport(miniBar);
  }

  function applyMiniBarCollapsedState() {
    const miniBar = document.getElementById('audio-player-mini-bar');
    if (!miniBar) return;

    const isMiniMode = getCurrentViewMode() === 'mini';

    const miniMainRow = document.getElementById('audio-mini-main-row');
    const miniCoverButton = document.getElementById('audio-mini-cover-button');
    const miniTextBlock = document.getElementById('audio-mini-text-block');
    const miniControls = document.getElementById('audio-mini-controls');
    const miniTrackFooter = document.getElementById('audio-mini-track-footer');
    const miniTrackList = document.getElementById('audio-mini-track-list');
    const miniTitle = document.getElementById('audio-mini-title');
    const miniSubtitle = document.getElementById('audio-mini-subtitle');
    const miniPeekButton = miniBar.querySelector('[data-action="toggle-mini-peek"]');
    const peekIcon = document.getElementById('audio-mini-peek-icon');
    const prevBtn = miniBar.querySelector('[data-action="prev-track"]');
    const playBtn = document.getElementById('btn-audio-mini-play-toggle');
    const nextBtn = miniBar.querySelector('[data-action="next-track"]');
    const dismissBtn = miniBar.querySelector('[data-action="dismiss-mini"]');
    const sheetBackdrop = document.getElementById('audio-mini-sheet-backdrop');
    const rightExpandButton = document.getElementById('audio-mini-right-expand');
    const rightExpandIcon = rightExpandButton ? rightExpandButton.querySelector('i') : null;
    const rightDockMode = isRightDockMiniPlayerMode();

    // 기본 떠다니는 미니바에서는 오동작 방지를 위해 숨김/펼침 버튼을 사용하지 않는다.
    if (!rightDockMode) {
      if (miniPeekButton) miniPeekButton.style.display = 'none';
      if (miniBarCollapsed) {
        miniBarCollapsed = false;
        saveMiniBarCollapsedState(false);
      }

      if (miniMainRow) {
        miniMainRow.style.flexDirection = 'row';
        miniMainRow.style.alignItems = 'center';
        miniMainRow.style.gap = '0.7rem';
        miniMainRow.style.padding = '0.58rem 0.68rem';
      }
      if (miniCoverButton) {
        miniCoverButton.style.width = '40px';
        miniCoverButton.style.height = '40px';
        miniCoverButton.style.borderRadius = '10px';
      }
      if (miniTextBlock) {
        miniTextBlock.style.flex = '1';
        miniTextBlock.style.width = '';
        miniTextBlock.style.alignItems = 'flex-start';
        miniTextBlock.style.textAlign = 'left';
      }
      if (miniTitle) miniTitle.style.fontSize = '0.84rem';
      if (miniSubtitle) miniSubtitle.style.fontSize = '0.72rem';
      if (miniControls) {
        miniControls.style.width = '';
        miniControls.style.justifyContent = 'flex-start';
      }
      if (miniTrackFooter) {
        miniTrackFooter.style.display = 'none';
      }
      if (miniTrackList) {
        miniTrackList.style.display = 'none';
      }
      if (prevBtn) {
        prevBtn.style.width = '28px';
        prevBtn.style.height = '28px';
      }
      if (playBtn) {
        playBtn.style.width = '32px';
        playBtn.style.height = '32px';
      }
      if (nextBtn) {
        nextBtn.style.width = '28px';
        nextBtn.style.height = '28px';
      }
      if (dismissBtn) {
        dismissBtn.style.width = '28px';
        dismissBtn.style.height = '28px';
      }

      miniBar.style.width = '';
      miniBar.style.flexDirection = '';
      miniBar.style.maxWidth = '';
      miniBar.style.left = miniBar.style.left || '12px';
      miniBar.style.right = '';
      miniBar.style.bottom = '';
      miniBar.style.borderRadius = '14px';
      if (sheetBackdrop) {
        sheetBackdrop.style.display = 'none';
        sheetBackdrop.style.pointerEvents = '';
      }
    } else {
      if (miniPeekButton) miniPeekButton.style.display = 'inline-flex';

      if (miniMainRow) {
        miniMainRow.style.flexDirection = 'column';
        miniMainRow.style.alignItems = 'stretch';
        miniMainRow.style.gap = '0.75rem';
        miniMainRow.style.padding = '0.85rem 0.9rem';
      }
      if (miniCoverButton) {
        miniCoverButton.style.width = '96px';
        miniCoverButton.style.height = '96px';
        miniCoverButton.style.borderRadius = '14px';
        miniCoverButton.style.margin = '0 auto';
      }
      if (miniTextBlock) {
        miniTextBlock.style.flex = '0 0 auto';
        miniTextBlock.style.width = '100%';
        miniTextBlock.style.alignItems = 'center';
        miniTextBlock.style.textAlign = 'center';
      }
      if (miniTitle) miniTitle.style.fontSize = '1.02rem';
      if (miniSubtitle) miniSubtitle.style.fontSize = '0.86rem';
      if (miniControls) {
        miniControls.style.width = '100%';
        miniControls.style.justifyContent = 'space-between';
      }
      if (prevBtn) {
        prevBtn.style.width = '40px';
        prevBtn.style.height = '40px';
      }
      if (playBtn) {
        playBtn.style.width = '52px';
        playBtn.style.height = '52px';
      }
      if (nextBtn) {
        nextBtn.style.width = '40px';
        nextBtn.style.height = '40px';
      }
      if (dismissBtn) {
        dismissBtn.style.width = '40px';
        dismissBtn.style.height = '40px';
      }

      miniBar.style.width = 'min(560px, 46vw, calc(100vw - 24px))';
      miniBar.style.flexDirection = 'column';
      miniBar.style.maxWidth = 'calc(100vw - 24px)';
      miniBar.style.left = '';
      miniBar.style.right = '12px';
      miniBar.style.top = 'calc(12px + env(safe-area-inset-top, 0px))';
      miniBar.style.bottom = '12px';
      miniBar.style.borderRadius = '18px';
      if (sheetBackdrop) {
        // right_dock 딤은 설정으로 제어한다.
        const shouldShowDim = isRightDockDimEnabled() && getCurrentViewMode() === 'mini';
        sheetBackdrop.style.pointerEvents = 'none';
        sheetBackdrop.style.display = shouldShowDim ? 'block' : 'none';
      }
      if (miniTrackFooter) {
        miniTrackFooter.style.display = 'block';
      }
      if (miniTrackList) {
        miniTrackList.style.display = 'block';
      }
    }

    miniBar.style.display = isMiniMode ? (rightDockMode ? 'flex' : 'block') : 'none';

    miniBar.style.right = rightDockMode ? '12px' : miniBar.style.right;

    if (getCurrentViewMode() !== 'mini') {
      miniBar.style.transform = 'translateX(0)';
      if (peekIcon) peekIcon.className = 'fa-solid fa-eye-slash';
      if (sheetBackdrop) {
        sheetBackdrop.style.display = 'none';
        sheetBackdrop.style.pointerEvents = '';
      }
      if (rightExpandButton) rightExpandButton.style.display = 'none';
      return;
    }

    if (rightDockMode) {
      if (miniBarCollapsed) {
        miniBar.style.transform = 'translateX(calc(100% + 28px))';
        if (peekIcon) peekIcon.className = 'fa-solid fa-eye';
        if (rightExpandIcon) rightExpandIcon.className = 'fa-solid fa-angle-left';
        if (rightExpandButton) rightExpandButton.style.display = 'inline-flex';
      } else {
        miniBar.style.transform = 'translateX(0)';
        if (peekIcon) peekIcon.className = 'fa-solid fa-eye-slash';
        if (rightExpandButton) rightExpandButton.style.display = 'none';
      }
      if (rightExpandIcon) rightExpandIcon.className = 'fa-solid fa-angle-left';
      return;
    }

    if (rightExpandButton) rightExpandButton.style.display = 'none';
    if (miniBarCollapsed) {
      miniBar.style.transform = 'translateX(calc(-100% + 74px))';
      if (peekIcon) peekIcon.className = 'fa-solid fa-eye';
    } else {
      miniBar.style.transform = 'translateX(0)';
      if (peekIcon) peekIcon.className = 'fa-solid fa-eye-slash';
    }
  }

  function applyMiniBarDragAvailability() {
    const miniBar = document.getElementById('audio-player-mini-bar');
    if (!miniBar) return;

    const dragHandle = miniBar.querySelector('[data-action="mini-drag-handle"]');
    const rightDockMode = isRightDockMiniPlayerMode();
    if (rightDockMode) {
      resetMiniBarPosition(miniBar);
    }

    if (isMiniBarDragEnabled()) {
      miniBar.style.cursor = 'grab';
      if (dragHandle) {
        dragHandle.style.opacity = '1';
        dragHandle.style.pointerEvents = 'auto';
        dragHandle.style.cursor = 'grab';
      }
      if (getCurrentViewMode() === 'mini') {
        if (!miniBar.style.left || !miniBar.style.left.endsWith('px')) {
          applySavedMiniBarPosition(miniBar);
        }
        if (!miniBarCollapsed) {
          clampMiniBarToViewport(miniBar);
        }
      }
    } else {
      miniBar.style.cursor = '';
      if (dragHandle) {
        dragHandle.style.opacity = rightDockMode ? '0' : '0.6';
        dragHandle.style.display = rightDockMode ? 'none' : 'inline-flex';
        dragHandle.style.pointerEvents = 'none';
        dragHandle.style.cursor = 'default';
      }
      if (!rightDockMode) {
        resetMiniBarPosition(miniBar);
      }
    }

    applyMiniBarCollapsedState();
  }

  function initMiniBarDrag() {
    if (miniBarDragBound) return;
    miniBarDragBound = true;

    const tryBind = () => {
      const miniBar = document.getElementById('audio-player-mini-bar');
      if (!miniBar) return false;

      miniBar.addEventListener('pointerdown', (e) => {
        if (!isMiniBarDragEnabled()) return;
        if (getCurrentViewMode() !== 'mini') return;
        if (e.button !== 0) return;

        const target = e.target;
        if (!target || typeof target.closest !== 'function') return;
        const dragHandle = target.closest('[data-action="mini-drag-handle"]');
        if (!dragHandle) return;

        const rect = miniBar.getBoundingClientRect();
        miniBarDragState.dragging = true;
        miniBarDragState.pointerId = e.pointerId;
        miniBarDragState.startX = e.clientX;
        miniBarDragState.startY = e.clientY;
        miniBarDragState.originLeft = rect.left;
        miniBarDragState.originTop = rect.top;
        miniBarDragState.moved = false;

        miniBar.style.left = `${rect.left}px`;
        miniBar.style.top = `${rect.top}px`;
        miniBar.style.cursor = 'grabbing';
        dragHandle.style.cursor = 'grabbing';

        try {
          miniBar.setPointerCapture(e.pointerId);
        } catch (err) {}
      });

      miniBar.addEventListener('pointermove', (e) => {
        if (!miniBarDragState.dragging) return;
        if (miniBarDragState.pointerId !== e.pointerId) return;

        const dx = e.clientX - miniBarDragState.startX;
        const dy = e.clientY - miniBarDragState.startY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
          miniBarDragState.moved = true;
        }

        const maxLeft = Math.max(0, window.innerWidth - miniBar.offsetWidth - 8);
        const maxTop = Math.max(0, window.innerHeight - miniBar.offsetHeight - 8);
        const nextLeft = Math.min(Math.max(miniBarDragState.originLeft + dx, 8), maxLeft);
        const nextTop = Math.min(Math.max(miniBarDragState.originTop + dy, 8), maxTop);

        miniBar.style.left = `${nextLeft}px`;
        miniBar.style.top = `${nextTop}px`;
      });

      const endDrag = (e) => {
        if (!miniBarDragState.dragging) return;
        if (miniBarDragState.pointerId !== e.pointerId) return;

        miniBarDragState.dragging = false;
        miniBarDragState.pointerId = null;
        miniBar.style.cursor = isMiniBarDragEnabled() ? 'grab' : '';
        const dragHandle = miniBar.querySelector('[data-action="mini-drag-handle"]');
        if (dragHandle) {
          dragHandle.style.cursor = isMiniBarDragEnabled() ? 'grab' : 'default';
        }

        try {
          miniBar.releasePointerCapture(e.pointerId);
        } catch (err) {}

        if (miniBarDragState.moved) {
          miniBarDragSuppressClickUntil = Date.now() + 220;
          const rect = miniBar.getBoundingClientRect();
          saveMiniBarPosition(rect.left, rect.top);
        }
      };

      miniBar.addEventListener('pointerup', endDrag);
      miniBar.addEventListener('pointercancel', endDrag);

      applyMiniBarDragAvailability();
      return true;
    };

    if (!tryBind()) {
      window.addEventListener('DOMContentLoaded', () => {
        tryBind();
      }, { once: true });
    }

    window.addEventListener('resize', () => {
      applyMiniBarDragAvailability();
    });
  }

  function setViewMode(mode, options = {}) {
    const skipMiniReposition = !!(options && options.skipMiniReposition);
    const modal = document.getElementById('audio-player-modal');
    const miniBar = document.getElementById('audio-player-mini-bar');
    const rightExpandButton = document.getElementById('audio-mini-right-expand');
    let normalizedMode = (mode === 'full' || mode === 'mini') ? mode : 'hidden';

    if (normalizedMode === 'mini' && !isMiniBarFeatureEnabled()) {
      normalizedMode = 'hidden';
    }

    setCurrentViewMode(normalizedMode);

    if (modal) {
      modal.style.display = normalizedMode === 'full' ? 'block' : 'none';
    }

    if (miniBar) {
      miniBar.style.display = normalizedMode === 'mini' ? 'block' : 'none';
      if (normalizedMode !== 'mini') {
        miniBar.style.transform = 'translateX(0)';
      }
      if (!skipMiniReposition && normalizedMode === 'mini' && isMiniBarDragEnabled()) {
        if (!miniBar.style.left || !miniBar.style.left.endsWith('px')) {
          applySavedMiniBarPosition(miniBar);
        }
      }
    }

    if (rightExpandButton && normalizedMode !== 'mini') {
      rightExpandButton.style.display = 'none';
    }

    if (!skipMiniReposition) {
      applyMiniBarDragAvailability();
    }
    applyMiniBarCollapsedState();

    document.body.style.overflow = normalizedMode === 'full' ? 'hidden' : '';
  }

  function applyAudioMiniPlayerMode(mode) {
    const prevMode = getConfiguredMiniPlayerMode();
    const nextMode = (mode === 'right_dock') ? 'right_dock' : 'mini';

    if (typeof window !== 'undefined') {
      window.__audioMiniPlayerMode = nextMode;
    }

    const miniBar = document.getElementById('audio-player-mini-bar');
    if (miniBar && prevMode === 'right_dock' && nextMode === 'mini') {
      // right_dock에서 사용하던 우측 고정/슬라이드 상태를 제거한다.
      miniBarCollapsed = false;
      saveMiniBarCollapsedState(false);
      miniBar.style.transform = 'translateX(0)';
      miniBar.style.right = '';
      miniBar.style.bottom = '';
      resetMiniBarPosition(miniBar);
    }

    miniBarCollapsed = loadMiniBarCollapsedState();
    applyMiniBarDragAvailability();
    applyMiniBarCollapsedState();

    if (getCurrentViewMode() === 'mini') {
      setViewMode('mini');
    }
  }

  function updateMiniPlayerUi() {
    const miniBar = document.getElementById('audio-player-mini-bar');
    const audiobookData = getAudiobookData();
    if (!miniBar || !audiobookData) return;

    const meta = audiobookData.meta || {};
    const tracks = audiobookData.tracks || [];
    const track = tracks[getCurrentTrackIndex()] || null;

    const titleEl = document.getElementById('audio-mini-title');
    const subtitleEl = document.getElementById('audio-mini-subtitle');
    const coverEl = document.getElementById('audio-mini-cover');
    const coverPlaceholder = document.getElementById('audio-mini-cover-placeholder');
    const progressEl = document.getElementById('audio-mini-progress');
    const trackFooterEl = document.getElementById('audio-mini-track-footer');
    const trackListEl = document.getElementById('audio-mini-track-list');

    if (titleEl) titleEl.textContent = meta.series_name || '오디오북';
    if (subtitleEl) subtitleEl.textContent = track ? (track.title || `Track ${track.track_number || getCurrentTrackIndex() + 1}`) : (meta.author || 'BookOasis');

    if (trackFooterEl) {
      if (track) {
        const trackNo = Number(track.track_number) > 0 ? Number(track.track_number) : (getCurrentTrackIndex() + 1);
        const totalTracks = tracks.length > 0 ? tracks.length : trackNo;
        const trackTitle = track.title || `Track ${trackNo}`;
        trackFooterEl.textContent = `트랙 ${trackNo}/${totalTracks} · ${trackTitle}`;
      } else {
        trackFooterEl.textContent = '트랙 정보 없음';
      }
    }

    if (trackListEl) {
      if (isRightDockMiniPlayerMode() && tracks.length > 0) {
        renderMiniTrackList(trackListEl, tracks, track);
        updateMiniTrackProgressBars(trackListEl, tracks, meta, track);
      } else {
        trackListEl.innerHTML = '';
        miniTrackListRenderKey = '';
        miniTrackListActiveId = null;
      }
    }

    if (coverEl && coverPlaceholder) {
      if (meta.cover_image) {
        coverEl.src = meta.cover_image;
        coverEl.style.display = 'block';
        coverPlaceholder.style.display = 'none';
        coverEl.onerror = () => {
          coverEl.style.display = 'none';
          coverPlaceholder.style.display = 'inline-flex';
        };
      } else {
        coverEl.style.display = 'none';
        coverPlaceholder.style.display = 'inline-flex';
      }
    }

    if (progressEl) {
      const duration = getEffectiveTrackDuration();
      const audioInstance = getAudioInstance();
      const cur = audioInstance ? Number(audioInstance.currentTime || 0) : 0;
      const pct = duration > 0 ? Math.max(0, Math.min(100, (cur / duration) * 100)) : 0;
      progressEl.style.width = `${pct}%`;
    }

    const audioInstance = getAudioInstance();
    const isPlaying = !!(audioInstance && !audioInstance.paused && !audioInstance.ended);
    updatePlaybackToggleButtons(isPlaying);
  }

  function toggleMiniPeek() {
    if (!isRightDockMiniPlayerMode()) return;
    miniBarCollapsed = !miniBarCollapsed;
    saveMiniBarCollapsedState(miniBarCollapsed);
    applyMiniBarCollapsedState();
  }

  function shouldSuppressOpenFull() {
    return Date.now() < miniBarDragSuppressClickUntil;
  }

  function revealIfCollapsed() {
    if (getCurrentViewMode() === 'mini' && miniBarCollapsed) {
      miniBarCollapsed = false;
      saveMiniBarCollapsedState(false);
      applyMiniBarCollapsedState();
      return true;
    }
    return false;
  }

  function markExpandGuard() {
    audioExpandGuardUntil = Date.now() + 300;
  }

  function shouldBlockClose() {
    return Date.now() < audioExpandGuardUntil;
  }

  function init() {
    initMiniBarDrag();
    miniBarCollapsed = loadMiniBarCollapsedState();
    applyMiniBarCollapsedState();
  }

  return {
    init,
    isMiniBarFeatureEnabled,
    setViewMode,
    applyAudioMiniPlayerMode,
    updateMiniPlayerUi,
    toggleMiniPeek,
    shouldSuppressOpenFull,
    revealIfCollapsed,
    markExpandGuard,
    shouldBlockClose
  };
}
