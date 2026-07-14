import { state } from './state.js';
import * as api from './api.js';
import { renderHistoryGrid, renderBooksGrid, appendBooksGrid } from './ui.js';
import { openReader } from './viewer.js';
import { loadLibraries } from './category.js';
import { initInfiniteScrollObserver } from './infinite_scroll.js';

function normalizeMetadataToken(token) {
  if (!token) return '';
  return String(token)
    .replace(/^[\s'"\[\],]+|[\s'"\[\],]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}


function updateLibraryTotalCount(items) {
  const countSpan = document.getElementById('library-total-count');
  if (!countSpan) return;
  const seriesCount = items.length;
  let bookCount = 0;
  items.forEach(item => {
    bookCount += (parseInt(item.book_count) || 1);
  });
  countSpan.innerText = i18n.t('book_list.total_count', {seriesCount: seriesCount.toLocaleString(), bookCount: bookCount.toLocaleString()});
}

function sortBooksList(filtered, sortDir) {
  filtered.sort((a, b) => {
    if (sortDir === 'asc' || sortDir === 'desc') {
      const nameA = a.series_name || '';
      const nameB = b.series_name || '';
      return sortDir === 'asc' 
        ? nameA.localeCompare(nameB, 'ko', { numeric: true, sensitivity: 'base' })
        : nameB.localeCompare(nameA, 'ko', { numeric: true, sensitivity: 'base' });
    } else {
      // date_desc (최신순), date_asc (과거순)
      const dateA = a.latest_added ? new Date(a.latest_added).getTime() : 0;
      const dateB = b.latest_added ? new Date(b.latest_added).getTime() : 0;
      return sortDir === 'date_desc' ? (dateB - dateA) : (dateA - dateB);
    }
  });
}


// 1. 도서 시리즈 목록 로드
export async function loadBooksList(isAppend = false) {
  if (state.isLoading) return;
  
  const container = document.getElementById('books-list-container');
  if (!container) return;
  const spinner = document.getElementById('infinite-scroll-spinner');

  state.isLoading = true;
  
  try {
    // append가 아닐 때는 최초 1회 전체 데이터를 가져옴
    if (!isAppend) {
      state.currentPage = 1;
      state.hasMore = true;
      container.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('book_list.loading')}</div>`;
      
      try {
        const data = await api.fetchAllBooksList(state.currentLibraryType, state.currentLibraryId);
        if (data.success) {
          state.allBooksData = data.series || [];
        } else {
          container.innerHTML = `<div class="loading-spinner">${i18n.t('book_list.load_fail', {error: data.error || ''})}</div>`;
          return;
        }
      } catch (e) {
        container.innerHTML = `<div class="loading-spinner">${i18n.t('book_list.server_error')}</div>`;
        console.error('도서 목록 로드 오류:', e);
        return;
      }
    }

  // 클라이언트 사이드 필터링 및 정렬 수행
  let filtered = [...state.allBooksData];

  // 1) 검색 필터링
  if (state.searchQuery) {
    filtered = filtered.filter(item => 
      (item.series_name && item.series_name.toLowerCase().includes(state.searchQuery)) ||
      (item.author && item.author.toLowerCase().includes(state.searchQuery))
    );
  }

  // 1-1) 장르 다중 필터링 (AND 결합)
  if (state.filterGenres && state.filterGenres.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.genre) return false;
      const itemGenres = item.genre.split(',').map(normalizeMetadataToken).filter(Boolean);
      const selectedGenres = state.filterGenres.map(normalizeMetadataToken).filter(Boolean);
      return selectedGenres.every(g => itemGenres.includes(g));
    });
  }

  // 1-2) 태그 다중 필터링 (AND 결합)
  if (state.filterTags && state.filterTags.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.tags) return false;
      const itemTags = item.tags.split(',').map(normalizeMetadataToken).filter(Boolean);
      const selectedTags = state.filterTags.map(normalizeMetadataToken).filter(Boolean);
      return selectedTags.every(t => itemTags.includes(t));
    });
  }

  // 2) 가나다(자연) 정렬 및 최신순 정렬 등
  const sortDir = state.currentSortDirection || 'asc';
  sortBooksList(filtered, sortDir);
  
  state.filteredBooksData = filtered;

  updateLibraryTotalCount(filtered);

  // 3) 클라이언트 사이드 페이징 적용 (청크로 나누기)
  const limit = state.LIMIT || 120;
  const offset = (state.currentPage - 1) * limit;
  const pageItems = filtered.slice(offset, offset + limit);
  
  state.hasMore = (offset + limit) < filtered.length;

  if (isAppend) {
    state.currentBooksData = state.currentBooksData.concat(pageItems);
    appendBooksGrid(pageItems);
  } else {
    state.currentBooksData = pageItems;
    renderBooksGrid(state.currentBooksData);
  }

  if (state.hasMore) {
    state.currentPage++;
  }

  if (spinner) {
    spinner.style.display = state.hasMore ? 'block' : 'none';
  }
  } finally {
    state.isLoading = false;
  }

  // 렌더링 및 스피너 상태 결정 완료 후 무한 스크롤 옵저버 재바인딩
  initInfiniteScrollObserver();
}

// 최근 읽은 도서 히스토리 목록 로드
export async function loadReadingHistory() {
  state.isLoading = true;
  state.hasMore = false;
  const spinner = document.getElementById('infinite-scroll-spinner');
  if (spinner) spinner.style.display = 'none';
  const container = document.getElementById('books-list-container');
  if (!container) { state.isLoading = false; return; }
  container.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${i18n.t('book_list.history_loading')}</div>`;
  try {
    const data = await api.fetchReadingHistory(state.currentLibraryType);
    if (data.success) {
      let books = data.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => !(b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages)));
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

  const searchBtn = document.getElementById('btn-library-search-action');
  if (searchBtn) {
    searchBtn.innerText = query ? i18n.t('common.reset') : i18n.t('common.search');
  }
  
  if (query && state.currentLibraryId === 'history') {
    state.currentLibraryId = 'all';
    loadLibraries();
  }
  
  // 서버에 요청 없이 로컬 상태 목록 갱신
  state.currentPage = 1;
  state.hasMore = true;
  
  let filtered = [...state.allBooksData];
  if (state.searchQuery) {
    filtered = filtered.filter(item => 
      (item.series_name && item.series_name.toLowerCase().includes(state.searchQuery)) ||
      (item.author && item.author.toLowerCase().includes(state.searchQuery))
    );
  }

  // 1-1) 장르 다중 필터링 (AND 결합)
  if (state.filterGenres && state.filterGenres.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.genre) return false;
      const itemGenres = item.genre.split(',').map(normalizeMetadataToken).filter(Boolean);
      const selectedGenres = state.filterGenres.map(normalizeMetadataToken).filter(Boolean);
      return selectedGenres.every(g => itemGenres.includes(g));
    });
  }

  // 1-2) 태그 다중 필터링 (AND 결합)
  if (state.filterTags && state.filterTags.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.tags) return false;
      const itemTags = item.tags.split(',').map(normalizeMetadataToken).filter(Boolean);
      const selectedTags = state.filterTags.map(normalizeMetadataToken).filter(Boolean);
      return selectedTags.every(t => itemTags.includes(t));
    });
  }

  const sortDir = state.currentSortDirection || 'asc';
  sortBooksList(filtered, sortDir);
  
  state.filteredBooksData = filtered;

  updateLibraryTotalCount(filtered);

  const limit = state.LIMIT || 120;
  const pageItems = filtered.slice(0, limit);
  state.hasMore = limit < filtered.length;
  state.currentPage = 2;
  
  state.currentBooksData = pageItems;
  renderBooksGrid(pageItems);

  const spinner = document.getElementById('infinite-scroll-spinner');
  if (spinner) {
    spinner.style.display = state.hasMore ? 'block' : 'none';
  }
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

  // 서버 요청 없이 로컬 상태 정렬 후 리렌더링
  state.currentPage = 1;
  state.hasMore = true;
  
  let filtered = [...state.allBooksData];
  if (state.searchQuery) {
    filtered = filtered.filter(item => 
      (item.series_name && item.series_name.toLowerCase().includes(state.searchQuery)) ||
      (item.author && item.author.toLowerCase().includes(state.searchQuery))
    );
  }

  sortBooksList(filtered, newSort);

  updateLibraryTotalCount(filtered);

  const limit = state.LIMIT || 120;
  const pageItems = filtered.slice(0, limit);
  state.hasMore = limit < filtered.length;
  state.currentPage = 2;
  
  state.currentBooksData = pageItems;
  renderBooksGrid(pageItems);

  const spinner = document.getElementById('infinite-scroll-spinner');
  if (spinner) {
    spinner.style.display = state.hasMore ? 'block' : 'none';
  }
}

// 시리즈 이어보기 로직
export async function resumeSeries(e, seriesName, libraryId) {
  if (e) {
    e.stopPropagation();
    e.preventDefault();
  }
  console.log(`[Resume-Series] 시리즈 이어보기 요청: ${seriesName} (카테고리: ${libraryId})`);
  
  const activeLibId = libraryId || state.currentLibraryId || 'all';

  try {
    const data = await api.fetchMediaDetail(state.currentLibraryType, activeLibId, seriesName);
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
