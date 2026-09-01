/* library_type_toggle.js – 일반도서/성인도서/오디오북 미디어 타입 토글 및 권한 관리 모듈 */
import { state } from './state.js';
import { loadLibraries } from './category.js';

export function canAccessAdultLibrary() {
  const user = state.currentUser || window.currentUser || {};
  const role = String(user.role || '').toLowerCase();
  if (role === 'admin') return true;

  const raw = user.has_adult_access;
  return raw === true || raw === 1 || String(raw) === '1';
}

export function canAccessAudiobookLibrary() {
  const user = state.currentUser || window.currentUser || {};
  const role = String(user.role || '').toLowerCase();
  if (role === 'admin') return true;

  const raw = user.has_audiobook_access;
  return raw === true || raw === 1 || String(raw) === '1';
}

export function canAccessVideoLibrary() {
  const user = state.currentUser || window.currentUser || {};
  const role = String(user.role || '').toLowerCase();
  if (role === 'admin') return true;

  const raw = user.has_video_access;
  return raw === true || raw === 1 || String(raw) === '1';
}

export function canAccessLibraryType(type) {
  if (type === 'adult') return canAccessAdultLibrary();
  if (type === 'audiobook') return canAccessAudiobookLibrary();
  if (type === 'video') return canAccessVideoLibrary();
  return true;
}

export function applyLibraryTypeToggleVisibility() {
  const toggleGroup = document.getElementById('library-type-toggle-group');
  if (!toggleGroup) return;

  const allowAdult = canAccessAdultLibrary();
  const allowAudiobook = canAccessAudiobookLibrary();
  const allowVideo = canAccessVideoLibrary();
  const btnGeneral = document.getElementById('btn-lib-general');
  const btnAdult = document.getElementById('btn-lib-adult');
  const btnAudiobook = document.getElementById('btn-lib-audiobook');
  const btnVideo = document.getElementById('btn-lib-video');

  if (btnGeneral) btnGeneral.style.display = 'inline-flex';
  if (btnAdult) btnAdult.style.display = allowAdult ? 'inline-flex' : 'none';
  if (btnAudiobook) btnAudiobook.style.display = allowAudiobook ? 'inline-flex' : 'none';
  if (btnVideo) btnVideo.style.display = allowVideo ? 'inline-flex' : 'none';

  const visibleCount = [btnGeneral, btnAdult, btnAudiobook, btnVideo].filter(btn => btn && btn.style.display !== 'none').length;
  toggleGroup.style.display = visibleCount > 1 ? 'inline-flex' : 'none';

  if (!canAccessLibraryType(state.currentLibraryType)) {
    state.currentLibraryType = 'general';
  }

  applyLibraryTypeButtonState(state.currentLibraryType || 'general');
}

export function applyLibraryTypeButtonState(type) {
  const safeType = (type === 'adult' || type === 'audiobook' || type === 'video') ? type : 'general';
  state.currentLibraryType = safeType;
  window.currentLibraryType = safeType;
  document.documentElement.setAttribute('data-library-type', safeType);

  // 초기 로드 1회 + 세션 전환마다 항상 거치는 유일한 지점이라, 플러그인이 세션 변경을
  // 실시간으로 구독할 수 있도록 여기서 이벤트를 발행한다 (window.BookOasisPlugin.getSession() 참고)
  window.dispatchEvent(new CustomEvent('bookoasis:session-change', { detail: { libraryType: safeType } }));

  document.querySelectorAll('#library-type-toggle-group .btn-toggle').forEach(btn => btn.classList.remove('active'));
  if (safeType === 'general') {
    document.getElementById('btn-lib-general')?.classList.add('active');
  } else if (safeType === 'adult') {
    document.getElementById('btn-lib-adult')?.classList.add('active');
  } else if (safeType === 'audiobook') {
    document.getElementById('btn-lib-audiobook')?.classList.add('active');
  } else if (safeType === 'video') {
    document.getElementById('btn-lib-video')?.classList.add('active');
  }
}

export async function switchLibraryType(type) {
  if (!canAccessLibraryType(type)) {
    if (type === 'adult') {
      alert('성인 도서관 접근 권한이 없습니다.');
    } else if (type === 'audiobook') {
      alert('오디오북 도서관 접근 권한이 없습니다.');
    } else if (type === 'video') {
      alert('영상 강좌 접근 권한이 없습니다.');
    }
    return;
  }

  applyLibraryTypeButtonState(type);
  localStorage.setItem('last_selected_library_type', type);

  // 영상 강좌는 일반 도서 그리드/대시보드 파이프라인을 타지 않고 전용 화면을 로드한다
  if (type === 'video') {
    if (typeof window.loadVideoLibraryView === 'function') {
      await window.loadVideoLibraryView();
    }
    return;
  }

  // 전역 뷰 상태 초기화 및 라이브러리 목록 재로드
  if (typeof window.selectCategory === 'function') {
    window.selectCategory('home');
  }
  if (typeof window.loadLibraries === 'function') {
    await window.loadLibraries();
  } else {
    await loadLibraries();
  }
}

window.canAccessAdultLibrary = canAccessAdultLibrary;
window.canAccessAudiobookLibrary = canAccessAudiobookLibrary;
window.canAccessVideoLibrary = canAccessVideoLibrary;
window.canAccessLibraryType = canAccessLibraryType;
window.applyLibraryTypeToggleVisibility = applyLibraryTypeToggleVisibility;
window.applyLibraryTypeButtonState = applyLibraryTypeButtonState;
window.switchLibraryType = switchLibraryType;
