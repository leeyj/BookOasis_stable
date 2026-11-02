import { buildFallbackCoverUrl, getBookCoverSrc, buildTextCoverDataUri, coverAlignToObjectPosition } from '../cover_fallback.js';
import { state } from '../state.js';
import { stripLeadingBracketTags } from '../series_display.js';
import { canDownloadFiles } from '../library_type_toggle.js';
import { canListen } from '../tts_launcher.js';
import { renderVolumeControls } from './volume_controller.js';

export function renderVolumeList(orderedBooks, safeSeriesName, actualLibraryId, dbType = 'general', options = {}) {
  const books = Array.isArray(orderedBooks) ? orderedBooks : [];
  const unreadOnly = options.unreadOnly === true;
  const sortOrder = options.sortOrder === 'newest' ? 'newest' : 'oldest';
  // 서버 파일 경로는 관리자에게만 (일반 사용자에겐 잡음이고 서버 구조가 드러난다)
  const currentUser = state.currentUser || window.currentUser || {};
  const showFilePath = String(currentUser.role || '').trim().toLowerCase() === 'admin';
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
      : i18n.t('detail.unread');
    const readBtnText = pagesRead > 0
      ? `<i class="lc lc-play"></i> ${i18n.t('detail.btn_resume')}`
      : `<i class="lc lc-play"></i> ${i18n.t('detail.btn_start')}`;
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
    const favIconClass = isFav ? 'fa-solid fa-star' : 'lc lc-star';
    const favIconColor = isFav ? '#eab308' : '#64748b';
    const favBtnHtml = `
      <button class="btn-fav-toggle volume-fav-btn" data-role="detail-book-favorite" data-book-id="${book.id}" data-next-status="${isFav ? 0 : 1}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" style="color:${favIconColor};" title="${i18n.t('detail.toggle_fav_book')}">
        <i class="${favIconClass}"></i>
      </button>
    `;

    const noCover = !book.cover_image;
    const isTextFormat = ['txt', 'text'].includes((book.file_format || '').toLowerCase());
    const isZipFormat = ['zip', 'cbz'].includes((book.file_format || '').toLowerCase());
    const filePathLower = (book.file_path || '').toLowerCase();
    const remoteKeywords = ['gdrive', 'rclone', 'vfs', 'google_drive', 'onedrive', 'sharepoint', 'nas_share', 'webdav'];
    const isRemoteFile = remoteKeywords.some((keyword) => filePathLower.includes(keyword));
    const noOffsets = isZipFormat && !isRemoteFile && (book.has_offsets === 0);
    const noCoverWarn = noCover && !isTextFormat;
    const noCoverInfo = noCover && isTextFormat;
    const needsWarn = noCoverWarn || noOffsets;

    const warnTexts = [];
    if (noCoverWarn) warnTexts.push(i18n.t('detail.warn_no_cover'));
    if (noOffsets) warnTexts.push(i18n.t('detail.warn_no_offset'));
    const warnBannerHtml = needsWarn ? `
      <div class="vol-warn-banner">
        <i class="lc lc-triangle-alert"></i>
        <span>${warnTexts.join(' · ')}</span>
        <button class="btn-rescan-book" data-role="detail-rescan-book" data-book-id="${book.id}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}">
          <i class="lc lc-rotate-cw"></i> ${i18n.t('detail.btn_rescan')}
        </button>
      </div>
    ` : '';

    const infoBannerHtml = (noCoverInfo && state.showTxtNoCoverInfoBanner !== false) ? `
      <div class="vol-warn-banner vol-warn-banner--info">
        <i class="lc lc-info"></i>
        <span>${i18n.t('detail.default_cover_txt')}</span>
      </div>
    ` : '';

    const isDownloadable = ['epub', 'pdf', 'txt', 'text'].includes(format) && canDownloadFiles();
    // 음성으로 듣기는 브라우저에서 텍스트를 합성하므로 TXT/EPUB만
    const isListenable = canListen(format);
    const readBtn = `<button class="btn-read" data-role="detail-continue" data-continue-action="reader" data-book-id="${book.id}" data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}" data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-pages-read="${book.pages_read}" data-total-pages="${book.total_pages}">${readBtnText}</button>`;
    const listenBtn = isListenable
      ? `<button class="btn-listen" data-role="detail-listen" data-book-id="${book.id}" data-db-type="${dbType}" title="${i18n.t('context_menu.tts_listen')}">
           <i class="lc lc-headphones"></i> ${i18n.t('tts.viewer_listen')}
         </button>`
      : '';
    const downloadBtn = isDownloadable
      ? `<a class="btn-download" href="/api/media/books/${book.id}/download?type=${dbType}" download title="${i18n.t('detail.btn_download')}" data-role="detail-download-link">
           <i class="lc lc-download"></i> ${i18n.t('detail.btn_download')}
         </a>`
      : '';
    const readBtnHtml = (listenBtn || downloadBtn)
      ? `<div class="btn-read-row">${readBtn}${listenBtn}${downloadBtn}</div>`
      : readBtn;

    volumesHtml += `
      <div class="volume-card" data-role="detail-volume-open-reader" data-book-id="${book.id}" data-cover-align="${book.cover_align || 'center'}" data-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}" data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}" data-pages-read="${pagesRead}" data-total-pages="${book.total_pages}" data-is-completed="${isCompletedValue ? 1 : 0}" data-page-missing="${noOffsets ? 1 : 0}" style="${unreadOnly && !isNotCompleted ? 'display: none;' : ''}">
        <img class="volume-thumb" src="${volumeCoverSrc}" alt="cover" style="object-position: ${coverAlignToObjectPosition(book.cover_align)} center;"
             onerror="if(this.src.indexOf('/covers/fallback')===-1 &amp;&amp; !this.src.startsWith('data:image/svg+xml')){this.src='${volumeFallbackCoverSrc}';}else{this.onerror=null; this.src='${buildTextCoverDataUri({ title: book.title || rawDisplayTitle, format: book.file_format, seed: book.id })}';}">
        <div class="volume-info">
          ${warnBannerHtml}
          ${infoBannerHtml}
          <div class="volume-title-row">
            <span class="volume-title">${rawDisplayTitle}</span>
            ${isCompleted}
            ${favBtnHtml}
          </div>
          ${showFilePath ? `<span class="volume-path">${pathDisplay}</span>` : ''}
          <div class="volume-meta-row">
            <span class="vol-meta"><i class="lc lc-file"></i> ${book.total_pages}p</span>
            <span class="vol-meta"><i class="lc lc-clock"></i> ${i18n.t('detail.time_est', { minutes: Math.max(1, Math.ceil(book.total_pages / 40)) })}</span>
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
        <i class="lc lc-layers"></i> ${i18n.t('dashboard.single_book_list')}
        <span class="vol-count-badge">${i18n.t('dashboard.book_unit', { count: books.length })}</span>
      </h4>
      ${renderVolumeControls(unreadOnly, sortOrder)}
    </div>
    <div class="volumes-list">
      ${volumesHtml}
    </div>
    <div class="volumes-empty-filter" style="display: none;">${i18n.t('detail.no_unread_books')}</div>
  </div>
`;
}