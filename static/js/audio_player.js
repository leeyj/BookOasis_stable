// static/js/audio_player.js - 바닐라 JS 몰입형 오디오북 플레이어 코어 컨트롤러
let audioInstance = null;
let currentAudiobookData = null;
let currentTrackIndex = 0;
let currentAudioSpeedIndex = 0;
let sleepTimerId = null;
let sleepMinutes = 0;
const audioSpeeds = [1.0, 1.25, 1.5, 1.75, 2.0, 0.75];
const sleepOptions = [0, 15, 30, 45, 60];
let currentSleepIndex = 0;
let lastObservedProgressKey = '';
let lastFlushedProgressKey = '';
let lastAutoSaveAtMs = 0;
const AUDIO_PROGRESS_AUTO_SAVE_MS = 10000;

export async function openAudioPlayer(audiobookId, trackIdOrTitle = null, startTime = 0) {
  try {
    const res = await fetch(`/api/media/detail?type=audiobook&representative_book_id=${audiobookId}`);
    if (!res.ok) throw new Error('Audiobook detail fetch failed');
    const data = await res.json();
    if (!data.success || !data.meta) throw new Error('Invalid audiobook data');

    currentAudiobookData = {
      meta: data.meta,
      tracks: data.books || []
    };

    openAudioPlayerModal(currentAudiobookData, trackIdOrTitle, startTime);
  } catch (err) {
    console.error('[AudioPlayer] Error opening audio player:', err);
    if (typeof window.showToast === 'function') {
      window.showToast('오디오북 정보를 불러오지 못했습니다.', 'error');
    } else {
      alert('오디오북 정보를 불러오지 못했습니다.');
    }
  }
}

export function openAudioPlayerModal(audioData, targetTrackId = null, startTime = 0) {
  const modal = document.getElementById('audio-player-modal');
  if (!modal) return;

  const meta = audioData.meta || {};
  const tracks = audioData.tracks || [];
  if (tracks.length === 0) return;

  let selectedIdx = 0;
  if (targetTrackId) {
    const foundIdx = tracks.findIndex(t => String(t.id) === String(targetTrackId) || t.title === targetTrackId);
    if (foundIdx !== -1) selectedIdx = foundIdx;
  }
  currentTrackIndex = selectedIdx;

  const currentTrack = tracks[currentTrackIndex];

  // DOM 요소를 업데이트합니다
  const headerTitleEl = document.getElementById('audio-player-header-title');
  const headerAuthorEl = document.getElementById('audio-player-header-author');
  const titleEl = document.getElementById('audio-player-title');
  const authorEl = document.getElementById('audio-player-author');
  const chapterBadgeEl = document.getElementById('audio-player-chapter-badge');
  const coverImg = document.getElementById('audio-player-cover');
  const coverPlaceholder = document.getElementById('audio-player-cover-placeholder');
  const backdrop = document.getElementById('audio-player-backdrop');

  if (headerTitleEl) headerTitleEl.textContent = meta.series_name || '오디오북';
  if (headerAuthorEl) headerAuthorEl.textContent = meta.author || 'BookOasis';
  if (titleEl) titleEl.textContent = meta.series_name || '오디오북';
  if (authorEl) authorEl.textContent = `${meta.author || '저자 미상'}${meta.publisher ? ' · ' + meta.publisher : ''}`;
  if (chapterBadgeEl) chapterBadgeEl.textContent = currentTrack ? (currentTrack.title || `CHAPTER ${currentTrack.track_number}`) : 'CHAPTER 1';

  // 앰비언트 배경 및 커버 렌더링
  if (meta.cover_image) {
    if (backdrop) backdrop.style.backgroundImage = `url('${meta.cover_image}')`;
    if (coverImg) {
      coverImg.src = meta.cover_image;
      coverImg.style.display = 'block';
      if (coverPlaceholder) coverPlaceholder.style.display = 'none';
      coverImg.onerror = () => {
        coverImg.style.display = 'none';
        if (coverPlaceholder) coverPlaceholder.style.display = 'flex';
        if (backdrop) backdrop.style.backgroundImage = 'none';
      };
    }
  } else {
    if (backdrop) backdrop.style.backgroundImage = 'none';
    if (coverPlaceholder) coverPlaceholder.style.display = 'flex';
    if (coverImg) coverImg.style.display = 'none';
  }

  modal.style.display = 'block';
  document.body.style.overflow = 'hidden';
  lastObservedProgressKey = '';
  lastFlushedProgressKey = '';
  lastAutoSaveAtMs = 0;

  if (!audioInstance) {
    audioInstance = new Audio();
    initAudioEvents();
  }

  setAudioVolume(audioInstance.volume ?? 1);

  const streamUrl = `/api/media/audiobooks/${meta.id}/tracks/${currentTrack.id}/stream`;
  audioInstance.src = streamUrl;
  audioInstance.playbackRate = audioSpeeds[currentAudioSpeedIndex];

  if (startTime > 0) {
    audioInstance.currentTime = startTime;
  } else if (meta.current_track_id === currentTrack.id && meta.current_time > 0) {
    audioInstance.currentTime = meta.current_time;
  }

  toggleAudioPlay(true);
  initMediaSession(meta, currentTrack);
  renderChapterList();
}

function initAudioEvents() {
  if (!audioInstance) return;

  const btnPlay = document.getElementById('btn-audio-play-toggle');
  const seekbar = document.getElementById('audio-player-seekbar');
  const currentTimeEl = document.getElementById('audio-player-current-time');
  const durationEl = document.getElementById('audio-player-duration');

  audioInstance.ontimeupdate = () => {
    if (!audioInstance) return;
    const cur = audioInstance.currentTime || 0;
    const dur = audioInstance.duration || 0;
    const remain = Math.max(0, dur - cur);

    if (currentTimeEl) currentTimeEl.textContent = formatTime(cur);
    if (durationEl) durationEl.textContent = dur > 0 ? `-${formatTime(remain)}` : '-0:00';

    if (seekbar && dur > 0 && !seekbar.dataset.isDragging) {
      seekbar.value = (cur / dur) * 100;
    }

    scheduleProgressSnapshot();
    maybeAutoSaveProgress();
  };

  audioInstance.onpause = () => {
    if (!audioInstance || audioInstance.ended) return;
    saveProgress(false, { useBeacon: true, force: true });
  };

  audioInstance.onended = () => {
    if (currentAudiobookData && currentAudiobookData.tracks && currentTrackIndex < currentAudiobookData.tracks.length - 1) {
      playNextTrack();
    } else {
      if (btnPlay) btnPlay.innerHTML = '<i class="fa-solid fa-play" style="margin-left: 4px;"></i>';
      saveProgress(true);
    }
  };

  if (seekbar) {
    seekbar.oninput = () => {
      seekbar.dataset.isDragging = 'true';
    };
    seekbar.onchange = () => {
      if (audioInstance && audioInstance.duration) {
        const pct = parseFloat(seekbar.value) / 100;
        audioInstance.currentTime = pct * audioInstance.duration;
      }
      delete seekbar.dataset.isDragging;
    };
  }
}

export function closeAudioPlayerModal() {
  const modal = document.getElementById('audio-player-modal');
  if (modal) modal.style.display = 'none';
  document.body.style.overflow = '';
  if (audioInstance) {
    audioInstance.pause();
    saveProgress(false);
  }
  const drawer = document.getElementById('audio-chapter-drawer');
  if (drawer) drawer.style.transform = 'translateY(100%)';
}

export function toggleAudioPlay(forcePlay = null) {
  if (!audioInstance) return;
  const btn = document.getElementById('btn-audio-play-toggle');
  const shouldPlay = forcePlay !== null ? forcePlay : audioInstance.paused;

  if (shouldPlay) {
    audioInstance.play().then(() => {
      if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    }).catch(e => console.log('[AudioPlayer] Play blocked:', e));
  } else {
    audioInstance.pause();
    if (btn) btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left: 4px;"></i>';
    saveProgress(false);
  }
}

export function playPrevTrack() {
  if (!currentAudiobookData || !currentAudiobookData.tracks) return;
  if (currentTrackIndex > 0) {
    saveProgress(false, { useBeacon: false, force: true });
    currentTrackIndex--;
    openAudioPlayerModal(currentAudiobookData, currentAudiobookData.tracks[currentTrackIndex].id, 0);
  } else {
    audioInstance.currentTime = 0;
  }
}

export function playNextTrack() {
  if (!currentAudiobookData || !currentAudiobookData.tracks) return;
  if (currentTrackIndex < currentAudiobookData.tracks.length - 1) {
    saveProgress(false, { useBeacon: false, force: true });
    currentTrackIndex++;
    openAudioPlayerModal(currentAudiobookData, currentAudiobookData.tracks[currentTrackIndex].id, 0);
  }
}

export function audioPlayerSkip(seconds = 15) {
  if (!audioInstance) return;
  audioInstance.currentTime = Math.max(0, Math.min(audioInstance.duration || 0, audioInstance.currentTime + seconds));
  scheduleProgressSnapshot();
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

export function toggleAudioChapterDrawer() {
  const drawer = document.getElementById('audio-chapter-drawer');
  if (!drawer) return;
  const isHidden = drawer.style.transform === 'translateY(100%)' || !drawer.style.transform;
  drawer.style.transform = isHidden ? 'translateY(0%)' : 'translateY(100%)';
}

function renderChapterList() {
  const container = document.getElementById('audio-chapter-list');
  if (!container || !currentAudiobookData || !currentAudiobookData.tracks) return;

  const tracks = currentAudiobookData.tracks;
  container.innerHTML = tracks.map((t, idx) => {
    const isPlaying = idx === currentTrackIndex;
    const activeStyle = isPlaying ? 'background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8;' : 'background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); color: #e2e8f0;';
    const playIcon = isPlaying ? '<i class="fa-solid fa-volume-high" style="color: #38bdf8;"></i>' : `<span style="font-size: 0.8rem; color: #64748b;">${t.track_number || (idx + 1)}</span>`;

    return `
      <div onclick="selectChapterTrack(${t.id})" style="display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1rem; border-radius: 12px; cursor: pointer; transition: all 0.2s; ${activeStyle}">
        <div style="display: flex; align-items: center; gap: 0.9rem; overflow: hidden;">
          ${playIcon}
          <span style="font-size: 0.9rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${t.title}</span>
        </div>
        <span style="font-size: 0.8rem; color: #94a3b8; font-family: monospace;">${t.time_str || ''}</span>
      </div>
    `;
  }).join('');
}

export function selectChapterTrack(trackId) {
  if (!currentAudiobookData) return;
  openAudioPlayerModal(currentAudiobookData, trackId, 0);
  toggleAudioChapterDrawer();
}

export function toggleVolumePopover() {
  const popover = document.getElementById('audio-volume-popover');
  if (popover) {
    popover.style.display = popover.style.display === 'none' ? 'block' : 'none';
  }
}

export function setAudioVolume(val) {
  let volume = parseFloat(val);
  if (isNaN(volume)) volume = 1;
  volume = Math.max(0, Math.min(1, volume));

  if (audioInstance) {
    audioInstance.volume = volume;
  }

  const slider = document.getElementById('audio-volume-slider');
  if (slider && String(slider.value) !== String(volume)) {
    slider.value = String(volume);
  }

  const valueLabel = document.getElementById('audio-volume-value');
  if (valueLabel) {
    valueLabel.textContent = `${Math.round(volume * 100)}%`;
  }

  const icon = document.getElementById('audio-player-vol-icon');
  if (icon) {
    if (volume === 0) icon.className = 'fa-solid fa-volume-xmark';
    else if (volume < 0.5) icon.className = 'fa-solid fa-volume-low';
    else icon.className = 'fa-solid fa-volume-high';
  }
}

export function cycleSleepTimer() {
  currentSleepIndex = (currentSleepIndex + 1) % sleepOptions.length;
  sleepMinutes = sleepOptions[currentSleepIndex];

  if (sleepTimerId) {
    clearTimeout(sleepTimerId);
    sleepTimerId = null;
  }

  const label = document.getElementById('audio-sleep-label');
  if (sleepMinutes > 0) {
    if (label) label.textContent = `${sleepMinutes}m`;
    sleepTimerId = setTimeout(() => {
      toggleAudioPlay(false);
      if (typeof window.showToast === 'function') {
        window.showToast('취침 타이머가 만료되어 오디오 재생을 정지했습니다.', 'info');
      }
    }, sleepMinutes * 60 * 1000);
  } else {
    if (label) label.textContent = 'Sleep';
  }
}

function saveProgress(isCompleted = false) {
  return saveProgressInternal(isCompleted, { useBeacon: false, force: false });
}

function scheduleProgressSnapshot() {
  const payload = buildProgressPayload(false);
  if (!payload) return;
  const progressKey = buildProgressKey(payload);
  lastObservedProgressKey = progressKey;
}

function maybeAutoSaveProgress() {
  if (!audioInstance || audioInstance.paused || audioInstance.ended) return;
  const now = Date.now();
  if ((now - lastAutoSaveAtMs) < AUDIO_PROGRESS_AUTO_SAVE_MS) return;
  lastAutoSaveAtMs = now;
  saveProgressInternal(false, { useBeacon: false, force: false });
}

function buildProgressPayload(isCompleted = false) {
  if (!currentAudiobookData || !currentAudiobookData.meta || !audioInstance) return;
  const meta = currentAudiobookData.meta;
  const tracks = currentAudiobookData.tracks || [];
  const track = tracks[currentTrackIndex];
  if (!track) return;

  return {
    current_track_id: track.id,
    current_time: audioInstance.currentTime || 0,
    playback_rate: audioSpeeds[currentAudioSpeedIndex],
    is_completed: isCompleted
  };
}

function buildProgressKey(payload) {
  const seconds = Math.floor(Number(payload.current_time || 0));
  return [payload.current_track_id, seconds, payload.playback_rate, payload.is_completed ? 1 : 0].join(':');
}

function saveProgressInternal(isCompleted = false, options = {}) {
  const payload = buildProgressPayload(isCompleted);
  if (!payload) return Promise.resolve(null);

  const { useBeacon = false, force = false } = options;
  const progressKey = buildProgressKey(payload);
  if (!force && progressKey === lastFlushedProgressKey) {
    return Promise.resolve(true);
  }
  lastObservedProgressKey = progressKey;
  lastFlushedProgressKey = progressKey;

  const meta = currentAudiobookData.meta;
  const url = `/api/media/audiobooks/${meta.id}/progress`;

  if (useBeacon && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      const sent = navigator.sendBeacon(url, blob);
      if (sent) {
        return Promise.resolve(true);
      }
    } catch (e) {
      console.warn('[AudioPlayer] Progress beacon failed, falling back to fetch:', e);
    }
  }

  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    keepalive: true
  }).catch(e => console.warn('[AudioPlayer] Progress save failed:', e));
}

function formatTime(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function initMediaSession(meta, track) {
  if ('mediaSession' in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: track ? track.title : meta.series_name,
      artist: meta.author || 'BookOasis',
      album: meta.series_name || 'Audiobook',
      artwork: meta.cover_image ? [{ src: meta.cover_image }] : []
    });

    navigator.mediaSession.setActionHandler('play', () => toggleAudioPlay(true));
    navigator.mediaSession.setActionHandler('pause', () => toggleAudioPlay(false));
    navigator.mediaSession.setActionHandler('seekbackward', () => audioPlayerSkip(-15));
    navigator.mediaSession.setActionHandler('seekforward', () => audioPlayerSkip(15));
    navigator.mediaSession.setActionHandler('previoustrack', () => playPrevTrack());
    navigator.mediaSession.setActionHandler('nexttrack', () => playNextTrack());
  }
}

// 전역 키보드 단축키 매핑 (스페이스: 재생/일시정지, 좌/우 방향키: -15초/+15초 이동, 상/하 방향키: 볼륨 조절)
window.addEventListener('keydown', (e) => {
  const modal = document.getElementById('audio-player-modal');
  const isModalOpen = modal && modal.style.display === 'block';
  const isAudioActive = audioInstance && !audioInstance.paused;

  if (isModalOpen && e.key === 'Escape') {
    e.preventDefault();
    closeAudioPlayerModal();
    return;
  }

  if (!isModalOpen && !isAudioActive) return;

  // 텍스트 입력 엘리먼트에 포커스가 있을 때는 기본 동작 방해하지 않음
  const activeTag = (document.activeElement && document.activeElement.tagName) ? document.activeElement.tagName.toUpperCase() : '';
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) || (document.activeElement && document.activeElement.isContentEditable)) {
    return;
  }

  if (e.key === ' ' || e.code === 'Space') {
    e.preventDefault();
    toggleAudioPlay();
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    audioPlayerSkip(-15);
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    audioPlayerSkip(15);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (audioInstance) {
      const newVol = Math.min(1.0, (audioInstance.volume !== undefined ? audioInstance.volume : 1.0) + 0.1);
      setAudioVolume(newVol);
      const slider = document.getElementById('audio-volume-slider');
      if (slider) slider.value = newVol;
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (audioInstance) {
      const newVol = Math.max(0.0, (audioInstance.volume !== undefined ? audioInstance.volume : 1.0) - 0.1);
      setAudioVolume(newVol);
      const slider = document.getElementById('audio-volume-slider');
      if (slider) slider.value = newVol;
    }
  }
});

window.openAudioPlayer = openAudioPlayer;
window.openAudioPlayerModal = openAudioPlayerModal;
window.closeAudioPlayerModal = closeAudioPlayerModal;
window.toggleAudioPlay = toggleAudioPlay;
window.playPrevTrack = playPrevTrack;
window.playNextTrack = playNextTrack;
window.audioPlayerSkip = audioPlayerSkip;
window.cycleAudioSpeed = cycleAudioSpeed;
window.toggleAudioChapterDrawer = toggleAudioChapterDrawer;
window.selectChapterTrack = selectChapterTrack;
window.toggleVolumePopover = toggleVolumePopover;
window.setAudioVolume = setAudioVolume;
window.cycleSleepTimer = cycleSleepTimer;

function flushAudioProgressForLifecycle(useBeacon = false) {
  const modal = document.getElementById('audio-player-modal');
  if (!modal || modal.style.display !== 'block') return;
  saveProgressInternal(false, { useBeacon, force: true });
}

window.addEventListener('pagehide', () => {
  flushAudioProgressForLifecycle(true);
});

window.addEventListener('beforeunload', () => {
  flushAudioProgressForLifecycle(true);
});

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    flushAudioProgressForLifecycle(true);
  }
});
