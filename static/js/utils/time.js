// time.js – 서버가 내려주는 타임스탬프 문자열을 다루는 공용 유틸리티.
// "N분 전" 식 상대시간 표시가 여러 파일에 제각각 구현되어 있던 것을 하나로 통합했다.

// 서버는 타임존 정보 없이 "YYYY-MM-DD HH:mm:ss" 형태의 로컬 시각을 내려준다.
// new Date()에 그대로 넘기면 브라우저/엔진에 따라 UTC로 해석되어 KST 기준 9시간 오차가 발생할 수 있어,
// 연-월-일-시-분-초 컴포넌트를 직접 읽어 항상 "로컬 시각"으로 고정 생성한다.
const NAIVE_DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/;

export function parseServerDateTime(value) {
  const raw = String(value ?? '').trim();
  if (!raw || raw === '-') return null;

  const naiveMatch = raw.match(NAIVE_DATETIME_RE);
  if (naiveMatch) {
    const [, y, mo, d, h, mi, s] = naiveMatch.map(Number);
    const local = new Date(y, mo - 1, d, h, mi, s);
    return Number.isNaN(local.getTime()) ? null : local;
  }

  // Z 또는 +09:00 같은 타임존 오프셋이 명시된 표준 ISO 문자열은 그대로 위임
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

// "N분 전" / "어제" / "N달 전" 식의 상대시간 문자열. 분 단위로 반올림하고, 하루가 지나면 "어제",
// 30일 이상이면 "N달 전"으로 표시한다 (scan_routes.py의 예전 백엔드 로직과 동일한 등급 체계).
export function formatRelativeTime(value, { fallback = '-' } = {}) {
  const target = value instanceof Date ? value : parseServerDateTime(value);
  if (!target) return fallback;

  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - target.getTime()) / 60000));
  if (elapsedMinutes < 1) {
    return i18n.t('settings.scan_just_now') || '방금 전';
  }
  if (elapsedMinutes < 60) {
    return i18n.t('settings.scan_minutes_ago', { count: elapsedMinutes });
  }
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) {
    return i18n.t('settings.scan_hours_ago', { count: elapsedHours });
  }
  const elapsedDays = Math.floor(elapsedHours / 24);
  if (elapsedDays === 1) {
    return i18n.t('settings.scan_yesterday') || '어제';
  }
  if (elapsedDays < 30) {
    return i18n.t('settings.scan_days_ago', { count: elapsedDays });
  }
  return i18n.t('settings.scan_months_ago', { count: Math.floor(elapsedDays / 30) });
}

// 초 단위 재생시간을 "h:mm:ss" (1시간 이상) 또는 "m:ss" 클록 포맷으로 표시한다.
// emptyLabel을 지정하면 0초 이하일 때 그 문자열을 대신 반환한다 (예: 아직 길이를 분석 못한 미디어의 '분석전').
export function formatClockDuration(totalSeconds, { emptyLabel = null } = {}) {
  const sec = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  if (sec <= 0 && emptyLabel !== null) return emptyLabel;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// 초 단위 재생시간을 "H시간 M분" 서술형으로 표시한다 (영상 강좌 목록 카드 등 클록 포맷이 아닌 곳에서 사용).
export function formatDurationLong(totalSeconds, { emptyLabel = '분석전' } = {}) {
  const sec = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  if (sec <= 0) return emptyLabel;
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  if (hours > 0) return `${hours}시간 ${minutes}분`;
  return `${minutes}분`;
}
