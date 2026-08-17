import { state } from './state.js';
import * as api from './api.js';
import { renderHistoryGrid, renderBooksGrid, appendBooksGrid, prependBooksGrid } from './ui.js?v=20260809-unread-series-v3';
import { openReader } from './viewer.js';
import { loadLibraries } from './category.js';
import { initInfiniteScrollObserver } from './infinite_scroll.js';
import { stripLeadingBracketTags } from './series_display.js';
import { mountIndexScrollbar, unmountIndexScrollbar } from './index_scrollbar.js';

let filterDebounceTimer = null;
let totalsRequestSerial = 0;

export function normalizeMetadataToken(token) {
  if (!token) return '';
  return String(token)
    .replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}


export function updateLibraryTotalCount(items, totals = null) {
  const countSpan = document.getElementById('library-total-count');
  if (!countSpan) return;
  const serverSeriesCount = Number(totals?.total_series_count);
  const serverBookCount = Number(totals?.total_book_count);
  const hasServerTotals = Number.isFinite(serverSeriesCount) && Number.isFinite(serverBookCount);
  const seriesCount = hasServerTotals ? serverSeriesCount : items.length;
  const bookCount = hasServerTotals
    ? serverBookCount
    : items.reduce((sum, item) => sum + (parseInt(item.book_count) || 1), 0);

  // 미디어 타입별로 "권" 단위가 어울리지 않는 경우(오디오북=트랙, 영상=편)를 위한 라벨 분기.
  const i18nKey = state.currentLibraryType === 'audiobook'
    ? 'book_list.total_count_audiobook'
    : state.currentLibraryType === 'video'
      ? 'book_list.total_count_video'
      : 'book_list.total_count';

  countSpan.innerText = i18n.t(i18nKey, {seriesCount: seriesCount.toLocaleString(), bookCount: bookCount.toLocaleString()});
}

// 1. 도서 시리즈 목록 로드
export async function loadBooksList(isAppend = false, startPage = null) {
  const currentId = state.currentLibraryId || '';
  if (['home', 'collection', 'settings', 'plugins'].includes(currentId) || currentId.startsWith('plugin_')) {
    console.warn(`[Book-List] loadBooksList skipped: currentLibraryId=${currentId} is not a book list category.`);
    return;
  }

  if (state.isLoading) {
    console.warn('[Book-List] loadBooksList skipped: already loading');
    return;
  }
  
  const container = document.getElementById('books-list-container');
  if (!container) {
    console.warn('[Book-List] loadBooksList skipped: #books-list-container missing');
    return;
  }
  const spinner = document.getElementById('infinite-scroll-spinner');

  state.isLoading = true;
  console.log(`[Book-List] loadBooksList 시작 - type=${state.currentLibraryType}, libraryId=${state.currentLibraryId}, isAppend=${isAppend}`);
  
  try {
    const limit = state.LIMIT || 120;
    const targetPage = isAppend ? state.currentPage : (startPage || 1);
    const requestFilters = {
      type: state.currentLibraryType,
      libraryId: state.currentLibraryId,
      search: state.searchQuery || '',
      genres: (state.filterGenres || []).map(normalizeMetadataToken).filter(Boolean),
      tags: (state.filterTags || []).map(normalizeMetadataToken).filter(Boolean),
    };
    const totalsSerial = isAppend ? totalsRequestSerial : ++totalsRequestSerial;

    if (!isAppend) {
      state.currentPage = targetPage;
      state.hasMore = true;
      state.firstLoadedPage = targetPage;
      state.hasPrevious = targetPage > 1;
      container.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('book_list.loading')}</div>`;
      const countSpan = document.getElementById('library-total-count');
      if (countSpan) countSpan.innerText = '';
    }

    const data = await api.fetchBooksList({
      type: requestFilters.type,
      libraryId: requestFilters.libraryId,
      page: targetPage,
      limit,
      search: requestFilters.search,
      sort: state.currentSortDirection || 'asc',
      genres: requestFilters.genres,
      tags: requestFilters.tags,
    });

    if (!data.success) {
      container.innerHTML = `<div class="loading-spinner">${i18n.t('book_list.load_fail', {error: data.error || ''})}</div>`;
      return;
    }

    const incomingSeries = Array.isArray(data.series) ? data.series : [];

    if (isAppend) {
      state.currentBooksData = state.currentBooksData.concat(incomingSeries);
      appendBooksGrid(incomingSeries);
    } else {
      state.currentBooksData = incomingSeries;
      renderBooksGrid(state.currentBooksData);
    }

    state.filteredBooksData = state.currentBooksData;
    if (!isAppend) {
      api.fetchBooksTotals(requestFilters)
        .then((totals) => {
          const isSameList = state.currentLibraryType === requestFilters.type
            && String(state.currentLibraryId || '') === String(requestFilters.libraryId || '');
          if (totalsSerial === totalsRequestSerial && isSameList && totals.success) {
            updateLibraryTotalCount([], totals);
          }
        })
        .catch((error) => console.warn('[Book-List] 전체 수량 조회 실패:', error));
    }

    state.hasMore = !!data.has_more;
    state.currentPage = state.hasMore ? (targetPage + 1) : targetPage;

  if (spinner) {
    spinner.style.display = state.hasMore ? 'block' : 'none';
  }
  if (!isAppend) {
    const spinnerTop = document.getElementById('infinite-scroll-spinner-top');
    if (spinnerTop) spinnerTop.style.display = state.hasPrevious ? 'block' : 'none';
  }

  const gridView = document.getElementById('books-grid-view');
  const isGridActive = !!(gridView && gridView.style.display !== 'none');
  const sortDir = state.currentSortDirection || 'asc';
  // 가나다 오름/내림차순일 때는 아직 전체 목록을 다 불러오지 못한 상태(hasMore=true)여도
  // 초성 바로가기 바를 표시한다. handleIndexClick이 필요 시 추가 페이지를 더 불러온다.
  if (isGridActive && (sortDir === 'asc' || sortDir === 'desc')) {
    mountIndexScrollbar();
  } else {
    unmountIndexScrollbar();
  }
  } finally {
    state.isLoading = false;
  }

  // 렌더링 및 스피너 상태 결정 완료 후 무한 스크롤 옵저버 재바인딩
  initInfiniteScrollObserver();
}

// 초성 바로가기 등으로 중간 페이지부터 로드된 경우, 위로 스크롤 시 이전 페이지를 앞에 이어붙인다.
export async function loadPreviousBooksPage() {
  if (state.isLoading || state.isLoadingPrevious || !state.hasPrevious) return;

  const container = document.getElementById('books-list-container');
  const mainContent = document.querySelector('.library-main-content');
  if (!container || !mainContent) return;

  const targetPage = state.firstLoadedPage - 1;
  if (targetPage < 1) {
    state.hasPrevious = false;
    return;
  }

  state.isLoadingPrevious = true;
  const spinnerTop = document.getElementById('infinite-scroll-spinner-top');
  if (spinnerTop) spinnerTop.classList.add('is-loading');

  try {
    const limit = state.LIMIT || 120;
    const data = await api.fetchBooksList({
      type: state.currentLibraryType,
      libraryId: state.currentLibraryId,
      page: targetPage,
      limit,
      search: state.searchQuery || '',
      sort: state.currentSortDirection || 'asc',
      genres: (state.filterGenres || []).map(normalizeMetadataToken).filter(Boolean),
      tags: (state.filterTags || []).map(normalizeMetadataToken).filter(Boolean),
    });

    if (!data.success) return;

    const incomingSeries = Array.isArray(data.series) ? data.series : [];
    if (incomingSeries.length === 0) {
      state.hasPrevious = false;
      return;
    }

    // 콘텐츠를 그리드 위쪽에 끼워넣으면 스크롤 위치가 밀려 보이므로,
    // 삽입 전후 높이 차이만큼 scrollTop을 보정해 사용자 시점을 그대로 유지한다.
    const heightBefore = container.scrollHeight;
    state.currentBooksData = incomingSeries.concat(state.currentBooksData);
    prependBooksGrid(incomingSeries);
    const heightAfter = container.scrollHeight;
    mainContent.scrollTop += (heightAfter - heightBefore);

    state.filteredBooksData = state.currentBooksData;
    state.firstLoadedPage = targetPage;
    state.hasPrevious = targetPage > 1;

    if (spinnerTop) spinnerTop.style.display = state.hasPrevious ? 'block' : 'none';
  } catch (e) {
    console.error('[Book-List] 이전 페이지 로드 실패:', e);
  } finally {
    state.isLoadingPrevious = false;
    if (spinnerTop) spinnerTop.classList.remove('is-loading');
  }
}

// 최근 읽은 도서 히스토리 목록 로드
export async function loadReadingHistory() {
  state.isLoading = true;
  state.hasMore = false;
  state.hasPrevious = false;
  const spinner = document.getElementById('infinite-scroll-spinner');
  if (spinner) spinner.style.display = 'none';
  const spinnerTop = document.getElementById('infinite-scroll-spinner-top');
  if (spinnerTop) spinnerTop.style.display = 'none';
  const container = document.getElementById('books-list-container');
  if (!container) { state.isLoading = false; return; }
  container.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('book_list.history_loading')}</div>`;
  try {
    const data = await api.fetchReadingHistory(state.currentLibraryType);
    if (data.success) {
      let books = data.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => {
          const fmt = String(b.file_format || '').toLowerCase();
          const isAudiobook = fmt === 'audiobook' || fmt === 'audio';
          const isCompleted = isAudiobook
            ? (b.is_completed === 1)
            : (b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages));
          const hasUnfinishedSiblings = Number(b.has_unfinished_siblings || 0) === 1;
          return !isCompleted || hasUnfinishedSiblings;
        });
      }
      renderHistoryGrid(books);
    } else {
      container.innerHTML = `<div class="loading-spinner">${i18n.t('book_list.history_fail', {error: data.error || ''})}</div>`;
    }
  } catch (e) {
    container.innerHTML = `<div class="loading-spinner">${i18n.t('book_list.server_error')}</div>`;
    console.error('히스토리 로드 오류:', e);
  } finally {
    state.isLoading = false;
  }
}

// 3. 도서 검색 필터링 (클라이언트 사이드 메모리 내 즉시 필터링)
export function filterBooks() {
  const query = document.getElementById('library-search').value.toLowerCase().trim();
  state.searchQuery = query;

  // 영상 강좌 세션은 개별 라이브러리 보기에서만 별도의 클라이언트 필터러(video_library.js)를 쓴다.
  // "전체보기"(all)/즐겨찾기/히스토리는 tab_media_library.js::selectCategory()가 video여도
  // loadVideoCourseGrid가 아니라 이 공용 파이프라인(loadBooksList)으로 그리드를 채우므로,
  // 여기서도 똑같이 일반 파이프라인을 타야 한다 - 안 그러면 filterVideoCourses가 채워진 적
  // 없는 lastLoadedVideos(빈 배열)를 대상으로 필터링해서 검색 결과가 항상 0건으로 나온다.
  if (state.currentLibraryType === 'video' && !['all', 'history', 'favorite'].includes(state.currentLibraryId)) {
    if (typeof window.filterVideoCourses === 'function') window.filterVideoCourses();
    return;
  }

  // 홈 대시보드에서는 검색 시 전체보기로 전환해 동일한 검색어로 목록 필터링한다.
  if (query && state.currentLibraryId === 'home' && typeof window.selectCategory === 'function') {
    window.selectCategory('all');
    return;
  }

  const searchBtn = document.getElementById('btn-library-search-action');
  if (searchBtn) {
    searchBtn.innerText = query ? i18n.t('common.reset') : i18n.t('common.search');
  }
  
  if (query && state.currentLibraryId === 'history') {
    state.currentLibraryId = 'all';
    loadLibraries();
    return;
  }

  if (filterDebounceTimer) {
    clearTimeout(filterDebounceTimer);
  }
  filterDebounceTimer = setTimeout(() => {
    state.currentPage = 1;
    state.hasMore = true;
    loadBooksList(false);
  }, 220);
}

export function updateSortButtonUI() {
  const btn = document.getElementById('btn-lib-sort');
  if (!btn) return;
  const currentSort = state.currentSortDirection || 'asc';
  if (currentSort === 'asc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-alpha-down"></i> ${i18n.t('book_list.sort_asc')}`;
  } else if (currentSort === 'desc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-alpha-up"></i> ${i18n.t('book_list.sort_desc')}`;
  } else if (currentSort === 'date_desc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-numeric-down-alt"></i> ${i18n.t('book_list.sort_date_desc')}`;
  } else if (currentSort === 'date_asc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-numeric-up"></i> ${i18n.t('book_list.sort_date_asc')}`;
  }
}

export function toggleLibrarySort() {
  const btn = document.getElementById('btn-lib-sort');
  if (!btn) return;

  const cycle = {
    'asc': 'desc',
    'desc': 'date_desc',
    'date_desc': 'date_asc',
    'date_asc': 'asc'
  };

  const newSort = cycle[state.currentSortDirection] || 'asc';
  state.currentSortDirection = newSort;
  localStorage.setItem('library_sort_direction', newSort);

  updateSortButtonUI();

  state.currentPage = 1;
  state.hasMore = true;
  loadBooksList(false);
}

// 시리즈 이어보기 로직
export async function resumeSeries(e, seriesName, libraryId, representativeBookId = null) {
  if (e) {
    e.stopPropagation();
    e.preventDefault();
  }
  console.log(`[Resume-Series] 시리즈 이어보기 요청: ${seriesName} (카테고리: ${libraryId})`);
  
  const activeLibId = libraryId || state.currentLibraryId || 'all';

  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, activeLibId, seriesName, representativeBookId);
    if (data.success && data.books && data.books.length > 0) {
      // 이어보기 우선순위 선정:
      // 1. 읽는 중인 도서 (0 < pages_read < total_pages 이며 미완료인 것)
      let targetBook = data.books.find(b => b.pages_read > 0 && b.pages_read < b.total_pages && !b.is_completed);
      
      // 2. 만약 없다면 아직 읽지 않은 첫 번째 도서
      if (!targetBook) {
        targetBook = data.books.find(b => !b.is_completed);
      }
      
      // 3. 만약 모든 책을 다 완독했거나 없다면 시리즈 내의 첫 번째 도서
      if (!targetBook) {
        targetBook = data.books[0];
      }

      // 오디오북은 상세 API가 트랙 목록을 반환하므로,
      // 트랙 ID와 작품 ID를 분리해서 플레이어를 직접 연다.
      if (state.currentLibraryType === 'audiobook' && typeof window.openAudioPlayer === 'function') {
        const resolvedAudiobookId = (data.meta && data.meta.id) ? data.meta.id : (targetBook.audiobook_id || representativeBookId || targetBook.id);
        const resumeTrackId = (data.meta && data.meta.current_track_id) ? data.meta.current_track_id : targetBook.id;
        const startTime = (data.meta && Number(data.meta.current_time) > 0)
          ? Number(data.meta.current_time)
          : (Number(targetBook.pages_read) || 0);
        window.openAudioPlayer(resolvedAudiobookId, resumeTrackId, startTime);
        return;
      }
      
      console.log(`[Resume-Series] 이어보기 도서 선정 성공: ${targetBook.title} (ID: ${targetBook.id}, p.${targetBook.pages_read})`);
      openReader(targetBook.id, targetBook.file_format, targetBook.title, targetBook.pages_read, targetBook.total_pages);
    } else {
      alert(i18n.t('book_list.resume_fail_list'));
    }
  } catch (err) {
    console.error('[Resume-Series] 이어보기 로직 에러:', err);
    alert(i18n.t('book_list.resume_fail_error'));
  }
}

/**
 * 특정 데이터 인덱스(순서)가 렌더링되도록 페이지를 강제 확장하고 해당 엘리먼트로 스크롤합니다.
 * @param {number} targetIndex - state.filteredBooksData 기준의 인덱스
 */
export function jumpToIndex(targetIndex) {
  if (targetIndex < 0 || targetIndex >= state.filteredBooksData.length) return;

  const targetPage = Math.floor(targetIndex / state.LIMIT) + 1;

  // 만약 대상 인덱스가 현재 렌더링된 페이지 범위를 벗어난 경우 (스크롤을 안 내린 상태)
  // 해당 페이지까지 한 번에 렌더링하도록 갱신합니다.
  if (targetPage > state.currentPage - 1) {
    state.currentPage = targetPage + 1; // hasMore를 위해 +1
    const limit = targetPage * state.LIMIT;
    const pageItems = state.filteredBooksData.slice(0, limit);
    state.hasMore = limit < state.filteredBooksData.length;
    
    state.currentBooksData = pageItems;
    renderBooksGrid(pageItems);

    const spinner = document.getElementById('infinite-scroll-spinner');
    if (spinner) {
      spinner.style.display = state.hasMore ? 'block' : 'none';
    }
    
    // 무한 스크롤 옵저버 재바인딩
    initInfiniteScrollObserver();
  }

  // 렌더링이 완료된 후 약간의 지연을 주고 DOM을 찾아 스크롤 이동
  setTimeout(() => {
    const cards = document.querySelectorAll('#books-list-container .book-card');
    if (cards[targetIndex]) {
      // 실제 스크롤 컨테이너(.library-main-content) 기준으로 이동
      // 레이아웃이 바뀌어도 동작하도록 window 스크롤은 fallback으로만 사용
      const mainContent = document.querySelector('.library-main-content');
      if (mainContent && mainContent.scrollHeight > mainContent.clientHeight) {
        const cardRect = cards[targetIndex].getBoundingClientRect();
        const mainRect = mainContent.getBoundingClientRect();
        const relativeTop = cardRect.top - mainRect.top;
        const y = Math.max(0, mainContent.scrollTop + relativeTop - 80);
        mainContent.scrollTo({ top: y, behavior: 'smooth' });
      } else {
        const y = cards[targetIndex].getBoundingClientRect().top + window.scrollY - 80;
        window.scrollTo({ top: y, behavior: 'smooth' });
      }
      
      // 사용자에게 시각적 피드백 제공 (깜빡임 효과)
      cards[targetIndex].style.transition = 'box-shadow 0.3s ease';
      cards[targetIndex].style.boxShadow = '0 0 15px rgba(168, 85, 247, 0.8)';
      setTimeout(() => {
        cards[targetIndex].style.boxShadow = '';
      }, 1500);
    }
  }, 50);
}
