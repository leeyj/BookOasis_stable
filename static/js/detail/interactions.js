export function bindDetailInteractions() {
  if (window.__detailRenderDelegationBound) {
    return;
  }

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="detail-genre-filter"], [data-role="detail-tag-filter"], [data-role="detail-collapse-toggle"], [data-role="detail-rescan-missing"], [data-role="detail-unlock-metadata"], [data-role="detail-cover-upload"], [data-role="detail-series-favorite"], [data-role="detail-edit-toggle"], [data-role="detail-plugin-meta-search"], [data-role="detail-rescan-series"], [data-role="detail-save-meta"], [data-role="detail-cancel-meta"], [data-role="detail-volume-filter"], [data-role="detail-volume-sort"], [data-role="detail-summary-toggle"], [data-role="detail-continue"], [data-role="detail-book-favorite"], [data-role="detail-rescan-book"], [data-role="detail-audio-open"], [data-role="detail-audio-play"], [data-role="detail-audio-tab"], [data-role="detail-volume-open-reader"], [data-role="detail-download-link"]')
      : null;
    if (!target) return;

    event.preventDefault();
    const role = target.getAttribute('data-role');

    if (role === 'detail-genre-filter') {
      return window.quickFilterByGenre?.(target.getAttribute('data-genre') || '');
    }
    if (role === 'detail-tag-filter') {
      return window.quickFilterByTag?.(target.getAttribute('data-tag') || '');
    }
    if (role === 'detail-collapse-toggle') {
      target.style.display = 'none';
      const next = target.nextElementSibling;
      if (next) next.style.display = 'inline-flex';
      return;
    }
    if (role === 'detail-rescan-missing') {
      return window.rescanMissingBooks?.(event, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '');
    }
    if (role === 'detail-unlock-metadata') {
      const bookIdRaw = target.getAttribute('data-book-id') || '';
      const bookId = bookIdRaw ? Number.parseInt(bookIdRaw, 10) : null;
      return window.handleUnlockMetadataEvent?.(event, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '', Number.isFinite(bookId) ? bookId : null);
    }
    if (role === 'detail-cover-upload') {
      return window.triggerCoverUpload?.(event);
    }
    if (role === 'detail-series-favorite') {
      const nextStatus = Number.parseInt(target.getAttribute('data-next-status') || '0', 10) || 0;
      return window.toggleSeriesFavorite?.(event, target.getAttribute('data-series-name') || '', nextStatus, target.getAttribute('data-library-id') || '');
    }
    if (role === 'detail-edit-toggle' || role === 'detail-cancel-meta') {
      return window.toggleMetaEditMode?.();
    }
    if (role === 'detail-plugin-meta-search') {
      const firstBookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      if (Number.isFinite(firstBookId) && firstBookId > 0) {
        return window.openMetadataSearchModal?.(firstBookId, target.getAttribute('data-series-name') || '', true);
      }
      return;
    }
    if (role === 'detail-rescan-series') {
      return window.rescanSeries?.(event, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '');
    }
    if (role === 'detail-save-meta') {
      return window.saveManualMetadata?.(target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '');
    }
    if (role === 'detail-volume-filter') {
      return window.toggleDetailUnreadFilter?.();
    }
    if (role === 'detail-volume-sort') {
      return window.setDetailVolumeSort?.(target.getAttribute('data-sort') || 'oldest');
    }
    if (role === 'detail-summary-toggle') {
      const wrap = target.closest('.book-summary-wrap');
      if (!wrap) return;
      const p = wrap.querySelector('.book-summary-text');
      if (!p) return;
      const expanded = p.classList.toggle('is-expanded');
      p.classList.toggle('is-collapsed', !expanded);
      wrap.classList.toggle('summary-expanded', expanded);
      target.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      target.textContent = expanded ? (target.getAttribute('data-less-label') || '접기') : (target.getAttribute('data-more-label') || '더보기');
      return;
    }
    if (role === 'detail-continue') {
      const action = target.getAttribute('data-continue-action');
      if (action === 'audio') {
        const aid = Number.parseInt(target.getAttribute('data-audiobook-id') || '', 10);
        const trackId = Number.parseInt(target.getAttribute('data-track-id') || '', 10);
        const startTime = Number(target.getAttribute('data-start-time') || '0') || 0;
        if (Number.isFinite(aid) && aid > 0) {
          return window.openAudioPlayer?.(aid, Number.isFinite(trackId) ? trackId : null, startTime);
        }
        return;
      }
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      const pagesRead = Number(target.getAttribute('data-pages-read') || '0') || 0;
      const totalPages = Number(target.getAttribute('data-total-pages') || '0') || 0;
      if (Number.isFinite(bookId) && bookId > 0) {
        return window.openReader?.(bookId, target.getAttribute('data-file-format') || '', target.getAttribute('data-book-title') || '', pagesRead, totalPages);
      }
      return;
    }
    if (role === 'detail-book-favorite') {
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      const nextStatus = Number.parseInt(target.getAttribute('data-next-status') || '0', 10) || 0;
      if (Number.isFinite(bookId) && bookId > 0) {
        return window.toggleBookFavorite?.(event, bookId, nextStatus, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '');
      }
      return;
    }
    if (role === 'detail-rescan-book') {
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      if (Number.isFinite(bookId) && bookId > 0) {
        return window.rescanBook?.(event, bookId, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || '');
      }
      return;
    }
    if (role === 'detail-audio-open' || role === 'detail-audio-play') {
      const aid = Number.parseInt(target.getAttribute('data-audiobook-id') || '', 10);
      const trackId = Number.parseInt(target.getAttribute('data-track-id') || '', 10);
      if (Number.isFinite(aid) && aid > 0 && Number.isFinite(trackId) && trackId > 0) {
        return window.openAudioPlayer?.(aid, trackId, 0);
      }
      return;
    }
    if (role === 'detail-audio-tab') {
      const root = target.closest('.ab-volumes-shell');
      const pane = target.getAttribute('data-target') || 'chapters';
      if (!root) return;
      root.querySelectorAll('.ab-tab-btn').forEach((buttonEl) => buttonEl.classList.remove('active'));
      root.querySelectorAll('.ab-tab-pane').forEach((paneEl) => paneEl.classList.remove('active'));
      target.classList.add('active');
      root.querySelector(`.ab-tab-pane[data-pane="${pane}"]`)?.classList.add('active');
      return;
    }
    if (role === 'detail-volume-open-reader') {
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      const pagesRead = Number(target.getAttribute('data-pages-read') || '0') || 0;
      const totalPages = Number(target.getAttribute('data-total-pages') || '0') || 0;
      if (Number.isFinite(bookId) && bookId > 0) {
        return window.openReader?.(bookId, target.getAttribute('data-file-format') || '', target.getAttribute('data-book-title') || '', pagesRead, totalPages);
      }
      return;
    }
    if (role === 'detail-download-link') {
      event.stopPropagation();
      return;
    }
  }, true);

  document.addEventListener('change', (event) => {
    const target = event && event.target;
    if (!target || !(target.matches instanceof Function)) return;
    if (!target.matches('[data-role="detail-cover-file-input"]')) return;
    window.handleCoverUploadSelect?.(event);
  }, true);

  document.addEventListener('touchstart', (event) => {
    const card = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.volume-card, .vol-grid-card')
      : null;
    if (!card) return;
    const title = card.getAttribute('data-title') || '';
    const bookId = Number.parseInt(card.getAttribute('data-book-id') || '', 10);
    if (!Number.isFinite(bookId) || bookId <= 0) return;
    if (typeof window.handleLongPressTouchStart === 'function') {
      window.handleLongPressTouchStart(event, (x, y) => {
        if (typeof window.showBookContextMenu === 'function') {
          window.showBookContextMenu(x, y, bookId, title, true);
        }
      });
    }
  }, { passive: true, capture: true });

  document.addEventListener('touchmove', (event) => {
    const card = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.volume-card, .vol-grid-card')
      : null;
    if (!card) return;
    window.handleLongPressTouchMove?.(event);
  }, { passive: true, capture: true });

  const endTouchHandler = (event) => {
    const card = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('.volume-card, .vol-grid-card')
      : null;
    if (!card) return;
    window.handleLongPressTouchEnd?.(event);
  };
  document.addEventListener('touchend', endTouchHandler, { capture: true });
  document.addEventListener('touchcancel', endTouchHandler, { capture: true });

  window.__detailRenderDelegationBound = true;
}