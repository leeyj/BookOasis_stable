// lyrics_panel.js - 음악 모드 가사 패널 (커버 자리를 대신해 보여 준다)
//
// 가사는 서버가 album.yaml → 곡 파일 태그 순으로 찾아 준다(/api/media/audiobooks/<aid>/tracks/<tid>/lyrics).
// 싱크 가사(LRC)면 재생 위치에 맞는 줄을 강조하고 가운데로 스크롤하며, 줄을 누르면 그 시각으로 이동한다.
// 가사 텍스트는 파일에서 온 임의 문자열이라 textContent로만 넣는다.

const LYRICS_OPEN_KEY = 'bookoasis.music.lyrics';

function readOpenPref() {
  try {
    return window.localStorage.getItem(LYRICS_OPEN_KEY) === '1';
  } catch (e) {
    return false;
  }
}

function writeOpenPref(open) {
  try {
    window.localStorage.setItem(LYRICS_OPEN_KEY, open ? '1' : '0');
  } catch (e) {}
}

// 시각 순으로 정렬된 줄 목록에서 time 이하인 마지막 줄 (없으면 -1)
export function findActiveLyricIndex(lines, time) {
  let lo = 0;
  let hi = lines.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (lines[mid].t <= time) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

export function createLyricsPanel({ onSeek, emptyLabel = '가사가 없습니다', loadingLabel = '가사를 불러오는 중…' }) {
  const cache = new Map(); // trackKey -> Promise<lyrics>
  let isOpen = readOpenPref();
  let currentKey = null;
  let currentLyrics = null;
  let activeIndex = -1;

  const panel = () => document.getElementById('audio-player-lyrics');
  const modal = () => document.getElementById('audio-player-modal');

  function applyOpenState(isMusic) {
    const open = isMusic && isOpen;
    modal()?.classList.toggle('is-lyrics-open', open);
    const btn = document.getElementById('btn-audio-lyrics');
    if (btn) btn.setAttribute('aria-pressed', open ? 'true' : 'false');
    return open;
  }

  function renderMessage(text) {
    const el = panel();
    if (!el) return;
    el.classList.remove('is-synced');
    el.replaceChildren();
    const p = document.createElement('p');
    p.className = 'audio-lyrics-empty';
    p.textContent = text;
    el.appendChild(p);
  }

  function render(lyrics) {
    const el = panel();
    if (!el) return;
    activeIndex = -1;
    if (!lyrics || !lyrics.lines || lyrics.lines.length === 0) {
      renderMessage(emptyLabel);
      return;
    }
    el.classList.toggle('is-synced', !!lyrics.synced);
    el.replaceChildren(...lyrics.lines.map((line, index) => {
      const p = document.createElement('p');
      p.className = 'audio-lyrics-line';
      p.textContent = line.text || ' ';
      if (lyrics.synced) {
        p.dataset.index = String(index);
        p.addEventListener('click', () => onSeek && onSeek(line.t));
      }
      return p;
    }));
    el.scrollTop = 0;
  }

  function fetchLyrics(meta, track) {
    const key = `${meta.id}:${track.id}`;
    if (!cache.has(key)) {
      cache.set(key, fetch(`/api/media/audiobooks/${meta.id}/tracks/${track.id}/lyrics`)
        .then((res) => res.json())
        .then((data) => (data && data.success ? data : null))
        .catch(() => {
          cache.delete(key);
          return null;
        }));
    }
    return cache.get(key);
  }

  async function show(meta, track) {
    const key = `${meta.id}:${track.id}`;
    currentKey = key;
    currentLyrics = null;
    renderMessage(loadingLabel);
    const lyrics = await fetchLyrics(meta, track);
    if (currentKey !== key) return; // 그사이 곡이 바뀜
    currentLyrics = lyrics;
    render(lyrics);
  }

  let currentMeta = null;
  let currentTrack = null;

  return {
    // 곡이 바뀔 때마다 부른다. 패널이 열려 있을 때만 가사를 불러온다.
    onTrackChange(meta, track) {
      currentMeta = meta;
      currentTrack = track;
      const isMusic = !!(meta && meta.is_music && track);
      currentKey = null;
      currentLyrics = null;
      if (applyOpenState(isMusic)) show(meta, track);
    },
    toggle() {
      isOpen = !isOpen;
      writeOpenPref(isOpen);
      const isMusic = !!(currentMeta && currentMeta.is_music && currentTrack);
      if (applyOpenState(isMusic) && currentKey !== `${currentMeta.id}:${currentTrack.id}`) {
        show(currentMeta, currentTrack);
      }
    },
    // timeupdate마다 부른다. 싱크 가사일 때만 강조/스크롤한다.
    sync(time) {
      if (!isOpen || !currentLyrics || !currentLyrics.synced) return;
      const index = findActiveLyricIndex(currentLyrics.lines, time);
      if (index === activeIndex) return;
      const el = panel();
      if (!el) return;
      el.querySelector('.audio-lyrics-line.is-active')?.classList.remove('is-active');
      activeIndex = index;
      if (index < 0) return;
      const line = el.querySelector(`.audio-lyrics-line[data-index="${index}"]`);
      if (!line) return;
      line.classList.add('is-active');
      el.scrollTo({ top: line.offsetTop - el.clientHeight / 2 + line.clientHeight / 2, behavior: 'smooth' });
    }
  };
}
