import { buildFallbackCoverUrl, getBookCoverSrc, coverAlignToObjectPosition } from '../cover_fallback.js';
import { stripLeadingBracketTags } from '../series_display.js';

export function renderVolumeGrid(orderedBooks, safeSeriesName, dbType = 'general', options = {}) {
  const books = Array.isArray(orderedBooks) ? orderedBooks : [];
  const unreadOnly = options.unreadOnly === true;
  const sortOrder = options.sortOrder === 'newest' ? 'newest' : 'oldest';
  let volumesHtml = '';

  books.forEach((book) => {
    const pagesRead = Math.max(0, Number(book.pages_read) || 0);
    const totalPages = Math.max(1, Number(book.total_pages) || 1);
    const isCompletedValue = Number(book.is_completed) === 1;
    const format = (book.file_format || '').toLowerCase();
    let rawDisplayTitle = book.title_alias || book.title || '';
    const pathText = book.file_path || '';
    const imgdirPathDisplay = pathText.replace(/[\\/]__folder__\.imgdir$/i, '');
    const pathDisplay = format === 'imgdir' ? imgdirPathDisplay : pathText;
    if (format === 'imgdir' && (!rawDisplayTitle || rawDisplayTitle === '__folder__')) {
      const normalized = (pathDisplay || '').replace(/\\/g, '/').replace(/\/+$/, '');
      rawDisplayTitle = normalized.split('/').pop() || '';
    }

    const imageDisplayTitle = stripLeadingBracketTags(rawDisplayTitle);
    const coverSrc = getBookCoverSrc({
      coverImage: book.cover_image,
      title: imageDisplayTitle,
      format: book.file_format,
      seed: book.id || book.file_path || `${safeSeriesName}:${imageDisplayTitle}`
    });
    buildFallbackCoverUrl({ id: book.id, title: imageDisplayTitle, format: book.file_format, seed: book.id });
    const coverObjectPosition = coverAlignToObjectPosition(book.cover_align);
    const progressPercent = totalPages > 0 ? Math.min(100, Math.round((pagesRead / totalPages) * 100)) : 0;
    const isNotCompleted = !isCompletedValue;
    const isDownloadable = ['epub', 'pdf', 'txt', 'text'].includes(format);
    const completedLabel = i18n.t('detail.badge_completed') || '완독';

    volumesHtml += `
         <div class="vol-grid-card${!isCompletedValue && pagesRead === 0 ? ' unread-card' : ''}"
           data-role="detail-volume-open-reader"
           data-book-id="${book.id}"
           data-cover-align="${book.cover_align || 'center'}"
           data-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}"
           data-book-title="${(rawDisplayTitle || '').replace(/"/g, '&quot;')}"
           data-file-format="${(book.file_format || '').replace(/"/g, '&quot;')}"
           data-pages-read="${pagesRead}"
           data-total-pages="${book.total_pages}"
           data-is-completed="${isCompletedValue ? 1 : 0}"
           style="${unreadOnly && !isNotCompleted ? 'display: none;' : ''}">
        <div class="vol-grid-thumb-container" style="position: relative; width: 100%; aspect-ratio: 1 / 1.45; overflow: hidden; border-radius: 8px;">
          <img class="vol-grid-thumb" src="${coverSrc}" alt="cover" data-title="${(imageDisplayTitle || '').replace(/"/g, '&quot;')}" data-format="${book.file_format || 'text'}"
               onerror="window.handleCoverError(this)" style="width: 100%; height: 100%; object-fit: cover; object-position: ${coverObjectPosition} center;">
          ${isCompletedValue ? `<span class="vol-grid-completed-dot" title="${completedLabel}" aria-label="${completedLabel}"></span>` : ''}
          ${isDownloadable ? `<a class="vol-grid-download-btn"
             href="/api/media/books/${book.id}/download?type=${dbType}"
             download
             title="${i18n.t('detail.btn_download') || '다운로드'}"
             data-role="detail-download-link">
            <i class="fa-solid fa-download"></i>
          </a>` : ''}
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
        <button type="button" class="volume-filter-btn${unreadOnly ? ' active' : ''}" data-role="detail-volume-filter" data-detail-unread-filter aria-pressed="${unreadOnly}">
          ${i18n.t('detail.unread_only')}
        </button>
        <div class="volume-sort-control" role="group" aria-label="${i18n.t('detail.sort_order')}">
          <button type="button" class="volume-sort-btn${sortOrder === 'oldest' ? ' active' : ''}" data-role="detail-volume-sort" data-sort="oldest" data-detail-sort="oldest" aria-pressed="${sortOrder === 'oldest'}">${i18n.t('detail.sort_oldest')}</button>
          <button type="button" class="volume-sort-btn${sortOrder === 'newest' ? ' active' : ''}" data-role="detail-volume-sort" data-sort="newest" data-detail-sort="newest" aria-pressed="${sortOrder === 'newest'}">${i18n.t('detail.sort_newest')}</button>
        </div>
      </div>
    </div>
    <div class="volumes-list-grid">
      ${volumesHtml}
    </div>
    <div class="volumes-empty-filter" style="display: none;">${i18n.t('detail.no_unread_books')}</div>
  </div>
`;
}