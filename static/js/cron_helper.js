// cron_helper.js – 스케줄 설정 모달의 Cron 표현식 ↔ 친화적 UI 헬퍼 (scheduler.js에서 분리)

function pad2(value) {
  return String(value).padStart(2, '0');
}

function getHelperElements() {
  return {
    mode: document.getElementById('scan-settings-helper-mode'),
    time: document.getElementById('scan-settings-helper-time'),
    weekdayWrap: document.getElementById('scan-settings-helper-weekday-wrap'),
    weekday: document.getElementById('scan-settings-helper-weekday'),
    monthdayWrap: document.getElementById('scan-settings-helper-monthday-wrap'),
    monthday: document.getElementById('scan-settings-helper-monthday'),
    summary: document.getElementById('scan-settings-helper-summary'),
    cronInput: document.getElementById('scan-settings-cron')
  };
}

function safeTimeToParts(timeVal) {
  const raw = String(timeVal || '03:00');
  const parts = raw.split(':');
  const hour = Math.min(23, Math.max(0, parseInt(parts[0], 10) || 3));
  const minute = Math.min(59, Math.max(0, parseInt(parts[1], 10) || 0));
  return { hour, minute };
}

function buildCronFromHelper(mode, timeVal, weekdayVal, monthdayVal) {
  const { hour, minute } = safeTimeToParts(timeVal);
  const mm = String(minute);
  const hh = String(hour);

  if (mode === 'daily') {
    return { cron: `${mm} ${hh} * * *`, summary: `매일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekdays') {
    return { cron: `${mm} ${hh} * * 1-5`, summary: `평일(월~금) ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekend') {
    return { cron: `${mm} ${hh} * * 0,6`, summary: `주말(일/토) ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'weekly_once') {
    const day = Math.min(6, Math.max(0, parseInt(weekdayVal, 10) || 0));
    const dayLabel = ['일', '월', '화', '수', '목', '금', '토'][day] || '일';
    return { cron: `${mm} ${hh} * * ${day}`, summary: `매주 ${dayLabel}요일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  if (mode === 'monthly') {
    const day = Math.min(31, Math.max(1, parseInt(monthdayVal, 10) || 1));
    return { cron: `${mm} ${hh} ${day} * *`, summary: `매월 ${day}일 ${pad2(hour)}:${pad2(minute)} 실행` };
  }
  return {
    cron: '',
    summary: '직접 입력 모드입니다. 아래 Cron 입력칸을 수정하세요.'
  };
}

function parseHelperStateFromCron(cronVal) {
  const text = String(cronVal || '').trim();
  if (!text) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const fields = text.split(/\s+/);
  if (fields.length !== 5) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const [minF, hourF, domF, monthF, dowF] = fields;
  if (!/^\d+$/.test(minF) || !/^\d+$/.test(hourF)) {
    return { mode: 'custom', hour: 3, minute: 0, weekday: '0', monthday: '1' };
  }

  const minute = Math.min(59, Math.max(0, parseInt(minF, 10)));
  const hour = Math.min(23, Math.max(0, parseInt(hourF, 10)));

  if (domF === '*' && monthF === '*' && dowF === '*') {
    return { mode: 'daily', hour, minute, weekday: '0', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && dowF === '1-5') {
    return { mode: 'weekdays', hour, minute, weekday: '1', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && (dowF === '0,6' || dowF === '6,0')) {
    return { mode: 'weekend', hour, minute, weekday: '0', monthday: '1' };
  }
  if (domF === '*' && monthF === '*' && /^[0-6]$/.test(dowF)) {
    return { mode: 'weekly_once', hour, minute, weekday: dowF, monthday: '1' };
  }
  if (/^\d+$/.test(domF) && monthF === '*' && dowF === '*') {
    const day = Math.min(31, Math.max(1, parseInt(domF, 10)));
    return { mode: 'monthly', hour, minute, weekday: '0', monthday: String(day) };
  }

  return { mode: 'custom', hour, minute, weekday: '0', monthday: '1' };
}

function refreshCronHelperVisibility(mode) {
  const els = getHelperElements();
  if (!els.mode) return;

  if (els.weekdayWrap) {
    els.weekdayWrap.style.display = mode === 'weekly_once' ? 'block' : 'none';
  }
  if (els.monthdayWrap) {
    els.monthdayWrap.style.display = mode === 'monthly' ? 'block' : 'none';
  }
}

function refreshCronHelperSummary() {
  const els = getHelperElements();
  if (!els.mode || !els.summary) return;

  const mode = els.mode.value || 'custom';
  const result = buildCronFromHelper(
    mode,
    els.time ? els.time.value : '03:00',
    els.weekday ? els.weekday.value : '0',
    els.monthday ? els.monthday.value : '1'
  );

  if (mode === 'custom') {
    const currentCron = els.cronInput ? String(els.cronInput.value || '').trim() : '';
    els.summary.textContent = currentCron
      ? `직접 입력 Cron: ${currentCron}`
      : '직접 입력 모드입니다. 아래 Cron 입력칸을 수정하세요.';
    return;
  }

  els.summary.textContent = `${result.summary} | Cron: ${result.cron}`;
}

export function hydrateCronHelperFromCron(cronVal) {
  const els = getHelperElements();
  if (!els.mode || !els.time || !els.weekday || !els.monthday) return;

  const parsed = parseHelperStateFromCron(cronVal);
  els.mode.value = parsed.mode;
  els.time.value = `${pad2(parsed.hour)}:${pad2(parsed.minute)}`;
  els.weekday.value = parsed.weekday;
  els.monthday.value = parsed.monthday;

  refreshCronHelperVisibility(parsed.mode);
  refreshCronHelperSummary();
}

export function onCronHelperModeChange() {
  const els = getHelperElements();
  const mode = els.mode ? els.mode.value : 'custom';
  refreshCronHelperVisibility(mode);
  refreshCronHelperSummary();
}
window.onCronHelperModeChange = onCronHelperModeChange;

export function updateCronHelperSummary() {
  refreshCronHelperSummary();
}
window.updateCronHelperSummary = updateCronHelperSummary;

export function applyCronHelperToInput() {
  const els = getHelperElements();
  if (!els.mode || !els.cronInput) return;

  const mode = els.mode.value || 'custom';
  if (mode === 'custom') {
    refreshCronHelperSummary();
    return;
  }

  const result = buildCronFromHelper(
    mode,
    els.time ? els.time.value : '03:00',
    els.weekday ? els.weekday.value : '0',
    els.monthday ? els.monthday.value : '1'
  );
  els.cronInput.value = result.cron;
  refreshCronHelperSummary();
}
window.applyCronHelperToInput = applyCronHelperToInput;
