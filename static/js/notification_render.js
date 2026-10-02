// notification_render.js – 알림센터 항목(services/notification_service.py 형식)을 문구/HTML로 바꾸는 순수 함수들.
// DOM·전역 상태에 의존하지 않아 node 테스트(tests/test_notification_render.mjs)에서 그대로 불러 쓴다.
import { formatRelativeTime } from './utils/time.js';

export function escapeActivityText(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeActivityAttribute(value) {
  return escapeActivityText(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ---- 알림센터 공통 렌더러 (/api/system/status의 notifications[], services/notification_service.py) ----
// 서버가 로그인 사용자 기준으로 이미 걸러서 내려주므로 여기서는 권한을 따지지 않는다.

const NOTIFY_TONE_ICONS = {
  error: 'fa-circle-exclamation',
  running: 'fa-circle-notch fa-spin',
  pending: 'fa-clock',
  new: 'fa-circle-plus',
  done: 'fa-circle-check',
  muted: 'fa-circle-minus',
  notice: 'fa-circle-info',
};
const NOTIFY_SOURCE_ICONS = { tts: 'fa-headphones', system: 'fa-gear', plugin: 'fa-puzzle-piece' };

export function tr(key, vars = {}, fallback = '') {
  if (!key) return fallback;
  const translator = window.i18n;
  if (!translator || typeof translator.t !== 'function') return fallback || key;
  const text = translator.t(key, vars, null);
  return text === key ? fallback : text;
}

// 작업 종류별 키(notify.scan.running.<task_type>)가 없으면 같은 묶음의 .default로 대신한다.
function trWithDefault(key, vars) {
  return tr(key, vars, tr(String(key || '').replace(/\.[^.]+$/, '.default'), vars, ''));
}

// vars 값 중 {time: ISO}는 상대 시각, {key: i18n 키}는 그 문구로 바꾼다.
function resolveNotifyVars(vars) {
  const out = {};
  Object.entries(vars || {}).forEach(([name, value]) => {
    if (value && typeof value === 'object') {
      if (value.time !== undefined) out[name] = formatRelativeTime(value.time);
      else if (value.key) out[name] = trWithDefault(value.key, {});
      else out[name] = '';
    } else if (typeof value === 'number') {
      out[name] = value.toLocaleString();
    } else {
      out[name] = value ?? '';
    }
  });
  return out;
}

export function notificationTitle(item) {
  let title = item?.title || tr(item?.title_key, resolveNotifyVars(item?.title_vars), '');
  if (!item?.title && item?.title_vars?.library) title = `${item.title_vars.library} · ${title}`;
  if (item?.adult) title += tr('notify.tts.adult_suffix', {}, ' (성인)');
  return title;
}

export function notificationDetail(item) {
  const parts = (Array.isArray(item?.detail) ? item.detail : [])
    .map(part => trWithDefault(part?.key, resolveNotifyVars(part?.vars)))
    .filter(Boolean);
  if (item?.raw_detail) parts.push(String(item.raw_detail));
  return parts.join(' · ');
}

function notificationVisualTone(item) {
  return item?.kind === 'running' && item?.progress?.pending ? 'pending' : (item?.tone || 'done');
}

function formatScanActivityElapsed(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return '';
  const elapsedSeconds = Math.max(0, Math.floor(Number(seconds)));
  if (elapsedSeconds < 60) return tr('notify.elapsed.seconds', { n: elapsedSeconds }, `${elapsedSeconds}초`);
  const minutes = Math.floor(elapsedSeconds / 60);
  if (minutes < 60) return tr('notify.elapsed.minutes', { n: minutes }, `${minutes}분`);
  const hours = Math.floor(minutes / 60);
  return tr('notify.elapsed.hours', { h: hours, m: minutes % 60 }, `${hours}시간 ${minutes % 60}분`);
}

function notificationMeta(item) {
  if (item?.kind === 'running') {
    if (item.source === 'tts' && item.progress?.percent !== undefined) return `${item.progress.percent}%`;
    return formatScanActivityElapsed(item.progress?.elapsed_seconds);
  }
  return item?.updated_at ? formatRelativeTime(item.updated_at, { fallback: '' }) : '';
}

export function notificationItemHtml(item) {
  const tone = notificationVisualTone(item);
  const title = notificationTitle(item);
  const detail = notificationDetail(item);
  const label = tr(`notify.label.${tone}`, {}, tone);
  const sourceIcon = NOTIFY_SOURCE_ICONS[item?.source];
  const unread = item?.read === false;
  // 문제 카드는 펼쳐서 시리즈 줄/조치를 볼 수 있다 (static/js/notification_cards.js)
  const multiCards = Array.isArray(item?.target?.cards) ? item.target.cards : null;
  const expandable = item?.kind === 'problem' && (item?.card?.group_key || multiCards);
  const cardData = expandable
    ? (multiCards ? { multi: true, cards: multiCards } : { card: item.card, actions: item.actions || [] })
    : null;
  const expandAttrs = expandable
    ? ` data-expand-key="${escapeActivityAttribute(multiCards ? item.id : item.card.group_key)}" data-card="${escapeActivityAttribute(JSON.stringify(cardData))}"`
    : '';
  const toggle = expandable
    ? `<button type="button" class="notify-card-toggle" data-notify-action="toggle_card" aria-expanded="false" title="${escapeActivityAttribute(tr('problems.action.more', {}, '더 보기'))}"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></button>`
    : '';
  return `
      <div class="scan-activity-item notify-tone-${tone}${unread ? ' is-unread' : ''}${expandable ? ' is-expandable' : ''}" data-notify-id="${escapeActivityAttribute(item?.id)}" data-kind="${escapeActivityAttribute(item?.kind)}"${expandAttrs}>
        <span class="scan-activity-item-icon">
          <i class="fa-solid ${NOTIFY_TONE_ICONS[tone] || NOTIFY_TONE_ICONS.done}" aria-hidden="true"></i>
        </span>
        <div class="scan-activity-item-copy">
          <div class="scan-activity-item-title" title="${escapeActivityAttribute(title)}">${sourceIcon ? `<i class="fa-solid ${sourceIcon} notify-source-icon" aria-hidden="true"></i>` : ''}${escapeActivityText(title)}</div>
          <div class="scan-activity-item-detail" title="${escapeActivityAttribute(detail)}">${escapeActivityText(detail)}</div>
        </div>
        <span class="scan-activity-item-side">
          <span class="notify-label">${unread ? '<span class="notify-unread-dot" aria-hidden="true"></span>' : ''}${escapeActivityText(label)}</span>
          <span class="scan-activity-item-time">${escapeActivityText(notificationMeta(item))}</span>
          ${toggle}
        </span>
      </div>`;
}

// 직전 폴링에서 진행 중이던 track_key가 이번에 최근 완료로 넘어온 항목 (토스트 대상).
export function finishedWhileWatching(items, previousKeys) {
  const runningKeys = new Set(items.filter(i => i.kind === 'running').map(i => i.track_key));
  const finished = previousKeys
    ? items.filter(item => item.kind === 'recent'
      && previousKeys.has(item.track_key)
      && !runningKeys.has(item.track_key))
    : [];
  return { runningKeys, finished };
}


// 아이콘 점과 팝오버 머리말에 쓰는 요약.
export function summarizeNotifications(items) {
  const list = Array.isArray(items) ? items : [];
  const runningCount = list.filter(i => i.kind === 'running').length;
  const actionCount = list.filter(i => i.kind === 'problem' && i.severity === 'action_required').length;
  const unreadCount = list.filter(i => i.read === false).length;
  const recentCount = list.filter(i => i.kind === 'recent').length;
  const text = actionCount ? tr('notify.summary.action', { count: actionCount }, `조치 필요 ${actionCount}건`)
    : runningCount ? tr('notify.summary.running', { count: runningCount }, `진행 중 ${runningCount}건`)
      : unreadCount ? tr('notify.summary.unread', { count: unreadCount }, `새 알림 ${unreadCount}건`)
        : recentCount ? tr('notify.summary.recent', { count: recentCount }, `최근 ${recentCount}건`)
          : tr('notify.summary.idle', {}, '대기 중');
  return { runningCount, actionCount, unreadCount, recentCount, isRunning: runningCount > 0, hasWarning: actionCount > 0, isEmpty: list.length === 0, text };
}

// [지우기] 대상 수: 최근 완료 + 참고(notice) 문제 카드. 진행 중·조치 필요 카드는 남는다
// (services/notification_service.clear_notifications와 같은 규칙). 0이면 버튼을 숨긴다.
export function clearableCount(items) {
  const list = Array.isArray(items) ? items : [];
  return list.filter(i => i.kind === 'recent'
    || (i.kind === 'problem' && i.severity === 'notice' && i.card?.group_key)).length;
}

// ---- 문제 카드 펼침 (카드 → 시리즈 줄 → 도서) ----

// 시리즈 줄 문구: 한 시리즈 전 권이 같은 문제면 "N권 전체", 일부면 "M권 중 N권".
export function problemLineText(line) {
  if (line?.target_type === 'library') return tr('problems.line.library', {}, '카테고리 전체');
  // 플러그인 문제 중 도서와 무관한 것(토큰 만료 등)
  if (line?.target_type === 'system') return tr('problems.line.system', {}, '공통 (특정 도서와 무관)');
  const name = line?.series_name || tr('problems.line.no_series', {}, '(시리즈 없음)');
  const count = Number(line?.open_count || 0);
  const total = Number(line?.series_total || 0);
  if (total && count >= total) return tr('problems.line.series_all', { name, count: count.toLocaleString() }, `${name} — ${count}권 전체`);
  if (total) return tr('problems.line.series_some', { name, count: count.toLocaleString(), total: total.toLocaleString() }, `${name} — ${total}권 중 ${count}권`);
  return tr('problems.line.series_count', { name, count: count.toLocaleString() }, `${name} — ${count}권`);
}

// 도서 한 권을 다시 보는 방법: 파일이 사라진 문제는 폴더 재스캔(scan-path), 파일 오류는 그 권만 재스캔.
export function itemRescanAction(item) {
  if (!item) return null;
  if (['file_missing', 'mass_missing'].includes(item.code)) return item.scan_path != null ? 'rescan_path' : null;
  if (item.book_id) return 'rescan_book';
  return item.scan_path != null ? 'rescan_path' : null;
}

export function cardActionButtons(card, actions) {
  const list = Array.isArray(actions) ? actions : [];
  const buttons = [];
  if (list.includes('rescan') && card?.library_id != null) buttons.push('rescan_all');
  if (list.includes('confirm_trash')) buttons.push('confirm_trash');
  if (list.includes('resolve') && card?.group_key) buttons.push('resolve');
  // 플러그인 카드: 플러그인이 정한 조치 하나 (기존 액션 RPC로 실행)
  if (list.includes('plugin_action') && card?.plugin?.action_id) buttons.push('plugin_action');
  if (card?.group_key) buttons.push('mute');
  return buttons;
}
