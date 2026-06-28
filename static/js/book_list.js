import { state } from './state.js';
import * as api from './api.js';
import { renderHistoryGrid, renderBooksGrid, appendBooksGrid } from './ui.js';
import { openReader } from './viewer.js';
import { loadLibraries } from './category.js';

function updateLibraryTotalCount(items) {
  const countSpan = document.getElementById('library-total-count');
  if (!countSpan) return;
  const seriesCount = items.length;
  let bookCount = 0;
  items.forEach(item => {
    bookCount += (parseInt(item.book_count) || 1);
  });
  countSpan.innerText = `(전체: ${seriesCount.toLocaleString()} 시리즈 / ${bookCount.toLocaleString()} 권)`;
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

  // append가 아닐 때는 최초 1회 전체 데이터를 가져옴
  if (!isAppend) {
    state.isLoading = true;
    state.currentPage = 1;
    state.hasMore = true;
    container.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 도서 목록을 불러오는 중...</div>';
    
    try {
      const data = await api.fetchAllBooksList(state.currentLibraryType, state.currentLibraryId);
      if (data.success) {
        state.allBooksData = data.series || [];
      } else {
        container.innerHTML = `<div class="loading-spinner">목록 로드 실패: ${data.error || '알 수 없는 오류'}</div>`;
        state.isLoading = false;
        return;
      }
    } catch (e) {
      container.innerHTML = '<div class="loading-spinner">서버 연결 오류가 발생했습니다.</div>';
      console.error('도서 목록 로드 오류:', e);
      state.isLoading = false;
      return;
    } finally {
      state.isLoading = false;
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
      const itemGenres = item.genre.split(',').map(g => g.trim());
      return state.filterGenres.every(g => itemGenres.includes(g));
    });
  }

  // 1-2) 태그 다중 필터링 (AND 결합)
  if (state.filterTags && state.filterTags.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.tags) return false;
      const itemTags = item.tags.split(',').map(t => t.trim());
      return state.filterTags.every(t => itemTags.includes(t));
    });
  }

  // 2) 가나다(자연) 정렬 및 최신순 정렬 등
  const sortDir = state.currentSortDirection || 'asc';
  sortBooksList(filtered, sortDir);

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
}

// 최근 읽은 도서 히스토리 목록 로드
export async function loadReadingHistory() {
  state.isLoading = true;
  state.hasMore = false;
  const spinner = document.getElementById('infinite-scroll-spinner');
  if (spinner) spinner.style.display = 'none';
  const container = document.getElementById('books-list-container');
  if (!container) { state.isLoading = false; return; }
  container.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 최근 읽은 도서를 불러오는 중...</div>';
  try {
    const data = await api.fetchReadingHistory(state.currentLibraryType);
    if (data.success) {
      let books = data.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => !(b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages)));
      }
      renderHistoryGrid(books);
    } else {
      container.innerHTML = `<div class="loading-spinner">히스토리 로드 실패: ${data.error || '알 수 없는 오류'}</div>`;
    }
  } catch (e) {
    container.innerHTML = '<div class="loading-spinner">서버 연결 오류가 발생했습니다.</div>';
    console.error('히스토리 로드 오류:', e);
  } finally {
    state.isLoading = false;
  }
}

// 3. 도서 검색 필터링 (클라이언트 사이드 메모리 내 즉시 필터링)
export function filterBooks() {
  const query = document.getElementById('library-search').value.toLowerCase().trim();
  state.searchQuery = query;
  
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
      const itemGenres = item.genre.split(',').map(g => g.trim());
      return state.filterGenres.every(g => itemGenres.includes(g));
    });
  }

  // 1-2) 태그 다중 필터링 (AND 결합)
  if (state.filterTags && state.filterTags.length > 0) {
    filtered = filtered.filter(item => {
      if (!item.tags) return false;
      const itemTags = item.tags.split(',').map(t => t.trim());
      return state.filterTags.every(t => itemTags.includes(t));
    });
  }

  const sortDir = state.currentSortDirection || 'asc';
  sortBooksList(filtered, sortDir);

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

  if (newSort === 'asc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-alpha-down"></i> 가나다 오름차순`;
  } else if (newSort === 'desc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-alpha-up"></i> 가나다 내림차순`;
  } else if (newSort === 'date_desc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-numeric-down-alt"></i> 최신 추가순`;
  } else if (newSort === 'date_asc') {
    btn.innerHTML = `<i class="fa-solid fa-sort-numeric-up"></i> 과거 추가순`;
  }

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
      alert('도서 목록을 불러오는 데 실패했습니다.');
    }
  } catch (err) {
    console.error('[Resume-Series] 이어보기 로직 에러:', err);
    alert('이어보기 중 오류가 발생했습니다.');
  }
}
