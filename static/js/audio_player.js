// static/js/audio_player.js - 바닐라 JS 오디오북 플레이어 코어 컨트롤러
let audioInstance = null;
let currentAudioSpeedIndex = 0;
const audioSpeeds = [1.0, 1.25, 1.5, 1.75, 2.0, 0.75];

export function openAudioPlayerModal(audioData = {}) {
  const modal = document.getElementById('audio-player-modal');
  if (!modal) return;

  const titleEl = document.getElementById('audio-player-title');
  const authorEl = document.getElementById('audio-player-author');

  if (titleEl) titleEl.textContent = audioData.title || '오디오북';
  if (authorEl) authorEl.textContent = audioData.author || '알 수 없는 저자';

  modal.style.display = 'flex';

  if (!audioInstance) {
    audioInstance = new Audio();
    initMediaSession(audioData);
  }
}

export function closeAudioPlayerModal() {
  const modal = document.getElementById('audio-player-modal');
  if (modal) modal.style.display = 'none';
  if (audioInstance) {
    audioInstance.pause();
  }
}

export function toggleAudioPlay() {
  if (!audioInstance) return;
  const btn = document.getElementById('btn-audio-play-toggle');
  if (audioInstance.paused) {
    audioInstance.play().catch(e => console.log('[AudioPlayer] Play blocked:', e));
    if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
  } else {
    audioInstance.pause();
    if (btn) btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left: 3px;"></i>';
  }
}

export function audioPlayerSkip(seconds = 15) {
  if (!audioInstance) return;
  audioInstance.currentTime = Math.max(0, audioInstance.currentTime + seconds);
}

export function cycleAudioSpeed() {
  currentAudioSpeedIndex = (currentAudioSpeedIndex + 1) % audioSpeeds.length;
  const speed = audioSpeeds[currentAudioSpeedIndex];
  if (audioInstance) {
    audioInstance.playbackRate = speed;
  }
  const label = document.getElementById('audio-player-speed-label');
  if (label) label.textContent = `${speed}x`;
}

export function toggleAudioChapterList() {
  console.log('[AudioPlayer] Chapter list toggled');
}

function initMediaSession(audioData) {
  if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: audioData.title || 'BookOasis Audiobook',
      artist: audioData.author || 'BookOasis',
      album: '오디오북 라이브러리',
    });

    navigator.mediaSession.setActionHandler('play', () => toggleAudioPlay());
    navigator.mediaSession.setActionHandler('pause', () => toggleAudioPlay());
    navigator.mediaSession.setActionHandler('seekbackward', () => audioPlayerSkip(-15));
    navigator.mediaSession.setActionHandler('seekforward', () => audioPlayerSkip(15));
  }
}

// 전역 윈도우 객체 바인딩 (HTML onclick 이벤트 지원)
window.openAudioPlayerModal = openAudioPlayerModal;
window.closeAudioPlayerModal = closeAudioPlayerModal;
window.toggleAudioPlay = toggleAudioPlay;
window.audioPlayerSkip = audioPlayerSkip;
window.cycleAudioSpeed = cycleAudioSpeed;
window.toggleAudioChapterList = toggleAudioChapterList;
