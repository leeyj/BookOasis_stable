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
  
  bookMenu.style.left = `${x + window.scrollX}px`;
  bookMenu.style.top = `${y + window.scrollY}px`;
  bookMenu.style.display = 'block';
  
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

export { triggerSearchMetadataAction as triggerSearchAladinMetadataAction };

// 도서 우클릭 메뉴 클릭 이외 시 닫기 핸들러 추가
document.addEventListener('click', () => {
  const bookMenu = document.getElementById('book-context-menu');
  if (bookMenu) bookMenu.style.display = 'none';
});
