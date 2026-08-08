// progress_sync.js - 오디오 진행도 저장/자동 저장/라이프사이클 플러시 전담

export function createAudioProgressSync(deps) {
  const {
    getAudioInstance,
    getAudiobookData,
    getCurrentTrackIndex,
    getPlaybackRate,
    onProgressSaved
  } = deps;

  const AUTO_SAVE_MS = 10000;
  let lastObservedProgressKey = '';
  let lastFlushedProgressKey = '';
  let lastAutoSaveAtMs = 0;

  function resetProgressTracking() {
    lastObservedProgressKey = '';
    lastFlushedProgressKey = '';
    lastAutoSaveAtMs = 0;
  }

  function buildProgressPayload(isCompleted = false) {
    const audioInstance = getAudioInstance();
    const audiobookData = getAudiobookData();
    if (!audiobookData || !audiobookData.meta || !audioInstance) return null;

    const tracks = audiobookData.tracks || [];
    const track = tracks[getCurrentTrackIndex()];
    if (!track) return null;

    return {
      current_track_id: track.id,
      current_time: audioInstance.currentTime || 0,
      playback_rate: getPlaybackRate(),
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

    const audiobookData = getAudiobookData();
    const meta = audiobookData.meta;
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
    }).then(async (response) => {
      if (response.ok) {
        try {
          const result = await response.clone().json();
          if (typeof onProgressSaved === 'function') {
            onProgressSaved(result, payload);
          }
          if (Number(result.track_is_completed) === 1 && result.track_id) {
            document.dispatchEvent(new CustomEvent('audiobook-track-completed', {
              detail: { trackId: Number(result.track_id) }
            }));
          }
        } catch (e) {
          // 진행 저장 성공 자체에는 영향을 주지 않는다.
        }
      }
      return response;
    }).catch(e => console.warn('[AudioPlayer] Progress save failed:', e));
  }

  function saveProgress(isCompleted = false, options = {}) {
    const merged = {
      useBeacon: false,
      force: false,
      ...(options || {})
    };
    return saveProgressInternal(isCompleted, merged);
  }

  function scheduleProgressSnapshot() {
    const payload = buildProgressPayload(false);
    if (!payload) return;
    lastObservedProgressKey = buildProgressKey(payload);
  }

  function maybeAutoSaveProgress() {
    const audioInstance = getAudioInstance();
    if (!audioInstance || audioInstance.paused || audioInstance.ended) return;

    const now = Date.now();
    if ((now - lastAutoSaveAtMs) < AUTO_SAVE_MS) return;

    lastAutoSaveAtMs = now;
    saveProgressInternal(false, { useBeacon: false, force: false });
  }

  function flushAudioProgressForLifecycle(useBeacon = false) {
    const audioInstance = getAudioInstance();
    const audiobookData = getAudiobookData();
    if (!audioInstance || !audiobookData) return;
    saveProgressInternal(false, { useBeacon, force: true });
  }

  return {
    resetProgressTracking,
    saveProgress,
    saveProgressInternal,
    scheduleProgressSnapshot,
    maybeAutoSaveProgress,
    flushAudioProgressForLifecycle
  };
}
