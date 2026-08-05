// detail_render.js – 도서 상세 화면의 HTML 템플릿 생성기
import { buildFallbackCoverUrl, getBookCoverSrc, buildTextCoverDataUri } from './cover_fallback.js';
import { state } from './state.js';
import { stripLeadingBracketTags, middleTruncateTitle } from './series_display.js';

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
  const headerFallbackCoverSrc = buildFallbackCoverUrl({
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
  const stars = '★'.repeat(Math.round(meta.score / 20)) + '☆'.repeat(5 - Math.round(meta.score / 20));
  const linkHtml = meta.link
    ? `<a href="${meta.link}" target="_blank" class="ridi-link-btn">${i18n.t('detail.ridi_link')}</a>`
    : '';

  const genresArr = (meta.genre || '')
    .split(',')
    .map(g => normalizeMetadataToken(g))
    .filter(g => g)
    .filter((g, idx, arr) => arr.indexOf(g) === idx);

  const tagsArr = (meta.tags || '')
    .split(',')
    .map(t => normalizeMetadataToken(t))
    .filter(t => t)
    .filter((t, idx, arr) => arr.indexOf(t) === idx);

  const shouldCollapse = state.collapseDetailGenreTags === true;

  // 장르 행 구성
  let genreRowHtml = '';
  if (genresArr.length > 0) {
    const visibleGenres = shouldCollapse ? genresArr.slice(0, 1) : genresArr;
    const hiddenGenres = shouldCollapse ? genresArr.slice(1) : [];

    const visibleItemsHtml = visibleGenres.map(g => `
      <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByGenre('${g.replace(/'/g, "\\'")}')">
        <i class="fa-solid fa-tag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${g}
      </span>
    `).join('');

    const hiddenItemsHtml = hiddenGenres.map(g => `
      <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByGenre('${g.replace(/'/g, "\\'")}')">
        <i class="fa-solid fa-tag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${g}
      </span>
    `).join('');

    const toggleBtnHtml = hiddenGenres.length > 0 ? `
      <span class="badge collapse-toggle-btn" onclick="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';" style="background: rgba(59, 130, 246, 0.25); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.5); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; font-weight: bold;" title="클릭하여 전체 장르 펼치기">
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

  // 태그 행 구성
  let tagRowHtml = '';
  if (tagsArr.length > 0) {
    const visibleTags = shouldCollapse ? tagsArr.slice(0, 1) : tagsArr;
    const hiddenTags = shouldCollapse ? tagsArr.slice(1) : [];

    const visibleItemsHtml = visibleTags.map(t => `
      <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByTag('${t.replace(/'/g, "\\'")}')">
        <i class="fa-solid fa-hashtag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${t}
      </span>
    `).join('');

    const hiddenItemsHtml = hiddenTags.map(t => `
      <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByTag('${t.replace(/'/g, "\\'")}')">
        <i class="fa-solid fa-hashtag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${t}
      </span>
    `).join('');

    const toggleBtnHtml = hiddenTags.length > 0 ? `
      <span class="badge collapse-toggle-btn" onclick="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';" style="background: rgba(16, 185, 129, 0.25); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.5); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; font-weight: bold;" title="클릭하여 전체 태그 펼치기">
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

  const missingPageBooks = books.filter(b => {
    const isZip = ['zip', 'cbz'].includes((b.file_format || '').toLowerCase());
    const filePathLower = (b.file_path || '').toLowerCase();
    const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
    const isRemote = remoteKeywords.some(keyword => filePathLower.includes(keyword));
    return isZip && !isRemote && (b.total_pages === 0 || b.has_offsets === 0);
  });
  const missingPageCount = missingPageBooks.length;
  const missingPageBannerHtml = missingPageCount > 0 ? `
      <div class="vol-warn-banner" style="margin-top: 1rem;">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>${i18n.t('detail.warn_series_missing_pages', { count: missingPageCount })}</span>
        <button class="btn-rescan-book" onclick="rescanMissingBooks(event, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')">
          <i class="fa-solid fa-rotate"></i> ${i18n.t('detail.btn_rescan_all')}
        </button>
      </div>
    ` : '';

  const isSeriesFav = books.some(b => b.is_favorite === 1);
  const seriesFavIconClass = isSeriesFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
  const seriesFavIconColor = isSeriesFav ? '#eab308' : '#64748b';

  // ── [이어서 읽기 책 탐색 알고리즘] ──
  let continueTarget = null;
  let continueReason = 'first'; // 'in-progress', 'recent', 'first'

  if (books && books.length > 0) {
    // 1순위: 읽는 중인 책 ( pages_read > 0 이며 is_completed = 0 )
    // 그 중 가장 최근 읽은 시간(last_read_at)이 최신인 책
    const inProgressBooks = books.filter(b => b.pages_read > 0 && b.is_completed === 0);
    if (inProgressBooks.length > 0) {
      inProgressBooks.sort((a, b) => new Date(b.last_read_at || 0) - new Date(a.last_read_at || 0));
      continueTarget = inProgressBooks[0];
      continueReason = 'in-progress';
    }

    // 2순위: 완료 상태를 포함하여 최근 읽은 기록(last_read_at)이 존재하는 최신 도서
    if (!continueTarget) {
      const readBooks = books.filter(b => b.last_read_at);
      if (readBooks.length > 0) {
        readBooks.sort((a, b) => new Date(b.last_read_at || 0) - new Date(a.last_read_at || 0));
        continueTarget = readBooks[0];
        continueReason = 'recent';
      }
    }

    // 3순위: 아무 기록도 없으면 리스트의 첫 번째 도서
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

    // 진행도 퍼센트 구하기
    let progressPercent = 0;
    if (continueTarget.pages_read > 0) {
      const fmt = (continueTarget.file_format || '').toLowerCase();
      if (fmt === 'epub') {
        progressPercent = continueTarget.pages_read;
      } else if (continueTarget.total_pages > 0) {
        progressPercent = Math.round((continueTarget.pages_read / continueTarget.total_pages) * 100);
      }
    }

    let tooltipTitle = '';
    if (continueReason === 'in-progress') {
      btnLabel = i18n.t('detail.continue_reading') || '이어서 읽기';
      tooltipTitle = `${continueTarget.title} (${progressPercent}%)`;
      btnColor = '#8b5cf6';
      btnBorder = '#a78bfa';
    } else if (continueReason === 'recent') {
      btnLabel = i18n.t('detail.continue_reading') || '이어서 읽기';
      tooltipTitle = continueTarget.title;
      btnColor = '#6d28d9';
      btnBorder = '#8b5cf6';
    } else {
      btnLabel = isAudioContext
        ? (i18n.t('detail.start_listening') || '처음부터 듣기')
        : (i18n.t('detail.start_reading') || '첫 권부터 읽기');
      tooltipTitle = continueTarget.title;
      btnColor = '#10b981';
      btnBorder = '#34d399';
      iconClass = 'fa-solid fa-book-open-reader';
    }

    const resumeTrackId = (meta && meta.current_track_id) ? meta.current_track_id : continueTarget.id;
    const resumeStartTime = (meta && Number(meta.current_time) > 0) ? Number(meta.current_time) : (continueTarget.pages_read || 0);
    const continueOnClick = isAudioContext
      ? `window.openAudioPlayer(${(meta && meta.id) ? meta.id : (continueTarget.audiobook_id || continueTarget.id)}, ${resumeTrackId}, ${resumeStartTime})`
      : `window.openReader(${continueTarget.id}, '${continueTarget.file_format}', '${continueTarget.title.replace(/'/g, "\\'")}', ${continueTarget.pages_read || 0}, ${continueTarget.total_pages || 0})`;

    continueBtnHtml = `
      <button class="ridi-link-btn" style="margin: 0; background: ${btnColor}; border-color: ${btnBorder}; font-weight: bold; color: #fff; display: inline-flex; align-items: center; gap: 0.3rem;" 
              title="${tooltipTitle.replace(/"/g, '&quot;')}"
              onclick="${continueOnClick}">
        <i class="${iconClass}"></i> ${btnLabel}
      </button>
    `;
  }

  const isLocked = Number(meta && meta.metadata_locked) === 1 || (books && books.some(b => Number(b.metadata_locked) === 1));
  const summaryText = meta.summary || i18n.t('detail.no_description');
  const summaryLineBreaks = (String(summaryText).match(/\n/g) || []).length;
  const shouldShowSummaryToggle = String(summaryText).length > 260 || summaryLineBreaks >= 5;
  const summaryToggleLabelMore = i18n.t('detail.summary_more') || '더보기';
  const summaryToggleLabelLess = i18n.t('detail.summary_less') || '접기';
  const isAudiobookContext = state.currentLibraryType === 'audiobook';
  const identifierLabel = 'ISBN(WEB_ID)';
  const identifierValue = isAudiobookContext ? (meta.web_id || '-') : (meta.isbn || '-');
  const identifierEditValue = isAudiobookContext ? (meta.web_id || '') : (meta.isbn || '');
  const detailLockedBadgeHtml = isLocked ? `
    <div class="book-card-locked-badge" title="메타데이터 잠김 (수동 편집됨)" style="position: absolute; bottom: 8px; left: 8px; z-index: 5; background: rgba(0, 0, 0, 0.65); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.4); width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.4); backdrop-filter: blur(2px);">
      <i class="fa-solid fa-lock" style="font-size: 0.7rem;"></i>
    </div>
  ` : '';
  const unlockBtnHtml = isLocked ? `
    <button class="ridi-link-btn btn-unlock-metadata" onclick="handleUnlockMetadataEvent(event, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}', ${firstBookId || 'null'})" style="background: #16a34a; border-color: #22c55e; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.3rem;" title="메타데이터 잠금을 해제하고 자동 스캔 갱신을 허용합니다">
      <i class="fa-solid fa-lock-open"></i> 잠금해제
    </button>
  ` : '';

  return `
    <!-- 상단 헤더: 커버(작게) + 메타정보 -->
    <div class="detail-header-panel">
      <div class="detail-cover-container" style="position: relative;" 
           ondragover="event.preventDefault(); this.style.borderColor='#a855f7';" 
           ondragleave="this.style.borderColor='rgba(255,255,255,0.08)';" 
           ondrop="handleCoverDrop(event); this.style.borderColor='rgba(255,255,255,0.08)';">
           <img class="detail-cover-sm" id="detail-cover-img-preview" src="${coverSrc}" alt="Cover" data-title="${(visibleTitle || '').replace(/"/g, '&quot;')}" data-format="${headerFormat}"
              onerror="window.handleCoverError(this)">
        ${detailLockedBadgeHtml}
        <div class="cover-upload-overlay" id="cover-upload-overlay-btn" onclick="triggerCoverUpload(event)">
          <i class="fa-solid fa-camera"></i>
          <span>${i18n.t('detail.change_cover')}</span>
        </div>
        <input type="file" id="cover-upload-file-input" accept="image/*" style="display: none;" onchange="handleCoverUploadSelect(event)">
      </div>
      
      <!-- 뷰어 모드 (일반 노출) -->
      <div id="detail-header-meta-view" class="detail-header-meta">
        <h3 class="book-detail-title" style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
          ${meta.series_alias || visibleTitle}
          ${meta.series_alias ? `<span style="font-size: 0.85rem; color: #94a3b8; font-weight: normal;">(${visibleTitle})</span>` : ''}
          <button class="btn-fav-toggle" onclick="toggleSeriesFavorite(event, '${safeSeriesName.replace(/'/g, "\\'")}', ${isSeriesFav ? 1 : 0}, '${actualLibraryId}')" style="background:none; border:none; color:${seriesFavIconColor}; cursor:pointer; font-size:1.4rem; display:inline-flex; align-items:center;" title="${i18n.t('detail.toggle_fav_series')}">
            <i class="${seriesFavIconClass}"></i>
          </button>
          <button class="ridi-link-btn btn-edit-toggle" onclick="toggleMetaEditMode()" style="background: #0284c7; border-color: #0ea5e9; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.4rem;">
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
            onclick="(function(btn){const wrap=btn.closest('.book-summary-wrap');if(!wrap)return;const p=wrap.querySelector('.book-summary-text');if(!p)return;const expanded=p.classList.toggle('is-expanded');p.classList.toggle('is-collapsed', !expanded);wrap.classList.toggle('summary-expanded', expanded);btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');btn.textContent=expanded?'${summaryToggleLabelLess}':'${summaryToggleLabelMore}';})(this)">${summaryToggleLabelMore}</button>
          ` : ''}
        </div>
        ${linkHtml}
        
        <!-- 버튼: 이어서 읽기 및 메타정보 찾기 -->
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem; flex-wrap: wrap; align-items: center;">
          ${continueBtnHtml}
          <button id="btn-manual-meta-search" class="ridi-link-btn" style="display:none; margin: 0; background: #7c3aed; border-color: #a855f7;"><i class="fa-solid fa-wand-magic-sparkles"></i> ${i18n.t('detail.btn_recommend_match')}</button>
          <button id="btn-plugin-meta-search" class="ridi-link-btn" onclick="openMetadataSearchModal(${firstBookId}, '${safeSeriesName.replace(/'/g, "\\'")}', true)" style="margin: 0; background: #2563eb; border-color: #3b82f6;"><i class="fa-solid fa-magnifying-glass"></i> ${i18n.t('detail.btn_search_meta')}</button>
          <button class="ridi-link-btn" onclick="rescanSeries(event, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')" style="margin: 0; background: #ea580c; border-color: #f97316; display: inline-flex; align-items: center; gap: 0.3rem;"><i class="fa-solid fa-arrows-rotate"></i> ${i18n.t('detail.btn_rescan_series')}</button>
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
          <button class="ridi-link-btn" onclick="saveManualMetadata('${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')" style="background: #22c55e; border-color: #4ade80;">${i18n.t('detail.btn_save')}</button>
          <button class="ridi-link-btn" onclick="toggleMetaEditMode()" style="background: #64748b; border-color: #94a3b8;">${i18n.t('detail.btn_cancel')}</button>
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

export function renderVolumesList(books, safeSeriesName, actualLibraryId, dbType = 'general', viewOptions = {}) {
  const unreadOnly = viewOptions.unreadOnly === true;
  const sortOrder = viewOptions.sortOrder === 'newest' ? 'newest' : 'oldest';
  const gridMode = viewOptions.gridMode === true || state.detailVolumeGridView === true;

  const orderedBooks = [...books].sort((left, right) => {
    const titleL = (left.title || '').toLowerCase();
    const titleR = (right.title || '').toLowerCase();
    const cmp = titleL.localeCompare(titleR, undefined, { numeric: true, sensitivity: 'base' });
    return sortOrder === 'newest' ? -cmp : cmp;
  });

  let volumesHtml = '';

  const toClock = (totalSec) => {
    const sec = Math.max(0, Math.floor(Number(totalSec) || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  const toSizeMB = (bytes) => {
    const n = Number(bytes) || 0;
    if (n <= 0) return '-';
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  };

  const isAudiobook = (state.currentLibraryType === 'audiobook') || (books && books.length > 0 && (books[0].audiobook_id || (books[0].file_format || '').toLowerCase() === 'm4a'));

  if (isAudiobook) {
    orderedBooks.sort((a, b) => {
      const tnA = Number(a.track_number) || 0;
      const tnB = Number(b.track_number) || 0;
      if (tnA !== tnB) return tnA - tnB;
      return (a.title || '').localeCompare(b.title || '', undefined, { numeric: true });
    });

    let chapterRowsHtml = '';
    let trackRowsHtml = '';
    let runningStartSec = 0;
    let totalBytes = 0;
    const aid = orderedBooks[0]?.audiobook_id || (state.detailMeta ? state.detailMeta.id : orderedBooks[0]?.id);

    orderedBooks.forEach((b, idx) => {
      const rawTitle = String(b.title || '');
      const cleanTitle = rawTitle.replace(/^\s*\[\s*\d+\s*\]\s*/, '').trim() || rawTitle;
      const durSec = Number(b.duration) || 0;
      const durationText = b.time_str || toClock(durSec);
      const startText = toClock(runningStartSec);
      runningStartSec += durSec;

      const fileSize = Number(b.file_size) || 0;
      totalBytes += fileSize;
      const codec = String(b.file_format || '-').toLowerCase();
      const kbps = durSec > 0 ? Math.round((fileSize * 8 / 1000) / durSec) : 0;

      chapterRowsHtml += `
        <tr onclick="window.openAudioPlayer(${aid}, ${b.id}, 0)">
          <td class="ab-col-play"><button class="ab-play-mini" onclick="event.stopPropagation(); window.openAudioPlayer(${aid}, ${b.id}, 0)"><i class="fa-solid fa-play"></i></button></td>
          <td class="ab-col-id">${idx}</td>
          <td class="ab-col-title">${cleanTitle}</td>
          <td class="ab-col-time">${startText}</td>
          <td class="ab-col-time">${durationText}</td>
        </tr>
      `;

      trackRowsHtml += `
        <tr onclick="window.openAudioPlayer(${aid}, ${b.id}, 0)">
          <td class="ab-col-play"><button class="ab-play-mini" onclick="event.stopPropagation(); window.openAudioPlayer(${aid}, ${b.id}, 0)"><i class="fa-solid fa-play"></i></button></td>
          <td class="ab-col-id">${idx + 1}</td>
          <td class="ab-col-title">${rawTitle}</td>
          <td class="ab-col-codec">${codec}</td>
          <td class="ab-col-time">${kbps > 0 ? `${kbps} KB` : '-'}</td>
          <td class="ab-col-size">${toSizeMB(fileSize)}</td>
          <td class="ab-col-time">${durationText}</td>
        </tr>
      `;
    });

    const totalDurationText = toClock(runningStartSec);

    return `
      <div class="volumes-section ab-volumes-shell" style="margin-top: 1.2rem;">
        <div class="ab-tab-header">
          <button class="ab-tab-btn active" data-target="chapters" onclick="(function(btn){const root=btn.closest('.ab-volumes-shell');root.querySelectorAll('.ab-tab-btn').forEach(b=>b.classList.remove('active'));root.querySelectorAll('.ab-tab-pane').forEach(p=>p.classList.remove('active'));btn.classList.add('active');root.querySelector('.ab-tab-pane[data-pane=chapters]').classList.add('active');})(this)">챕터 <span>${orderedBooks.length}</span></button>
          <button class="ab-tab-btn" data-target="tracks" onclick="(function(btn){const root=btn.closest('.ab-volumes-shell');root.querySelectorAll('.ab-tab-btn').forEach(b=>b.classList.remove('active'));root.querySelectorAll('.ab-tab-pane').forEach(p=>p.classList.remove('active'));btn.classList.add('active');root.querySelector('.ab-tab-pane[data-pane=tracks]').classList.add('active');})(this)">오디오 트랙 <span>${orderedBooks.length}</span></button>
          <button class="ab-tab-btn" data-target="detail" onclick="(function(btn){const root=btn.closest('.ab-volumes-shell');root.querySelectorAll('.ab-tab-btn').forEach(b=>b.classList.remove('active'));root.querySelectorAll('.ab-tab-pane').forEach(p=>p.classList.remove('active'));btn.classList.add('active');root.querySelector('.ab-tab-pane[data-pane=detail]').classList.add('active');})(this)">세부사항</button>
        </div>

        <div class="ab-tab-pane active" data-pane="chapters">
          <div class="ab-table-wrap">
            <table class="ab-detail-table">
              <thead>
                <tr>
                  <th class="ab-col-play"></th>
                  <th class="ab-col-id">Id</th>
                  <th>제목</th>
                  <th class="ab-col-time">시작</th>
                  <th class="ab-col-time">기간</th>
                </tr>
              </thead>
              <tbody>${chapterRowsHtml}</tbody>
            </table>
          </div>
        </div>

        <div class="ab-tab-pane" data-pane="tracks">
          <div class="ab-table-wrap">
            <table class="ab-detail-table">
              <thead>
                <tr>
                  <th class="ab-col-play"></th>
                  <th class="ab-col-id">#</th>
                  <th>파일 이름</th>
                  <th class="ab-col-codec">코덱</th>
                  <th class="ab-col-time">비트레이트</th>
                  <th class="ab-col-size">크기</th>
                  <th class="ab-col-time">기간</th>
                </tr>
              </thead>
              <tbody>${trackRowsHtml}</tbody>
            </table>
          </div>
        </div>

        <div class="ab-tab-pane" data-pane="detail">
          <div class="ab-stats-grid">
            <div class="ab-stat-card"><span class="k">총 트랙</span><strong>${orderedBooks.length}</strong></div>
            <div class="ab-stat-card"><span class="k">총 재생시간</span><strong>${totalDurationText}</strong></div>
            <div class="ab-stat-card"><span class="k">총 크기</span><strong>${toSizeMB(totalBytes)}</strong></div>
            <div class="ab-stat-card"><span class="k">평균 길이</span><strong>${orderedBooks.length > 0 ? toClock(Math.round(runningStartSec / orderedBooks.length)) : '-'}</strong></div>
          </div>
        </div>
      </div>
    `;
  }

  if (gridMode) {
    // ── 그리드 모드: 커버 + 제목만 ──────────────────────────────
    orderedBooks.forEach(b => {
      const pagesRead = Math.max(0, Number(b.pages_read) || 0);
      const totalPages = Math.max(1, Number(b.total_pages) || 1);
      const isCompletedValue = Number(b.is_completed) === 1;
      const fmt = (b.file_format || '').toLowerCase();
      let rawDisplayTitle = b.title_alias || b.title || '';
      const pathText = b.file_path || '';
      const imgdirPathDisplay = pathText.replace(/[\\/]__folder__\.imgdir$/i, '');
      const pathDisplay = fmt === 'imgdir' ? imgdirPathDisplay : pathText;
      if (fmt === 'imgdir' && (!rawDisplayTitle || rawDisplayTitle === '__folder__')) {
        const normalized = (pathDisplay || '').replace(/\\/g, '/').replace(/\/+$/, '');
        rawDisplayTitle = normalized.split('/').pop() || '';
      }

      const imageDisplayTitle = stripLeadingBracketTags(rawDisplayTitle);
      const volCoverSrc = getBookCoverSrc({
        coverImage: b.cover_image,
        title: imageDisplayTitle,
        format: b.file_format,
        seed: b.id || b.file_path || `${safeSeriesName}:${imageDisplayTitle}`
      });
      const volumeFallbackCoverSrc = buildFallbackCoverUrl({ id: b.id, title: imageDisplayTitle, format: b.file_format, seed: b.id });
      const progressPercent = totalPages > 0 ? Math.min(100, Math.round((pagesRead / totalPages) * 100)) : 0;
      const isNotCompleted = !isCompletedValue;

      volumesHtml += `
        <div class="vol-grid-card${!isCompletedValue && pagesRead === 0 ? ' unread-card' : ''}"
             data-book-id="${b.id}"
             data-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}"
             data-pages-read="${pagesRead}"
             data-is-completed="${isCompletedValue ? 1 : 0}"
             style="${unreadOnly && !isNotCompleted ? 'display: none;' : ''}"
             onclick="openReader(${b.id}, '${(b.file_format || '').replace(/'/g, "\\'")}', '${(rawDisplayTitle || '').replace(/'/g, "\\'")}', ${b.pages_read}, ${b.total_pages})"
             oncontextmenu="event.preventDefault(); event.stopPropagation(); if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(event.clientX, event.clientY, ${b.id}, '${(rawDisplayTitle || '').replace(/'/g, "\\'")}', true);"
             ontouchstart="window.handleLongPressTouchStart(event, (x, y) => { if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(x, y, ${b.id}, '${(rawDisplayTitle || '').replace(/'/g, "\\\\\\\\\\'")}', true); })"
             ontouchmove="window.handleLongPressTouchMove(event)"
             ontouchend="window.handleLongPressTouchEnd(event)"
             ontouchcancel="window.handleLongPressTouchEnd(event)">
          ${isCompletedValue ? '<span class="vol-grid-completed-badge">완독</span>' : ''}
          <div class="vol-grid-thumb-container" style="position: relative; width: 100%; aspect-ratio: 1 / 1.45; overflow: hidden; border-radius: 8px;">
            <img class="vol-grid-thumb" src="${volCoverSrc}" alt="cover" data-title="${(imageDisplayTitle || '').replace(/"/g, '&quot;')}" data-format="${b.file_format || 'text'}"
                 onerror="window.handleCoverError(this)" style="width: 100%; height: 100%; object-fit: cover;">
            <a class="vol-grid-download-btn"
               href="/api/media/books/${b.id}/download?type=${dbType}"
               download
               title="${i18n.t('detail.btn_download') || '다운로드'}"
               onclick="event.stopPropagation();">
              <i class="fa-solid fa-download"></i>
            </a>
          </div>
          ${pagesRead > 0 && !isCompletedValue ? `
          <div class="vol-grid-progress">
            <div class="vol-grid-progress-bar" style="width: ${progressPercent}%"></div>
          </div>` : ''}
          <span class="vol-grid-title" title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}">${rawDisplayTitle}</span>
        </div>
      `;
    });

    return `
    <div class="volumes-section">
      <div class="volumes-section-toolbar">
        <h4 class="volumes-section-title">
          <i class="fa-solid fa-layer-group"></i> ${i18n.t('dashboard.single_book_list')}
          <span class="vol-count-badge">${i18n.t('dashboard.book_unit', { count: books.length })}</span>
        </h4>
        <div class="volume-list-controls" aria-label="${i18n.t('detail.list_controls')}">
          <button type="button" class="volume-filter-btn${unreadOnly ? ' active' : ''}" data-detail-unread-filter aria-pressed="${unreadOnly}" onclick="toggleDetailUnreadFilter()">
            ${i18n.t('detail.unread_only')}
          </button>
          <div class="volume-sort-control" role="group" aria-label="${i18n.t('detail.sort_order')}">
            <button type="button" class="volume-sort-btn${sortOrder === 'oldest' ? ' active' : ''}" data-detail-sort="oldest" aria-pressed="${sortOrder === 'oldest'}" onclick="setDetailVolumeSort('oldest')">${i18n.t('detail.sort_oldest')}</button>
            <button type="button" class="volume-sort-btn${sortOrder === 'newest' ? ' active' : ''}" data-detail-sort="newest" aria-pressed="${sortOrder === 'newest'}" onclick="setDetailVolumeSort('newest')">${i18n.t('detail.sort_newest')}</button>
          </div>
        </div>
      </div>
      <div class="volumes-list-grid">
        ${volumesHtml}
      </div>
      <div class="volumes-empty-filter" style="display: none;">${i18n.t('detail.no_unread_books')}</div>
    </div>
  `;
  } else {
    // ── 리스트 모드: 기존과 동일 ─────────────────────────────────
    orderedBooks.forEach(b => {
      const pagesRead = Math.max(0, Number(b.pages_read) || 0);
      const isCompletedValue = Number(b.is_completed) === 1;
      const isNotCompleted = !isCompletedValue;
      const fmt = (b.file_format || '').toLowerCase();
      const pathText = b.file_path || '';
      const imgdirPathDisplay = pathText.replace(/[\\/]__folder__\.imgdir$/i, '');
      const pathDisplay = fmt === 'imgdir' ? imgdirPathDisplay : pathText;
      let rawDisplayTitle = b.title || '';
      if (fmt === 'imgdir' && (!rawDisplayTitle || rawDisplayTitle === '__folder__')) {
        const normalized = (pathDisplay || '').replace(/\\/g, '/').replace(/\/+$/, '');
        const segments = normalized.split('/').filter(Boolean);
        if (segments.length > 0) {
          rawDisplayTitle = segments[segments.length - 1];
        }
      }

      const imageDisplayTitle = stripLeadingBracketTags(rawDisplayTitle);

      const progressPercent = b.total_pages > 0 ? Math.round((pagesRead / b.total_pages) * 100) : 0;
      const progressText = pagesRead > 0
        ? `${pagesRead}p / ${b.total_pages}p (${progressPercent}%)`
        : '미독';
      const readBtnText = pagesRead > 0
        ? `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_resume')}`
        : `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_start')}`;
      const volumeFallbackCoverSrc = buildFallbackCoverUrl({
        title: imageDisplayTitle,
        format: b.file_format,
        seed: b.id || b.file_path || `${safeSeriesName}:${imageDisplayTitle}`
      });
      const volCoverSrc = getBookCoverSrc({
        coverImage: b.cover_image,
        title: imageDisplayTitle,
        format: b.file_format,
        seed: b.id || b.file_path || `${safeSeriesName}:${imageDisplayTitle}`
      });
      const isCompleted = isCompletedValue
        ? `<span class="vol-badge-completed">${i18n.t('detail.badge_completed')}</span>`
        : '';

      const isFav = b.is_favorite === 1;
      const favIconClass = isFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
      const favIconColor = isFav ? '#eab308' : '#64748b';
      const favBtnHtml = `
      <button class="btn-fav-toggle" onclick="toggleBookFavorite(event, ${b.id}, ${isFav ? 0 : 1}, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')" style="background:none; border:none; color:${favIconColor}; cursor:pointer; font-size:1.1rem; padding:0 0.5rem; display:inline-flex; align-items:center;" title="${i18n.t('detail.toggle_fav_book')}">
        <i class="${favIconClass}"></i>
      </button>
    `;

      const noCover = !b.cover_image;
      const isTextFormat = ['txt', 'text'].includes((b.file_format || '').toLowerCase());
      const isZipFormat = ['zip', 'cbz'].includes((b.file_format || '').toLowerCase());

      // 원격 경로 여부 판단 (gdrive, rclone, vfs, google_drive, onedrive, sharepoint, nas_share, webdav 등)
      const filePathLower = (b.file_path || '').toLowerCase();
      const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
      const isRemoteFile = remoteKeywords.some(keyword => filePathLower.includes(keyword));

      // 원격 파일은 백그라운드 오프셋 조회를 하지 않으므로 warn_no_offset 경고창 노출 대상에서 제외합니다.
      const noOffsets = isZipFormat && !isRemoteFile && (b.total_pages === 0 || b.has_offsets === 0);
      const noCoverWarn = noCover && !isTextFormat;
      const noCoverInfo = noCover && isTextFormat;
      const needsWarn = noCoverWarn || noOffsets;

      let warnTexts = [];
      if (noCoverWarn) warnTexts.push(i18n.t('detail.warn_no_cover'));
      if (noOffsets) warnTexts.push(i18n.t('detail.warn_no_offset'));
      const warnBannerHtml = needsWarn ? `
      <div class="vol-warn-banner">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>${warnTexts.join(' · ')}</span>
        <button class="btn-rescan-book" onclick="rescanBook(event, ${b.id}, '${safeSeriesName.replace(/'/g, "\\'")}', '${actualLibraryId}')">
          <i class="fa-solid fa-rotate"></i> ${i18n.t('detail.btn_rescan')}
        </button>
      </div>
    ` : '';

      const infoBannerHtml = (noCoverInfo && state.showTxtNoCoverInfoBanner !== false) ? `
      <div class="vol-warn-banner" style="border-color: rgba(59, 130, 246, 0.35); background: rgba(30, 58, 138, 0.22); color: #93c5fd;">
        <i class="fa-solid fa-circle-info"></i>
        <span>기본 커버 사용 중 (TXT)</span>
      </div>
    ` : '';

      // epub/pdf/txt 포맷은 이어보기(절반) + 다운로드 버튼을 나란히 표시
      const isDownloadable = ['epub', 'pdf', 'txt', 'text'].includes(fmt);
      const readBtnHtml = isDownloadable
        ? `<div class="btn-read-row">
           <button class="btn-read" onclick="openReader(${b.id}, '${(b.file_format || '').replace(/'/g, "\\'")}', '${(rawDisplayTitle || '').replace(/'/g, "\\'")}', ${b.pages_read}, ${b.total_pages})">${readBtnText}</button>
           <a class="btn-download" href="/api/media/books/${b.id}/download?type=${dbType}" download title="${i18n.t('detail.btn_download')}">
             <i class="fa-solid fa-download"></i> ${i18n.t('detail.btn_download')}
           </a>
         </div>`
        : `<button class="btn-read" onclick="openReader(${b.id}, '${(b.file_format || '').replace(/'/g, "\\'")}', '${(rawDisplayTitle || '').replace(/'/g, "\\'")}', ${b.pages_read}, ${b.total_pages})">${readBtnText}</button>`;

      volumesHtml += `
      <div class="volume-card" data-book-id="${b.id}" data-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-pages-read="${pagesRead}" data-is-completed="${isCompletedValue ? 1 : 0}" data-page-missing="${noOffsets ? 1 : 0}" style="${unreadOnly && !isNotCompleted ? 'display: none;' : ''}" oncontextmenu="event.preventDefault(); event.stopPropagation(); if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(event.clientX, event.clientY, ${b.id}, '${(rawDisplayTitle || '').replace(/'/g, "\\'")}', true);" ontouchstart="window.handleLongPressTouchStart(event, (x, y) => { if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(x, y, ${b.id}, '${(rawDisplayTitle || '').replace(/'/g, "\\\\\\'")}', true); })" ontouchmove="window.handleLongPressTouchMove(event)" ontouchend="window.handleLongPressTouchEnd(event)" ontouchcancel="window.handleLongPressTouchEnd(event)">
        <img class="volume-thumb" src="${volCoverSrc}" alt="cover"
             onerror="if(this.src.indexOf('/covers/fallback')===-1 &amp;&amp; !this.src.startsWith('data:image/svg+xml')){this.src='${volumeFallbackCoverSrc}';}else{this.onerror=null; this.src='${buildTextCoverDataUri({ title: b.title || rawDisplayTitle, format: b.file_format, seed: b.id })}';}">
        <div class="volume-info">
          ${warnBannerHtml}
          ${infoBannerHtml}
          <div class="volume-title-row" style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
            <span class="volume-title">${rawDisplayTitle}</span>
            ${isCompleted}
            ${favBtnHtml}
          </div>
          <span class="volume-path" style="font-size: 0.72rem; color: #64748b; word-break: break-all; margin-top: 0.15rem; display: block;">(${pathDisplay})</span>
          <div class="volume-meta-row">
            <span class="vol-meta"><i class="fa-regular fa-file"></i> ${b.total_pages}p</span>
            <span class="vol-meta"><i class="fa-regular fa-clock"></i> ${i18n.t('detail.time_est', { minutes: Math.max(1, Math.ceil(b.total_pages / 40)) })}</span>
          </div>
          <div class="volume-progress-bar-wrap">
            <div class="volume-progress-bar" style="width: ${progressPercent}%"></div>
          </div>
          <div class="chapter-progress-text">${progressText}</div>
        </div>
        ${readBtnHtml}
      </div>
    `;
    });

    return `
    <div class="volumes-section">
      <div class="volumes-section-toolbar">
        <h4 class="volumes-section-title">
          <i class="fa-solid fa-layer-group"></i> ${i18n.t('dashboard.single_book_list')}
          <span class="vol-count-badge">${i18n.t('dashboard.book_unit', { count: books.length })}</span>
        </h4>
        <div class="volume-list-controls" aria-label="${i18n.t('detail.list_controls')}">
          <button type="button" class="volume-filter-btn${unreadOnly ? ' active' : ''}" data-detail-unread-filter aria-pressed="${unreadOnly}" onclick="toggleDetailUnreadFilter()">
            ${i18n.t('detail.unread_only')}
          </button>
          <div class="volume-sort-control" role="group" aria-label="${i18n.t('detail.sort_order')}">
            <button type="button" class="volume-sort-btn${sortOrder === 'oldest' ? ' active' : ''}" data-detail-sort="oldest" aria-pressed="${sortOrder === 'oldest'}" onclick="setDetailVolumeSort('oldest')">${i18n.t('detail.sort_oldest')}</button>
            <button type="button" class="volume-sort-btn${sortOrder === 'newest' ? ' active' : ''}" data-detail-sort="newest" aria-pressed="${sortOrder === 'newest'}" onclick="setDetailVolumeSort('newest')">${i18n.t('detail.sort_newest')}</button>
          </div>
        </div>
      </div>
      <div class="volumes-list">
        ${volumesHtml}
      </div>
      <div class="volumes-empty-filter" style="display: none;">${i18n.t('detail.no_unread_books')}</div>
    </div>
  `;
  }
}

export function renderRecommendList(recommends, seriesName) {
  let recHtml = '';
  recommends.forEach(rec => {
    const recDisplaySeries = stripLeadingBracketTags(rec.series_name);
    recHtml += `
      <div class="recommend-card" style="display: flex; flex-direction: column; gap: 0.3rem; padding: 0.6rem; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
          <strong style="font-size: 0.85rem; color: #fff;">${recDisplaySeries}</strong>
          <button class="btn-apply-meta" data-source-id="${rec.id}" style="padding: 0.2rem 0.6rem; font-size: 0.72rem; font-weight: 700; color: #fff; background: #7c3aed; border: none; border-radius: 4px; cursor: pointer; transition: background 0.2s;">${i18n.t('detail.btn_apply_meta')}</button>
        </div>
        <div style="font-size: 0.72rem; color: #94a3b8;">
          <span>${i18n.t('detail.text_author', { author: rec.author })}</span> | <span>${i18n.t('detail.text_publisher', { publisher: rec.publisher })}</span>
        </div>
        <p style="margin: 0.2rem 0 0 0; font-size: 0.72rem; color: #cbd5e1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; line-height: 1.4;">${rec.summary}</p>
      </div>
    `;
  });
  return recHtml;
}
