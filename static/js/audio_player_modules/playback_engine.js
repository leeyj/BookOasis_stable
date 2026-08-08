// playback_engine.js - WebAudio/MediaSession 전담

export function createAudioPlaybackEngine() {
  // iOS Safari 감지:
  // iOS는 createMediaElementSource()로 AudioContext에 연결하면
  // 화면 잠금 시 AudioContext가 강제 suspend되어 소리가 완전히 끊김.
  const IS_IOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

  let audioCtx = null;
  let gainNode = null;
  let audioSourceNode = null;
  let currentVolumeValue = 1.0;

  function setupWebAudioGainNode(audioEl) {
    if (IS_IOS) return;
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

    navigator.mediaSession.setActionHandler('play', () => handlers.onPlay());
    navigator.mediaSession.setActionHandler('pause', () => handlers.onPause());
    navigator.mediaSession.setActionHandler('seekbackward', (details) => handlers.onSeekBackward(details));
    navigator.mediaSession.setActionHandler('seekforward', (details) => handlers.onSeekForward(details));
    navigator.mediaSession.setActionHandler('previoustrack', () => handlers.onPrevTrack());
    navigator.mediaSession.setActionHandler('nexttrack', () => handlers.onNextTrack());

    try {
      navigator.mediaSession.setActionHandler('seekto', (details) => handlers.onSeekTo(details));
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
