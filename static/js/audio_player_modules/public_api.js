// public_api.js - 오디오 플레이어 글로벌 API 노출 도우미

export function registerAudioPlayerPublicApi(apiMap) {
  if (typeof window === 'undefined' || !apiMap) return;
  Object.keys(apiMap).forEach((key) => {
    window[key] = apiMap[key];
  });
}
