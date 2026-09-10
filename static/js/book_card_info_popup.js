// book_card_info_popup.js – 그리드 카드 '...' 아이콘 클릭 시 뜨는 읽기전용 정보 팝업
// (제목/실제경로/도서 수/파일 크기). 기존 book_context_menu.js의 액션 메뉴와는 별개의 팝업이다.
import { state } from './state.js';
import * as api from './api.js';
import { positionMenuAtElement, hideFloatingMenu, bindFloatingMenuOutsideClose } from './context_menu_manager.js';

function formatBytes(bytes) {
  const n = Number(bytes) || 0;
  if (n <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const idx = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  const value = n / Math.pow(1024, idx);
  return `${idx === 0 ? value : value.toFixed(2)} ${units[idx]}`;
}

let loadSeq = 0;

function closePopup() {
  hideFloatingMenu('book-info-popup');
}

async function openPopup(anchorBtn, card) {
  const popup = document.getElementById('book-info-popup');
  if (!popup) return;

  const bookId = card.dataset.bookId || '';
  const seriesName = card.dataset.seriesName || '';
  const libraryId = card.dataset.libraryId || '';
  const bookCount = parseInt(card.dataset.bookCount, 10) || 1;
  const isSeries = bookCount > 1 && !!seriesName;

  const titleEl = document.getElementById('book-info-popup-title');
  const pathEl = document.getElementById('book-info-popup-path');
  const countRowEl = document.getElementById('book-info-popup-count-row');
  const countEl = document.getElementById('book-info-popup-count');
  const sizeEl = document.getElementById('book-info-popup-size');

  titleEl.textContent = card.dataset.title || '';
  pathEl.textContent = '조회 중...';
  countRowEl.style.display = isSeries ? '' : 'none';
  countEl.textContent = '';
  sizeEl.textContent = '조회 중...';

  positionMenuAtElement(popup, anchorBtn, { zIndex: 20070 });

  const seq = ++loadSeq;
  try {
    const res = await api.fetchBookCardInfo(state.currentLibraryType, {
      bookId: isSeries ? null : bookId,
      seriesName: isSeries ? seriesName : '',
      libraryId,
    });
    if (seq !== loadSeq) return;

    if (!res || !res.success) {
      pathEl.textContent = '정보를 불러오지 못했습니다.';
      sizeEl.textContent = '-';
      return;
    }

    pathEl.textContent = res.physical_path || '-';
    countEl.textContent = `${res.book_count || 1}권`;
    sizeEl.textContent = formatBytes(res.total_size);
  } catch (err) {
    if (seq !== loadSeq) return;
    console.error('[BookCardInfoPopup] 정보 조회 실패:', err);
    pathEl.textContent = '정보를 불러오지 못했습니다.';
    sizeEl.textContent = '-';
  }
}

document.addEventListener('click', (event) => {
  const kebabBtn = event.target.closest('.book-card-kebab-btn');
  if (kebabBtn) {
    event.preventDefault();
    event.stopPropagation();
    // context_menu_manager.js의 bindFloatingMenuOutsideClose는 document에 같은 캡처 단계로
    // 등록되어 있어 stopPropagation만으로는 막지 못한다(같은 노드의 다른 리스너는 그대로 실행됨).
    // 그 리스너가 "방금 연 팝업을 바깥 클릭으로 간주해 즉시 닫는" 것을 막으려면
    // stopImmediatePropagation으로 이 클릭 이벤트의 나머지 리스너 실행 자체를 끊어야 한다.
    if (typeof event.stopImmediatePropagation === 'function') {
      event.stopImmediatePropagation();
    }
    const card = kebabBtn.closest('.book-card');
    if (card) openPopup(kebabBtn, card);
    return;
  }

  if (event.target.closest('[data-role="book-info-popup-close"]')) {
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === 'function') {
      event.stopImmediatePropagation();
    }
    closePopup();
    return;
  }
}, true);

bindFloatingMenuOutsideClose('book-info-popup');
