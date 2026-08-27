(function () {
  const LOG_PREFIX = '[Spotify-Mood-Plugin]';
  let currentMoodKey = null;
  let currentQuery = null;
  let currentKind = 'playlist';
  let currentMine = false;

  function buildUrl(params) {
    // Development Mode(Extended Quota Mode 미승인) Spotify 앱은 검색 limit이 10을 넘으면
    // 타입 무관하게 400 "Invalid limit"을 반환하므로 10으로 고정한다.
    const search = new URLSearchParams({ type: 'general', limit: '10', ...params });
    return '/api/media/dashboard/widgets/spotify_mood/data?' + search.toString();
  }

  function callPluginAction(actionId, context, popup) {
    return fetch('/api/media/context-menu/book/plugins/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'general', plugin_id: 'spotify_mood', action_id: actionId, context: context || {} }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.open_url && popup) {
          popup.location.href = data.open_url;
        } else if (popup) {
          popup.close();
        }
        return data;
      })
      .catch((err) => {
        if (popup) popup.close();
        throw err;
      });
  }

  function updateConnectionUI(connected) {
    const connectBtn = document.getElementById('sm-connect-btn');
    const disconnectBtn = document.getElementById('sm-disconnect-btn');
    const myPlaylistsBtn = document.getElementById('sm-my-playlists-btn');
    if (!connectBtn || !disconnectBtn || !myPlaylistsBtn) return;
    connectBtn.style.display = connected ? 'none' : 'inline-flex';
    disconnectBtn.style.display = connected ? 'inline-flex' : 'none';
    myPlaylistsBtn.style.display = connected ? 'inline-flex' : 'none';
    myPlaylistsBtn.classList.toggle('active', connected && currentMine);
  }

  function renderMoodPicker(moods, activeKey) {
    const picker = document.getElementById('sm-mood-picker');
    if (!picker) return;
    picker.innerHTML = '';
    (moods || []).forEach((mood) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'sm-mood-chip' + (mood.key === activeKey ? ' active' : '');
      chip.textContent = mood.label;
      chip.addEventListener('click', () => {
        currentQuery = null;
        currentMine = false;
        currentMoodKey = mood.key;
        document.getElementById('sm-search-input').value = '';
        document.getElementById('sm-clear-search-btn').style.display = 'none';
        document.getElementById('sm-my-playlists-btn').classList.remove('active');
        fetchData();
      });
      picker.appendChild(chip);
    });
  }

  function renderGrid(items) {
    const grid = document.getElementById('sm-grid');
    const status = document.getElementById('sm-status');
    if (!grid || !status) return;
    grid.innerHTML = '';

    if (!items || items.length === 0) {
      status.textContent = '표시할 결과가 없습니다.';
      status.style.display = 'block';
      return;
    }
    status.style.display = 'none';

    items.forEach((item) => {
      const card = document.createElement('div');
      card.className = 'sm-card';

      const coverBox = document.createElement('div');
      coverBox.className = 'sm-card-cover';
      if (item.cover) {
        const img = document.createElement('img');
        img.src = item.cover;
        img.alt = item.title || '';
        img.loading = 'lazy';
        coverBox.appendChild(img);
      } else {
        const icon = document.createElement('i');
        icon.className = 'fa-brands fa-spotify';
        coverBox.appendChild(icon);
      }

      if (item.spotify_id && item.kind) {
        const playBtn = document.createElement('button');
        playBtn.type = 'button';
        playBtn.className = 'sm-card-play';
        playBtn.title = '바로 재생';
        playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
        playBtn.addEventListener('click', () => openPlayer(item.kind, item.spotify_id));
        coverBox.appendChild(playBtn);
      }
      card.appendChild(coverBox);

      const body = document.createElement('div');
      body.className = 'sm-card-body';

      const title = document.createElement('a');
      title.className = 'sm-card-title';
      title.textContent = item.title || '';
      title.title = '스포티파이에서 열기: ' + (item.title || '');
      title.href = item.link || '#';
      title.target = '_blank';
      title.rel = 'noopener noreferrer';
      body.appendChild(title);

      const sub = document.createElement('span');
      sub.className = 'sm-card-sub';
      sub.textContent = item.author || '';
      sub.title = item.author || '';
      body.appendChild(sub);

      const meta = document.createElement('span');
      meta.className = 'sm-card-meta';
      meta.textContent = item.pubDate || '';
      body.appendChild(meta);

      card.appendChild(body);
      grid.appendChild(card);
    });
  }

  // 카테고리 탭을 벗어나면 core가 #library-plugin-custom-view의 innerHTML을 통째로 갈아치워서
  // 그 안에 있던 iframe도 함께 사라진다 (재생이 끊김). 그래서 재생 패널은 플러그인 컨테이너
  // 밖(document.body)에 붙여, 다른 탭으로 이동해도 음악이 계속 흐르게 한다.
  function ensureFloatingPlayer() {
    let host = document.getElementById('spotify-mood-floating-player');
    if (host) return host;

    if (!document.getElementById('spotify-mood-floating-player-style')) {
      const style = document.createElement('style');
      style.id = 'spotify-mood-floating-player-style';
      style.textContent = `
        #spotify-mood-floating-player {
          position: fixed;
          right: 1rem;
          bottom: 1rem;
          width: 320px;
          max-width: calc(100vw - 2rem);
          background: var(--app-bg-card, #1e1e2e);
          border: 1px solid var(--app-border, #333);
          border-radius: 10px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.35);
          z-index: 999999;
          overflow: hidden;
        }
        #spotify-mood-floating-player .smfp-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0.4rem 0.6rem;
          background: var(--app-bg-sidebar, #181825);
          color: var(--app-text-primary, #eee);
          font-size: 0.8rem;
          font-weight: 600;
        }
        #spotify-mood-floating-player .smfp-close {
          background: none;
          border: none;
          color: inherit;
          cursor: pointer;
          font-size: 1rem;
          line-height: 1;
          padding: 0.2rem 0.4rem;
        }
        #spotify-mood-floating-player iframe {
          display: block;
          border: none;
        }
      `;
      document.head.appendChild(style);
    }

    host = document.createElement('div');
    host.id = 'spotify-mood-floating-player';
    host.innerHTML = `
      <div class="smfp-header">
        <span>🎧 Spotify</span>
        <button type="button" class="smfp-close" title="닫기">✕</button>
      </div>
      <iframe id="spotify-mood-floating-frame" width="100%" height="152" frameborder="0"
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
    `;
    document.body.appendChild(host);
    host.querySelector('.smfp-close').addEventListener('click', () => {
      const frame = document.getElementById('spotify-mood-floating-frame');
      if (frame) frame.src = '';
      host.remove();
    });
    return host;
  }

  function openPlayer(kind, spotifyId) {
    ensureFloatingPlayer();
    const frame = document.getElementById('spotify-mood-floating-frame');
    if (frame) {
      frame.src = `https://open.spotify.com/embed/${kind}/${spotifyId}?utm_source=generator&theme=0`;
    }
  }

  function fetchData() {
    const status = document.getElementById('sm-status');
    const moodLabel = document.getElementById('sm-mood-label');
    if (!status || !moodLabel) return;

    status.textContent = '불러오는 중...';
    status.style.display = 'block';
    document.getElementById('sm-grid').innerHTML = '';
    // 재생 중인 플로팅 플레이어는 무드/검색 새로고침과 무관하게 계속 재생되도록 여기서 건드리지 않는다.

    const params = {};
    if (currentMine) {
      params.mine = '1';
    } else if (currentQuery) {
      params.q = currentQuery;
      params.kind = currentKind;
    } else if (currentMoodKey) {
      params.mood = currentMoodKey;
    }

    const url = buildUrl(params);
    console.log(LOG_PREFIX, '요청:', url);

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        if (typeof data.connected === 'boolean') {
          updateConnectionUI(data.connected);
        }

        if (!data.success) {
          moodLabel.textContent = data.error || '데이터를 불러오지 못했습니다.';
          status.textContent = data.error || '오류가 발생했습니다.';
          status.style.display = 'block';
          return;
        }

        moodLabel.textContent = data.mood || '';
        if (!currentQuery && !currentMine) {
          currentMoodKey = data.mood_key || currentMoodKey;
          renderMoodPicker(data.moods, currentMoodKey);
        }
        renderGrid(data.items);
      })
      .catch((err) => {
        console.error(LOG_PREFIX, '요청 실패:', err);
        moodLabel.textContent = '서버 연결 오류';
        status.textContent = '서버 연결 오류';
        status.style.display = 'block';
      });
  }

  const refreshBtn = document.getElementById('sm-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', fetchData);
  }

  const searchForm = document.getElementById('sm-search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('sm-search-input');
      const kindSelect = document.getElementById('sm-kind-select');
      const q = (input.value || '').trim();
      if (!q) return;
      currentQuery = q;
      currentMine = false;
      currentKind = kindSelect.value || 'playlist';
      document.getElementById('sm-clear-search-btn').style.display = 'inline-flex';
      document.getElementById('sm-my-playlists-btn').classList.remove('active');
      fetchData();
    });
  }

  const clearBtn = document.getElementById('sm-clear-search-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      currentQuery = null;
      document.getElementById('sm-search-input').value = '';
      clearBtn.style.display = 'none';
      fetchData();
    });
  }

  const myPlaylistsBtn = document.getElementById('sm-my-playlists-btn');
  if (myPlaylistsBtn) {
    myPlaylistsBtn.addEventListener('click', () => {
      currentMine = !currentMine;
      if (currentMine) {
        currentQuery = null;
        document.getElementById('sm-search-input').value = '';
        document.getElementById('sm-clear-search-btn').style.display = 'none';
      }
      myPlaylistsBtn.classList.toggle('active', currentMine);
      fetchData();
    });
  }

  const connectBtn = document.getElementById('sm-connect-btn');
  if (connectBtn) {
    connectBtn.addEventListener('click', () => {
      // 팝업 차단을 피하려면 비동기 응답 전, 클릭 이벤트 시점에 미리 빈 창을 열어둬야 한다
      // (static/js/book_context_menu.js와 동일한 패턴).
      const popup = window.open('', '_blank');
      if (popup) {
        popup.document.write('<!doctype html><title>Spotify 연결 중...</title><p>Spotify 로그인 화면으로 이동합니다...</p>');
        popup.document.close();
      }
      callPluginAction('spotify_oauth_start', {}, popup).then((data) => {
        if (!data.success) {
          alert(data.error || 'Spotify 연결을 시작하지 못했습니다.');
        }
      });
    });
  }

  const disconnectBtn = document.getElementById('sm-disconnect-btn');
  if (disconnectBtn) {
    disconnectBtn.addEventListener('click', () => {
      if (!confirm('Spotify 계정 연결을 해제할까요? (내 플레이리스트를 더 이상 볼 수 없습니다)')) return;
      callPluginAction('spotify_oauth_disconnect', {}, null).then((data) => {
        if (data.success) {
          currentMine = false;
          fetchData();
        } else {
          alert(data.error || '연결 해제에 실패했습니다.');
        }
      });
    });
  }

  fetchData();
})();
