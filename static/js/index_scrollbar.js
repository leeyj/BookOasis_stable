import { state } from './state.js';
import { jumpToIndex } from './book_list.js';
import { stripLeadingBracketTags } from './series_display.js';

// 한글 초성 배열
const CHOSEONG = [
  'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ',
  'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ',
  'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
];

/**
 * 텍스트의 첫 글자를 분석하여 초성, 알파벳 대문자, 또는 '#'을 반환합니다.
 */
export function getInitial(text) {
  if (!text || text.trim() === '') return '#';
  
  const firstChar = text.trim().charAt(0);
  const code = firstChar.charCodeAt(0);

  // 한글 가(AC00) ~ 힣(D7A3)
  if (code >= 0xAC00 && code <= 0xD7A3) {
    const choseongIndex = Math.floor((code - 0xAC00) / 588);
    return CHOSEONG[choseongIndex];
  }
  
  // 이미 초성인 경우 (ㄱ ~ ㅎ)
  if (code >= 0x3131 && code <= 0x314E) {
    return firstChar;
  }

  // 영문 알파벳
  if (/[a-zA-Z]/.test(firstChar)) {
    return firstChar.toUpperCase();
  }

  // 숫자 및 기타 기호
  return '#';
}

const INDEX_CHARS = [
  '#', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
  'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
  'ㄱ', 'ㄴ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
];

let scrollbarEl = null;

export function mountIndexScrollbar() {
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

function handleIndexClick(char) {
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

  if (!state.filteredBooksData || state.filteredBooksData.length === 0) return;

  // 2. target 인덱스 찾기
  let targetIndex = -1;

  for (let i = 0; i < state.filteredBooksData.length; i++) {
    const book = state.filteredBooksData[i];
    // ui.js의 normalizeBookTitle 로직과 동일하게 제목을 가져옴
    const title = stripLeadingBracketTags(book.series_name || book.title || '');
    const initial = getInitial(title);

    // ASC 정렬 시 첫 번째 매칭 아이템
    if (sortDir === 'asc' && initial === char) {
      targetIndex = i;
      break;
    }
    
    // DESC 정렬 시에도 일단 첫 번째 매칭을 찾음 (역순이므로 가장 Z나 ㅎ에 가까운 것부터 나옴)
    // 좀 더 엄밀하게 하려면 이진 탐색 등을 쓸 수 있지만, 브라우저 성능이 충분하므로 선형 탐색 사용
    if (sortDir === 'desc' && initial === char) {
      targetIndex = i;
      break;
    }
  }

  // 3. 찾았으면 이동, 못 찾았으면 알림
  if (targetIndex !== -1) {
    jumpToIndex(targetIndex);
  } else {
    // 해당 초성으로 시작하는 책이 없음
    console.log(`'${char}'(으)로 시작하는 책을 찾을 수 없습니다.`);
  }
}
