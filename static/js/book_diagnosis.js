// book_diagnosis.js – 도서 [진단] 모달 (관리자). 도서 메뉴와 알림센터 문제 카드의 도서 줄에서 연다.
// 결과 렌더는 diagnosis_render.js(순수 함수), 서버는 GET /api/problems/diagnose.
import { diagnosisHtml } from './diagnosis_render.js';
import { escapeActivityText, tr } from './notification_render.js';
import { refreshSystemStatus } from './scan_activity_status.js';

let current = null; // { dbType, bookId }

function ensureModal() {
  let modal = document.getElementById('diagnose-modal');
  if (modal) return modal;
  modal = document.createElement('div');
  modal.id = 'diagnose-modal';
  modal.className = 'diagnose-modal';
  modal.hidden = true;
  modal.innerHTML = `
    <div class="diagnose-dialog" role="dialog" aria-modal="true" aria-labelledby="diagnose-modal-title">
      <header class="diagnose-header">
        <strong id="diagnose-modal-title"></strong>
        <button type="button" class="diagnose-close" data-diagnose-action="close" aria-label="close"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
      </header>
      <div class="diagnose-body" data-role="diagnose-body"></div>
      <footer class="diagnose-footer">
        <button type="button" class="notify-card-btn" data-diagnose-action="rerun"></button>
      </footer>
    </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', event => {
    event.stopPropagation();
    if (event.target === modal) { closeBookDiagnosis(); return; }
    const btn = event.target.closest('[data-diagnose-action]');
    if (btn) runAction(btn);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !modal.hidden) closeBookDiagnosis();
  });
  return modal;
}

function setBody(html) {
  const body = document.querySelector('#diagnose-modal [data-role="diagnose-body"]');
  if (body) body.innerHTML = html;
}

async function load() {
  if (!current) return;
  setBody(`<div class="notify-card-note">${escapeActivityText(tr('diagnose.running', {}, '진단 중... (원격 드라이브는 몇 초 걸릴 수 있습니다)'))}</div>`);
  try {
    const res = await fetch(`/api/problems/diagnose?type=${encodeURIComponent(current.dbType)}&book_id=${encodeURIComponent(current.bookId)}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.success) throw new Error(data.error || `HTTP ${res.status}`);
    setBody(diagnosisHtml(data));
  } catch (err) {
    setBody(`<div class="notify-card-note is-error">${escapeActivityText(tr('problems.action.failed', { error: err.message }, `처리하지 못했습니다: ${err.message}`))}</div>`);
  }
}

function toast(message, type = 'success') {
  if (typeof window.showToast === 'function') window.showToast(escapeActivityText(message), type);
}

async function runAction(btn) {
  const action = btn.getAttribute('data-diagnose-action');
  if (action === 'close') { closeBookDiagnosis(); return; }
  if (action === 'rerun') { load(); return; }
  const d = btn.dataset;
  btn.disabled = true;
  try {
    let res;
    if (action === 'rescan_path') {
      const fd = new FormData();
      fd.append('type', current.dbType);
      fd.append('path', d.scanPath || '');
      res = await fetch(`/api/media/libraries/${encodeURIComponent(d.libraryId)}/scan-path`, { method: 'POST', body: fd });
    } else if (action === 'rescan_book') {
      res = await fetch('/api/media/books/scan-batch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: current.dbType, book_ids: [Number(d.bookId)], scope: 'book' }),
      });
    } else {
      return;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) throw new Error(data.error || `HTTP ${res.status}`);
    toast(action === 'rescan_book' ? tr('problems.action.queued', {}, '재스캔을 등록했습니다.') : tr('problems.action.done', {}, '처리했습니다.'));
    if (action === 'rescan_path') load(); // 폴더 재스캔은 동기 실행 - 끝난 상태로 다시 진단
    refreshSystemStatus();
  } catch (err) {
    toast(tr('problems.action.failed', { error: err.message }, `처리하지 못했습니다: ${err.message}`), 'error');
  } finally {
    btn.disabled = false;
  }
}

export function openBookDiagnosis(dbType, bookId, title = '') {
  if (!bookId) return;
  const modal = ensureModal();
  current = { dbType: dbType || 'general', bookId };
  modal.querySelector('#diagnose-modal-title').textContent = title
    ? `${tr('diagnose.title', {}, '진단')} · ${title}` : tr('diagnose.title', {}, '진단');
  modal.querySelector('[data-diagnose-action="rerun"]').textContent = tr('diagnose.rerun', {}, '다시 진단');
  modal.hidden = false;
  load();
}

export function closeBookDiagnosis() {
  const modal = document.getElementById('diagnose-modal');
  if (modal) modal.hidden = true;
  current = null;
}

window.openBookDiagnosis = openBookDiagnosis;
