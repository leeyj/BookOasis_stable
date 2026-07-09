// viewer_next_episode.js – 다음 편 이어서 보기 제어 모듈
import { state } from './state.js';
import { closeMediaViewer } from './viewer.js';

let nextEpisodeBusy = false;
let nextEpisodeModalOpen = false;
let noNextEpisodeAlertTimer = null;
let lastHandledBookId = null;
let lastHandledAt = 0;
let userInteractionSerial = 0;
let interactionTrackerBound = false;
let nextEpisodeArmBookId = null;
let nextEpisodeArmInteractionSerial = -1;

let lastScrollDirection = 'none';

function bindUserInteractionTracker() {
  if (interactionTrackerBound || typeof document === 'undefined') return;
  interactionTrackerBound = true;

  const markInteraction = (event) => {
    if (event && event.isTrusted === false) return;
    
    if (event && event.type === 'wheel') {
      lastScrollDirection = event.deltaY > 0 ? 'down' : 'up';
      if (event.deltaY < 0) {
        clearNextEpisodeArm();
      }
    } else if (event && event.type === 'keydown') {
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight' || event.key === ' ') {
        lastScrollDirection = 'down';
      } else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
        lastScrollDirection = 'up';
        clearNextEpisodeArm();
      }
    } else if (event && (event.type === 'touchstart' || event.type === 'pointerdown')) {
      // 터치/포인터 입력은 우선 기본방향 down으로 세팅하되 이전의 up 락을 초기화
      lastScrollDirection = 'down';
    }

    userInteractionSerial += 1;
  };

  document.addEventListener('pointerdown', markInteraction, { capture: true, passive: true });
  document.addEventListener('touchstart', markInteraction, { capture: true, passive: true });
  document.addEventListener('wheel', markInteraction, { capture: true, passive: true });
  document.addEventListener('keydown', markInteraction, { capture: true });
  document.addEventListener('click', markInteraction, { capture: true, passive: true });
}

let nextEpisodeArmTime = 0;

function armNextEpisode(bookId) {
  nextEpisodeArmBookId = String(bookId ?? '');
  nextEpisodeArmInteractionSerial = userInteractionSerial;
  nextEpisodeArmTime = Date.now();
  lastScrollDirection = 'none';
}

export function clearNextEpisodeArm() {
  nextEpisodeArmBookId = null;
  nextEpisodeArmInteractionSerial = -1;
  nextEpisodeArmTime = 0;
  lastScrollDirection = 'none';
}

export function handleNextEpisode(currentBookId) {
  bindUserInteractionTracker();

  if (nextEpisodeBusy || nextEpisodeModalOpen) {
    return;
  }

  const currentBookIdKey = String(currentBookId ?? '');
  const isComic = state.currentViewerFormat === 'zip' || state.currentViewerFormat === 'cbz';

  // [수정] 만약 아예 다른 책이거나 arming 정보가 없는데 serial이 비정상적으로 같거나 큰 경우 방어
  if (nextEpisodeArmBookId !== currentBookIdKey) {
    console.log(`[Viewer-Next] Arming next episode for book: ${currentBookIdKey}. Resetting arm state. Current serial: ${userInteractionSerial}`);
    // 책이 달라진 시점이므로 Arming 데이터를 초기화하고 새로 지정
    armNextEpisode(currentBookIdKey);
    return;
  }

  if (isComic) {
    const elapsed = Date.now() - nextEpisodeArmTime;
    const diff = userInteractionSerial - nextEpisodeArmInteractionSerial;
    console.log(`[Viewer-Next] Checking comic next episode conditions. Elapsed: ${elapsed}ms (req: >=800ms), Serial Diff: ${diff} (req: >=3), Direction: ${lastScrollDirection}`);
    
    // 위로 스크롤 시 다음권 진행 취소
    if (lastScrollDirection === 'up') {
      clearNextEpisodeArm();
      return;
    }

    if (diff < 3 || elapsed < 800) {
      return;
    }
    console.log(`[Viewer-Next] All conditions met! Triggering next episode.`);
  } else {
    if (userInteractionSerial <= nextEpisodeArmInteractionSerial) {
      return;
    }
  }

  clearNextEpisodeArm();
  executeNextEpisodeFetch(currentBookId);
}

/**
 * 2단계 Arming 검증을 건너뛰고 즉각 다음 에피소드를 조회하여 이동시킵니다.
 * 만화책 스크롤 최하단 감지나 수동 클릭 등에서 명시적인 동작이 감지되었을 때 직접 호출합니다.
 */
export function handleNextEpisodeDirect(currentBookId, forceModal = false) {
  if (nextEpisodeBusy || nextEpisodeModalOpen) {
    return;
  }
  clearNextEpisodeArm();
  executeNextEpisodeFetch(currentBookId, forceModal);
}

function executeNextEpisodeFetch(currentBookId, forceModal = false) {
  const now = Date.now();
  if (String(lastHandledBookId) === String(currentBookId) && now - lastHandledAt < 2500) {
    return;
  }
  lastHandledBookId = currentBookId;
  lastHandledAt = now;

  nextEpisodeBusy = true;
  if (noNextEpisodeAlertTimer) {
    clearTimeout(noNextEpisodeAlertTimer);
    noNextEpisodeAlertTimer = null;
  }
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
        if (String(nextBook.id) === String(currentBookId)) {
          console.warn('[Viewer-Next] next book id is same as current book id. skip transition.', {
            currentBookId,
            nextBookId: nextBook.id,
          });
          noNextEpisodeAlertTimer = setTimeout(() => {
            noNextEpisodeAlertTimer = null;
            alert(i18n.t('viewer.last_page_episode'));
          }, 200);
          return null;
        }
        if (noNextEpisodeAlertTimer) {
          clearTimeout(noNextEpisodeAlertTimer);
          noNextEpisodeAlertTimer = null;
        }
        // 사용자 경험 통일을 위해 설정값에 상관없이 모든 도서 포맷에서 항상 확인 팝업을 띄웁니다.
        const action = 'prompt';

        if (action === 'direct') {
          return triggerOpenNextBook(nextBook);
        } else {
          nextEpisodeModalOpen = true;
          showNextEpisodeModal(nextBook);
          return null;
        }
      } else {
        noNextEpisodeAlertTimer = setTimeout(() => {
          noNextEpisodeAlertTimer = null;
          alert(i18n.t('viewer.last_page_episode'));
        }, 350);
        return null;
      }
    })
    .catch(err => {
      console.error('[Viewer-Next] Failed to fetch next book details:', err);
      noNextEpisodeAlertTimer = setTimeout(() => {
        noNextEpisodeAlertTimer = null;
        alert(i18n.t('viewer.last_page'));
      }, 350);
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
    clearNextEpisodeArm();
    return;
  }

  // 1. 현재 열려 있는 뷰어를 완전히 닫고 다음 책으로 전환하여 깜빡임 루프를 방지합니다.
  closeMediaViewer(false, false);

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
      if (noNextEpisodeAlertTimer) {
        clearTimeout(noNextEpisodeAlertTimer);
        noNextEpisodeAlertTimer = null;
      }
    })
    .finally(() => {
      nextEpisodeBusy = false;
      nextEpisodeModalOpen = false;
      clearNextEpisodeArm();
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
    clearNextEpisodeArm();
  };
}
