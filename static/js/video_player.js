// static/js/video_player.js - 영상 강좌 재생 모달 (네이티브 <video controls> 기반, 최소 통합 스코프)
// audio_player.js::openAudioPlayer()와 동일하게 공용 상세 API(/api/media/detail)를 직접 fetch해서 연다.
import { remoteLog } from './remote_log.js';

let currentMeta = null;
let currentEpisodes = [];
let currentEpisodeIndex = -1;
let lastAutoSaveAtMs = 0;
const AUTO_SAVE_MS = 10000;

function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function getOverlay() {
  let overlay = document.getElementById('video-player-modal-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'video-player-modal-overlay';
    overlay.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:9100; display:none; align-items:center; justify-content:center; padding:2rem;';
    document.body.appendChild(overlay);
  }
  return overlay;
}

function saveProgress(isCompleted = false, useBeacon = false) {
  if (!currentMeta || currentEpisodeIndex < 0) return;
  const episode = currentEpisodes[currentEpisodeIndex];
  const videoEl = document.getElementById('video-player-el');
  if (!episode || !videoEl) return;

  const payload = {
    current_episode_id: episode.id,
    current_time: videoEl.currentTime || 0,
    playback_rate: videoEl.playbackRate || 1.0,
    is_completed: isCompleted
  };
  const url = `/api/media/videos/${currentMeta.id}/progress`;

  if (useBeacon && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      if (navigator.sendBeacon(url, blob)) return;
    } catch (e) { /* fallback to fetch below */ }
  }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    keepalive: true
  }).catch(e => console.warn('[VideoPlayer] progress save failed:', e));
}

function maybeAutoSaveProgress() {
  const now = Date.now();
  if ((now - lastAutoSaveAtMs) < AUTO_SAVE_MS) return;
  lastAutoSaveAtMs = now;
  saveProgress(false, false);
}

function renderPlayerModal(startTime = 0) {
  const overlay = getOverlay();
  const episode = currentEpisodes[currentEpisodeIndex];
  const hasPrev = currentEpisodeIndex > 0;
  const hasNext = currentEpisodeIndex >= 0 && currentEpisodeIndex < currentEpisodes.length - 1;

  const transportBtnStyle = (enabled) => `padding:0.7rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.06); color:#fff; font-weight:700; cursor:${enabled ? 'pointer' : 'not-allowed'}; opacity:${enabled ? '1' : '0.35'}; display:flex; align-items:center; justify-content:center;`;

  overlay.innerHTML = `
    <div style="width:min(1100px, 100%); display:flex; flex-direction:column; gap:0.8rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; color:#e2e8f0;">
        <div>
          <div style="font-size:0.8rem; color:#94a3b8;">${escapeHtml(currentMeta.series_name || currentMeta.title || '')}</div>
          <div style="font-size:1rem; font-weight:700;">#${episode.episode_number} ${escapeHtml(episode.title)}</div>
        </div>
        <button data-role="video-player-close" style="background:none; border:none; color:#94a3b8; font-size:1.6rem; cursor:pointer;">&times;</button>
      </div>
      <video id="video-player-el" controls autoplay playsinline webkit-playsinline style="width:100%; max-height:70vh; background:#000; border-radius:8px;"
             src="/api/media/videos/${currentMeta.id}/episodes/${episode.id}/stream">${episode.has_subtitle ? `<track kind="subtitles" src="/api/media/videos/${currentMeta.id}/episodes/${episode.id}/subtitle" srclang="ko" label="자막" default>` : ''}</video>
      <div style="display:flex; justify-content:center; align-items:center; gap:0.8rem;">
        <button data-role="video-player-prev" ${hasPrev ? '' : 'disabled'} title="이전 회차" style="${transportBtnStyle(hasPrev)} width:3rem; height:3rem;">
          <i class="fa-solid fa-backward-step"></i>
        </button>
        <button data-role="video-player-toggle" title="재생/일시정지" style="${transportBtnStyle(true)} width:3.6rem; height:3.6rem; background:rgba(168,85,247,0.25); border-color:rgba(168,85,247,0.5); font-size:1.2rem;">
          <i class="fa-solid fa-pause" data-role="video-player-toggle-icon"></i>
        </button>
        <button data-role="video-player-next" ${hasNext ? '' : 'disabled'} title="다음 회차" style="${transportBtnStyle(hasNext)} width:3rem; height:3rem;">
          <i class="fa-solid fa-forward-step"></i>
        </button>
      </div>
    </div>
  `;

  overlay.querySelector('[data-role="video-player-close"]').addEventListener('click', closeVideoPlayer);
  overlay.querySelector('[data-role="video-player-prev"]')?.addEventListener('click', () => {
    if (hasPrev) playEpisodeAtIndex(currentEpisodeIndex - 1);
  });
  overlay.querySelector('[data-role="video-player-next"]')?.addEventListener('click', () => {
    if (hasNext) playEpisodeAtIndex(currentEpisodeIndex + 1);
  });

  const videoEl = document.getElementById('video-player-el');
  const toggleBtn = overlay.querySelector('[data-role="video-player-toggle"]');
  const toggleIcon = overlay.querySelector('[data-role="video-player-toggle-icon"]');

  const syncToggleIcon = () => {
    toggleIcon.className = (videoEl.paused || videoEl.ended) ? 'fa-solid fa-play' : 'fa-solid fa-pause';
  };
  toggleBtn.addEventListener('click', () => {
    if (videoEl.paused || videoEl.ended) {
      videoEl.play();
    } else {
      videoEl.pause();
    }
  });
  videoEl.addEventListener('play', syncToggleIcon);
  videoEl.addEventListener('pause', syncToggleIcon);
  videoEl.addEventListener('canplay', syncToggleIcon, { once: true });

  // iOS에서 재생이 아예 시작 안 되는 문제를 실기기에서 진단하기 위한 원격 로깅.
  // MediaError.code로 원인을 구분할 수 있다: 1=중단, 2=네트워크, 3=디코딩 실패,
  // 4=MEDIA_ERR_SRC_NOT_SUPPORTED(포맷/컨테이너 자체를 브라우저가 지원 안 함 - mkv
  // 컨테이너 미지원이 원인이라면 이 코드가 찍힐 가능성이 높다).
  videoEl.addEventListener('error', () => {
    const err = videoEl.error;
    remoteLog('video-error', {
      code: err ? err.code : null,
      message: err ? err.message : null,
      src: videoEl.currentSrc,
      networkState: videoEl.networkState,
      readyState: videoEl.readyState
    });
  });
  videoEl.addEventListener('loadstart', () => remoteLog('video-loadstart', { src: videoEl.currentSrc }));
  videoEl.addEventListener('loadedmetadata', () => remoteLog('video-loadedmetadata', { duration: videoEl.duration }));
  videoEl.addEventListener('canplay', () => remoteLog('video-canplay', {}), { once: true });
  videoEl.addEventListener('stalled', () => remoteLog('video-stalled', { currentTime: videoEl.currentTime }));
  videoEl.addEventListener('suspend', () => remoteLog('video-suspend', { currentTime: videoEl.currentTime }));

  if (startTime > 0) {
    videoEl.addEventListener('loadedmetadata', () => {
      videoEl.currentTime = startTime;
    }, { once: true });
  }

  videoEl.addEventListener('timeupdate', maybeAutoSaveProgress);
  videoEl.addEventListener('pause', () => saveProgress(false, false));
  videoEl.addEventListener('ended', () => {
    saveProgress(true, false);
    if (hasNext) playEpisodeAtIndex(currentEpisodeIndex + 1);
  });

  // episode 메타데이터를 await fetch()로 가져온 뒤 이 모달을 렌더링하므로, 원래 클릭했던
  // 사용자 제스처 컨텍스트가 이미 끊겨 있다. 그 상태에서 HTML의 autoplay 속성에만
  // 의존하면 iOS Safari 등 엄격한 브라우저에서 소리 있는 자동재생이 조용히 차단되어
  // 아예 재생이 시작되지 않는 경우가 있다. play()를 명시적으로 한 번 더 호출해서 결과를
  // 확인하고, 차단됐다면(Promise reject) 콘솔에 남겨 진단 가능하게 한다 — 이 경우
  // canplay 시점에 실행되는 syncToggleIcon이 '재생' 아이콘으로 정확히 되돌려주므로
  // 사용자가 직접 탭해서 시작할 수 있다.
  videoEl.play().catch((err) => {
    console.warn('[VideoPlayer] Autoplay blocked, waiting for manual tap:', err);
  });

  initMediaSession(currentMeta, episode, videoEl, hasPrev, hasNext);
}

function initMediaSession(meta, episode, videoEl, hasPrev, hasNext) {
  if (!('mediaSession' in navigator)) return;

  navigator.mediaSession.metadata = new MediaMetadata({
    title: `#${episode.episode_number} ${episode.title}`,
    artist: meta.series_name || meta.title || 'BookOasis',
    album: meta.series_name || meta.title || 'Video Course',
    artwork: meta.cover_image ? [{ src: meta.cover_image }] : []
  });

  navigator.mediaSession.setActionHandler('play', () => videoEl.play());
  navigator.mediaSession.setActionHandler('pause', () => videoEl.pause());
  navigator.mediaSession.setActionHandler('seekbackward', (details) => {
    videoEl.currentTime = Math.max(0, videoEl.currentTime - (details.seekOffset ?? 15));
  });
  navigator.mediaSession.setActionHandler('seekforward', (details) => {
    videoEl.currentTime = videoEl.currentTime + (details.seekOffset ?? 15);
  });
  navigator.mediaSession.setActionHandler('previoustrack', hasPrev ? () => playEpisodeAtIndex(currentEpisodeIndex - 1) : null);
  navigator.mediaSession.setActionHandler('nexttrack', hasNext ? () => playEpisodeAtIndex(currentEpisodeIndex + 1) : null);

  try {
    navigator.mediaSession.setActionHandler('seekto', (details) => {
      if (details.seekTime != null) videoEl.currentTime = details.seekTime;
    });
  } catch (e) {}

  const syncPlaybackState = () => {
    navigator.mediaSession.playbackState = videoEl.paused ? 'paused' : 'playing';
  };
  videoEl.addEventListener('play', syncPlaybackState);
  videoEl.addEventListener('pause', syncPlaybackState);
}

function playEpisodeAtIndex(index) {
  currentEpisodeIndex = index;
  lastAutoSaveAtMs = 0;
  renderPlayerModal(0);
}

export async function openVideoPlayer(videoId, episodeId = null, startTime = 0) {
  try {
    const res = await fetch(`/api/media/detail?type=video&representative_book_id=${videoId}`);
    if (!res.ok) throw new Error('Video detail fetch failed');
    const data = await res.json();
    if (!data.success || !data.meta) throw new Error('Invalid video data');

    currentMeta = data.meta;
    currentEpisodes = data.books || [];
    if (currentEpisodes.length === 0) throw new Error('No episodes');

    const targetEpisodeId = episodeId || currentMeta.current_episode_id || currentEpisodes[0].id;
    const idx = currentEpisodes.findIndex(ep => Number(ep.id) === Number(targetEpisodeId));
    currentEpisodeIndex = idx >= 0 ? idx : 0;

    const resumingSameEpisode = Number(currentEpisodes[currentEpisodeIndex].id) === Number(currentMeta.current_episode_id);
    const initialStartTime = startTime > 0
      ? Number(startTime)
      : (resumingSameEpisode ? Number(currentMeta.current_time || 0) : 0);

    const overlay = getOverlay();
    overlay.style.display = 'flex';
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeVideoPlayer();
    });
    renderPlayerModal(initialStartTime);
  } catch (err) {
    console.error('[VideoPlayer] Error opening video player:', err);
    if (typeof window.showToast === 'function') {
      window.showToast('영상 강좌 정보를 불러오지 못했습니다.', 'error');
    } else {
      alert('영상 강좌 정보를 불러오지 못했습니다.');
    }
  }
}

export function closeVideoPlayer() {
  const videoEl = document.getElementById('video-player-el');
  if (videoEl && !videoEl.paused) {
    saveProgress(false, true);
    videoEl.pause();
  }
  const overlay = document.getElementById('video-player-modal-overlay');
  if (overlay) overlay.style.display = 'none';
  currentMeta = null;
  currentEpisodes = [];
  currentEpisodeIndex = -1;
}

window.addEventListener('beforeunload', () => {
  const videoEl = document.getElementById('video-player-el');
  if (videoEl && !videoEl.paused) saveProgress(false, true);
});

window.openVideoPlayer = openVideoPlayer;
window.closeVideoPlayer = closeVideoPlayer;
