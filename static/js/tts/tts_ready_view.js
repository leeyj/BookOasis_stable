// tts_ready_view.js – 드로어 "음성 준비됨": 서버 미리 만들기로 음성이 저장된 책 목록 (services/tts_pregen_service.py)
// 음성은 서버 공용이라 누가 만들었든 모든 책을 보여준다. 카드는 일반 목록과 같은 createBookCard를 쓰고,
// 표지 오른쪽 아래 버튼을 "듣기"로 바꾼 뒤 아래에 음성 설정·용량 한 줄과 (지울 권한이 있으면) 삭제 버튼을 붙인다.
import { state } from '../state.js';
import { createBookCard } from '../ui.js';
import { openBookDetail } from '../modal.js';
import { showToast } from '../view_manager.js';

const tr = (key, vars, fallback) => {
  if (window.i18n && typeof window.i18n.t === 'function') return window.i18n.t(`tts_ready.${key}`, vars || {}, fallback);
  return fallback;
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function formatBytes(bytes) {
  const mb = Number(bytes || 0) / (1024 * 1024);
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)}GB` : `${Math.max(1, Math.round(mb))}MB`;
}

function formatHours(sec) {
  const hours = Number(sec || 0) / 3600;
  if (hours >= 1) return tr('hours', { n: hours >= 10 ? Math.round(hours) : hours.toFixed(1) }, `${hours.toFixed(1)}시간`);
  return tr('minutes', { n: Math.max(1, Math.round(hours * 60)) }, `${Math.max(1, Math.round(hours * 60))}분`);
}

function metaText(tts) {
  const steps = Number(tts.steps) === 8 ? tr('steps_best', null, '좋음') : tr('steps_normal', null, '보통');
  const quality = tts.quality === 'compact' ? tr('quality_compact', null, '절약') : tr('quality_standard', null, '표준');
  return `${tts.voice} · ${steps} · ${Number(tts.speed)}× · ${quality} · ${formatHours(tts.duration_sec)} · ${formatBytes(tts.bytes)}`;
}

async function deleteAudio(item, card) {
  const title = item.title || '';
  if (!window.confirm(tr('delete_confirm', { title, size: formatBytes(item.tts.bytes) }, `"${title}"의 미리 만든 음성(${formatBytes(item.tts.bytes)})을 지울까요?`))) return;
  try {
    const res = await fetch(`/api/media/tts/audio/books/${item.tts.id}?db_type=${encodeURIComponent(state.currentLibraryType)}`, {
      method: 'DELETE', credentials: 'same-origin',
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 409) throw new Error(tr('delete_busy', null, '지금 만드는 중인 음성입니다. 먼저 미리 만들기를 취소하세요.'));
    if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
    card.remove();
    showToast(tr('deleted', null, '미리 만든 음성을 지웠습니다.'), 'success');
    const container = document.getElementById('books-list-container');
    if (container && !container.querySelector('.book-card')) renderEmpty(container);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function renderEmpty(container) {
  container.innerHTML = `<div class="loading-spinner">${escapeHtml(tr('empty', null, '아직 미리 만든 음성이 없습니다. 도서 메뉴의 "음성 미리 만들기"로 만들 수 있습니다.'))}</div>`;
}

function buildCard(item) {
  // 다 읽은 책도 "듣기" 버튼이 보이도록 진행률은 넘기지 않는다 (이 화면은 듣기용)
  const cardItem = { ...item, pages_read: 0, is_completed: 0 };
  const displayTitle = item.series_alias || item.series_name || item.title;
  const card = createBookCard(cardItem, {
    actionTitle: tr('listen', null, '듣기'),
    markUnreadScope: 'book',
    onPrimaryClick: (e) => openBookDetail(e, item.series_name || item.title, item.library_id, item.id, displayTitle),
    onActionClick: (e) => {
      e?.stopPropagation?.();
      window.openListen?.(item.id, state.currentLibraryType);
    },
  });
  const actionIcon = card.querySelector('.btn-resume-series i');
  if (actionIcon) actionIcon.className = 'fa-solid fa-headphones';

  const info = card.querySelector('.book-card-info');
  if (info) {
    const meta = document.createElement('p');
    meta.className = 'book-card-sub-progress tts-ready-meta';
    meta.style.cssText = 'display:flex; align-items:center; gap:0.35rem; flex-wrap:wrap;';
    meta.innerHTML = `<span>${escapeHtml(metaText(item.tts))}</span>`;
    if (item.tts.can_delete) {
      const del = document.createElement('button');
      del.type = 'button';
      del.title = tr('delete', null, '음성 지우기');
      del.setAttribute('aria-label', del.title);
      del.style.cssText = 'margin-left:auto; background:none; border:none; color:var(--app-text-muted); cursor:pointer; padding:0.2rem 0.3rem;';
      del.innerHTML = '<i class="fa-solid fa-trash-can" aria-hidden="true"></i>';
      del.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        deleteAudio(item, card);
      });
      meta.appendChild(del);
    }
    info.appendChild(meta);
  }
  return card;
}

export async function renderTtsReadyView() {
  const container = document.getElementById('books-list-container');
  if (!container) return;
  state.hasMore = false;
  state.hasPrevious = false;
  ['infinite-scroll-spinner', 'infinite-scroll-spinner-top'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  container.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> ${escapeHtml(tr('loading', null, '불러오는 중...'))}</div>`;
  const requestedType = state.currentLibraryType;
  try {
    const res = await fetch(`/api/media/tts/audio/books?type=${encodeURIComponent(requestedType)}&_ts=${Date.now()}`, { credentials: 'same-origin' });
    const data = await res.json();
    // 기다리는 사이 다른 화면으로 옮겼으면 그리지 않는다
    if (state.currentLibraryId !== 'tts_ready' || state.currentLibraryType !== requestedType) return;
    if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
    const books = data.books || [];
    const countBadge = document.getElementById('library-total-count');
    if (countBadge) countBadge.textContent = books.length ? `(${books.length})` : '';
    if (!books.length) {
      renderEmpty(container);
      return;
    }
    container.innerHTML = '';
    const fragment = document.createDocumentFragment();
    books.forEach((item) => fragment.appendChild(buildCard(item)));
    container.appendChild(fragment);
  } catch (e) {
    container.innerHTML = `<div class="loading-spinner">${escapeHtml(tr('load_failed', { error: e.message }, `목록을 불러오지 못했습니다: ${e.message}`))}</div>`;
  }
}
