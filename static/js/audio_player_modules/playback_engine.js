// playback_engine.js - WebAudio/MediaSession 전담
import { remoteLog } from '../remote_log.js';

export function createAudioPlaybackEngine() {
  // 모바일(iOS/Android 공통) 감지:
  // createMediaElementSource()로 <audio>를 AudioContext에 연결하면, 화면 잠금 시
  // 대부분의 모바일 브라우저(iOS Safari뿐 아니라 Android Chrome 등도 포함)가 백그라운드
  // 절전/오디오 포커스 정책으로 AudioContext를 강제 suspend시켜 소리가 끊긴다. 게다가
  // 현재 resume 시점은 화면이 "다시 보일 때"(onVisibilityVisible)뿐이라 잠금 중에는
  // 계속 무음 상태다. 이 GainNode 경로는 볼륨을 0~1 범위로만 쓰고(오디오 요소의
  // audioEl.volume이 이미 커버 가능) analyser 등 다른 기능도 없어 실질적 이득이
  // 없으므로, 모바일에서는 아예 WebAudio 라우팅 자체를 쓰지 않고 audioEl.volume만으로
  // 볼륨을 제어한다 (데스크톱은 화면 잠금 개념이 없어 기존 동작 유지).
  const IS_MOBILE = /iPad|iPhone|iPod|Android|Mobile/i.test(navigator.userAgent) && !window.MSStream;
  remoteLog('playback-engine-init', { isMobile: IS_MOBILE, userAgent: navigator.userAgent });

  let audioCtx = null;
  let gainNode = null;
  let audioSourceNode = null;
  let currentVolumeValue = 1.0;

  function setupWebAudioGainNode(audioEl) {
    if (IS_MOBILE) return;
    if (!audioEl) return;

    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;

      if (!audioCtx) {
        audioCtx = new AudioContextClass();
      }

      if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume().catch(() => {});
      }

      if (!audioSourceNode && audioCtx && audioEl) {
        audioSourceNode = audioCtx.createMediaElementSource(audioEl);
        gainNode = audioCtx.createGain();
        audioSourceNode.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        if (gainNode && gainNode.gain) {
          gainNode.gain.value = currentVolumeValue;
        }
      }
    } catch (e) {
      console.warn('[AudioPlayer] Web Audio GainNode setup warning:', e);
    }
  }

  function ensureAudioContextResumed() {
    if (audioCtx && audioCtx.state === 'suspended') {
      remoteLog('audiocontext-resume-attempt', { isMobile: IS_MOBILE });
      audioCtx.resume().catch(e => console.warn('[AudioPlayer] AudioContext resume failed:', e));
    }
  }

  function bindResumeOnPlay(audioEl) {
    if (!audioEl) return;
    audioEl.addEventListener('play', ensureAudioContextResumed);
    audioEl.addEventListener('playing', ensureAudioContextResumed);
  }

  function setVolume(audioEl, value) {
    let volume = parseFloat(value);
    if (isNaN(volume)) volume = 1;
    volume = Math.max(0, Math.min(1, volume));
    currentVolumeValue = volume;

    if (audioEl) {
      try {
        audioEl.volume = volume;
      } catch (e) {}
    }

    setupWebAudioGainNode(audioEl);
    if (gainNode && gainNode.gain) {
      gainNode.gain.value = volume;
    }

    return volume;
  }

  function initMediaSession(meta, track, handlers) {
    if (!('mediaSession' in navigator)) return;

    navigator.mediaSession.metadata = new MediaMetadata({
      title: track ? track.title : meta.series_name,
      artist: meta.author || 'BookOasis',
      album: meta.series_name || 'Audiobook',
      artwork: meta.cover_image ? [{ src: meta.cover_image }] : []
    });
    remoteLog('mediasession-metadata-set', { title: track ? track.title : meta.series_name });

    // OS가 잠금화면 미디어 컨트롤/백그라운드 재생 대상으로 이 세션을 인지했다면, 잠금
    // 중 사용자가 컨트롤을 조작하지 않아도 최소한 OS가 재생 상태를 물어보는 상호작용이
    // 있을 수 있다. 반대로 잠금 내내 이 핸들러들이 단 한 번도 안 찍히면, 애초에 OS가
    // 이 페이지를 "백그라운드 재생 가능" 세션으로 인식조차 못하고 있다는 강한 신호다.
    navigator.mediaSession.setActionHandler('play', () => { remoteLog('mediasession-action', { action: 'play' }); handlers.onPlay(); });
    navigator.mediaSession.setActionHandler('pause', () => { remoteLog('mediasession-action', { action: 'pause' }); handlers.onPause(); });
    navigator.mediaSession.setActionHandler('seekbackward', (details) => { remoteLog('mediasession-action', { action: 'seekbackward' }); handlers.onSeekBackward(details); });
    navigator.mediaSession.setActionHandler('seekforward', (details) => { remoteLog('mediasession-action', { action: 'seekforward' }); handlers.onSeekForward(details); });
    navigator.mediaSession.setActionHandler('previoustrack', () => { remoteLog('mediasession-action', { action: 'previoustrack' }); handlers.onPrevTrack(); });
    navigator.mediaSession.setActionHandler('nexttrack', () => { remoteLog('mediasession-action', { action: 'nexttrack' }); handlers.onNextTrack(); });

    try {
      navigator.mediaSession.setActionHandler('seekto', (details) => { remoteLog('mediasession-action', { action: 'seekto' }); handlers.onSeekTo(details); });
    } catch (e) {}
  }

  return {
    setupWebAudioGainNode,
    ensureAudioContextResumed,
    bindResumeOnPlay,
    setVolume,
    initMediaSession
  };
}
