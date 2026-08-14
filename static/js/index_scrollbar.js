import { state } from './state.js';
import { loadBooksList, normalizeMetadataToken } from './book_list.js';
import * as api from './api.js';

// 초성/알파벳 분류 로직은 서버(services/series_service.py의 _get_initial)에서 동일하게 수행하여
// 목표 페이지/오프셋을 계산해주므로, 클라이언트에서는 별도로 분류할 필요가 없습니다.

const INDEX_CHARS = [
  '#', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
  'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
  'ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
];

let scrollbarEl = null;

export function mountIndexScrollbar() {
  const sortDir = state.currentSortDirection || 'asc';
  // 추가일 정렬(최신/과거)에서는 우측 초성 바로가기를 숨깁니다.
  if (sortDir === 'date_desc' || sortDir === 'date_asc') {
    return;
  }

  if (scrollbarEl) return; // 이미 마운트됨

  // 모바일에서는 CSS로 display: none 처리하겠지만, 
  // 자바스크립트에서도 화면 너비가 너무 작으면 아예 렌더링을 건너뛰는 방어 코드
  if (window.innerWidth <= 768) {
    return;
  }

  scrollbarEl = document.createElement('div');
  scrollbarEl.className = 'alphabet-scrollbar';

  INDEX_CHARS.forEach(char => {
    const item = document.createElement('div');
    item.className = 'alphabet-item';
    item.textContent = char;
    item.dataset.char = char;
    
    item.onclick = (e) => {
      e.stopPropagation();
      handleIndexClick(char);
    };
    
    scrollbarEl.appendChild(item);
  });

  // library-main-content에 클래스는 유지하되, DOM은 body에 부착하여 backdrop-filter 영향을 받지 않도록 함
  const mainContent = document.querySelector('.library-main-content');
  if (mainContent) {
    mainContent.classList.add('has-index-scrollbar');
  }
  document.body.appendChild(scrollbarEl);
}

export function unmountIndexScrollbar() {
  if (scrollbarEl && scrollbarEl.parentNode) {
    scrollbarEl.parentNode.removeChild(scrollbarEl);
    scrollbarEl = null;
  }
  const mainContent = document.querySelector('.library-main-content');
  if (mainContent) {
    mainContent.classList.remove('has-index-scrollbar');
  }
}

let isJumping = false;

// 새로 로드된(단일 페이지) 그리드에서 해당 오프셋의 카드로 스크롤 이동
function scrollToCardOffset(offsetInPage) {
  setTimeout(() => {
    const cards = document.querySelectorAll('#books-list-container .book-card');
    const card = cards[offsetInPage];
    if (!card) return;
    const mainContent = document.querySelector('.library-main-content');
    if (mainContent && mainContent.scrollHeight > mainContent.clientHeight) {
      const cardRect = card.getBoundingClientRect();
      const mainRect = mainContent.getBoundingClientRect();
      const offsetTop = cardRect.top - mainRect.top + mainContent.scrollTop;
      mainContent.scrollTo({ top: Math.max(0, offsetTop - 80), behavior: 'auto' });
    } else {
      card.scrollIntoView({ behavior: 'auto', block: 'start' });
    }
  }, 60);
}

async function handleIndexClick(char) {
  // 1. 현재 데이터가 가나다 정렬(asc, desc)일 때만 동작하도록 제한
  const sortDir = state.currentSortDirection || 'asc';
  if (sortDir !== 'asc' && sortDir !== 'desc') {
    if (window.i18n) {
      alert(window.i18n.t('book_list.sort_required') || '이름(가나다) 정렬일 때만 사용할 수 있습니다.');
    } else {
      alert('이름(가나다) 정렬일 때만 사용할 수 있습니다.');
    }
    return;
  }

  if (isJumping) return;
  isJumping = true;
  if (scrollbarEl) scrollbarEl.classList.add('is-loading');

  try {
    const limit = state.LIMIT || 120;
    const result = await api.fetchJumpPosition({
      type: state.currentLibraryType,
      libraryId: state.currentLibraryId,
      search: state.searchQuery || '',
      sort: sortDir,
      genres: (state.filterGenres || []).map(normalizeMetadataToken).filter(Boolean),
      tags: (state.filterTags || []).map(normalizeMetadataToken).filter(Boolean),
      char,
      limit,
    });

    if (!result || !result.success || !result.found) {
      console.log(`'${char}'(으)로 시작하는 책을 찾을 수 없습니다.`);
      return;
    }

    // 대상 페이지만 바로 불러와서 교체하고(중간 페이지들은 건너뜀), 그 안의 정확한 위치로 스크롤한다.
    await loadBooksList(false, result.page);
    scrollToCardOffset(result.offset_in_page);
  } catch (e) {
    console.error('[Index-Scrollbar] 초성 바로가기 실패:', e);
  } finally {
    isJumping = false;
    if (scrollbarEl) scrollbarEl.classList.remove('is-loading');
  }
}
