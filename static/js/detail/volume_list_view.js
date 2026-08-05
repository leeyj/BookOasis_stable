import { buildFallbackCoverUrl, getBookCoverSrc, buildTextCoverDataUri } from '../cover_fallback.js';
import { state } from '../state.js';
import { stripLeadingBracketTags } from '../series_display.js';

export function renderVolumeList(orderedBooks, safeSeriesName, actualLibraryId, dbType = 'general', options = {}) {
  const books = Array.isArray(orderedBooks) ? orderedBooks : [];
  const unreadOnly = options.unreadOnly === true;
  const sortOrder = options.sortOrder === 'newest' ? 'newest' : 'oldest';
  let volumesHtml = '';

  books.forEach((book) => {
    const pagesRead = Math.max(0, Number(book.pages_read) || 0);
    const isCompletedValue = Number(book.is_completed) === 1;
    const isNotCompleted = !isCompletedValue;
    const format = (book.file_format || '').toLowerCase();
    const pathText = book.file_path || '';
    const imgdirPathDisplay = pathText.replace(/[\\/]__folder__\.imgdir$/i, '');
    const pathDisplay = format === 'imgdir' ? imgdirPathDisplay : pathText;
    let rawDisplayTitle = book.title || '';
    if (format === 'imgdir' && (!rawDisplayTitle || rawDisplayTitle === '__folder__')) {
      const normalized = (pathDisplay || '').replace(/\\/g, '/').replace(/\/+$/, '');
      const segments = normalized.split('/').filter(Boolean);
      if (segments.length > 0) {
        rawDisplayTitle = segments[segments.length - 1];
      }
    }

    const imageDisplayTitle = stripLeadingBracketTags(rawDisplayTitle);
    const progressPercent = book.total_pages > 0 ? Math.round((pagesRead / book.total_pages) * 100) : 0;
    const progressText = pagesRead > 0
      ? `${pagesRead}p / ${book.total_pages}p (${progressPercent}%)`
      : '미독';
    const readBtnText = pagesRead > 0
      ? `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_resume')}`
      : `<i class="fa-solid fa-play"></i> ${i18n.t('detail.btn_start')}`;
    const volumeFallbackCoverSrc = buildFallbackCoverUrl({
      title: imageDisplayTitle,
      format: book.file_format,
      seed: book.id || book.file_path || `${safeSeriesName}:${imageDisplayTitle}`
    });
    const volumeCoverSrc = getBookCoverSrc({
      coverImage: book.cover_image,
      title: imageDisplayTitle,
      format: book.file_format,
      seed: book.id || book.file_path || `${safeSeriesName}:${imageDisplayTitle}`
    });
    const isCompleted = isCompletedValue
      ? `<span class="vol-badge-completed">${i18n.t('detail.badge_completed')}</span>`
      : '';

    const isFav = book.is_favorite === 1;
    const favIconClass = isFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
    const favIconColor = isFav ? '#eab308' : '#64748b';
    const favBtnHtml = `
      <button class="btn-fav-toggle" data-role="detail-book-favorite" data-book-id="${book.id}" data-next-status="${isFav ? 0 : 1}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" style="background:none; border:none; color:${favIconColor}; cursor:pointer; font-size:1.1rem; padding:0 0.5rem; display:inline-flex; align-items:center;" title="${i18n.t('detail.toggle_fav_book')}">
        <i class="${favIconClass}"></i>
      </button>
    `;

    const noCover = !book.cover_image;
    const isTextFormat = ['txt', 'text'].includes((book.file_format || '').toLowerCase());
    const isZipFormat = ['zip', 'cbz'].includes((book.file_format || '').toLowerCase());
    const filePathLower = (book.file_path || '').toLowerCase();
    const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
    const isRemoteFile = remoteKeywords.some((keyword) => filePathLower.includes(keyword));
    const noOffsets = isZipFormat && !isRemoteFile && (book.total_pages === 0 || book.has_offsets === 0);
    const noCoverWarn = noCover && !isTextFormat;
    const noCoverInfo = noCover && isTextFormat;
    const needsWarn = noCoverWarn || noOffsets;

    const warnTexts = [];
    if (noCoverWarn) warnTexts.push(i18n.t('detail.warn_no_cover'));
    if (noOffsets) warnTexts.push(i18n.t('detail.warn_no_offset'));
    const warnBannerHtml = needsWarn ? `
      <div class="vol-warn-banner">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>${warnTexts.join(' · ')}</span>
        <button class="btn-rescan-book" data-role="detail-rescan-book" data-book-id="${book.id}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}">
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

    const isDownloadable = ['epub', 'pdf', 'txt', 'text'].includes(format);
    const readBtnHtml = isDownloadable
      ? `<div class="btn-read-row">
           <button class="btn-read" data-role="detail-continue" data-continue-action="reader" data-book-id="${book.id}" data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}" data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-pages-read="${book.pages_read}" data-total-pages="${book.total_pages}">${readBtnText}</button>
           <a class="btn-download" href="/api/media/books/${book.id}/download?type=${dbType}" download title="${i18n.t('detail.btn_download')}">
             <i class="fa-solid fa-download"></i> ${i18n.t('detail.btn_download')}
           </a>
         </div>`
      : `<button class="btn-read" data-role="detail-continue" data-continue-action="reader" data-book-id="${book.id}" data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}" data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-pages-read="${book.pages_read}" data-total-pages="${book.total_pages}">${readBtnText}</button>`;

    volumesHtml += `
      <div class="volume-card" data-role="detail-volume-open-reader" data-book-id="${book.id}" data-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}" data-pages-read="${pagesRead}" data-total-pages="${book.total_pages}" data-is-completed="${isCompletedValue ? 1 : 0}" data-page-missing="${noOffsets ? 1 : 0}" style="${unreadOnly && !isNotCompleted ? 'display: none;' : ''}">
        <img class="volume-thumb" src="${volumeCoverSrc}" alt="cover"
             onerror="if(this.src.indexOf('/covers/fallback')===-1 &amp;&amp; !this.src.startsWith('data:image/svg+xml')){this.src='${volumeFallbackCoverSrc}';}else{this.onerror=null; this.src='${buildTextCoverDataUri({ title: book.title || rawDisplayTitle, format: book.file_format, seed: book.id })}';}">
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
            <span class="vol-meta"><i class="fa-regular fa-file"></i> ${book.total_pages}p</span>
            <span class="vol-meta"><i class="fa-regular fa-clock"></i> ${i18n.t('detail.time_est', { minutes: Math.max(1, Math.ceil(book.total_pages / 40)) })}</span>
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
        <button type="button" class="volume-filter-btn${unreadOnly ? ' active' : ''}" data-role="detail-volume-filter" data-detail-unread-filter aria-pressed="${unreadOnly}">
          ${i18n.t('detail.unread_only')}
        </button>
        <div class="volume-sort-control" role="group" aria-label="${i18n.t('detail.sort_order')}">
          <button type="button" class="volume-sort-btn${sortOrder === 'oldest' ? ' active' : ''}" data-role="detail-volume-sort" data-sort="oldest" data-detail-sort="oldest" aria-pressed="${sortOrder === 'oldest'}">${i18n.t('detail.sort_oldest')}</button>
          <button type="button" class="volume-sort-btn${sortOrder === 'newest' ? ' active' : ''}" data-role="detail-volume-sort" data-sort="newest" data-detail-sort="newest" aria-pressed="${sortOrder === 'newest'}">${i18n.t('detail.sort_newest')}</button>
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