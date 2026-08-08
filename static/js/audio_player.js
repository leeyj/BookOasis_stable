// static/js/audio_player.js - 바닐라 JS 몰입형 오디오북 플레이어 코어 컨트롤러
import { createAudioProgressSync } from './audio_player_modules/progress_sync.js';
import { initAudioLifecycleAndShortcuts } from './audio_player_modules/lifecycle_shortcuts.js';
import { createMiniPlayerUiController } from './audio_player_modules/mini_player_ui.js';
import { createAudioPlaybackEngine } from './audio_player_modules/playback_engine.js';
import { registerAudioPlayerPublicApi } from './audio_player_modules/public_api.js';

let audioInstance = null;
let currentAudiobookData = null;
let currentTrackIndex = 0;

document.addEventListener('audiobook-track-completed', (event) => {
  const trackId = Number(event?.detail?.trackId || 0);
  if (!trackId) return;
  document.querySelectorAll(`[data-audiobook-track-completed="${trackId}"]`).forEach((dot) => {
    dot.classList.add('is-visible');
  });
});
let currentAudioPlayerViewMode = 'hidden'; // hidden | mini | full
let currentAudioSpeedIndex = 0;
let sleepTimerId = null;
let sleepMinutes = 0;
const audioSpeeds = [1.0, 1.25, 1.5, 1.75, 2.0, 0.75];
const sleepOptions = [0, 15, 30, 45, 60];
let currentSleepIndex = 0;
const playbackEngine = createAudioPlaybackEngine();

const progressSync = createAudioProgressSync({
  getAudioInstance: () => audioInstance,
  getAudiobookData: () => currentAudiobookData,
  getCurrentTrackIndex: () => currentTrackIndex,
  getPlaybackRate: () => audioSpeeds[currentAudioSpeedIndex],
  onProgressSaved: (result) => {
    if (!currentAudiobookData || !Array.isArray(currentAudiobookData.tracks)) return;
    const savedTrackId = Number(result?.track_id || 0);
    if (!savedTrackId) return;

    const track = currentAudiobookData.tracks.find((row) => Number(row?.id || 0) === savedTrackId);
    if (!track) return;

    const nextPct = Number(result?.track_progress_pct || 0);
    if (Number.isFinite(nextPct)) {
      track.track_progress_pct = Math.max(0, Math.min(100, nextPct));
    }
    track.is_track_completed = Number(result?.track_is_completed) === 1 ? 1 : 0;

    const allTracksCompleted = currentAudiobookData.tracks.length > 0
      && currentAudiobookData.tracks.every((row) => {
        const pct = Number(row?.track_progress_pct || 0);
        return Number(row?.is_track_completed) === 1 || pct >= 95;
      });

    if (allTracksCompleted) {
      document.querySelectorAll(`[data-audiobook-completed="${currentAudiobookData.meta?.id || ''}"]`).forEach((badge) => {
        badge.classList.add('is-visible');
      });
      const cardCover = document.querySelector(`.book-card[data-book-id="${currentAudiobookData.meta?.id || ''}"] .book-card-cover`);
      if (cardCover && !cardCover.querySelector('.book-card-audiobook-completed')) {
        const completedDot = document.createElement('span');
        completedDot.className = 'book-card-audiobook-completed';
        completedDot.title = window.i18n?.t('detail.audiobook_completed') || '청취 완료';
        completedDot.setAttribute('aria-label', completedDot.title);
        cardCover.appendChild(completedDot);
      }
    }

    updateMiniPlayerUi();
  }
});

const miniPlayerUi = createMiniPlayerUiController({
  getCurrentViewMode: () => currentAudioPlayerViewMode,
  setCurrentViewMode: (mode) => {
    currentAudioPlayerViewMode = mode;
  },
  getAudiobookData: () => currentAudiobookData,
  getCurrentTrackIndex: () => currentTrackIndex,
  getAudioInstance: () => audioInstance,
  getEffectiveTrackDuration,
  updatePlaybackToggleButtons
});

function isMiniBarFeatureEnabled() {
  return miniPlayerUi.isMiniBarFeatureEnabled();
}

function getInitialAudioPlayerViewMode() {
  const configuredMode = (typeof window !== 'undefined' && window.__audioMiniPlayerMode)
    ? String(window.__audioMiniPlayerMode)
    : 'mini';

  // right_dock 설정에서는 재생 시작 시 전체 모달 대신 우측 패널로 진입한다.
  if (configuredMode === 'right_dock' && isMiniBarFeatureEnabled()) {
    return 'mini';
  }

  return 'full';
}

function initMiniBarDrag() {
  miniPlayerUi.init();
}

function setupWebAudioGainNode(audioEl) {
  playbackEngine.setupWebAudioGainNode(audioEl);
}


function initAudioPlayerDelegation() {
  if (window.__audioPlayerDelegationBound) return;

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="audio-player-action"], [data-role="audio-chapter-track"]')
      : null;
    if (!target) return;

    event.preventDefault();

    if (target.getAttribute('data-role') === 'audio-chapter-track') {
      const trackId = Number.parseInt(target.getAttribute('data-track-id') || '', 10);
      if (Number.isFinite(trackId) && trackId > 0) {
        selectChapterTrack(trackId);
      }
      return;
    }

    const action = target.getAttribute('data-action');
    const rawValue = target.getAttribute('data-value');
    if (action === 'mini-drag-handle') return;
    if (action === 'toggle-mini-peek') {
      miniPlayerUi.toggleMiniPeek();
      return;
    }
    if (action === 'open-full' && miniPlayerUi.shouldSuppressOpenFull()) return;
    if (action === 'open-full' && miniPlayerUi.revealIfCollapsed()) return;
    if (action === 'close' && miniPlayerUi.shouldBlockClose()) return;
    if (action === 'close') return closeAudioPlayerModal();
    if (action === 'open-full') return expandAudioPlayerModal();
    if (action === 'dismiss-mini') return stopAndHideAudioPlayer();
    if (action === 'bookmark') return toggleAudioBookmark();
    if (action === 'fullscreen') return toggleAudioFullscreen();
    if (action === 'prev-track') return playPrevTrack();
    if (action === 'next-track') return playNextTrack();
    if (action === 'skip') return audioPlayerSkip(Number.parseFloat(rawValue || '0') || 0);
    if (action === 'toggle-play') return toggleAudioPlay();
    if (action === 'cycle-speed') return cycleAudioSpeed();
    if (action === 'toggle-chapters') return toggleAudioChapterDrawer();
    if (action === 'set-volume') return setAudioVolume(rawValue);
    if (action === 'cycle-sleep') return cycleSleepTimer();
  }, true);

  document.addEventListener('input', (event) => {
    const target = event && event.target;
    if (!target || !(target.matches instanceof Function)) return;
    if (!target.matches('[data-role="audio-player-input"]')) return;

    const action = target.getAttribute('data-action');
    if (action === 'set-volume') {
      setAudioVolume(target.value);
    }
  }, true);

  window.__audioPlayerDelegationBound = true;
}

initAudioPlayerDelegation();
initMiniBarDrag();

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

    openAudioPlayerModal(currentAudiobookData, trackIdOrTitle, startTime, {
      viewMode: getInitialAudioPlayerViewMode()
    });
  } catch (err) {
    console.error('[AudioPlayer] Error opening audio player:', err);
    if (typeof window.showToast === 'function') {
      window.showToast('오디오북 정보를 불러오지 못했습니다.', 'error');
    } else {
      alert('오디오북 정보를 불러오지 못했습니다.');
    }
  }
}

function setAudioPlayerViewMode(mode, options = {}) {
  miniPlayerUi.setViewMode(mode, options);
}

export function applyAudioMiniPlayerMode(mode) {
  miniPlayerUi.applyAudioMiniPlayerMode(mode);
  if (currentAudioPlayerViewMode === 'mini') {
    updateMiniPlayerUi();
  }
}

function updatePlaybackToggleButtons(isPlaying) {
  const playHtml = '<i class="fa-solid fa-play" style="margin-left: 4px;"></i>';
  const pauseHtml = '<i class="fa-solid fa-pause"></i>';
  const html = isPlaying ? pauseHtml : playHtml;

  const fullBtn = document.getElementById('btn-audio-play-toggle');
  if (fullBtn) fullBtn.innerHTML = html;

  const miniBtn = document.getElementById('btn-audio-mini-play-toggle');
  if (miniBtn) miniBtn.innerHTML = html;
}

function updateMiniPlayerUi() {
  miniPlayerUi.updateMiniPlayerUi();
}

export function expandAudioPlayerModal() {
  if (!currentAudiobookData) return;
  miniPlayerUi.markExpandGuard();
  setAudioPlayerViewMode('full');
  updateMiniPlayerUi();
}

export function openAudioPlayerModal(audioData, targetTrackId = null, startTime = 0, options = {}) {
  const modal = document.getElementById('audio-player-modal');
  if (!modal) return;

  const requestedViewMode = options.viewMode || currentAudioPlayerViewMode || 'full';
  const isMiniTrackSwitch = (currentAudioPlayerViewMode === 'mini' && requestedViewMode === 'mini');

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

  setAudioPlayerViewMode(requestedViewMode === 'hidden' ? 'mini' : requestedViewMode, {
    skipMiniReposition: isMiniTrackSwitch
  });
  progressSync.resetProgressTracking();

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
  updateMiniPlayerUi();
}

function getEffectiveTrackDuration() {
  if (audioInstance && Number.isFinite(audioInstance.duration) && audioInstance.duration > 0 && audioInstance.duration !== Infinity) {
    return audioInstance.duration;
  }
  if (currentAudiobookData && currentAudiobookData.tracks && currentAudiobookData.tracks[currentTrackIndex]) {
    const track = currentAudiobookData.tracks[currentTrackIndex];
    if (Number.isFinite(Number(track.duration)) && Number(track.duration) > 0) {
      return Number(track.duration);
    }
    if (Number.isFinite(Number(track.total_duration)) && Number(track.total_duration) > 0) {
      return Number(track.total_duration);
    }
    if (track.time_str && typeof track.time_str === 'string') {
      const parts = track.time_str.split(':').map(p => parseInt(p, 10));
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        return parts[0] * 60 + parts[1];
      } else if (parts.length === 3 && !isNaN(parts[0]) && !isNaN(parts[1]) && !isNaN(parts[2])) {
        return parts[0] * 3600 + parts[1] * 60 + parts[2];
      }
    }
  }
  return 0;
}

function initAudioEvents() {
  if (!audioInstance) return;

  const btnPlay = document.getElementById('btn-audio-play-toggle');
  const seekbar = document.getElementById('audio-player-seekbar');
  const currentTimeEl = document.getElementById('audio-player-current-time');
  const durationEl = document.getElementById('audio-player-duration');

  // iOS 핵심: play/playing 이벤트 시점에 AudioContext를 resume함.
  // createMediaElementSource 연결 이후 AudioContext가 suspended이면 소리가 나지 않음.
  playbackEngine.bindResumeOnPlay(audioInstance);

  audioInstance.ontimeupdate = () => {
    if (!audioInstance) return;
    const cur = audioInstance.currentTime || 0;
    const effDur = getEffectiveTrackDuration();
    const remain = Math.max(0, effDur - cur);

    if (currentTimeEl) currentTimeEl.textContent = formatTime(cur);
    if (durationEl) durationEl.textContent = effDur > 0 ? `-${formatTime(remain)}` : '-0:00';

    if (seekbar && effDur > 0 && !seekbar.dataset.isDragging) {
      seekbar.value = Math.min(100, Math.max(0, (cur / effDur) * 100));
    }

    scheduleProgressSnapshot();
    maybeAutoSaveProgress();
    updateMiniPlayerUi();
  };

  audioInstance.onpause = () => {
    updatePlaybackToggleButtons(false);
    if (!audioInstance || audioInstance.ended) return;
    // 일시정지는 페이지 이탈이 아니므로 fetch keepalive 기반 강제 저장을 우선한다.
    saveProgress(false, { useBeacon: false, force: true });
  };

  audioInstance.onended = () => {
    if (currentAudiobookData && currentAudiobookData.tracks && currentTrackIndex < currentAudiobookData.tracks.length - 1) {
      playNextTrack();
    } else {
      updatePlaybackToggleButtons(false);
      const completedAudiobookId = currentAudiobookData?.meta?.id;
      saveProgress(true).then((result) => {
        if (!completedAudiobookId || (result && result.ok === false)) return;
        document.querySelectorAll(`[data-audiobook-completed="${completedAudiobookId}"]`).forEach((badge) => {
          badge.classList.add('is-visible');
        });
        const cardCover = document.querySelector(`.book-card[data-book-id="${completedAudiobookId}"] .book-card-cover`);
        if (cardCover && !cardCover.querySelector('.book-card-audiobook-completed')) {
          const completedDot = document.createElement('span');
          completedDot.className = 'book-card-audiobook-completed';
          completedDot.title = window.i18n?.t('detail.audiobook_completed') || '청취 완료';
          completedDot.setAttribute('aria-label', completedDot.title);
          cardCover.appendChild(completedDot);
        }
      });
    }
    updateMiniPlayerUi();
  };

  if (seekbar) {
    seekbar.oninput = () => {
      seekbar.dataset.isDragging = 'true';
    };
    seekbar.onchange = () => {
      const effDur = getEffectiveTrackDuration();
      if (audioInstance && effDur > 0) {
        const pct = parseFloat(seekbar.value) / 100;
        audioInstance.currentTime = pct * effDur;
      }
      delete seekbar.dataset.isDragging;
    };
  }
}

export function closeAudioPlayerModal() {
  if (!isMiniBarFeatureEnabled()) {
    stopAndHideAudioPlayer();
    return;
  }

  // full 모달 닫기는 재생 유지 + 미니바 축소로 동작
  if (audioInstance) {
    saveProgress(false);
  }
  setAudioPlayerViewMode('mini');
  const drawer = document.getElementById('audio-chapter-drawer');
  if (drawer) drawer.style.transform = 'translateY(100%)';
  updateMiniPlayerUi();
}

export function stopAndHideAudioPlayer() {
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
  }
  const hadAudio = !!audioInstance;
  if (audioInstance) {
    audioInstance.pause();
    // 명시적 종료(X/중지)는 페이지 이탈 상황이 아니므로 beacon 대신 fetch 강제 저장을 우선 사용.
    saveProgressInternal(false, { useBeacon: false, force: true }).catch(() => {});
  }

  // 일부 브라우저에서 pause 직후 currentTime 반영 지연이 있어 짧은 지연 후 1회 보강 저장.
  if (hadAudio) {
    setTimeout(() => {
      saveProgressInternal(false, { useBeacon: false, force: true }).catch(() => {});
    }, 120);
  }

  const drawer = document.getElementById('audio-chapter-drawer');
  if (drawer) drawer.style.transform = 'translateY(100%)';
  setAudioPlayerViewMode('hidden');
}

export function toggleAudioBookmark() {
  const msg = '오디오북 북마크 기능은 준비 중입니다.';
  if (typeof window.showToast === 'function') {
    window.showToast(msg, 'info');
  } else {
    alert(msg);
  }
}

export async function toggleAudioFullscreen() {
  const modal = document.getElementById('audio-player-modal');
  if (!modal) return;

  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    if (typeof modal.requestFullscreen === 'function') {
      await modal.requestFullscreen();
    }
  } catch (err) {
    console.warn('[AudioPlayer] Fullscreen toggle failed:', err);
  }
}

export function toggleAudioPlay(forcePlay = null) {
  if (!audioInstance) return;
  setupWebAudioGainNode(audioInstance);
  playbackEngine.ensureAudioContextResumed();
  const btn = document.getElementById('btn-audio-play-toggle');
  const shouldPlay = forcePlay !== null ? forcePlay : audioInstance.paused;

  if (shouldPlay) {
    audioInstance.play().then(() => {
      if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
      updatePlaybackToggleButtons(true);
      updateMiniPlayerUi();
    }).catch(e => console.log('[AudioPlayer] Play blocked:', e));
  } else {
    audioInstance.pause();
    if (btn) btn.innerHTML = '<i class="fa-solid fa-play" style="margin-left: 4px;"></i>';
    updatePlaybackToggleButtons(false);
    updateMiniPlayerUi();
    // 저장은 onpause 핸들러에서 단일 경로로 처리한다.
  }
}

export function playPrevTrack() {
  if (!currentAudiobookData || !currentAudiobookData.tracks) return;
  if (currentTrackIndex > 0) {
    saveProgress(false, { useBeacon: false, force: true });
    currentTrackIndex--;
    openAudioPlayerModal(currentAudiobookData, currentAudiobookData.tracks[currentTrackIndex].id, 0, { viewMode: currentAudioPlayerViewMode || 'mini' });
  } else {
    audioInstance.currentTime = 0;
    updateMiniPlayerUi();
  }
}

export function playNextTrack() {
  if (!currentAudiobookData || !currentAudiobookData.tracks) return;
  if (currentTrackIndex < currentAudiobookData.tracks.length - 1) {
    saveProgress(false, { useBeacon: false, force: true });
    currentTrackIndex++;
    openAudioPlayerModal(currentAudiobookData, currentAudiobookData.tracks[currentTrackIndex].id, 0, { viewMode: currentAudioPlayerViewMode || 'mini' });
  }
}

export function audioPlayerSkip(seconds = 15) {
  if (!audioInstance) return;
  const effDur = getEffectiveTrackDuration();
  const maxTime = effDur > 0 ? effDur : (Number.isFinite(audioInstance.duration) ? audioInstance.duration : 0);
  const targetTime = Math.max(0, audioInstance.currentTime + seconds);
  audioInstance.currentTime = maxTime > 0 ? Math.min(maxTime, targetTime) : targetTime;
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
      <div data-role="audio-chapter-track" data-track-id="${t.id}" style="display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1rem; border-radius: 12px; cursor: pointer; transition: all 0.2s; ${activeStyle}">
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
  openAudioPlayerModal(currentAudiobookData, trackId, 0, { viewMode: currentAudioPlayerViewMode || 'full' });
  toggleAudioChapterDrawer();
}

export function toggleVolumePopover() {
  const popover = document.getElementById('audio-volume-popover');
  if (popover) {
    popover.style.display = popover.style.display === 'none' ? 'block' : 'none';
  }
}

export function setAudioVolume(val) {
  const volume = playbackEngine.setVolume(audioInstance, val);

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

function saveProgress(isCompleted = false, options = {}) {
  return progressSync.saveProgress(isCompleted, options);
}

function scheduleProgressSnapshot() {
  progressSync.scheduleProgressSnapshot();
}

function maybeAutoSaveProgress() {
  progressSync.maybeAutoSaveProgress();
}

function saveProgressInternal(isCompleted = false, options = {}) {
  return progressSync.saveProgressInternal(isCompleted, options);
}

function formatTime(sec) {
  if (!sec || !Number.isFinite(sec) || sec < 0) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function initMediaSession(meta, track) {
  playbackEngine.initMediaSession(meta, track, {
    onPlay: () => toggleAudioPlay(true),
    onPause: () => toggleAudioPlay(false),
    onSeekBackward: (details) => audioPlayerSkip(-(details.seekOffset ?? 15)),
    onSeekForward: (details) => audioPlayerSkip(details.seekOffset ?? 15),
    onPrevTrack: () => playPrevTrack(),
    onNextTrack: () => playNextTrack(),
    onSeekTo: (details) => {
      if (audioInstance && details.seekTime != null) {
        audioInstance.currentTime = details.seekTime;
      }
    }
  });
}

registerAudioPlayerPublicApi({
  openAudioPlayer,
  openAudioPlayerModal,
  closeAudioPlayerModal,
  toggleAudioBookmark,
  toggleAudioFullscreen,
  expandAudioPlayerModal,
  stopAndHideAudioPlayer,
  applyAudioMiniPlayerMode,
  toggleAudioPlay,
  playPrevTrack,
  playNextTrack,
  audioPlayerSkip,
  cycleAudioSpeed,
  toggleAudioChapterDrawer,
  selectChapterTrack,
  toggleVolumePopover,
  setAudioVolume,
  cycleSleepTimer
});

function flushAudioProgressForLifecycle(useBeacon = false) {
  progressSync.flushAudioProgressForLifecycle(useBeacon);
}

initAudioLifecycleAndShortcuts({
  isModalOpen: () => {
    const modal = document.getElementById('audio-player-modal');
    return !!(modal && modal.style.display === 'block');
  },
  isAudioActive: () => !!(audioInstance && !audioInstance.paused),
  onEscape: () => closeAudioPlayerModal(),
  onTogglePlay: () => toggleAudioPlay(),
  onSkipBackward: () => audioPlayerSkip(-15),
  onSkipForward: () => audioPlayerSkip(15),
  onPageHide: () => flushAudioProgressForLifecycle(true),
  onBeforeUnload: () => flushAudioProgressForLifecycle(true),
  onVisibilityHidden: () => {
    // 화면 잠금/탭 전환 시 진행도 즉시 저장
    flushAudioProgressForLifecycle(true);
  },
  onVisibilityVisible: () => {
    // iOS Safari는 화면 잠금 시 AudioContext를 강제 suspend 처리함.
    // 화면 복귀 시 명시적으로 resume하지 않으면 소리가 끊긴 채 유지됨.
    playbackEngine.ensureAudioContextResumed();
  }
});
