// key_defaults.js – 뷰어 단축키 기본값 (설정 > 단축키 탭과 뷰어 입력 처리가 함께 쓴다)
// 예전엔 keys_tab.html 인라인 스크립트와 input_controller.js에 따로 적혀 있어, 설정 화면이 보여주는
// 기본값(ChannelDown/AudioVolumeDown 누락)과 실제 동작이 달랐다.
export const DEFAULT_VIEWER_KEYS = Object.freeze({
  next: 'ArrowRight, Space, PageDown, VolumeDown, ChannelDown, AudioVolumeDown',
  prev: 'ArrowLeft, PageUp, VolumeUp, ChannelUp, AudioVolumeUp',
  close: 'Escape',
  dashboard: 'Home',
});

/** 저장된 커스텀 키(없으면 기본값)를 소문자 키 이름 배열로 */
export function getViewerKeyList(target) {
  let saved = null;
  try { saved = localStorage.getItem(`custom_key_${target}`); } catch (_) { /* 저장소 차단 */ }
  return String(saved || DEFAULT_VIEWER_KEYS[target] || '')
    .split(',')
    .map((k) => k.trim().toLowerCase())
    .filter(Boolean);
}
