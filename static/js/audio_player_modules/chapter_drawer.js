// chapter_drawer.js - 오디오 챕터(트랙) 드로어 리스트 렌더링/전환 전담

export function createChapterDrawer(deps) {
  const {
    getAudiobookData,
    getCurrentTrackIndex,
    getViewMode,
    openTrack
  } = deps;

  function renderChapterList() {
    const container = document.getElementById('audio-chapter-list');
    const audiobookData = getAudiobookData();
    if (!container || !audiobookData || !audiobookData.tracks) return;

    const tracks = audiobookData.tracks;
    const currentTrackIndex = getCurrentTrackIndex();
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

  function toggleAudioChapterDrawer() {
    const drawer = document.getElementById('audio-chapter-drawer');
    if (!drawer) return;
    const isHidden = drawer.style.transform === 'translateY(100%)' || !drawer.style.transform;
    drawer.style.transform = isHidden ? 'translateY(0%)' : 'translateY(100%)';
  }

  function selectChapterTrack(trackId) {
    const audiobookData = getAudiobookData();
    if (!audiobookData) return;
    openTrack(trackId, 0, { viewMode: getViewMode() || 'full' });
    toggleAudioChapterDrawer();
  }

  return { renderChapterList, toggleAudioChapterDrawer, selectChapterTrack };
}
