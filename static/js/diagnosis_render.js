// diagnosis_render.js – 도서 [진단] 결과(services/book_diagnosis_service.py)를 HTML로 바꾸는 순수 함수.
// DOM에 의존하지 않아 node 테스트(tests/test_notification_render.mjs)에서 그대로 불러 쓴다.
// 모달 열기/조치 실행은 static/js/book_diagnosis.js.
import { escapeActivityText, tr } from './notification_render.js';

const CHECK_ICONS = {
  ok: 'fa-circle-check',
  fail: 'fa-circle-xmark',
  warn: 'fa-triangle-exclamation',
  skip: 'fa-circle-minus',
};

const CHECK_FALLBACK = { ok: '정상', fail: '문제 있음', warn: '확인 필요', skip: '생략' };

function attr(value) {
  return escapeActivityText(value).replace(/"/g, '&quot;');
}

function vars(raw) {
  const out = {};
  Object.entries(raw || {}).forEach(([k, v]) => { out[k] = typeof v === 'number' ? v.toLocaleString() : (v ?? ''); });
  return out;
}

export function diagnosisCheckText(check) {
  return tr(check?.key, vars(check?.vars), CHECK_FALLBACK[check?.status] || '');
}

export function diagnosisActionLabel(action) {
  if (action?.id === 'rescan_path') return tr('diagnose.action.rescan_folder', {}, '폴더 재스캔');
  if (action?.id === 'rescan_book') return tr('diagnose.action.rescan_book', {}, '이 책 재스캔');
  return action?.id || '';
}

// 결론 톤: 실패 항목이 있으면 error, 경고만 있으면 notice, 아니면 done
export function diagnosisTone(result) {
  const statuses = (result?.checks || []).map(c => c.status);
  if (statuses.includes('fail')) return 'error';
  if (statuses.includes('warn') || (result?.problems || []).length) return 'notice';
  return 'done';
}

export function diagnosisHtml(result) {
  const book = result?.book;
  const head = book
    ? `<div class="diagnose-book">
         <div class="diagnose-book-title">${escapeActivityText(book.title || `#${book.id}`)}</div>
         <div class="diagnose-book-path" title="${attr(book.file_path)}">${escapeActivityText([book.library, book.file_path].filter(Boolean).join(' · '))}</div>
       </div>`
    : '';
  const checks = (result?.checks || []).map(check => `
      <li class="diagnose-check is-${attr(check.status)}">
        <i class="fa-solid ${CHECK_ICONS[check.status] || CHECK_ICONS.skip}" aria-hidden="true"></i>
        <span>${escapeActivityText(diagnosisCheckText(check))}</span>
      </li>`).join('');
  const conclusion = result?.conclusion
    ? `<div class="diagnose-conclusion notify-tone-${diagnosisTone(result)}">→ ${escapeActivityText(tr(result.conclusion.key, vars(result.conclusion.vars), ''))}</div>`
    : '';
  const actions = (result?.actions || []).map(action => `
      <button type="button" class="notify-card-btn" data-diagnose-action="${attr(action.id)}"
        data-library-id="${attr(action.library_id ?? '')}" data-scan-path="${attr(action.scan_path ?? '')}"
        data-book-id="${attr(action.book_id ?? '')}">${escapeActivityText(diagnosisActionLabel(action))}</button>`).join('');
  const problems = (result?.problems || []).length
    ? `<div class="diagnose-problems">
         <div class="diagnose-subtitle">${escapeActivityText(tr('diagnose.open_problems', {}, '열린 문제 기록'))}</div>
         <ul>${result.problems.map(p => `<li>${escapeActivityText(tr(p.title_key, {}, p.code))}${p.occurrence_count > 1 ? ` ×${p.occurrence_count}` : ''}${p.message ? ` <span class="diagnose-problem-msg">${escapeActivityText(p.message)}</span>` : ''}</li>`).join('')}</ul>
       </div>`
    : '';
  return `${head}<ul class="diagnose-checks">${checks}</ul>${conclusion}${actions ? `<div class="diagnose-actions">${actions}</div>` : ''}${problems}`;
}
