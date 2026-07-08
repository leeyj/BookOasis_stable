// detail_render.js – 도서 상세 화면의 HTML 템플릿 생성기

function normalizeMetadataToken(token) {
  if (!token) return '';
  return String(token)
    .replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

export function renderDetailHeader(meta, books, safeSeriesName, actualLibraryId) {
  const firstBookId = books.length > 0 ? books[0].id : null;
  const coverSrc = meta.cover_image
    ? `/covers/${meta.cover_image}`
    : '/static/images/default_cover.jpg';
  const stars = '★'.repeat(Math.round(meta.score / 20)) + '☆'.repeat(5 - Math.round(meta.score / 20));
  const linkHtml = meta.link
    ? `<a href="${meta.link}" target="_blank" class="ridi-link-btn">${i18n.t('detail.ridi_link')}</a>`
    : '';

  const genresHtml = (meta.genre || '')
    .split(',')
    .map(g => normalizeMetadataToken(g))
    .filter(g => g)
    .filter((g, idx, arr) => arr.indexOf(g) === idx)
    .map(g => `<span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByGenre('${g.replace(/'/g, "\\'")}')"><i class="fa-solid fa-tag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${g}</span>`)
    .join('');

  const tagsHtml = (meta.tags || '')
    .split(',')
    .map(t => normalizeMetadataToken(t))
    .filter(t => t)
    .filter((t, idx, arr) => arr.indexOf(t) === idx)
    .map(t => `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center;" onclick="window.quickFilterByTag('${t.replace(/'/g, "\\'")}')"><i class="fa-solid fa-hashtag" style="font-size: 0.7rem; margin-right: 0.2rem;"></i>${t}</span>`)
    .join('');

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
        <span>${i18n.t('detail.warn_series_missing_pages', {count: missingPageCount})}</span>
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
      btnLabel = i18n.t('detail.start_reading') || '첫 권부터 읽기';
      tooltipTitle = continueTarget.title;
      btnColor = '#10b981';
      btnBorder = '#34d399';
      iconClass = 'fa-solid fa-book-open-reader';
    }
    
    continueBtnHtml = `
      <button class="ridi-link-btn" style="margin: 0; background: ${btnColor}; border-color: ${btnBorder}; font-weight: bold; color: #fff; display: inline-flex; align-items: center; gap: 0.3rem;" 
              title="${tooltipTitle.replace(/"/g, '&quot;')}"
              onclick="window.openReader(${continueTarget.id}, '${continueTarget.file_format}', '${continueTarget.title.replace(/'/g, "\\'")}', ${continueTarget.pages_read || 0}, ${continueTarget.total_pages || 0})">
        <i class="${iconClass}"></i> ${btnLabel}
      </button>
    `;
  }

  return `
    <!-- 상단 헤더: 커버(작게) + 메타정보 -->
    <div class="detail-header-panel">
      <div class="detail-cover-container" 
           ondragover="event.preventDefault(); this.style.borderColor='#a855f7';" 
           ondragleave="this.style.borderColor='rgba(255,255,255,0.08)';" 
           ondrop="handleCoverDrop(event); this.style.borderColor='rgba(255,255,255,0.08)';">
        <img class="detail-cover-sm" id="detail-cover-img-preview" src="${coverSrc}" alt="Cover"
             onerror="this.onerror=null; this.src='/static/images/default_cover.jpg';">
        <div class="cover-upload-overlay" id="cover-upload-overlay-btn" onclick="triggerCoverUpload(event)">
          <i class="fa-solid fa-camera"></i>
          <span>${i18n.t('detail.change_cover')}</span>
        </div>
        <input type="file" id="cover-upload-file-input" accept="image/*" style="display: none;" onchange="handleCoverUploadSelect(event)">
      </div>
      
      <!-- 뷰어 모드 (일반 노출) -->
      <div id="detail-header-meta-view" class="detail-header-meta">
        <h3 class="book-detail-title" style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
          ${safeSeriesName}
          <button class="btn-fav-toggle" onclick="toggleSeriesFavorite(event, '${safeSeriesName.replace(/'/g, "\\'")}', ${isSeriesFav ? 1 : 0}, '${actualLibraryId}')" style="background:none; border:none; color:${seriesFavIconColor}; cursor:pointer; font-size:1.4rem; display:inline-flex; align-items:center;" title="${i18n.t('detail.toggle_fav_series')}">
            <i class="${seriesFavIconClass}"></i>
          </button>
          <button class="ridi-link-btn btn-edit-toggle" onclick="toggleMetaEditMode()" style="background: #0284c7; border-color: #0ea5e9; font-size: 0.75rem; padding: 0.2rem 0.6rem; display: inline-flex; align-items: center; gap: 0.2rem; margin-left: 0.4rem;">
            <i class="fa-solid fa-pen-to-square"></i> ${i18n.t('detail.edit_info')}
          </button>
        </h3>
        <div class="detail-meta">
          <span class="badge">${safeSeriesName}</span>
          <span class="meta-item"><i class="fa-solid fa-pen-nib"></i> ${meta.author || '-'}</span>
          <span class="meta-item"><i class="fa-solid fa-building"></i> ${meta.publisher || '-'}</span>
          <span class="meta-item"><i class="fa-solid fa-book-open"></i> ${books.length}권</span>
        </div>
        <div class="detail-meta-tags" style="display: flex; gap: 0.4rem; margin-top: 0.5rem; margin-bottom: 0.8rem; flex-wrap: wrap;">
          ${genresHtml}
          ${tagsHtml}
        </div>
        ${missingPageBannerHtml}
        <div class="detail-score">${stars}</div>
        <p class="book-summary-text">${meta.summary || i18n.t('detail.no_description')}</p>
        ${linkHtml}
        
        <!-- 버튼: 이어서 읽기 및 메타정보 찾기 -->
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem; flex-wrap: wrap; align-items: center;">
          ${continueBtnHtml}
          <button id="btn-manual-meta-search" class="ridi-link-btn" style="display:none; margin: 0; background: #7c3aed; border-color: #a855f7;"><i class="fa-solid fa-wand-magic-sparkles"></i> ${i18n.t('detail.btn_recommend_match')}</button>
          <button id="btn-plugin-meta-search" class="ridi-link-btn" onclick="openMetadataSearchModal(${firstBookId}, '${safeSeriesName.replace(/'/g, "\\'")}', true)" style="margin: 0; background: #2563eb; border-color: #3b82f6;"><i class="fa-solid fa-magnifying-glass"></i> ${i18n.t('detail.btn_search_meta')}</button>
        </div>
      </div>

      <!-- 편집 모드 (수동 입력 폼) -->
      <div id="detail-header-meta-edit" class="detail-header-meta" style="display: none;">
        <h3 class="book-detail-title" style="margin-bottom: 0.5rem; font-size: 1.3rem;">${i18n.t('detail.edit_title')} <span style="font-size: 0.8rem; color: #94a3b8; font-weight: normal; margin-left: 0.5rem;">${i18n.t('detail.edit_subtitle')}</span></h3>
        <div class="edit-meta-form-group">
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_author')}</label>
            <input type="text" id="edit-author-input" class="edit-meta-input" value="${meta.author === '-' ? '' : meta.author}">
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

export function renderVolumesList(books, safeSeriesName, actualLibraryId) {
  let volumesHtml = '';
  books.forEach(b => {
    const fmt = (b.file_format || '').toLowerCase();
    const pathText = b.file_path || '';
    const imgdirPathDisplay = pathText.replace(/[\\/]__folder__\.imgdir$/i, '');
    const pathDisplay = fmt === 'imgdir' ? imgdirPathDisplay : pathText;
    let displayTitle = b.title || '';
    if (fmt === 'imgdir' && (!displayTitle || displayTitle === '__folder__')) {
      const normalized = (pathDisplay || '').replace(/\\/g, '/').replace(/\/+$/, '');
      const segments = normalized.split('/').filter(Boolean);
      if (segments.length > 0) {
        displayTitle = segments[segments.length - 1];
      }
    }

    const progressPercent = b.total_pages > 0 ? Math.round((b.pages_read / b.total_pages) * 100) : 0;
    const progressText = b.pages_read > 0
      ? `${b.pages_read}p / ${b.total_pages}p (${progressPercent}%)`
      : '미독';
    const readBtnText = b.pages_read > 0
      ? `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_resume')}`
      : `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_start')}`;
    const volCoverSrc = b.cover_image
      ? `/covers/${b.cover_image}`
      : '/static/images/default_cover.jpg';
    const isCompleted = b.is_completed
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
    const isZipFormat = ['zip', 'cbz'].includes((b.file_format || '').toLowerCase());
    
    // 원격 경로 여부 판단 (gdrive, rclone, vfs, google_drive, onedrive, sharepoint, nas_share, webdav 등)
    const filePathLower = (b.file_path || '').toLowerCase();
    const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
    const isRemoteFile = remoteKeywords.some(keyword => filePathLower.includes(keyword));
    
    // 원격 파일은 백그라운드 오프셋 조회를 하지 않으므로 warn_no_offset 경고창 노출 대상에서 제외합니다.
    const noOffsets = isZipFormat && !isRemoteFile && (b.total_pages === 0 || b.has_offsets === 0);
    const needsWarn = noCover || noOffsets;

    let warnTexts = [];
    if (noCover) warnTexts.push(i18n.t('detail.warn_no_cover'));
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

    volumesHtml += `
      <div class="volume-card" data-book-id="${b.id}" data-page-missing="${noOffsets ? 1 : 0}" oncontextmenu="event.preventDefault(); event.stopPropagation(); if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(event.clientX, event.clientY, ${b.id}, '${(b.title || '').replace(/'/g, "\\'")}', true);" ontouchstart="window.handleLongPressTouchStart(event, (x, y) => { if (typeof window.showBookContextMenu === 'function') window.showBookContextMenu(x, y, ${b.id}, '${(b.title || '').replace(/'/g, "\\\\'")}', true); })" ontouchmove="window.handleLongPressTouchMove(event)" ontouchend="window.handleLongPressTouchEnd(event)" ontouchcancel="window.handleLongPressTouchEnd(event)">
        <img class="volume-thumb" src="${volCoverSrc}" alt="cover"
             onerror="this.onerror=null; this.src='/static/images/default_cover.jpg';">
        <div class="volume-info">
          ${warnBannerHtml}
          <div class="volume-title-row" style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
            <span class="volume-title">${displayTitle}</span>
            ${isCompleted}
            ${favBtnHtml}
          </div>
          <span class="volume-path" style="font-size: 0.72rem; color: #64748b; word-break: break-all; margin-top: 0.15rem; display: block;">(${pathDisplay})</span>
          <div class="volume-meta-row">
            <span class="vol-meta"><i class="fa-regular fa-file"></i> ${b.total_pages}p</span>
            <span class="vol-meta"><i class="fa-regular fa-clock"></i> ${i18n.t('detail.time_est', {minutes: Math.max(1, Math.ceil(b.total_pages / 40))})}</span>
          </div>
          <div class="volume-progress-bar-wrap">
            <div class="volume-progress-bar" style="width: ${progressPercent}%"></div>
          </div>
          <div class="chapter-progress-text">${progressText}</div>
        </div>
        <button class="btn-read" onclick="openReader(${b.id}, '${(b.file_format || '').replace(/'/g, "\\'")}', '${(displayTitle || '').replace(/'/g, "\\'")}', ${b.pages_read}, ${b.total_pages})">${readBtnText}</button>
      </div>
    `;
  });

  return `
    <div class="volumes-section">
      <h4 class="volumes-section-title">
        <i class="fa-solid fa-layer-group"></i> ${i18n.t('dashboard.single_book_list')}
        <span class="vol-count-badge">${i18n.t('dashboard.book_unit', {count: books.length})}</span>
      </h4>
      <div class="volumes-list">
        ${volumesHtml}
      </div>
    </div>
  `;
}

export function renderRecommendList(recommends, seriesName) {
  let recHtml = '';
  recommends.forEach(rec => {
    recHtml += `
      <div class="recommend-card" style="display: flex; flex-direction: column; gap: 0.3rem; padding: 0.6rem; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
          <strong style="font-size: 0.85rem; color: #fff;">${rec.series_name}</strong>
          <button class="btn-apply-meta" data-source-id="${rec.id}" style="padding: 0.2rem 0.6rem; font-size: 0.72rem; font-weight: 700; color: #fff; background: #7c3aed; border: none; border-radius: 4px; cursor: pointer; transition: background 0.2s;">${i18n.t('detail.btn_apply_meta')}</button>
        </div>
        <div style="font-size: 0.72rem; color: #94a3b8;">
          <span>${i18n.t('detail.text_author', {author: rec.author})}</span> | <span>${i18n.t('detail.text_publisher', {publisher: rec.publisher})}</span>
        </div>
        <p style="margin: 0.2rem 0 0 0; font-size: 0.72rem; color: #cbd5e1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; line-height: 1.4;">${rec.summary}</p>
      </div>
    `;
  });
  return recHtml;
}
