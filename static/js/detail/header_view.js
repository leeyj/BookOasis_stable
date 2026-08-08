import { buildFallbackCoverUrl, getBookCoverSrc } from '../cover_fallback.js';
import { state } from '../state.js';
import { stripLeadingBracketTags } from '../series_display.js';

function normalizeMetadataToken(token) {
  if (!token) return '';
  return String(token)
    .replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

export function renderDetailHeader(meta, books, safeSeriesName, actualLibraryId, displayTitle = '') {
  let visibleTitle = stripLeadingBracketTags(String(displayTitle || '').trim() || safeSeriesName);

  const toSeriesLikeTitle = (rawTitle) => {
    let text = String(rawTitle || '').trim();
    if (!text) return '';
    if (safeSeriesName) {
      const escapedSeries = safeSeriesName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(new RegExp(`^\\[\\s*${escapedSeries}\\s*\\]\\s*`, 'i'), '').trim();
    }
    const trimmed = text
      .replace(/\s*[-:|]\s*\d+\s*(권|화|부|편)$/i, '')
      .replace(/\s+제?\d+\s*(권|화|부|편)$/i, '')
      .replace(/\s+\d+\s*(권|화|부|편)$/i, '')
      .trim();
    return stripLeadingBracketTags(trimmed || text);
  };

  if ((!displayTitle || !String(displayTitle).trim()) && books && books.length > 0 && safeSeriesName) {
    const firstTitle = String(books[0].title || '').trim();
    if (firstTitle) {
      const escapedSeries = safeSeriesName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const bracketPrefix = new RegExp(`^\\[\\s*${escapedSeries}\\s*\\]\\s*(.+)$`, 'i');
      const match = firstTitle.match(bracketPrefix);
      if (match && match[1] && match[1].trim()) {
        visibleTitle = toSeriesLikeTitle(match[1].trim());
      }
    }
  }
  const firstBookId = books.length > 0 ? books[0].id : null;
  const headerFormat = books.length > 0 ? books[0].file_format : 'text';
  buildFallbackCoverUrl({
    title: visibleTitle,
    format: headerFormat,
    seed: `${actualLibraryId}:${safeSeriesName}`
  });
  const coverSrc = getBookCoverSrc({
    coverImage: meta.cover_image,
    title: visibleTitle,
    format: headerFormat,
    seed: `${actualLibraryId}:${safeSeriesName}`
  });
  const normalizedScore = Number.isFinite(Number(meta.score)) ? Number(meta.score) : 0;
  const clampedScore = Math.max(0, Math.min(100, normalizedScore));
  const starCount = Math.max(0, Math.min(5, Math.round(clampedScore / 20)));
  const stars = '★'.repeat(starCount) + '☆'.repeat(5 - starCount);
  const linkHtml = meta.link
    ? `<a href="${meta.link}" target="_blank" class="ridi-link-btn">${i18n.t('detail.ridi_link')}</a>`
    : '';

  const genresArr = (meta.genre || '')
    .split(',')
    .map((genre) => normalizeMetadataToken(genre))
    .filter((genre) => genre)
    .filter((genre, idx, arr) => arr.indexOf(genre) === idx);

  const tagsArr = (meta.tags || '')
    .split(',')
    .map((tag) => normalizeMetadataToken(tag))
    .filter((tag) => tag)
    .filter((tag, idx, arr) => arr.indexOf(tag) === idx);

  const shouldCollapse = state.collapseDetailGenreTags === true;

  let genreRowHtml = '';
  if (genresArr.length > 0) {
    const visibleGenres = shouldCollapse ? genresArr.slice(0, 1) : genresArr;
    const hiddenGenres = shouldCollapse ? genresArr.slice(1) : [];

    const visibleItemsHtml = visibleGenres.map((genre) => `
      <span class="badge" data-role="detail-genre-filter" data-genre="${genre.replace(/"/g, '&quot;')}" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;">
        <i class="fa-solid fa-tag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${genre}
      </span>
    `).join('');

    const hiddenItemsHtml = hiddenGenres.map((genre) => `
      <span class="badge" data-role="detail-genre-filter" data-genre="${genre.replace(/"/g, '&quot;')}" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;">
        <i class="fa-solid fa-tag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${genre}
      </span>
    `).join('');

    const toggleBtnHtml = hiddenGenres.length > 0 ? `
      <span class="badge collapse-toggle-btn" data-role="detail-collapse-toggle" style="background: rgba(59, 130, 246, 0.25); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.5); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; font-weight: bold;" title="클릭하여 전체 장르 펼치기">
        +${hiddenGenres.length}
      </span>
      <span class="hidden-genres-wrap" style="display: none; gap: 0.4rem; flex-wrap: wrap;">${hiddenItemsHtml}</span>
    ` : '';

    genreRowHtml = `
      <div class="detail-genre-row" style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
        <span style="font-size: 0.8rem; font-weight: 700; color: #94a3b8; margin-right: 0.2rem;">장르:</span>
        ${visibleItemsHtml}
        ${toggleBtnHtml}
      </div>
    `;
  }

  let tagRowHtml = '';
  if (tagsArr.length > 0) {
    const visibleTags = shouldCollapse ? tagsArr.slice(0, 1) : tagsArr;
    const hiddenTags = shouldCollapse ? tagsArr.slice(1) : [];

    const visibleItemsHtml = visibleTags.map((tag) => `
      <span class="badge" data-role="detail-tag-filter" data-tag="${tag.replace(/"/g, '&quot;')}" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;">
        <i class="fa-solid fa-hashtag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${tag}
      </span>
    `).join('');

    const hiddenItemsHtml = hiddenTags.map((tag) => `
      <span class="badge" data-role="detail-tag-filter" data-tag="${tag.replace(/"/g, '&quot;')}" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;">
        <i class="fa-solid fa-hashtag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${tag}
      </span>
    `).join('');

    const toggleBtnHtml = hiddenTags.length > 0 ? `
      <span class="badge collapse-toggle-btn" data-role="detail-collapse-toggle" style="background: rgba(16, 185, 129, 0.25); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.5); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; font-weight: bold;" title="클릭하여 전체 태그 펼치기">
        +${hiddenTags.length}
      </span>
      <span class="hidden-tags-wrap" style="display: none; gap: 0.4rem; flex-wrap: wrap;">${hiddenItemsHtml}</span>
    ` : '';

    tagRowHtml = `
      <div class="detail-tag-row" style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
        <span style="font-size: 0.8rem; font-weight: 700; color: #94a3b8; margin-right: 0.2rem;">태그:</span>
        ${visibleItemsHtml}
        ${toggleBtnHtml}
      </div>
    `;
  }

  const missingPageBooks = books.filter((book) => {
    const isZip = ['zip', 'cbz'].includes((book.file_format || '').toLowerCase());
    const filePathLower = (book.file_path || '').toLowerCase();
    const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
    const isRemote = remoteKeywords.some((keyword) => filePathLower.includes(keyword));
    const totalPages = Number(book.total_pages) || 0;
    const hasOffsets = Number(book.has_offsets) || 0;
    return isZip && !isRemote && (totalPages === 0 && hasOffsets === 0);
  });
  const missingPageCount = missingPageBooks.length;
  const missingPageBannerHtml = missingPageCount > 0 ? `
      <div class="vol-warn-banner" style="margin-top: 1rem;">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>${i18n.t('detail.warn_series_missing_pages', { count: missingPageCount })}</span>
        <button class="btn-rescan-book" data-role="detail-rescan-missing" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}">
          <i class="fa-solid fa-rotate"></i> ${i18n.t('detail.btn_rescan_all')}
        </button>
      </div>
    ` : '';

  const isSeriesFav = books.some((book) => book.is_favorite === 1);
  const seriesFavIconClass = isSeriesFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
  const seriesFavIconColor = isSeriesFav ? '#eab308' : '#64748b';

  let continueTarget = null;
  let continueReason = 'first';

  const firstFmt = books.length > 0 ? String(books[0].file_format || '').toLowerCase() : '';
  const isAudiobookLib = state.currentLibraryType === 'audiobook' || ['audiobook', 'mp3', 'm4a', 'm4b', 'flac', 'aac', 'wav', 'ogg', 'opus', 'wma'].includes(firstFmt);

  let hasAudioProgress = false;
  if (isAudiobookLib && meta) {
    const curTime = Number(meta.current_time || 0);
    const totalPct = Number(meta.total_progress_pct || 0);
    if (curTime > 0 || totalPct > 0 || meta.current_track_id || Number(meta.is_completed) === 1) {
      hasAudioProgress = true;
      continueReason = 'in-progress';
      if (meta.current_track_id && books && books.length > 0) {
        continueTarget = books.find((b) => Number(b.id) === Number(meta.current_track_id));
      }
      if (!continueTarget && books && books.length > 0) {
        continueTarget = books[0];
      }
    }
  }

  if (!continueTarget && books && books.length > 0) {
    const inProgressBooks = books.filter((book) => book.pages_read > 0 && book.is_completed === 0);
    if (inProgressBooks.length > 0) {
      inProgressBooks.sort((left, right) => new Date(right.last_read_at || 0) - new Date(left.last_read_at || 0));
      continueTarget = inProgressBooks[0];
      continueReason = 'in-progress';
    }

    if (!continueTarget) {
      const readBooks = books.filter((book) => book.last_read_at);
      if (readBooks.length > 0) {
        readBooks.sort((left, right) => new Date(right.last_read_at || 0) - new Date(left.last_read_at || 0));
        continueTarget = readBooks[0];
        continueReason = 'recent';
      }
    }

    if (!continueTarget) {
      continueTarget = books[0];
      continueReason = 'first';
    }
  }

  let continueBtnHtml = '';
  if (continueTarget) {
    let btnLabel = '';
    let btnColor = '#7c3aed';
    let btnBorder = '#a855f7';
    let iconClass = 'fa-solid fa-play';
    const continueFmt = String(continueTarget.file_format || '').toLowerCase();
    const isAudioContext = state.currentLibraryType === 'audiobook' || ['audiobook', 'mp3', 'm4a', 'm4b', 'flac', 'aac', 'wav', 'ogg', 'opus', 'wma'].includes(continueFmt);

    let progressPercent = 0;
    if (hasAudioProgress && meta && Number(meta.total_progress_pct) > 0) {
      progressPercent = Math.round(Number(meta.total_progress_pct));
    } else if (continueTarget.pages_read > 0) {
      const format = (continueTarget.file_format || '').toLowerCase();
      if (format === 'epub') {
        progressPercent = continueTarget.pages_read;
      } else if (continueTarget.total_pages > 0) {
        progressPercent = Math.round((continueTarget.pages_read / continueTarget.total_pages) * 100);
      }
    }

    let tooltipTitle = '';
    if (continueReason === 'in-progress') {
      btnLabel = isAudioContext
        ? (i18n.t('detail.continue_listening') || '이어서 듣기')
        : (i18n.t('detail.continue_reading') || '이어서 읽기');
      tooltipTitle = `${continueTarget.title}${progressPercent > 0 ? ` (${progressPercent}%)` : ''}`;
      btnColor = '#8b5cf6';
      btnBorder = '#a78bfa';
      iconClass = isAudioContext ? 'fa-solid fa-headphones' : 'fa-solid fa-play';
    } else if (continueReason === 'recent') {
      btnLabel = isAudioContext
        ? (i18n.t('detail.continue_listening') || '이어서 듣기')
        : (i18n.t('detail.continue_reading') || '이어서 읽기');
      tooltipTitle = continueTarget.title;
      btnColor = '#6d28d9';
      btnBorder = '#8b5cf6';
      iconClass = isAudioContext ? 'fa-solid fa-headphones' : 'fa-solid fa-play';
    } else {
      btnLabel = isAudioContext
        ? (i18n.t('detail.start_listening') || '처음부터 듣기')
        : (i18n.t('detail.start_reading') || '첫 권부터 읽기');
      tooltipTitle = continueTarget.title;
      btnColor = '#10b981';
      btnBorder = '#34d399';
      iconClass = isAudioContext ? 'fa-solid fa-headphones' : 'fa-solid fa-book-open-reader';
    }

    const resumeTrackId = (meta && meta.current_track_id) ? meta.current_track_id : continueTarget.id;
    const resumeStartTime = (meta && Number(meta.current_time) > 0) ? Number(meta.current_time) : (continueTarget.pages_read || 0);
    continueBtnHtml = `
      <button class="ridi-link-btn" style="margin: 0; background: ${btnColor}; border-color: ${btnBorder}; font-weight: bold; color: #fff; display: inline-flex; align-items: center; gap: 0.3rem;" 
              data-role="detail-continue"
              data-continue-action="${isAudioContext ? 'audio' : 'reader'}"
              data-audiobook-id="${(meta && meta.id) ? meta.id : (continueTarget.audiobook_id || continueTarget.id || '')}"
              data-track-id="${resumeTrackId || ''}"
              data-start-time="${resumeStartTime || 0}"
              data-book-id="${continueTarget.id || ''}"
              data-file-format="${(continueTarget.file_format || '').replace(/"/g, '&quot;')}"
              data-book-title="${(continueTarget.title || '').replace(/"/g, '&quot;')}"
              data-pages-read="${continueTarget.pages_read || 0}"
              data-total-pages="${continueTarget.total_pages || 0}"
              title="${tooltipTitle.replace(/"/g, '&quot;')}">
        <i class="${iconClass}"></i> ${btnLabel}
      </button>
    `;
  }

  const isLocked = Number(meta && meta.metadata_locked) === 1 || (books && books.some((book) => Number(book.metadata_locked) === 1));
  const summaryText = meta.summary || i18n.t('detail.no_description');
  const summaryLineBreaks = (String(summaryText).match(/\n/g) || []).length;
  const shouldShowSummaryToggle = String(summaryText).length > 260 || summaryLineBreaks >= 5;
  const summaryToggleLabelMore = i18n.t('detail.summary_more') || '더보기';
  const summaryToggleLabelLess = i18n.t('detail.summary_less') || '접기';
  const isAudiobookContext = state.currentLibraryType === 'audiobook';
  const isAudiobookCompleted = isAudiobookContext && Number(meta.is_completed) === 1;
  const audiobookCompletedBadgeHtml = isAudiobookContext ? `
    <span class="audiobook-completed-badge${isAudiobookCompleted ? ' is-visible' : ''}" data-audiobook-completed="${meta.id || ''}">
      <i class="fa-solid fa-headphones"></i> ${i18n.t('detail.audiobook_completed')}
    </span>
  ` : '';
  const markSeriesCompletedLabel = isAudiobookContext
    ? i18n.t('detail.btn_mark_audiobook_completed')
    : i18n.t('detail.btn_mark_series_completed');
  const markSeriesCompletedBtnHtml = `
    <button class="ridi-link-btn" data-role="detail-mark-series-complete" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" style="margin: 0; background: #16a34a; border-color: #22c55e; display: inline-flex; align-items: center; gap: 0.3rem;"><i class="fa-solid fa-circle-check"></i> ${markSeriesCompletedLabel}</button>
  `;
  const identifierLabel = 'ISBN(WEB_ID)';
  const identifierValue = isAudiobookContext ? (meta.web_id || '-') : (meta.isbn || '-');
  const identifierEditValue = isAudiobookContext ? (meta.web_id || '') : (meta.isbn || '');
  const detailLockedBadgeHtml = isLocked ? `
    <div class="book-card-locked-badge" title="메타데이터 잠김 (수동 편집됨)" style="position: absolute; bottom: 8px; left: 8px; z-index: 5; background: rgba(0, 0, 0, 0.65); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.4); width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.4); backdrop-filter: blur(2px);">
      <i class="fa-solid fa-lock" style="font-size: 0.7rem;"></i>
    </div>
  ` : '';
  const unlockBtnHtml = isLocked ? `
    <button class="ridi-link-btn btn-unlock-metadata" data-role="detail-unlock-metadata" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" data-book-id="${firstBookId || ''}" style="background: #16a34a; border-color: #22c55e; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.3rem;" title="메타데이터 잠금을 해제하고 자동 스캔 갱신을 허용합니다">
      <i class="fa-solid fa-lock-open"></i> 잠금해제
    </button>
  ` : '';

  return `
    <!-- 상단 헤더: 커버(작게) + 메타정보 -->
    <div class="detail-header-panel">
      <div class="detail-cover-container" data-role="detail-cover-dropzone" style="position: relative;">
           <img class="detail-cover-sm" id="detail-cover-img-preview" src="${coverSrc}" alt="Cover" data-title="${(visibleTitle || '').replace(/"/g, '&quot;')}" data-format="${headerFormat}"
              onerror="window.handleCoverError(this)">
        ${detailLockedBadgeHtml}
        <div class="cover-upload-overlay" id="cover-upload-overlay-btn" data-role="detail-cover-upload">
          <i class="fa-solid fa-camera"></i>
          <span>${i18n.t('detail.change_cover')}</span>
        </div>
        <input type="file" id="cover-upload-file-input" data-role="detail-cover-file-input" accept="image/*" style="display: none;">
      </div>
      
      <!-- 뷰어 모드 (일반 노출) -->
      <div id="detail-header-meta-view" class="detail-header-meta">
        <h3 class="book-detail-title" style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
          ${meta.series_alias || visibleTitle}
          ${meta.series_alias ? `<span style="font-size: 0.85rem; color: #94a3b8; font-weight: normal;">(${visibleTitle})</span>` : ''}
          ${audiobookCompletedBadgeHtml}
          <button class="btn-fav-toggle" data-role="detail-series-favorite" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" data-next-status="${isSeriesFav ? 1 : 0}" style="background:none; border:none; color:${seriesFavIconColor}; cursor:pointer; font-size:1.4rem; display:inline-flex; align-items:center;" title="${i18n.t('detail.toggle_fav_series')}">
            <i class="${seriesFavIconClass}"></i>
          </button>
          <button class="ridi-link-btn btn-edit-toggle" data-role="detail-edit-toggle" style="background: #0284c7; border-color: #0ea5e9; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.4rem;">
            <i class="fa-solid fa-pen-to-square"></i> ${i18n.t('detail.edit_info')}
          </button>
          ${unlockBtnHtml}
        </h3>
        <div class="detail-meta">
          <span class="badge">${meta.series_alias || visibleTitle}</span>
          <span class="meta-item"><i class="fa-solid fa-pen-nib"></i> ${meta.author || '-'}</span>
          <span class="meta-item"><i class="fa-solid fa-barcode"></i> ${identifierLabel}: ${identifierValue}</span>
          <span class="meta-item"><i class="fa-solid fa-building"></i> ${meta.publisher || '-'}</span>
          <span class="meta-item"><i class="fa-solid fa-book-open"></i> ${books.length}권</span>
        </div>
        <div class="detail-meta-tags" style="display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem; margin-bottom: 0.8rem;">
          ${genreRowHtml}
          ${tagRowHtml}
        </div>
        ${missingPageBannerHtml}
        <div class="detail-score">${stars}</div>
        <div class="book-summary-wrap${shouldShowSummaryToggle ? ' has-toggle' : ''}">
          <p class="book-summary-text${shouldShowSummaryToggle ? ' is-collapsed' : ''}">${summaryText}</p>
          ${shouldShowSummaryToggle ? `
          <button class="book-summary-toggle" type="button"
            aria-expanded="false"
            data-role="detail-summary-toggle" data-more-label="${summaryToggleLabelMore.replace(/"/g, '&quot;')}" data-less-label="${summaryToggleLabelLess.replace(/"/g, '&quot;')}">${summaryToggleLabelMore}</button>
          ` : ''}
        </div>
        ${linkHtml}
        
        <!-- 버튼: 이어서 읽기 및 메타정보 찾기 -->
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem; flex-wrap: wrap; align-items: center;">
          ${continueBtnHtml}
          <button id="btn-manual-meta-search" class="ridi-link-btn" style="display:none; margin: 0; background: #7c3aed; border-color: #a855f7;"><i class="fa-solid fa-wand-magic-sparkles"></i> ${i18n.t('detail.btn_recommend_match')}</button>
          <button id="btn-plugin-meta-search" class="ridi-link-btn" data-role="detail-plugin-meta-search" data-book-id="${firstBookId || ''}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" style="margin: 0; background: #2563eb; border-color: #3b82f6;"><i class="fa-solid fa-magnifying-glass"></i> ${i18n.t('detail.btn_search_meta')}</button>
          <button class="ridi-link-btn" data-role="detail-rescan-series" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" style="margin: 0; background: #ea580c; border-color: #f97316; display: inline-flex; align-items: center; gap: 0.3rem;"><i class="fa-solid fa-arrows-rotate"></i> ${i18n.t('detail.btn_rescan_series')}</button>
          ${markSeriesCompletedBtnHtml}
        </div>
      </div>

      <!-- 편집 모드 (수동 입력 폼) -->
      <div id="detail-header-meta-edit" class="detail-header-meta" style="display: none;">
        <h3 class="book-detail-title" style="margin-bottom: 0.5rem; font-size: 1.3rem;">${i18n.t('detail.edit_title')} <span style="font-size: 0.8rem; color: #94a3b8; font-weight: normal; margin-left: 0.5rem;">${i18n.t('detail.edit_subtitle')}</span></h3>
        <div class="edit-meta-form-group">
          <div class="edit-meta-row-item">
            <label>시리즈 별칭 (Alias)</label>
            <input type="text" id="edit-series-alias-input" class="edit-meta-input" value="${meta.series_alias || ''}" placeholder="기본 폴더명 대신 표시할 제목">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_author')}</label>
            <input type="text" id="edit-author-input" class="edit-meta-input" value="${meta.author === '-' ? '' : meta.author}">
          </div>
          <div class="edit-meta-row-item">
            <label>${identifierLabel}</label>
            <input type="text" id="edit-isbn-input" class="edit-meta-input" value="${identifierEditValue}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_publisher')}</label>
            <input type="text" id="edit-publisher-input" class="edit-meta-input" value="${meta.publisher === '-' ? '' : meta.publisher}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_ridi_link')}</label>
            <input type="text" id="edit-link-input" class="edit-meta-input" value="${meta.link || ''}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_genre')}</label>
            <input type="text" id="edit-genre-input" class="edit-meta-input" value="${meta.genre || ''}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_tags')}</label>
            <input type="text" id="edit-tags-input" class="edit-meta-input" value="${meta.tags || ''}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_summary')}</label>
            <textarea id="edit-summary-input" class="edit-meta-textarea">${meta.summary === i18n.t('detail.no_description') || meta.summary === '등록된 설명이 없습니다.' ? '' : meta.summary}</textarea>
          </div>
        </div>
        <div class="edit-meta-buttons-row">
          <button class="ridi-link-btn" data-role="detail-save-meta" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" style="background: #22c55e; border-color: #4ade80;">${i18n.t('detail.btn_save')}</button>
          <button class="ridi-link-btn" data-role="detail-cancel-meta" style="background: #64748b; border-color: #94a3b8;">${i18n.t('detail.btn_cancel')}</button>
        </div>
      </div>
      
      <!-- 유사 메타데이터 추천 영역 -->
      <div id="meta-recommend-section" style="display:none; margin-top: 1rem; padding: 1rem; background: rgba(30, 41, 59, 0.5); border: 1px dashed rgba(168, 85, 247, 0.4); border-radius: 8px; width: 100%;">
        <h5 style="margin: 0 0 0.8rem 0; color: #c084fc; font-size: 0.85rem;"><i class="fa-solid fa-wand-magic-sparkles"></i> ${i18n.t('detail.title_recommend')}</h5>
        <div id="recommend-candidates-list" style="display: flex; flex-direction: column; gap: 0.6rem;">
          <div style="font-size:0.75rem; color:#64748b;"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('detail.loading_recommend')}</div>
        </div>
      </div>
    </div>
  `;
}