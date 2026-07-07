// book_context_menu.js – 도서 우클릭 단독 스캔 컨텍스트 메뉴 제어 모듈
import { state } from './state.js';
import * as api from './api.js';
import { openBookDetail } from './modal.js';
import { loadBooksList, loadReadingHistory } from './book_list.js';
import { loadDashboardData } from './dashboard.js';

let currentTargetBook = null;

export function showBookContextMenu(x, y, bookId, bookTitle, isVolumeDetail = false) {
  const bookMenu = document.getElementById('book-context-menu');
  if (!bookMenu) return;
  
  currentTargetBook = { id: bookId, title: bookTitle, isVolumeDetail };
  
  // 임시 표시하여 실제 메뉴 크기 측정
  bookMenu.style.display = 'block';
  const menuHeight = bookMenu.offsetHeight || 180;
  const menuWidth = bookMenu.offsetWidth || 160;
  
  // 뷰포트 경계 검사 및 위치 보정
  let targetX = x + window.scrollX;
  let targetY = y + window.scrollY;
  
  if (y + menuHeight > window.innerHeight) {
    targetY = (y - menuHeight) + window.scrollY;
    // 음수가 되지 않도록 최소 한계 보정
    if (targetY < window.scrollY) targetY = window.scrollY;
  }
  
  if (x + menuWidth > window.innerWidth) {
    targetX = (x - menuWidth) + window.scrollX;
    if (targetX < window.scrollX) targetX = window.scrollX;
  }
  
  bookMenu.style.left = `${targetX}px`;
  bookMenu.style.top = `${targetY}px`;
  
  // 다른 메뉴 닫기
  const libMenu = document.getElementById('library-context-menu');
  if (libMenu) libMenu.style.display = 'none';
}

export async function triggerScanSingleBookAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title, isVolumeDetail } = currentTargetBook;
  
  import('./view_manager.js').then(async (vm) => {
    vm.showToast(`"${title}" 스캔 중...`, 'info');
    try {
      const res = await api.scanSingleBook(state.currentLibraryType, id);
      if (res.success) {
        vm.showToast(res.message, 'success');
        
        const newCoverName = res.cover_image;
        if (!newCoverName) return;

        // 캐시 버스팅을 위한 URL 타임스탬프 생성
        const cacheBustedCoverUrl = `/covers/${newCoverName}?t=${Date.now()}`;

        if (isVolumeDetail) {
          // 상세 뷰: 해당 volume-card의 img 갱신
          // oncontextmenu 식에 b.id 값을 인자로 보냈음
          const volCards = document.querySelectorAll('.volume-card');
          volCards.forEach(card => {
            // 인라인 oncontextmenu 식 문자열 분석 혹은 innerHTML 내 openReader 호출 등으로 매칭 탐색
            if (card.outerHTML.includes(`openReader(${id},`) || card.outerHTML.includes(`showBookContextMenu(event.clientX, event.clientY, ${id},`)) {
              const img = card.querySelector('.volume-thumb');
              if (img) {
                img.src = cacheBustedCoverUrl;
                console.log(`[CacheBusting] 상세 뷰 단행본 표지 교체 성공 (ID: ${id})`);
              }
            }
          });
        } else {
          // 그리드 뷰: data-book-id 기반으로 매칭되는 카드 찾기
          const targetCard = document.querySelector(`.book-card[data-book-id="${id}"]`);
          if (targetCard) {
            const img = targetCard.querySelector('.book-card-cover img');
            if (img) {
              img.src = cacheBustedCoverUrl;
              console.log(`[CacheBusting] 그리드 뷰 책 표지 교체 성공 (ID: ${id})`);
            }
          }
        }
      } else {
        vm.showToast(`스캔 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('단일 도서 스캔 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

window.triggerScanSingleBookAction = triggerScanSingleBookAction;

export function triggerSearchMetadataAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title } = currentTargetBook;
  
  if (typeof window.openMetadataSearchModal === 'function') {
    window.openMetadataSearchModal(id, title);
  } else if (typeof window.openAladinSearchModal === 'function') {
    window.openAladinSearchModal(id, title);
  } else {
    console.error('[Global Trigger ERROR] window.openMetadataSearchModal 함수가 바인딩되지 않았습니다.');
  }
}
window.triggerSearchMetadataAction = triggerSearchMetadataAction;
window.triggerSearchAladinMetadataAction = triggerSearchMetadataAction;

export async function triggerMarkAsUnreadAction() {
  if (!currentTargetBook || !currentTargetBook.id) return;
  const { id, title } = currentTargetBook;

  import('./view_manager.js').then(async (vm) => {
    try {
      const res = await api.markBookAsUnread(state.currentLibraryType, id);
      if (res.success) {
        vm.showToast(`"${title}" 도서가 읽지 않은 상태(0%)로 변경되었습니다.`, 'success');
        
        // 화면 리프레시: 현재 위치한 탭/뷰에 맞추어 라이브 리로드 실행
        if (state.currentLibraryId === 'home') {
          loadDashboardData();
        } else if (state.currentLibraryId === 'history') {
          loadReadingHistory();
        } else {
          // 상세 뷰 혹은 일반 도서 목록 새로고침
          const detailModal = document.getElementById('book-detail-modal');
          if (detailModal && detailModal.style.display === 'flex') {
            const seriesName = document.querySelector('.detail-title-text')?.textContent || '';
            if (seriesName) {
              openBookDetail(null, seriesName, state.currentLibraryId);
            }
          }
          loadBooksList();
        }
      } else {
        vm.showToast(`변경 실패: ${res.error}`, 'error');
      }
    } catch (err) {
      console.error('도서 읽지않음 처리 API 에러:', err);
      vm.showToast('서버 통신 중 오류가 발생했습니다.', 'error');
    }
  });
}

window.triggerMarkAsUnreadAction = triggerMarkAsUnreadAction;
export { triggerSearchMetadataAction as triggerSearchAladinMetadataAction };

window.showBookContextMenu = showBookContextMenu;

// 도서 우클릭 메뉴 클릭 이외 시 닫기 핸들러 추가
document.addEventListener('click', () => {
  const bookMenu = document.getElementById('book-context-menu');
  if (bookMenu) bookMenu.style.display = 'none';
});

// 모바일 터치 기기용 롱 프레스 감지 헬퍼 함수
let longPressTimer = null;
let touchStartX = 0;
let touchStartY = 0;
const touchMoveThreshold = 10;

window.handleLongPressTouchStart = function(event, callback) {
  if (event.touches.length > 1) return;
  const touch = event.touches[0];
  touchStartX = touch.clientX;
  touchStartY = touch.clientY;
  
  if (longPressTimer) clearTimeout(longPressTimer);
  
  longPressTimer = setTimeout(() => {
    if (typeof callback === 'function') {
      // 기본 터치 홀드 효과 방지 (돋보기, 텍스트 선택 등 방어)
      if (event.cancelable) {
        event.preventDefault();
      }
      callback(touch.clientX, touch.clientY);
    }
    longPressTimer = null;
  }, 600); // 600ms 길게 누름 감지
};

window.handleLongPressTouchMove = function(event) {
  if (!longPressTimer) return;
  const touch = event.touches[0];
  const diffX = Math.abs(touch.clientX - touchStartX);
  const diffY = Math.abs(touch.clientY - touchStartY);
  if (diffX > touchMoveThreshold || diffY > touchMoveThreshold) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
};

window.handleLongPressTouchEnd = function(event) {
  if (longPressTimer) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
};
