// viewer_next_episode.js – 다음 편 이어서 보기 제어 모듈
import { state } from './state.js';
import { closeMediaViewer } from './viewer.js';

let nextEpisodeBusy = false;
let nextEpisodeModalOpen = false;

/**
 * 다음 편 조회를 요청하고 설정된 액션 옵션에 따라 처리합니다.
 * @param {string|number} currentBookId - 현재 읽고 있는 도서 ID
 */
export function handleNextEpisode(currentBookId) {
  if (nextEpisodeBusy || nextEpisodeModalOpen) {
    return;
  }

  nextEpisodeBusy = true;
  const url = `/api/media/next-book?type=${state.currentLibraryType}&book_id=${currentBookId}`;

  fetch(url)
    .then(async res => {
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      return await res.json();
    })
    .then(data => {
      if (data.success && data.next_book) {
        const nextBook = data.next_book;
        const action = localStorage.getItem('viewer_next_episode_action') || 'direct';

        if (action === 'direct') {
          return triggerOpenNextBook(nextBook);
        } else {
          nextEpisodeModalOpen = true;
          showNextEpisodeModal(nextBook);
          return null;
        }
      } else {
        alert(i18n.t('viewer.last_page_episode'));
        return null;
      }
    })
    .catch(err => {
      console.error('[Viewer-Next] Failed to fetch next book details:', err);
      alert(i18n.t('viewer.last_page'));
    })
    .finally(() => {
      // For prompt mode, lock is released on confirm/cancel handlers.
      if (!nextEpisodeModalOpen) {
        nextEpisodeBusy = false;
      }
    });
}

function triggerOpenNextBook(nextBook) {
  if (!nextBook || !nextBook.id) {
    nextEpisodeBusy = false;
    nextEpisodeModalOpen = false;
    return;
  }

  // 1. 현재 열려 있는 뷰어 닫기 (isTransitioning 옵션을 켜서 모달을 숨기지 않음)
  closeMediaViewer(false, true);

  // 2. 순환 참조 회피를 위해 viewer.js를 동적으로 임포트하여 다음 책 로드
  return import('./viewer.js')
    .then(m => {
      m.openReader(
        nextBook.id,
        nextBook.file_format,
        nextBook.title,
        nextBook.pages_read || 0,
        nextBook.total_pages || 0
      );
    })
    .catch(err => {
      console.error('[Viewer-Next] Failed to open next book:', err);
    })
    .finally(() => {
      nextEpisodeBusy = false;
      nextEpisodeModalOpen = false;
    });
}

function showNextEpisodeModal(nextBook) {
  const modal = document.getElementById('viewer-next-episode-modal');
  const titleEl = document.getElementById('viewer-next-episode-title');
  const confirmBtn = document.getElementById('viewer-next-episode-confirm-btn');
  const cancelBtn = document.getElementById('viewer-next-episode-cancel-btn');

  if (!modal) return;

  if (titleEl) {
    titleEl.textContent = `${i18n.t('viewer.next_episode', {title: nextBook.title})}`;
  }

  // 모달 활성화
  modal.style.display = 'flex';

  // 버튼 이벤트 연결 (기존 리스너 중복 방지를 위한 단일화)
  confirmBtn.onclick = () => {
    modal.style.display = 'none';
    nextEpisodeModalOpen = false;
    triggerOpenNextBook(nextBook);
  };

  cancelBtn.onclick = () => {
    modal.style.display = 'none';
    nextEpisodeModalOpen = false;
    nextEpisodeBusy = false;
  };
}
