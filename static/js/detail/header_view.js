import { buildFallbackCoverUrl, getBookCoverSrc } from '../cover_fallback.js';
import { state } from '../state.js';
import { stripLeadingBracketTags } from '../series_display.js';
import { formatClockDuration } from '../utils/time.js';

function normalizeMetadataToken(token) {
  if (!token) return '';
  return String(token)
    .replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

// author/publisher/summary/genre/tags/link/series_alias 등은 사용자/플러그인/MCP 쓰기 도구가
// 자유 텍스트로 채울 수 있는 필드라, 텍스트 노드/속성값으로 꽂기 전에 항상 이스케이프해야 한다
// (과거 이 파일은 이 필드들을 이스케이프 없이 innerHTML에 직접 삽입해 저장형 XSS가 가능했다).
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// href로 쓰기 전에 http(s)/상대경로만 허용 - javascript: 등 위험한 프로토콜 차단
function safeHref(url) {
  const trimmed = String(url || '').trim();
  if (/^https?:\/\//i.test(trimmed) || trimmed.startsWith('/')) return trimmed;
  return '';
}

export function renderDetailHeader(meta, books, safeSeriesName, actualLibraryId, displayTitle = '') {
  const booksLvValue = String(meta.books_lv || '').trim().toLowerCase();
  const isAdultMangaRating = ['r18', 'r18+', '성인망가', 'adult manga'].includes(booksLvValue);
  const isPornRating = [
    'adult only', 'adult only 18+', 'adultsonly18+', 'adults only 18+',
    'x18+', '포르노', 'porn', 'pornography',
  ].includes(booksLvValue);
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
  const safeLinkUrl = safeHref(meta.link);
  // 바깥 링크(리디북스 등)는 버튼 상자 대신 메타 줄 끝의 글자 링크
  const linkHtml = safeLinkUrl
    ? `<a href="${escapeHtml(safeLinkUrl)}" target="_blank" rel="noopener noreferrer" class="meta-item detail-meta-link">${i18n.t('detail.ridi_link')} <i class="lc lc-external-link"></i></a>`
    : '';

  const ratingLevel = Number(meta.content_rating_level);
  let ratingBadgeHtml = '';
  if (state.showContentRatingBadge === true && Number.isFinite(ratingLevel)) {
    // 배지 배경은 .detail-badge가 이 글자색을 옅게 섞어 만든다
    const ratingColorMap = {
      0: { fg: '#94a3b8' },
      15: { fg: '#eab308' },
      18: { fg: '#ef4444' },
      19: { fg: '#c084fc' },
      20: { fg: '#f43f5e' },
    };
    const colors = ratingColorMap[ratingLevel] || ratingColorMap[18];
    const ratingLabelMap = {
      0: '전체이용가', 15: '15세이상', 18: '18세이상(성인)',
      19: '성인망가', 20: '포르노',
    };
    const ratingLabelKo = meta.content_rating_label || ratingLabelMap[ratingLevel] || '포르노';
    const ratingKey = `detail.rating_level_${ratingLevel}`;
    const ratingLabel = i18n.t(ratingKey) !== ratingKey ? i18n.t(ratingKey) : ratingLabelKo;
    ratingBadgeHtml = `
      <span class="badge detail-badge" data-role="detail-rating-badge" title="${i18n.t('detail.rating_badge_title')}" style="--badge-color: ${colors.fg};">
        <i class="lc lc-shield-half"></i>${ratingLabel}
      </span>
    `;
  }

  // 연재상태 배지 - 등급 배지와 달리 민감 정보가 아니므로(개인 취향 토글 없이) 항상 노출.
  // tools/scanner/metadata/kavita_yaml.py가 채워 넣는 books.publication_status(원본 코드)를
  // services/book_detail_service.py가 라벨로 변환해 내려준다. 값이 없거나(아직 재스캔 전)
  // 인식 못 하는 코드면 "알 수 없음"으로 표시된다.
  const publicationStatusColorMap = {
    '연재': { fg: '#60a5fa' },
    '휴재': { fg: '#eab308' },
    '완결': { fg: '#4ade80' },
  };
  const publicationStatusLabel = meta.publication_status_label || '알 수 없음';
  const publicationStatusColors = publicationStatusColorMap[publicationStatusLabel] || { fg: '#94a3b8' };
  const publicationStatusCode = ['0', '1', '2'].includes(String(meta.publication_status ?? '')) ? String(meta.publication_status) : 'unknown';
  const publicationStatusKey = `detail.publication_status_${publicationStatusCode}`;
  const publicationStatusText = i18n.t(publicationStatusKey) !== publicationStatusKey ? i18n.t(publicationStatusKey) : publicationStatusLabel;
  const publicationStatusBadgeHtml = `
    <span class="badge detail-badge" data-role="detail-publication-status-badge" title="${i18n.t('detail.publication_status_title')}" style="--badge-color: ${publicationStatusColors.fg};">
      <i class="fa-solid fa-bookmark"></i>${escapeHtml(publicationStatusText)}
    </span>
  `;

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

  // 장르·태그 줄: 상자 없는 글자 링크(.detail-chip). 누르면 그 장르·태그로 목록 필터.
  // "+N"은 접힌 나머지를 펼친다 (interactions.js detail-collapse-toggle이 다음 형제를 inline-flex로)
  const buildChipRow = (items, { kind, label, icon, dataAttr, role, toggleTitle }) => {
    if (items.length === 0) return '';
    const visible = shouldCollapse ? items.slice(0, 1) : items;
    const hidden = shouldCollapse ? items.slice(1) : [];
    const chip = (value) => `
      <span class="badge detail-chip detail-chip--${kind}" data-role="${role}" ${dataAttr}="${escapeHtml(value)}">
        <i class="${icon}"></i>${escapeHtml(value)}
      </span>
    `;
    const toggleHtml = hidden.length > 0 ? `
      <span class="badge detail-chip detail-chip--more collapse-toggle-btn" data-role="detail-collapse-toggle" title="${toggleTitle}">+${hidden.length}</span>
      <span class="hidden-${kind}s-wrap detail-chip-hidden" style="display: none;">${hidden.map(chip).join('')}</span>
    ` : '';
    return `
      <div class="detail-${kind}-row detail-chip-row">
        <span class="detail-chip-label">${label}</span>
        ${visible.map(chip).join('')}
        ${toggleHtml}
      </div>
    `;
  };

  const genreRowHtml = buildChipRow(genresArr, {
    kind: 'genre', label: i18n.t('detail.chip_genre'), icon: 'lc lc-tag', dataAttr: 'data-genre',
    role: 'detail-genre-filter', toggleTitle: i18n.t('detail.chip_genre_expand'),
  });
  const tagRowHtml = buildChipRow(tagsArr, {
    kind: 'tag', label: i18n.t('detail.chip_tag'), icon: 'lc lc-hash', dataAttr: 'data-tag',
    role: 'detail-tag-filter', toggleTitle: i18n.t('detail.chip_tag_expand'),
  });

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
      <div class="vol-warn-banner detail-warn-banner">
        <i class="lc lc-triangle-alert"></i>
        <span>${i18n.t('detail.warn_series_missing_pages', { count: missingPageCount })}</span>
        <button class="btn-rescan-book" data-role="detail-rescan-missing" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}">
          <i class="lc lc-rotate-cw"></i> ${i18n.t('detail.btn_rescan_all')}
        </button>
      </div>
    ` : '';

  const isSeriesFav = books.some((book) => book.is_favorite === 1);
  const seriesFavIconClass = isSeriesFav ? 'fa-solid fa-star' : 'lc lc-star';
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

  const isVideoLib = state.currentLibraryType === 'video' || (books && books.length > 0 && books[0].video_id != null);

  let hasVideoProgress = false;
  if (isVideoLib && meta) {
    const curTime = Number(meta.current_time || 0);
    const totalPct = Number(meta.total_progress_pct || 0);
    if (curTime > 0 || totalPct > 0 || meta.current_episode_id || Number(meta.is_completed) === 1) {
      hasVideoProgress = true;
      continueReason = 'in-progress';
      if (meta.current_episode_id && books && books.length > 0) {
        continueTarget = books.find((b) => Number(b.id) === Number(meta.current_episode_id));
      }
      if (!continueTarget && books && books.length > 0) {
        continueTarget = books[0];
      }
    }
  }

  if (!continueTarget && isVideoLib && books && books.length > 0) {
    continueTarget = books[0];
    continueReason = 'first';
  }

  if (!continueTarget && !isVideoLib && books && books.length > 0) {
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
    let iconClass = 'lc lc-play';
    const continueFmt = String(continueTarget.file_format || '').toLowerCase();
    const isAudioContext = state.currentLibraryType === 'audiobook' || ['audiobook', 'mp3', 'm4a', 'm4b', 'flac', 'aac', 'wav', 'ogg', 'opus', 'wma'].includes(continueFmt);
    const isVideoBtnContext = isVideoLib || continueTarget.video_id != null;

    let progressPercent = 0;
    if ((hasAudioProgress || hasVideoProgress) && meta && Number(meta.total_progress_pct) > 0) {
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
      btnLabel = isVideoBtnContext
        ? i18n.t('detail.continue_watching')
        : isAudioContext
          ? (i18n.t('detail.continue_listening') || '이어서 듣기')
          : (i18n.t('detail.continue_reading') || '이어서 읽기');
      tooltipTitle = `${continueTarget.title}${progressPercent > 0 ? ` (${progressPercent}%)` : ''}`;
      iconClass = isVideoBtnContext ? 'lc lc-clapperboard' : isAudioContext ? 'lc lc-headphones' : 'lc lc-play';
    } else if (continueReason === 'recent') {
      btnLabel = isVideoBtnContext
        ? i18n.t('detail.continue_watching')
        : isAudioContext
          ? (i18n.t('detail.continue_listening') || '이어서 듣기')
          : (i18n.t('detail.continue_reading') || '이어서 읽기');
      tooltipTitle = continueTarget.title;
      iconClass = isVideoBtnContext ? 'lc lc-clapperboard' : isAudioContext ? 'lc lc-headphones' : 'lc lc-play';
    } else {
      btnLabel = isVideoBtnContext
        ? i18n.t('detail.start_watching')
        : isAudioContext
          ? (i18n.t('detail.start_listening') || '처음부터 듣기')
          : (i18n.t('detail.start_reading') || '첫 권부터 읽기');
      tooltipTitle = continueTarget.title;
      iconClass = isVideoBtnContext ? 'lc lc-clapperboard' : isAudioContext ? 'lc lc-headphones' : 'lc lc-book-open-text';
    }

    const resumeTrackId = (meta && meta.current_track_id) ? meta.current_track_id : continueTarget.id;
    const resumeStartTime = (meta && Number(meta.current_time) > 0) ? Number(meta.current_time) : (continueTarget.pages_read || 0);
    const continueAction = isVideoBtnContext ? 'video' : (isAudioContext ? 'audio' : 'reader');
    continueBtnHtml = `
      <button class="ridi-link-btn ridi-link-btn--primary"
              data-role="detail-continue"
              data-continue-action="${continueAction}"
              data-audiobook-id="${(meta && meta.id) ? meta.id : (continueTarget.audiobook_id || continueTarget.id || '')}"
              data-track-id="${resumeTrackId || ''}"
              data-video-id="${(meta && meta.id) ? meta.id : (continueTarget.video_id || '')}"
              data-episode-id="${(meta && meta.current_episode_id) ? meta.current_episode_id : (continueTarget.video_id ? continueTarget.id : '')}"
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
  // 서버는 설명이 없으면 한국어 기본 문구를 넣어 보낸다 - 화면에는 현재 언어로
  const summaryTextRaw = (!meta.summary || meta.summary === '등록된 설명이 없습니다.') ? i18n.t('detail.no_description') : meta.summary;
  const summaryText = escapeHtml(summaryTextRaw);
  const summaryLineBreaks = (String(summaryTextRaw).match(/\n/g) || []).length;
  const shouldShowSummaryToggle = String(summaryTextRaw).length > 260 || summaryLineBreaks >= 5;
  const summaryToggleLabelMore = i18n.t('detail.summary_more') || '더보기';
  const summaryToggleLabelLess = i18n.t('detail.summary_less') || '접기';
  const isAudiobookContext = state.currentLibraryType === 'audiobook';
  // 음악 카테고리(오디오북 세션 '음악' 속성): 책 전용 정보(ISBN/출판사/권/별점/청취 완료/메타 검색)를 숨기고
  // 아티스트 · 곡 수 · 총 길이 · 연도 · 장르 한 줄과 [재생] [셔플 재생] [재스캔]만 둔다.
  const isMusicContext = isAudiobookContext && !!(meta && meta.is_music);
  const isAudiobookCompleted = isAudiobookContext && Number(meta.is_completed) === 1;
  const audiobookCompletedBadgeHtml = (isAudiobookContext && !isMusicContext) ? `
    <span class="audiobook-completed-badge${isAudiobookCompleted ? ' is-visible' : ''}" data-audiobook-completed="${meta.id || ''}">
      <i class="lc lc-headphones"></i> ${i18n.t('detail.audiobook_completed')}
    </span>
  ` : '';
  // 영상 강좌는 show.yaml 스캔 메타 전용이라 즐겨찾기/편집/플러그인 메타검색/커버 업로드/
  // 개별 재스캔/전체완료 표시 등 "도서 카탈로그 편집" 계열 버튼에 대응하는 백엔드가 없다 - 헤더에서 숨김.
  const isVideoContext = state.currentLibraryType === 'video';
  const markSeriesCompletedLabel = isAudiobookContext
    ? i18n.t('detail.btn_mark_audiobook_completed')
    : i18n.t('detail.btn_mark_series_completed');
  const markSeriesUnreadLabel = isAudiobookContext
    ? i18n.t('detail.btn_mark_audiobook_unread')
    : i18n.t('detail.btn_mark_series_unread');
  const markSeriesCompletedBtnHtml = (isVideoContext || isMusicContext) ? '' : `
    <button type="button" class="detail-more-item" data-role="detail-mark-series-complete" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}"><i class="lc lc-circle-check"></i> ${markSeriesCompletedLabel}</button>
    <button type="button" class="detail-more-item" data-role="detail-mark-series-unread" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}"><i class="lc lc-eye-off"></i> ${markSeriesUnreadLabel}</button>
  `;
  const identifierLabel = 'ISBN(WEB_ID)';
  const identifierValue = escapeHtml((isAudiobookContext || isVideoContext) ? (meta.web_id || '-') : (meta.isbn || '-'));
  const identifierEditValue = escapeHtml((isAudiobookContext || isVideoContext) ? (meta.web_id || '') : (meta.isbn || ''));
  const detailLockedBadgeHtml = isLocked ? `
    <div class="book-card-locked-badge" title="${i18n.t('book_list.metadata_locked')}">
      <i class="lc lc-lock"></i>
    </div>
  ` : '';
  const unlockBtnHtml = isLocked ? `
    <button type="button" class="detail-more-item btn-unlock-metadata" data-role="detail-unlock-metadata" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" data-book-id="${isAudiobookContext ? (meta.id || '') : (firstBookId || '')}" title="메타데이터 잠금을 해제하고 자동 스캔 갱신을 허용합니다">
      <i class="lc lc-lock-open"></i> ${i18n.t('detail.unlock_metadata')}
    </button>
  ` : '';
  // 그리드 카드에서 이 표시를 없애고(카드가 많을 때 잡음이 심했음) 상세화면에서만
  // 보여주기로 함 - has_metadata는 book_detail_service.py가 계산해서 내려준다.
  const metadataMissingBadgeHtml = (!isMusicContext && Number(meta && meta.has_metadata) === 0) ? `
    <span class="detail-metadata-missing-badge" title="${i18n.t('detail.metadata_missing_title')}" aria-label="${i18n.t('detail.metadata_missing_title')}">
      <i class="lc lc-unlink" aria-hidden="true"></i> ${i18n.t('detail.metadata_missing') || '메타데이터 없음'}
    </span>
  ` : '';

  const seriesFavBtnHtml = `
          <button class="btn-fav-toggle detail-series-fav" data-role="detail-series-favorite" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" data-next-status="${isSeriesFav ? 1 : 0}" style="color:${seriesFavIconColor};" title="${i18n.t('detail.toggle_fav_series')}">
            <i class="${seriesFavIconClass}"></i>
          </button>
  `;
  const editToggleBtnHtml = isVideoContext ? '' : `
          <button type="button" class="detail-more-item btn-edit-toggle" data-role="detail-edit-toggle">
            <i class="lc lc-square-pen"></i> ${i18n.t('detail.edit_info')}
          </button>
  `;
  const coverUploadOverlayHtml = isVideoContext ? '' : `
        <div class="cover-upload-overlay" id="cover-upload-overlay-btn" data-role="detail-cover-upload">
          <i class="lc lc-camera"></i>
          <span>${i18n.t('detail.change_cover')}</span>
        </div>
        <input type="file" id="cover-upload-file-input" data-role="detail-cover-file-input" accept="image/*" style="display: none;">
  `;
  const pluginMetaSearchBtnHtml = (isVideoContext || isMusicContext) ? '' : `
          <button type="button" id="btn-plugin-meta-search" class="detail-more-item" data-role="detail-plugin-meta-search" data-book-id="${firstBookId || ''}" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}"><i class="lc lc-search"></i> ${i18n.t('detail.btn_search_meta')}</button>
  `;
  const rescanSeriesBtnHtml = isVideoContext ? '' : `
          <button type="button" class="detail-more-item" data-role="detail-rescan-series" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}"><i class="lc lc-refresh-cw"></i> ${isMusicContext ? i18n.t('detail.rescan_short') : i18n.t('detail.btn_rescan_series')}</button>
  `;
  const volumeCountLabel = i18n.t(isVideoContext ? 'book_list.video_episodes' : 'detail.volume_count', { n: books.length });
  // 원격 음악은 재생 전엔 곡 길이를 모르므로(0) 모든 곡 길이를 알 때만 총 재생시간을 보인다
  const musicTotalSeconds = books.length > 0 && books.every((book) => Number(book.duration) > 0)
    ? books.reduce((sum, book) => sum + Number(book.duration), 0)
    : 0;
  const musicMetaHtml = isMusicContext ? [
    meta.author && meta.author !== '-' ? `<span class="meta-item"><i class="lc lc-user"></i> ${escapeHtml(meta.author)}</span>` : '',
    `<span class="meta-item"><i class="lc lc-music"></i> ${i18n.t('detail.track_count', { n: books.length })}</span>`,
    musicTotalSeconds > 0 ? `<span class="meta-item"><i class="lc lc-clock"></i> ${formatClockDuration(musicTotalSeconds)}</span>` : '',
    meta.music_year ? `<span class="meta-item"><i class="lc lc-calendar"></i> ${escapeHtml(meta.music_year)}</span>` : '',
    meta.music_genres ? `<span class="meta-item"><i class="lc lc-tag"></i> ${escapeHtml(meta.music_genres)}</span>` : '',
  ].join('') : '';
  const musicShuffleBtnHtml = isMusicContext ? `
          <button class="ridi-link-btn" data-role="detail-music-shuffle" data-audiobook-id="${meta.id || ''}"><i class="lc lc-shuffle"></i> ${i18n.t('detail.shuffle_play')}</button>
  ` : '';
  if (isMusicContext && continueTarget) {
    // 음악은 이어듣기가 없다: 항상 1번 곡부터 [재생]
    continueBtnHtml = `
      <button class="ridi-link-btn ridi-link-btn--primary"
              data-role="detail-continue" data-continue-action="audio" data-audiobook-id="${meta.id || ''}"
              data-track-id="${books[0] ? books[0].id : ''}" data-start-time="0">
        <i class="lc lc-play"></i> ${i18n.t('collections.action_play')}
      </button>
    `;
  }

  // ⋯ 더보기: 메뉴는 body로 빼지 않고 헤더 안에 둔다 - index.js가 렌더 직후 #btn-manual-meta-search를,
  // metadata_editor.js가 .btn-edit-toggle을 직접 찾아 다루기 때문. 열고 닫기는 interactions.js(detail-more-toggle)
  const recommendMatchBtnHtml = (isVideoContext || isMusicContext) ? '' : `
          <button type="button" id="btn-manual-meta-search" class="detail-more-item" style="display:none;"><i class="lc lc-wand-sparkles"></i> ${i18n.t('detail.btn_recommend_match')}</button>
  `;
  const moreItemsHtml = [
    recommendMatchBtnHtml,
    pluginMetaSearchBtnHtml,
    rescanSeriesBtnHtml,
    markSeriesCompletedBtnHtml,
    editToggleBtnHtml,
    unlockBtnHtml,
  ].join('').trim();
  const moreLabel = i18n.t('detail.more_actions');
  const moreMenuHtml = moreItemsHtml ? `
          <div class="detail-more">
            <button type="button" class="detail-more-toggle" data-role="detail-more-toggle" aria-haspopup="menu" aria-expanded="false" title="${moreLabel}" aria-label="${moreLabel}">
              <i class="lc lc-ellipsis"></i>
            </button>
            <div class="detail-more-menu" role="menu">
              ${moreItemsHtml}
            </div>
          </div>
  ` : '';

  return `
    <!-- 상단 헤더: 커버(작게) + 메타정보 -->
    <div class="detail-header-panel">
      <div class="detail-cover-container${isMusicContext ? ' is-square' : ''}" data-role="detail-cover-dropzone" style="position: relative;">
           <img class="detail-cover-sm" id="detail-cover-img-preview" src="${coverSrc}" alt="Cover" data-title="${(visibleTitle || '').replace(/"/g, '&quot;')}" data-format="${headerFormat}"
              onerror="window.handleCoverError(this)">
        ${detailLockedBadgeHtml}
        ${coverUploadOverlayHtml}
      </div>

      <!-- 뷰어 모드 (일반 노출) -->
      <div id="detail-header-meta-view" class="detail-header-meta">
        <h3 class="book-detail-title">
          ${escapeHtml(meta.series_alias || visibleTitle)}
          ${meta.series_alias ? `<span class="detail-title-alias">(${escapeHtml(visibleTitle)})</span>` : ''}
          ${audiobookCompletedBadgeHtml}
          ${metadataMissingBadgeHtml}
          ${seriesFavBtnHtml}
        </h3>
        <div class="detail-meta">
          ${isMusicContext ? musicMetaHtml : `
          <span class="meta-item"><i class="lc lc-pen-tool"></i> ${escapeHtml(meta.author || '-')}</span>
          <span class="meta-item"><i class="lc lc-barcode"></i> ${identifierLabel}: ${identifierValue}</span>
          <span class="meta-item"><i class="lc lc-building"></i> ${escapeHtml(meta.publisher || '-')}</span>
          <span class="meta-item"><i class="lc lc-book-open"></i> ${volumeCountLabel}</span>`}
          ${linkHtml}
        </div>
        <div class="detail-meta-tags">
          ${!isMusicContext && (ratingBadgeHtml || publicationStatusBadgeHtml) ? `<div class="detail-rating-row">${ratingBadgeHtml}${publicationStatusBadgeHtml}</div>` : ''}
          ${genreRowHtml}
          ${tagRowHtml}
        </div>
        ${missingPageBannerHtml}
        ${isMusicContext ? '' : `<div class="detail-score" id="detail-score-root" data-static-stars="${stars}">${stars}</div>`}
      </div>

      <!-- 요약/설명 + 액션 버튼: 커버 폭에 갇히지 않도록 전체 너비 별도 줄로 배치(커버 아래 빈 공간 재활용) -->
      <div id="detail-header-full-row" class="detail-header-full-row">
        <div class="book-summary-wrap${shouldShowSummaryToggle ? ' has-toggle' : ''}"${isMusicContext && (!meta.summary || meta.summary === '등록된 설명이 없습니다.' || meta.summary === i18n.t('detail.no_description')) ? ' hidden' : ''}>
          <p class="book-summary-text${shouldShowSummaryToggle ? ' is-collapsed' : ''}">${summaryText}</p>
          ${shouldShowSummaryToggle ? `
          <button class="book-summary-toggle" type="button"
            aria-expanded="false"
            data-role="detail-summary-toggle" data-more-label="${summaryToggleLabelMore.replace(/"/g, '&quot;')}" data-less-label="${summaryToggleLabelLess.replace(/"/g, '&quot;')}">${summaryToggleLabelMore}</button>
          ` : ''}
        </div>

        <!-- 버튼: 주 버튼(이어서 읽기)만 밖에, 관리용 동작은 ⋯ 메뉴 안에 -->
        <div class="detail-actions">
          ${continueBtnHtml}
          ${musicShuffleBtnHtml}
          ${moreMenuHtml}
        </div>
      </div>

      <!-- 편집 모드 (수동 입력 폼) -->
      <div id="detail-header-meta-edit" class="detail-header-meta" style="display: none;">
        <h3 class="book-detail-title" style="margin-bottom: 0.5rem; font-size: 1.3rem;">${i18n.t('detail.edit_title')} <span style="font-size: 0.8rem; color: var(--app-text-muted); font-weight: normal; margin-left: 0.5rem;">${i18n.t('detail.edit_subtitle')}</span></h3>
        <div class="edit-meta-form-group">
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.series_alias_label')}</label>
            <input type="text" id="edit-series-alias-input" class="edit-meta-input" value="${escapeHtml(meta.series_alias || '')}" placeholder="${i18n.t('detail.series_alias_placeholder')}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_author')}</label>
            <input type="text" id="edit-author-input" class="edit-meta-input" value="${escapeHtml(meta.author === '-' ? '' : meta.author)}">
          </div>
          <div class="edit-meta-row-item">
            <label>${identifierLabel}</label>
            <input type="text" id="edit-isbn-input" class="edit-meta-input" value="${identifierEditValue}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_publisher')}</label>
            <input type="text" id="edit-publisher-input" class="edit-meta-input" value="${escapeHtml(meta.publisher === '-' ? '' : meta.publisher)}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_ridi_link')}</label>
            <input type="text" id="edit-link-input" class="edit-meta-input" value="${escapeHtml(meta.link || '')}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_genre')}</label>
            <input type="text" id="edit-genre-input" class="edit-meta-input" value="${escapeHtml(meta.genre || '')}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_tags')}</label>
            <input type="text" id="edit-tags-input" class="edit-meta-input" value="${escapeHtml(meta.tags || '')}">
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_books_lv')}</label>
            <select id="edit-books-lv-input" class="edit-meta-input">
              <option value="" ${!booksLvValue ? 'selected' : ''}>${i18n.t('detail.books_lv_unset')}</option>
              <option value="everyone" ${booksLvValue === 'everyone' ? 'selected' : ''}>everyone</option>
              <option value="일반" ${booksLvValue === '일반' ? 'selected' : ''}>일반</option>
              <option value="ma15+" ${booksLvValue === 'ma15+' ? 'selected' : ''}>ma15+</option>
              <option value="m" ${booksLvValue === 'm' ? 'selected' : ''}>m</option>
              <option value="15세" ${booksLvValue === '15세' ? 'selected' : ''}>15세</option>
              <option value="r18" ${isAdultMangaRating ? 'selected' : ''}>${i18n.t('detail.lv_r18')}</option>
              <option value="adult only 18+" ${isPornRating ? 'selected' : ''}>${i18n.t('detail.lv_adult_only')}</option>
              <option value="18세" ${['18세', '18세이상', '18세이상(성인)', '성인'].includes(booksLvValue) ? 'selected' : ''}>18세</option>
            </select>
          </div>
          <div class="edit-meta-row-item">
            <label>${i18n.t('detail.label_summary')}</label>
            <textarea id="edit-summary-input" class="edit-meta-textarea">${escapeHtml(meta.summary === i18n.t('detail.no_description') || meta.summary === '등록된 설명이 없습니다.' ? '' : meta.summary)}</textarea>
          </div>
        </div>
        <div class="edit-meta-buttons-row">
          <button class="ridi-link-btn ridi-link-btn--primary" data-role="detail-save-meta" data-series-name="${safeSeriesName.replace(/"/g, '&quot;')}" data-library-id="${actualLibraryId}" data-audiobook-id="${isAudiobookContext ? (meta.id || '') : ''}">${i18n.t('detail.btn_save')}</button>
          <button class="ridi-link-btn" data-role="detail-cancel-meta">${i18n.t('detail.btn_cancel')}</button>
        </div>
      </div>
      
      <!-- 유사 메타데이터 추천 영역 (음악 카테고리는 도서 메타 추천 대상이 아님) -->
      ${isMusicContext ? '' : `<div id="meta-recommend-section" style="display:none; margin-top: 1rem; padding: 1rem; background: rgba(var(--app-panel-rgb), 0.5); border: 1px dashed rgba(168, 85, 247, 0.4); border-radius: 8px; width: 100%;">
        <h5 style="margin: 0 0 0.8rem 0; color: var(--app-accent-hover); font-size: 0.85rem;"><i class="lc lc-wand-sparkles"></i> ${i18n.t('detail.title_recommend')}</h5>
        <div id="recommend-candidates-list" style="display: flex; flex-direction: column; gap: 0.6rem;">
          <div style="font-size:0.75rem; color: var(--app-text-muted);"><i class="lc lc-loader-circle lc-spin"></i> ${i18n.t('detail.loading_recommend')}</div>
        </div>
      </div>`}
    </div>
  `;
}
