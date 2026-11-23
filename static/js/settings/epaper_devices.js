// settings/epaper_devices.js – 내 설정 > e-paper 리더: "웹 받기 기기"·"피드 기기" 선택.
// 목록·현재 값은 GET /api/media/settings/user 응답의 epaper(모델 표는 services/epaper/devices.py)에서 온다.
// 저장값은 모델 id(빈 문자열 = 없음). 표에 없는 id가 저장돼 있으면 "찾을 수 없음" 안내를 보인다.

const KINDS = [
  { kind: 'web', key: 'EPAPER_WEB_DEVICE', selectId: 'my-setting-epaper-web-device', missingId: 'my-setting-epaper-web-missing' },
  { kind: 'feed', key: 'EPAPER_FEED_DEVICE', selectId: 'my-setting-epaper-feed-device', missingId: 'my-setting-epaper-feed-missing' },
];

function modelLabel(model) {
  const lang = String(window.i18n?.currentLang || 'ko');
  const name = lang === 'ko' ? model.name : (model.name_en || model.name);
  return model.verified ? name : `${name} ${window.i18n?.t?.('settings.epaper_unverified_suffix') || '(실기기 확인 안 됨)'}`;
}

export function renderEpaperDeviceSettings(info) {
  if (!info || !info.models) return;
  KINDS.forEach(({ kind, selectId, missingId }) => {
    const select = document.getElementById(selectId);
    if (!select) return;
    const current = info[kind] || {};
    select.textContent = '';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = window.i18n?.t?.(kind === 'feed' ? 'settings.epaper_feed_none' : 'settings.epaper_web_none')
      || (kind === 'feed' ? '없음 (기본: reTerminal 프로필 v1)' : '없음 (메뉴 숨김)');
    select.appendChild(none);
    (info.models[kind] || []).forEach((model) => {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = modelLabel(model);
      select.appendChild(option);
    });
    select.value = current.missing ? '' : (current.model_id || '');
    const missing = document.getElementById(missingId);
    if (missing) missing.hidden = !current.missing;
  });
}

// 저장할 [key, value] 목록. 폼에 칸이 없으면(옛 템플릿 캐시) 빈 목록 - 저장된 값을 지우지 않는다.
export function collectEpaperDeviceSettings() {
  return KINDS
    .map(({ key, selectId }) => {
      const select = document.getElementById(selectId);
      return select && select.options.length ? [key, select.value || ''] : null;
    })
    .filter(Boolean);
}
