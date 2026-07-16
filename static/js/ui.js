// ui.js – UI 렌더링 및 그리드 함수들
import { state } from './state.js';
import { openBookDetail } from './modal.js';
import { openReader } from './viewer.js';
import { showToast } from './view_manager.js';
import { buildFallbackCoverUrl, getBookCoverSrc } from './cover_fallback.js';

// 지연 로딩을 위한 단일 싱글톤 IntersectionObserver 인스턴스
const lazyImageObserver = ('IntersectionObserver' in window)
  ? new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const lazyImage = entry.target;
          if (lazyImage.dataset.src) {
            lazyImage.src = lazyImage.dataset.src;
            lazyImage.removeAttribute('data-src'); // 중복 분석 방지용 속성 제거
          }
          observer.unobserve(lazyImage);
        }
      });
    }, {
      rootMargin: '100px 0px', // 뷰포트에 도달하기 100px 전에 로딩 시작
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
  const normalizedTitle = normalizeBookTitle(item);
  if (!showVolumeCount) {
    return normalizedTitle;
  }

  const bookCount = parseInt(item.book_count, 10) || 0;
  const representativeTitle = String(item.representative_title || '').trim();
  const seriesName = String(item.series_name || '').trim();
  const authorName = String(item.author || '').trim();
  const normalizedSeries = seriesName.toLowerCase();
  const normalizedAuthor = authorName.toLowerCase();
  const isAuthorOnlySeries = !!(normalizedSeries && normalizedAuthor && normalizedSeries === normalizedAuthor);

  const toSeriesLikeTitle = (rawTitle) => {
    let text = String(rawTitle || '').trim();
    if (!text) return '';
    if (seriesName) {
      const escapedSeries = seriesName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(new RegExp(`^\\[\\s*${escapedSeries}\\s*\\]\\s*`, 'i'), '').trim();
    }
    const trimmed = text
      .replace(/\s*[-:|]\s*\d+\s*(권|화|부|편)$/i, '')
      .replace(/\s+제?\d+\s*(권|화|부|편)$/i, '')
      .replace(/\s+\d+\s*(권|화|부|편)$/i, '')
      .trim();
    return trimmed || text;
  };

  if (bookCount === 1 && representativeTitle) {
    return representativeTitle;
  }

  if (bookCount > 1 && representativeTitle && (isAuthorOnlySeries || !seriesName || seriesName === '기타 단행본')) {
    return toSeriesLikeTitle(representativeTitle);
  }

  if (bookCount > 1 && representativeTitle && seriesName) {
    const escapedSeries = seriesName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const bracketPrefix = new RegExp(`^\\[\\s*${escapedSeries}\\s*\\]\\s*(.+)$`, 'i');
    const match = representativeTitle.match(bracketPrefix);
    if (match && match[1] && match[1].trim()) {
      return toSeriesLikeTitle(match[1].trim());
    }
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

  const displayTitle = resolveCardDisplayTitle(item, options.showVolumeCount);
  const fallbackCoverSrc = buildFallbackCoverUrl({
    title: displayTitle,
    format: item.file_format,
    seed: item.id || item.representative_book_id || item.file_path || displayTitle
  });
  const coverSrc = getBookCoverSrc({
    coverImage: item.cover_image,
    title: displayTitle,
    format: item.file_format,
    seed: item.id || item.representative_book_id || item.file_path || displayTitle
  });
  const useLazyLoad = options.lazyLoad !== false;
  
  // 1. 공통 카드 클릭 핸들러 (아이콘 및 별 클릭 분기)
  card.onclick = (e) => {
    if (e.target.closest('.btn-resume-series') || e.target.closest('.btn-card-fav-toggle')) {
      return;
    }
    if (typeof options.onPrimaryClick === 'function') {
      options.onPrimaryClick(e, item);
    }
  };

  // 2. 뱃지 정보 결정
  let badgeHtml = '';
  if (options.showProgress && item.total_pages > 0) {
    const progressPercent = Math.round((item.pages_read / item.total_pages) * 100);
    badgeHtml = `<span class="book-badge-count" style="background-color: #a855f7;">${progressPercent}%</span>`;
  } else if (options.showVolumeCount && item.book_count !== undefined) {
    badgeHtml = `<span class="book-badge-count">${item.book_count}${i18n.t('dashboard.unit_books')}</span>`;
  }

  // 3. 서브 텍스트 메타정보 결정
  let subTextHtml = '';
  if (item.pages_read > 0 && options.showProgress) {
    subTextHtml = `<p style="font-size:0.75rem; color:#94a3b8; margin:0.25rem 0 0 0;">${i18n.t('dashboard.continue_reading', {pages: item.pages_read})}</p>`;
  } else if (options.isNew) {
    subTextHtml = `<p style="font-size:0.75rem; color:#94a3b8; margin:0.25rem 0 0 0;">${i18n.t('dashboard.new_arrival')}</p>`;
  }

  // 4. 즐겨찾기 버튼 구성
  const isFav = item.is_favorite === 1;
  const favIconClass = isFav ? 'fa-solid fa-star' : 'fa-regular fa-star';
  const favBtnHtml = `
    <button class="btn-card-fav-toggle ${isFav ? 'active' : ''}" title="즐겨찾기 토글" onclick="toggleCardFavoriteEvent(event, '${displayTitle.replace(/'/g, "\\'")}', ${item.id || 'null'}, ${isFav ? 0 : 1})">
      <i class="${favIconClass}"></i>
    </button>
  `;

  // 1x1 투명 GIF를 기본 src로 지정하고 data-src에 실제 coverSrc를 둡니다.
  const lazyPlaceholder = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  const imgSrc = useLazyLoad ? lazyPlaceholder : coverSrc;
  const imgDataSrcAttr = useLazyLoad ? `data-src="${coverSrc}"` : '';

  card.innerHTML = `
    <div class="book-card-cover">
      <div class="book-card-overlay"></div>
      <img src="${imgSrc}" ${imgDataSrcAttr} alt="${displayTitle}">
      ${badgeHtml}
      ${favBtnHtml}
      <button class="btn-resume-series" title="${options.actionTitle || '읽기'}">
        <i class="fa-solid fa-book-open"></i>
      </button>
    </div>
    <div class="book-card-info">
      <h4 class="book-card-title" title="${displayTitle}">${displayTitle}</h4>
      ${subTextHtml}
    </div>
  `;

  // IntersectionObserver 싱글톤 적용
  const imgEl = card.querySelector('img');
  if (imgEl) {
    imgEl.onerror = () => {
      const currentSrc = imgEl.getAttribute('src') || '';
      if (currentSrc !== fallbackCoverSrc) {
        imgEl.setAttribute('src', fallbackCoverSrc);
        return;
      }
      imgEl.onerror = null;
      imgEl.setAttribute('src', '/static/images/default_cover.jpg');
    };
  }
  if (imgEl && useLazyLoad) {
    if (imgEl.dataset && imgEl.dataset.src) {
      if (lazyImageObserver) {
        lazyImageObserver.observe(imgEl);
      } else {
        // Fallback: 브라우저가 지원하지 않을 경우 즉시 로딩
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

  // 우클릭 컨텍스트 메뉴 바인딩 (이 책 스캔용)
  card.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // book_id가 존재하는 경우에만 실행 (시리즈 카드인 경우 대리 book_id 설정 가능)
    const targetBookId = item.id || item.representative_book_id || null;
    if (typeof window.showBookContextMenu === 'function') {
      window.showBookContextMenu(e.clientX, e.clientY, targetBookId, displayTitle);
    }
  });

  // 모바일 터치 대응 (롱 프레스 감지)
  card.addEventListener('touchstart', (e) => {
    const targetBookId = item.id || item.representative_book_id || null;
    if (typeof window.handleLongPressTouchStart === 'function') {
      window.handleLongPressTouchStart(e, (x, y) => {
        if (typeof window.showBookContextMenu === 'function') {
          window.showBookContextMenu(x, y, targetBookId, displayTitle);
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
    const normalizedTitle = normalizeBookTitle(item);
    const card = createBookCard(item, {
      showProgress: true,
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

// 대시보드 최근 읽은 도서 렌더링
export function renderDashboardHistory(booksList) {
  const container = document.getElementById('dashboard-history-row');
  if (!container) return;

  if (booksList.length === 0) {
    const tNoHistory = window.i18n ? window.i18n.t('common.no_history_books') : '최근에 읽은 도서 내역이 없습니다.';
    container.innerHTML = `<div class="loading-spinner" style="grid-column:1/-1; padding:2rem;">${tNoHistory}</div>`;
    return;
  }

  container.innerHTML = '';
  const fragment = document.createDocumentFragment();
  booksList.forEach(item => {
    const normalizedTitle = normalizeBookTitle(item);
    const card = createBookCard(item, {
      showProgress: true,
      lazyLoad: false,
      actionTitle: '이어읽기',
      onPrimaryClick: (e) => openBookDetail(e, item.series_name || normalizedTitle, item.library_id, item.id),
      onActionClick: () => openReader(item.id, item.file_format, normalizedTitle, item.pages_read, item.total_pages)
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
    container.innerHTML = '<div class="loading-spinner" style="grid-column:1/-1; padding:2rem;">최근에 추가된 도서가 없습니다.</div>';
    return;
  }

  container.innerHTML = '';
  const fragment = document.createDocumentFragment();
  booksList.forEach(item => {
    const normalizedTitle = normalizeBookTitle(item);
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
  
  // 즉시 UI 피드백 반영 (Optimistic Update)
  const btn = event.currentTarget || event.target.closest('.btn-card-fav-toggle');
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
    res = await window.toggleFavoriteAction(bookId, nextStatus);
  } else {
    res = await window.toggleSeriesFavoriteAction(name, nextStatus);
  }
  
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


/**
 * ────────────────────────────────────────────────────────
 * 📌 시스템 상태 뉴스 티커 폴링 관리 루틴
 * ────────────────────────────────────────────────────────
 */
let statusIntervalId = null;
let lastTickerContent = '';

export function startSystemStatusPolling() {
  if (statusIntervalId) return;
  
  const poll = async () => {
    try {
      const res = await fetch(`/api/system/status?type=${state.currentLibraryType}`);
      const data = await res.json();
      
      const footer = document.getElementById('system-ticker-footer');
      const contentEl = document.getElementById('system-ticker-content');
      
      if (data.success && data.is_active && data.tasks && data.tasks.length > 0) {
        const textMessage = data.tasks.join("   |   ");
        if (footer && contentEl) {
          // 상태가 변경되었거나 새로운 텍스트일 때만 DOM 조작
          if (lastTickerContent !== textMessage) {
            contentEl.innerText = textMessage;
            lastTickerContent = textMessage;
            
            // marquee 애니메이션 속도를 글자 길이에 맞춰 동적 조절
            const duration = Math.max(15, Math.min(60, textMessage.length * 0.35));
            contentEl.style.animationDuration = `${duration}s`;
          }
          
          if (footer.style.display === 'none') {
            footer.style.display = 'flex';
            console.log('[SystemTicker] 📢 백그라운드 활성 태스크 감지로 속보 푸터 바 활성화.');
          }
        }
      } else {
        if (footer && footer.style.display !== 'none') {
          footer.style.display = 'none';
          lastTickerContent = '';
          console.log('[SystemTicker] 🤫 백그라운드 태스크가 없어 속보 푸터 바 은닉.');
          
          // 스캔 완료 시 보관함 리스트 실시간 자동 갱신
          if (state.currentLibraryId === 'home') {
            if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
          } else if (state.currentLibraryId === 'history') {
            if (typeof window.loadReadingHistory === 'function') window.loadReadingHistory();
          } else if (state.currentLibraryId !== 'settings') {
            if (typeof window.loadBooksList === 'function') window.loadBooksList(false);
          }
        }
      }
    } catch (err) {
      console.error('[SystemTicker] 상태 조회 실패:', err);
    }
  };
  
  // 최초 1회 즉시 실행 후 5초 주기 폴링
  poll();
  statusIntervalId = setInterval(poll, 5000);
}

// 스크립트 로드 시 즉시 시작
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startSystemStatusPolling);
} else {
  startSystemStatusPolling();
}


