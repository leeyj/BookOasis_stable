// static/js/video_library.js - 영상 강좌 전용 브라우징 화면
// 사이드바(라이브러리 목록 + 추가/수정/삭제/스캔 CRUD)는 기존 category/index.js를 그대로 재사용하고
// (data-library-type="video" 상태에서 Home/History/즐겨찾기/컬렉션/스마트추천/플러그인 메뉴는 CSS로 숨김),
// 그리드 콘텐츠(강좌 카드)만 전용 렌더러로 대체한다. 카드 클릭은 오디오북과 동일하게 공용 상세화면
// 파이프라인(openBookDetail)을 그대로 타서, 상세화면/에피소드 목록/재생시간 저장 UI가 오디오북과 일치한다.
import { openBookDetail } from './detail/index.js';
import { updateLibraryTotalCount } from './book_list.js';
import { positionMenuAtPoint, hideFloatingMenu, bindFloatingMenuOutsideClose } from './context_menu_manager.js';
import { state } from './state.js';

function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  if (seconds <= 0) return '분석전';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}시간 ${minutes}분`;
  return `${minutes}분`;
}

let lastLoadedVideos = [];
let lastLoadedLibraryId = null;

// 영상 강좌 카드 전용 우클릭 컨텍스트 메뉴 - 일반 도서용 book-context-menu는
// books 테이블 기준 액션(즉시 스캔/읽지 않음 처리 등)이라 video_id에 대응하지 않으므로,
// 실제로 동작하는 항목(상세보기/즐겨찾기/컬렉션 추가)만 담은 축소 메뉴를 별도로 둔다.
let videoContextMenuBound = false;
let currentContextCard = null;

function bindVideoContextMenuOnce() {
  if (videoContextMenuBound) return;
  videoContextMenuBound = true;
  const menu = document.getElementById('video-context-menu');
  if (!menu) return;

  menu.addEventListener('click', (event) => {
    if (event.target.closest('[data-role="video-context-close"]')) {
      hideFloatingMenu(menu);
      return;
    }
    const actionEl = event.target.closest('[data-role="video-context-action"]');
    if (!actionEl || !currentContextCard) return;
    const action = actionEl.getAttribute('data-action');
    const card = currentContextCard;
    hideFloatingMenu(menu);

    if (action === 'open-detail') {
      const videoId = parseInt(card.getAttribute('data-video-id'), 10);
      const title = card.getAttribute('data-video-title') || '';
      if (Number.isFinite(videoId)) {
        openBookDetail(null, title, card.dataset.libraryId || lastLoadedLibraryId, videoId, title);
      }
    } else if (action === 'toggle-favorite') {
      card.querySelector('[data-role="video-course-favorite"]')?.click();
    } else if (action === 'add-to-collection') {
      card.querySelector('[data-role="video-course-add-collection"]')?.click();
    }
  });

  bindFloatingMenuOutsideClose(menu);
}

function showVideoContextMenu(x, y, card, libraryId) {
  bindVideoContextMenuOnce();
  currentContextCard = card;
  card.dataset.libraryId = libraryId ?? '';

  const title = card.getAttribute('data-video-title') || '';
  const titleEl = document.getElementById('video-ctx-title');
  if (titleEl) titleEl.textContent = title || '강좌 메뉴';

  const favBtn = card.querySelector('[data-role="video-course-favorite"]');
  const favLabelEl = document.getElementById('video-ctx-favorite-label');
  if (favLabelEl) favLabelEl.textContent = favBtn?.classList.contains('active') ? '즐겨찾기 해제' : '즐겨찾기 추가';

  positionMenuAtPoint('video-context-menu', x, y, { zIndex: 20060 });
}

function updateVideoTotalCount(videos) {
  const totalEpisodes = videos.reduce((sum, v) => sum + (parseInt(v.total_episodes, 10) || 0), 0);
  updateLibraryTotalCount(videos, { total_series_count: videos.length, total_book_count: totalEpisodes });
}

function renderVideoCourseCards(videos, libraryId, emptyMessage) {
  const container = document.getElementById('books-list-container');
  if (!container) return;

  if (videos.length === 0) {
    container.innerHTML = `<div class="loading-spinner">${escapeHtml(emptyMessage)}</div>`;
    return;
  }

  // #books-list-container 자체가 이미 .books-grid(display:grid) 클래스를 갖고 있으므로,
  // 일반 도서 그리드와 동일하게 카드를 컨테이너의 직속 자식으로 주입해야 한다.
  // (내부에 .books-grid로 한 번 더 감싸면 그리드가 중첩되어 카드가 1열로 무너지고 커버 이미지가 넘친다.)
  container.innerHTML = videos.map(v => {
    const isFav = Number(v.is_favorite) === 1;
    return `
    <div class="book-card" data-role="video-course-card" data-video-id="${v.id}" data-video-title="${escapeHtml(v.title)}">
      <div class="book-card-cover">
        <div class="book-card-overlay"></div>
        <img src="/api/media/videos/${v.id}/cover" alt="${escapeHtml(v.title)}" decoding="async" loading="lazy">
        <div class="book-badge-count">${v.total_episodes || 0}편</div>
        <button class="btn-card-fav-toggle" data-role="video-course-add-collection" title="컬렉션에 추가"
                style="position:absolute; top:8px; left:8px; background:rgba(15,23,42,0.75); border:none; color:#c084fc; width:1.9rem; height:1.9rem; border-radius:50%; cursor:pointer; display:flex; align-items:center; justify-content:center; z-index:2;">
          <i class="fa-solid fa-folder-plus"></i>
        </button>
        <button class="btn-card-fav-toggle ${isFav ? 'active' : ''}" data-role="video-course-favorite" data-next-status="${isFav ? 0 : 1}" title="즐겨찾기 토글"
                style="position:absolute; top:8px; right:8px; background:rgba(15,23,42,0.75); border:none; color:${isFav ? '#eab308' : '#94a3b8'}; width:1.9rem; height:1.9rem; border-radius:50%; cursor:pointer; display:flex; align-items:center; justify-content:center; z-index:2;">
          <i class="${isFav ? 'fa-solid' : 'fa-regular'} fa-star"></i>
        </button>
      </div>
      <div class="book-card-info">
        <p class="book-card-title" title="${escapeHtml(v.title)}">${escapeHtml(v.title)}</p>
        <span style="font-size:0.72rem; color:#94a3b8;">${formatDuration(v.total_duration)}</span>
      </div>
    </div>
  `;
  }).join('');

  container.querySelectorAll('[data-role="video-course-add-collection"]').forEach(el => {
    el.addEventListener('click', (event) => {
      event.stopPropagation();
      event.preventDefault();
      const card = el.closest('[data-role="video-course-card"]');
      const videoId = parseInt(card?.getAttribute('data-video-id'), 10);
      const title = card?.getAttribute('data-video-title') || '';
      if (!Number.isFinite(videoId)) return;
      import('./tab_collections.js').then((colls) => {
        colls.openAddToCollectionModal({ video_id: videoId, title });
      });
    });
  });

  container.querySelectorAll('[data-role="video-course-favorite"]').forEach(el => {
    el.addEventListener('click', async (event) => {
      event.stopPropagation();
      event.preventDefault();
      const card = el.closest('[data-role="video-course-card"]');
      const title = card?.getAttribute('data-video-title') || '';
      const nextStatus = parseInt(el.getAttribute('data-next-status'), 10) === 1;
      if (!title) return;

      // 낙관적 UI 갱신
      const icon = el.querySelector('i');
      el.classList.toggle('active', nextStatus);
      el.setAttribute('data-next-status', nextStatus ? 0 : 1);
      el.style.color = nextStatus ? '#eab308' : '#94a3b8';
      if (icon) icon.className = nextStatus ? 'fa-solid fa-star' : 'fa-regular fa-star';

      try {
        const res = await fetch('/api/media/series/favorite', {
          method: 'POST',
          body: new URLSearchParams({ type: 'video', series_name: title, is_favorite: nextStatus ? '1' : '0' })
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'favorite toggle failed');

        const videoId = parseInt(card?.getAttribute('data-video-id'), 10);
        const cached = lastLoadedVideos.find(v => v.id === videoId);
        if (cached) cached.is_favorite = nextStatus ? 1 : 0;
      } catch (e) {
        console.error('[VideoLibrary] favorite toggle failed:', e);
        // 실패 시 되돌림
        el.classList.toggle('active', !nextStatus);
        el.setAttribute('data-next-status', nextStatus ? 1 : 0);
        el.style.color = !nextStatus ? '#eab308' : '#94a3b8';
        if (icon) icon.className = !nextStatus ? 'fa-solid fa-star' : 'fa-regular fa-star';
      }
    });
  });

  container.querySelectorAll('[data-role="video-course-card"]').forEach(el => {
    el.addEventListener('click', (event) => {
      const videoId = parseInt(el.getAttribute('data-video-id'), 10);
      const title = el.getAttribute('data-video-title') || '';
      if (Number.isFinite(videoId)) {
        openBookDetail(event, title, libraryId, videoId, title);
      }
    });
    el.addEventListener('contextmenu', (event) => {
      event.preventDefault();
      event.stopPropagation();
      showVideoContextMenu(event.clientX, event.clientY, el, libraryId);
    });
  });
}

// 영상 세션으로 전환될 때(툴바 토글 클릭 / 딥링크) 호출 - Home은 오디오북과 동일하게
// 공용 대시보드(최근 시청/신규 추가)를 그대로 재사용한다. 개별 강좌 그리드 로드는
// 사이드바에서 라이브러리를 클릭했을 때(selectCategory 경유)로 미룬다.
export async function loadVideoLibraryView() {
  lastLoadedVideos = [];
  lastLoadedLibraryId = null;
  if (typeof window.selectCategory === 'function') {
    window.selectCategory('home');
  }
  if (typeof window.loadLibraries === 'function') {
    await window.loadLibraries();
  }
}

// tab_media_library.js의 selectCategory()가 data-library-type="video"일 때 위임하는 진입점
export async function loadVideoCourseGrid(libraryId) {
  const container = document.getElementById('books-list-container');
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner">강좌 목록을 불러오는 중...</div>';

  try {
    const res = await fetch(`/api/media/videos?library_id=${libraryId}&_=${Date.now()}`, { cache: 'no-store' });
    const data = await res.json();
    if (!data.success) {
      container.innerHTML = `<div class="loading-spinner">강좌 목록을 불러오지 못했습니다: ${escapeHtml(data.error || '')}</div>`;
      return;
    }

    lastLoadedVideos = data.videos || [];
    lastLoadedLibraryId = libraryId;

    // 검색창에 이미 입력된 검색어가 있으면(라이브러리 전환 시에도) 유지 적용
    const query = (document.getElementById('library-search')?.value || '').toLowerCase().trim();
    const visibleVideos = query
      ? lastLoadedVideos.filter(v => (v.title || '').toLowerCase().includes(query))
      : lastLoadedVideos;

    updateVideoTotalCount(visibleVideos);
    renderVideoCourseCards(
      visibleVideos,
      libraryId,
      query ? '검색 결과가 없습니다.' : '이 라이브러리에는 아직 스캔된 강좌가 없습니다. 사이드바에서 우클릭(또는 메뉴)으로 스캔을 실행해 주세요.'
    );
  } catch (e) {
    container.innerHTML = '<div class="loading-spinner">서버 요청 중 오류가 발생했습니다.</div>';
    console.error('[VideoLibrary] course list load failed:', e);
  }
}

// book_list.js::toggleLibrarySort()가 video 세션일 때 위임하는 진입점 - 서버 재조회 없이
// 이미 불러온 강좌 목록을 클라이언트 사이드에서 재정렬해 전용 카드 렌더러(renderVideoCourseCards)로
// 다시 그린다. 여기를 거치지 않고 loadBooksList()로 빠지면 공용 카드 렌더러가 영상을 오디오북으로
// 오인해(total_tracks 유무 기준) 재생시간/분석전 배지 대신 헤드폰 아이콘 배지를 보여주게 된다.
// videos 테이블에는 생성일시 컬럼이 없어(list_videos_by_library 참고), 날짜순 정렬은 auto-increment id를
// 대리 지표로 사용한다 (id가 클수록 최근 스캔된 항목).
export function sortVideoCourses() {
  const sortDir = state.currentSortDirection || 'asc';
  const sorted = [...lastLoadedVideos];

  if (sortDir === 'desc') {
    sorted.sort((a, b) => String(b.title || '').localeCompare(String(a.title || ''), 'ko'));
  } else if (sortDir === 'date_desc') {
    sorted.sort((a, b) => (Number(b.id) || 0) - (Number(a.id) || 0));
  } else if (sortDir === 'date_asc') {
    sorted.sort((a, b) => (Number(a.id) || 0) - (Number(b.id) || 0));
  } else {
    sorted.sort((a, b) => String(a.title || '').localeCompare(String(b.title || ''), 'ko'));
  }

  lastLoadedVideos = sorted;

  const query = (document.getElementById('library-search')?.value || '').toLowerCase().trim();
  const visibleVideos = query
    ? lastLoadedVideos.filter(v => (v.title || '').toLowerCase().includes(query))
    : lastLoadedVideos;

  updateVideoTotalCount(visibleVideos);
  renderVideoCourseCards(
    visibleVideos,
    lastLoadedLibraryId,
    query ? '검색 결과가 없습니다.' : '이 라이브러리에는 아직 스캔된 강좌가 없습니다.'
  );
}
window.sortVideoCourses = sortVideoCourses;

// book_list.js::filterBooks()가 video 세션일 때 위임하는 진입점 - 이미 불러온 강좌 목록을
// 서버 재조회 없이 제목 기준으로 클라이언트 사이드 필터링한다.
export function filterVideoCourses() {
  const searchInput = document.getElementById('library-search');
  const query = (searchInput?.value || '').toLowerCase().trim();

  const searchBtn = document.getElementById('btn-library-search-action');
  if (searchBtn) {
    searchBtn.innerText = query ? (window.i18n?.t('common.reset') || '초기화') : (window.i18n?.t('common.search') || '검색');
  }

  const filtered = query
    ? lastLoadedVideos.filter(v => (v.title || '').toLowerCase().includes(query))
    : lastLoadedVideos;

  updateVideoTotalCount(filtered);
  renderVideoCourseCards(filtered, lastLoadedLibraryId, query ? '검색 결과가 없습니다.' : '이 라이브러리에는 아직 스캔된 강좌가 없습니다.');
}

window.loadVideoLibraryView = loadVideoLibraryView;
window.loadVideoCourseGrid = loadVideoCourseGrid;
window.filterVideoCourses = filterVideoCourses;
