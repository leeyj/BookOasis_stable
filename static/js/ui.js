// ui.js – UI 렌더링 및 그리드 함수들
import { state } from './state.js';
import { openBookDetail } from './modal.js';
import { openReader } from './viewer.js';
import { showToast } from './view_manager.js';
import { buildFallbackCoverUrl, getBookCoverSrc, buildTextCoverDataUri } from './cover_fallback.js';
import { stripLeadingBracketTags, middleTruncateTitle } from './series_display.js';
import './scan_activity_status.js';

// 지연 로딩을 위한 단일 싱글톤 IntersectionObserver 인스턴스
const lazyImageObserver = ('IntersectionObserver' in window)
  ? new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const lazyImage = entry.target;
        if (lazyImage.dataset.src) {
          lazyImage.src = lazyImage.dataset.src;
          lazyImage.removeAttribute('data-src');
        }
        observer.unobserve(lazyImage);
      }
    });
  }, {
    rootMargin: '200px 0px',
    threshold: 0.01
  })
  : null;



function normalizeBookTitle(item) {
  let title = item.title || '';
  const fmt = (item.file_format || '').toLowerCase();
  const filePath = item.file_path || '';

  if (fmt === 'imgdir') {
    if (!title || title === '__folder__') {
      const normalized = filePath
        .replace(/\\/g, '/')
        .replace(/\/+$/, '')
        .replace(/\/__folder__\.imgdir$/i, '');
      const segments = normalized.split('/').filter(Boolean);
      if (segments.length > 0) {
        title = segments[segments.length - 1];
      }
    }
  }

  return title;
}

function resolveCardDisplayTitle(item, showVolumeCount) {
  if (item.series_alias) {
    return item.series_alias;
  }
  if (item.display_name) {
    return item.display_name;
  }
  const rawNormalizedTitle = String(normalizeBookTitle(item) || '').trim();
  const rawRepresentativeTitle = String(item.representative_title || '').trim();
  const rawSeriesName = String(item.series_name || '').trim();
  const rawAnchorDir = String(item.anchor_dir || '').trim();
  const normalizedTitle = stripLeadingBracketTags(rawNormalizedTitle);
  const representativeTitle = stripLeadingBracketTags(rawRepresentativeTitle);
  const seriesName = stripLeadingBracketTags(rawSeriesName);
  let anchorDirTitle = '';
  if (rawAnchorDir) {
    const normalizedDir = rawAnchorDir.replace(/\\/g, '/').replace(/\/+$/, '');
    const segments = normalizedDir.split('/').filter(Boolean);
    if (segments.length > 0) {
      anchorDirTitle = stripLeadingBracketTags(segments[segments.length - 1]);
    }
  }
  // Single-volume groups should open detail with the actual title, not author-like series labels.
  const bookCount = parseInt(item.book_count, 10) || 0;
  if (showVolumeCount && bookCount === 1) {
    if (anchorDirTitle) {
      return anchorDirTitle;
    }

    if (rawRepresentativeTitle && seriesName) {
      const escapedSeries = seriesName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const bracketPrefix = new RegExp(`^\\[\\s*${escapedSeries}\\s*\\]\\s*(.+)$`, 'i');
      const match = rawRepresentativeTitle.match(bracketPrefix);
      if (match && match[1] && match[1].trim()) {
        const extracted = stripLeadingBracketTags(match[1].trim());
        if (extracted) return extracted;
      }
    }

    const looksLikeFileLabel = /(^\d{1,4}\s*[-_.]\s*\d|\[(txt|epub|pdf|cbz|zip)\]\s*$|\.(txt|epub|pdf|cbz|zip)\s*$)/i
      .test(rawRepresentativeTitle);
    if (looksLikeFileLabel && seriesName) {
      return seriesName;
    }

    return representativeTitle || seriesName || normalizedTitle;
  }
  return seriesName || representativeTitle || normalizedTitle;
}


/**
 * ────────────────────────────────────────────────────────
 * 📌 공통 도서 카드 엘리먼트 생성기 (Kavita 스타일 컴포넌트)
 * ────────────────────────────────────────────────────────
 * @param {Object} item - 도서 또는 시리즈 데이터 객체
 * @param {Object} options - 카드별 렌더링 분기 옵션
 * @param {boolean} options.showProgress - 진행률(퍼센트) 배지 노출 여부
 * @param {boolean} options.showVolumeCount - 권수 배지 노출 여부
 * @param {string} options.markUnreadScope - 읽지 않음 처리 범위 ('book' 또는 'series')
 * @param {boolean} options.isNew - 신규 도서 서브텍스트 노출 여부
 * @param {string} options.actionTitle - 책 모양 버튼 툴팁 타이틀
 * @param {function} options.onPrimaryClick - 카드 본체 클릭 핸들러 (e, item)
 * @param {function} options.onActionClick - 책 아이콘(바로보기) 클릭 핸들러 (e, item)
 * @returns {HTMLElement} 생성된 카드 DOM 객체
 */
export function createBookCard(item, options = {}) {
  const card = document.createElement('div');
  card.className = 'book-card';
  card.dataset.bookId = item.id || item.representative_book_id || '';

  const fmt = String(item.file_format || '').toLowerCase();
  const hasTrackCount = Number(item.total_tracks || 0) > 0;
  const isAudiobook = (
    ['audiobook', 'audio', 'mp3', 'm4a', 'm4b', 'flac', 'aac', 'wav', 'ogg', 'opus'].includes(fmt) ||
    hasTrackCount ||
    item.audiobook_id !== undefined
  );
  const coverFormat = isAudiobook ? 'audiobook' : item.file_format;

  const rawSeriesName = String(item.series_name || '').trim();
  const displayTitle = resolveCardDisplayTitle(item, options.showVolumeCount);
  card.dataset.title = displayTitle;
  card.dataset.markUnreadScope = options.markUnreadScope || 'book';
  card.dataset.seriesName = rawSeriesName;
  card.dataset.libraryId = item.library_id ?? '';
  const fallbackCoverSrc = buildFallbackCoverUrl({
    title: displayTitle,
    format: coverFormat,
    seed: item.id || item.representative_book_id || item.file_path || displayTitle
  });
  const coverSrc = getBookCoverSrc({
    coverImage: item.cover_image,
    title: displayTitle,
    format: coverFormat,
    seed: item.id || item.representative_book_id || item.file_path || displayTitle
  });
  const useLazyLoad = options.lazyLoad !== false;
  const shouldHideCover = !!state.currentLibraryHideCovers;

  // 1. 공통 카드 클릭 핸들러 (아이콘 및 별 클릭 분기, Swiper/가로 스크롤 드래그 삼킴 안전대책)
  let lastClickTime = 0;
  const handlePrimaryClick = (e) => {
    const now = Date.now();
    if (now - lastClickTime < 200) return; // 중복 호출 방지
    lastClickTime = now;

    if (e.target.closest('.btn-resume-series') || e.target.closest('.btn-card-fav-toggle')) {
      return;
    }
    console.log('[BookCard] Triggering handlePrimaryClick!', item);
    if (typeof options.onPrimaryClick === 'function') {
      options.onPrimaryClick(e, item);
    }
  };

  card.onclick = handlePrimaryClick;

  let pointerStartX = 0;
  let pointerStartY = 0;
  card.onpointerdown = (e) => {
    if (e.button !== 0) return;
    pointerStartX = e.clientX;
    pointerStartY = e.clientY;
  };
  card.onpointerup = (e) => {
    if (e.button !== 0) return;
    const diffX = Math.abs(e.clientX - pointerStartX);
    const diffY = Math.abs(e.clientY - pointerStartY);
    if (diffX < 8 && diffY < 8) {
      handlePrimaryClick(e);
    }
  };

  // 썸네일 상단 오버레이 메타(진행률/권수 배지)는 중복 노출 방지를 위해 숨김 처리
  const badgeHtml = '';

  // 제목 하단 메타 텍스트는 유지 (이어읽기/신규/오디오 정보)
  let subTextHtml = '';
  if (isAudiobook) {
    const chapters = (item.total_tracks !== undefined && Number(item.total_tracks) > 0)
      ? Number(item.total_tracks)
      : ((item.book_count !== undefined && Number(item.book_count) > 0) ? Number(item.book_count) : (Number(item.total_pages) || 1));
    subTextHtml = `<p class="book-card-sub-audio"><i class="fa-solid fa-headphones"></i> ${chapters}</p>`;
  } else if (item.pages_read > 0 && options.showProgress) {
    subTextHtml = `<p class="book-card-sub-progress">${i18n.t('dashboard.continue_reading', { pages: item.pages_read })}</p>`;
  }

  // 4. 즐겨찾기 버튼 구성
  const isFav = item.is_favorite === 1;
  const favIconClass = isFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
  const favoriteTargetName = rawSeriesName || displayTitle;
  const favBtnHtml = `
    <button class="btn-card-fav-toggle ${isFav ? 'active' : ''}" title="즐겨찾기 토글" data-role="card-favorite-toggle" data-favorite-name="${favoriteTargetName.replace(/"/g, '&quot;')}" data-book-id="${item.id || ''}" data-next-status="${isFav ? 0 : 1}">
      <i class="${favIconClass}"></i>
    </button>
  `;

  const lazyPlaceholder = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  const imgSrc = shouldHideCover ? fallbackCoverSrc : (useLazyLoad ? lazyPlaceholder : coverSrc);
  const imgDataSrcAttr = (!shouldHideCover && useLazyLoad) ? `data-src="${coverSrc}"` : '';

  // 5. 메타데이터 잠금 배지 구성 (커버 좌측 하단 녹색 자물쇠 아이콘)
  let lockedBadgeHtml = '';
  if (item.metadata_locked === 1 || item.metadata_locked === '1') {
    lockedBadgeHtml = `
      <div class="book-card-locked-badge" title="메타데이터 잠김 (수동 편집됨)">
        <i class="fa-solid fa-lock"></i>
      </div>
    `;
  }

  const audiobookCompletedDotHtml = isAudiobook && Number(item.is_completed) === 1
    ? `<span class="book-card-audiobook-completed" title="${i18n.t('detail.audiobook_completed')}" aria-label="${i18n.t('detail.audiobook_completed')}"></span>`
    : '';

  card.innerHTML = `
    <div class="book-card-cover">
      <div class="book-card-overlay"></div>
      <img src="${imgSrc}" ${imgDataSrcAttr} alt="${displayTitle}" decoding="async" loading="lazy">
      ${badgeHtml}
      ${favBtnHtml}
      ${lockedBadgeHtml}
      ${audiobookCompletedDotHtml}

      <button class="btn-resume-series" title="${options.actionTitle || '읽기'}">
        <i class="fa-solid fa-book-open"></i>
      </button>
    </div>
    <div class="book-card-info">
      <h4 class="book-card-title" title="${displayTitle}">${displayTitle}</h4>
      ${subTextHtml}
    </div>
  `;

  const imgEl = card.querySelector('img');
  if (imgEl && !shouldHideCover) {
    imgEl.onerror = () => {
      const currentSrc = imgEl.getAttribute('src') || '';
      if (currentSrc !== fallbackCoverSrc && !currentSrc.startsWith('data:image/svg+xml')) {
        imgEl.setAttribute('src', fallbackCoverSrc);
        return;
      }
      imgEl.onerror = null;
      const svgUri = buildTextCoverDataUri({ title: item.title, format: coverFormat, seed: item.id });
      imgEl.setAttribute('src', svgUri);
    };
  }

  if (imgEl && useLazyLoad && !shouldHideCover) {
    if (imgEl.dataset && imgEl.dataset.src) {
      if (lazyImageObserver) {
        lazyImageObserver.observe(imgEl);
      } else {
        imgEl.src = imgEl.dataset.src;
      }
    }
  }




  // 재생 버튼 클릭 핸들러 명시적 바인딩
  const resumeBtn = card.querySelector('.btn-resume-series');
  if (resumeBtn && typeof options.onActionClick === 'function') {
    resumeBtn.onclick = (e) => {
      e.stopPropagation();
      e.preventDefault();
      options.onActionClick(e, item);
    };
  }

  const favBtn = card.querySelector('[data-role="card-favorite-toggle"]');
  if (favBtn) {
    favBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      const nextStatus = Number.parseInt(favBtn.getAttribute('data-next-status') || '0', 10) || 0;
      const bookIdRaw = favBtn.getAttribute('data-book-id') || '';
      const parsedBookId = Number.parseInt(bookIdRaw, 10);
      const bookId = Number.isFinite(parsedBookId) ? parsedBookId : null;
      toggleCardFavoriteEvent(e, favBtn.getAttribute('data-favorite-name') || '', bookId, nextStatus);
    });
  }

  // 우클릭 컨텍스트 메뉴 바인딩 (이 책 스캔용)
  card.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();

    // book_id가 존재하는 경우에만 실행 (시리즈 카드인 경우 대리 book_id 설정 가능)
    const targetBookId = item.id || item.representative_book_id || null;
    if (typeof window.showBookContextMenu === 'function') {
      window.showBookContextMenu(e.clientX, e.clientY, targetBookId, displayTitle, false, {
        markUnreadScope: options.markUnreadScope || 'book',
        seriesName: item.series_name || '',
        libraryId: item.library_id ?? null,
      });
    }
  });

  // 모바일 터치 대응 (롱 프레스 감지)
  card.addEventListener('touchstart', (e) => {
    const targetBookId = item.id || item.representative_book_id || null;
    if (typeof window.handleLongPressTouchStart === 'function') {
      window.handleLongPressTouchStart(e, (x, y) => {
        if (typeof window.showBookContextMenu === 'function') {
          window.showBookContextMenu(x, y, targetBookId, displayTitle, false, {
            markUnreadScope: options.markUnreadScope || 'book',
            seriesName: item.series_name || '',
            libraryId: item.library_id ?? null,
          });
        }
      });
    }
  }, { passive: true });

  card.addEventListener('touchmove', (e) => {
    if (typeof window.handleLongPressTouchMove === 'function') {
      window.handleLongPressTouchMove(e);
    }
  }, { passive: true });

  card.addEventListener('touchend', (e) => {
    if (typeof window.handleLongPressTouchEnd === 'function') {
      window.handleLongPressTouchEnd(e);
    }
  });

  card.addEventListener('touchcancel', (e) => {
    if (typeof window.handleLongPressTouchEnd === 'function') {
      window.handleLongPressTouchEnd(e);
    }
  });

  return card;
}

// 최근 읽은 도서 그리드 렌더링
export function renderHistoryGrid(booksList) {
  const container = document.getElementById('books-list-container');
  if (!container) return;

  if (booksList.length === 0) {
    const tNoHistory = window.i18n ? window.i18n.t('common.no_history_books') : '최근에 읽은 도서 내역이 없습니다.';
    container.innerHTML = `<div class="loading-spinner">${tNoHistory}</div>`;
    return;
  }

  container.innerHTML = '';
  const fragment = document.createDocumentFragment();
  booksList.forEach(item => {
    const isSeriesHistory = (parseInt(item.book_count, 10) || 0) > 1;
    const normalizedTitle = stripLeadingBracketTags(normalizeBookTitle(item));
    const card = createBookCard(item, isSeriesHistory ? {
      showVolumeCount: true,
      markUnreadScope: 'series',
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name || normalizedTitle, item.library_id, item.representative_book_id, item.series_alias || item.series_name || normalizedTitle),
      onActionClick: (e) => {
        if (typeof window.resumeSeries === 'function') {
          window.resumeSeries(e, item.series_name, item.library_id, item.representative_book_id);
        }
      }
    } : {
      showProgress: true,
      markUnreadScope: 'series',
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name || normalizedTitle, item.library_id, item.id),
      onActionClick: () => openReader(item.id, item.file_format, normalizedTitle, item.pages_read, item.total_pages)
    });
    fragment.appendChild(card);
  });
  container.appendChild(fragment);
}

// 도서 시리즈 목록 렌더링
export function renderBooksGrid(seriesList) {
  const container = document.getElementById('books-list-container');
  if (!container) return;

  if (seriesList.length === 0) {
    const tNoBooks = window.i18n ? window.i18n.t('common.no_library_books') : '보관함에 등록된 도서가 없습니다.';
    container.innerHTML = `<div class="loading-spinner">${tNoBooks}</div>`;
    return;
  }

  container.innerHTML = '';
  appendBooksGrid(seriesList);
}

// 도서 시리즈 목록 추가 (무한 스크롤 연동)
export function appendBooksGrid(seriesList) {
  const container = document.getElementById('books-list-container');
  if (!container) return;

  const fragment = document.createDocumentFragment();
  seriesList.forEach(item => {
    const detailDisplayTitle = resolveCardDisplayTitle(item, true);
    const card = createBookCard(item, {
      showVolumeCount: true,
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name, item.library_id, item.representative_book_id, detailDisplayTitle),
      onActionClick: (e) => {
        if (typeof window.resumeSeries === 'function') {
          window.resumeSeries(e, item.series_name, item.library_id, item.representative_book_id);
        }
      }
    });
    fragment.appendChild(card);
  });
  container.appendChild(fragment);
}

// 도서 시리즈 목록 앞쪽에 삽입 (초성 점프 이후 위쪽 무한 스크롤 연동)
export function prependBooksGrid(seriesList) {
  const container = document.getElementById('books-list-container');
  if (!container) return;

  const fragment = document.createDocumentFragment();
  seriesList.forEach(item => {
    const detailDisplayTitle = resolveCardDisplayTitle(item, true);
    const card = createBookCard(item, {
      showVolumeCount: true,
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name, item.library_id, item.representative_book_id, detailDisplayTitle),
      onActionClick: (e) => {
        if (typeof window.resumeSeries === 'function') {
          window.resumeSeries(e, item.series_name, item.library_id, item.representative_book_id);
        }
      }
    });
    fragment.appendChild(card);
  });
  container.insertBefore(fragment, container.firstChild);
}

// 대시보드 최근 읽은 도서 렌더링
export function renderDashboardHistory(booksList) {
  const container = document.getElementById('dashboard-history-row');
  if (!container) return;

  if (booksList.length === 0) {
    const tNoHistory = window.i18n ? window.i18n.t('common.no_history_books') : '최근에 읽은 도서 내역이 없습니다.';
    container.innerHTML = `<div class="loading-spinner loading-spinner--compact">${tNoHistory}</div>`;
    return;
  }

  container.innerHTML = '';
  const fragment = document.createDocumentFragment();
  booksList.forEach(item => {
    const isSeriesHistory = (parseInt(item.book_count, 10) || 0) > 1;
    const normalizedTitle = stripLeadingBracketTags(normalizeBookTitle(item));
    const targetSeriesName = item.series_name || item.title || normalizedTitle;
    const targetLibraryId = item.library_id || null;
    const targetBookId = item.book_id || item.id || item.representative_book_id;
    const fileFormat = (item.file_format || '').toLowerCase();
    const isAudio = fileFormat === 'audiobook' || fileFormat === 'audio';

    const card = createBookCard(item, {
      showProgress: true,
      markUnreadScope: 'series',
      lazyLoad: false,
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => {
        console.log('[Dashboard-ReadingHistory] Card Primary Clicked (Opening Detail):', { targetSeriesName, targetLibraryId, targetBookId });
        if (typeof window.openBookDetail === 'function') {
          window.openBookDetail(e, targetSeriesName, targetLibraryId, targetBookId, item.series_alias || targetSeriesName);
        }
      },
      onActionClick: (e) => {
        console.log('[Dashboard-ReadingHistory] Card Action Clicked (Opening Reader):', { targetBookId, targetSeriesName, fileFormat });
        if (isAudio && typeof window.openAudioPlayer === 'function') {
          window.openAudioPlayer(targetBookId);
        } else if (targetBookId && fileFormat && typeof window.openReader === 'function') {
          window.openReader(targetBookId, fileFormat, normalizedTitle, item.pages_read || 0, item.total_pages || 0);
        } else if (typeof window.resumeSeries === 'function') {
          window.resumeSeries(e, targetSeriesName, targetLibraryId, targetBookId);
        }
      }
    });
    fragment.appendChild(card);
  });
  container.appendChild(fragment);
}

// 대시보드 신규 추가 도서 렌더링
export function renderDashboardRecentlyAdded(booksList) {
  const container = document.getElementById('dashboard-new-row');
  if (!container) return;

  if (booksList.length === 0) {
    container.innerHTML = '<div class="loading-spinner loading-spinner--compact">최근에 추가된 도서가 없습니다.</div>';
    return;
  }

  container.innerHTML = '';
  const fragment = document.createDocumentFragment();
  booksList.forEach(item => {
    const normalizedTitle = stripLeadingBracketTags(normalizeBookTitle(item));
    const card = createBookCard(item, {
      isNew: true,
      lazyLoad: false,
      actionTitle: '바로읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name || normalizedTitle, item.library_id, item.id),
      onActionClick: () => openReader(item.id, item.file_format, normalizedTitle, 0, item.total_pages)
    });
    fragment.appendChild(card);
  });
  container.appendChild(fragment);
}

window.toggleCardFavoriteEvent = async (event, name, bookId, nextStatus) => {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }

  console.log(`[Favorite-Action] 카드 즐겨찾기 별 클릭: name="${name}", bookId=${bookId}, nextStatus=${nextStatus}, currentLibId=${state.currentLibraryId}`);

  // 즉시 UI 피드백 반영 (Optimistic Update)
  const btn = event.currentTarget || (event.target && event.target.closest ? event.target.closest('.btn-card-fav-toggle') : null);
  let originalClass = '';
  let originalActive = false;
  if (btn) {
    originalActive = btn.classList.contains('active');
    const icon = btn.querySelector('i');
    if (icon) {
      originalClass = icon.className;
      if (nextStatus === 1) {
        btn.classList.add('active');
        icon.className = 'fa-solid fa-star';
      } else {
        btn.classList.remove('active');
        icon.className = 'fa-regular fa-star';
      }
    }
  }

  let res;
  if (bookId && state.currentLibraryId === 'history') {
    console.log(`[Favorite-Action] window.toggleFavoriteAction 호출 (bookId=${bookId}, status=${nextStatus})`);
    res = await window.toggleFavoriteAction(bookId, nextStatus);
  } else {
    console.log(`[Favorite-Action] window.toggleSeriesFavoriteAction 호출 (name="${name}", status=${nextStatus})`);
    res = await window.toggleSeriesFavoriteAction(name, nextStatus);
  }
  console.log(`[Favorite-Action] 토글 API 응답 결과:`, res);

  if (res && res.success) {
    const statusText = nextStatus === 1 ? '등록' : '해제';
    showToast(`"${name}" 즐겨찾기가 ${statusText}되었습니다.`, 'success');

    if (state.currentLibraryId === 'home') {
      if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
    } else if (state.currentLibraryId === 'history') {
      if (typeof window.loadReadingHistory === 'function') window.loadReadingHistory();
    } else {
      if (typeof window.loadBooksList === 'function') window.loadBooksList(false);
    }
  } else {
    // 실패 시 UI 복원
    if (btn) {
      if (originalActive) btn.classList.add('active');
      else btn.classList.remove('active');
      const icon = btn.querySelector('i');
      if (icon) icon.className = originalClass;
    }
    showToast('즐겨찾기 업데이트에 실패했습니다.', 'error');
  }
};


