(function () {
  // 이 파일은 core가 `new Function('pluginId', 'container', bundle.js)`로 감싸서
  // 실행한다 - 즉 'pluginId'와 'container'는 이미 파라미터로 주어진 전역 스코프
  // 변수이며, 아래 IIFE는 그 값을 그대로 클로저로 캡처해서 쓴다.
  const LOG_PREFIX = '[Reading-Mate-Plugin]';
  const DATA_URL = '/api/media/dashboard/widgets/reading_mate/data';

  // 채팅 히스토리는 이 클로저(모듈 스코프 변수)에만 존재한다 - 탭을 옮겨도
  // 살아있지만, 페이지를 새로고침하면 사라진다. 서버에 영구 저장하지 않는 이유는
  // 이 샘플이 "마운트 지속" 패턴 자체를 보여주는 데 집중하기 위함이다. 대화를
  // 새로고침 후에도 이어가고 싶다면 sessionStorage에 history 배열을 그대로
  // 저장/복원하면 된다.
  let history = [];
  let characterName = null;

  // ------------------------------------------------------------------
  // 1) 마스코트 전용 CSS를 document.head에 직접 주입한다.
  //    이유: style.css는 카테고리 탭 컨테이너 안에서만 살아있고, 다른 탭으로
  //    이동하면 코어가 그 컨테이너를 통째로 갈아치우면서 함께 사라진다.
  //    마스코트는 document.body에 붙어 탭을 넘어 계속 떠 있어야 하므로,
  //    스타일도 독립적으로 살려둔다 (spotify_mood 샘플의 플로팅 플레이어와 동일한 트릭).
  // ------------------------------------------------------------------
  function ensureMascotStyle() {
    if (document.getElementById('reading-mate-mascot-style')) return;
    const style = document.createElement('style');
    style.id = 'reading-mate-mascot-style';
    style.textContent = `
      #reading-mate-mascot {
        position: fixed;
        right: 1.25rem;
        bottom: 1.25rem;
        z-index: 999999;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        font-family: inherit;
      }
      #reading-mate-mascot .rm-avatar-btn {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        border: 2px solid var(--app-accent, #7c5cff);
        background: var(--app-bg-card, #1e1e2e);
        cursor: pointer;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.8rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        padding: 0;
      }
      #reading-mate-mascot .rm-avatar-btn img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      #reading-mate-mascot .rm-chat-panel {
        width: 320px;
        max-width: calc(100vw - 2rem);
        max-height: 420px;
        margin-bottom: 0.6rem;
        display: none;
        flex-direction: column;
        background: var(--app-bg-card, #1e1e2e);
        border: 1px solid var(--app-border, #333);
        border-radius: 12px;
        box-shadow: 0 10px 28px rgba(0,0,0,0.4);
        overflow: hidden;
      }
      #reading-mate-mascot .rm-chat-panel.open { display: flex; }
      #reading-mate-mascot .rm-chat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.55rem 0.75rem;
        background: var(--app-bg-sidebar, #181825);
        color: var(--app-text-primary, #eee);
        font-size: 0.85rem;
        font-weight: 600;
      }
      #reading-mate-mascot .rm-chat-close {
        background: none;
        border: none;
        color: inherit;
        cursor: pointer;
        font-size: 1rem;
        line-height: 1;
      }
      #reading-mate-mascot .rm-chat-body {
        flex: 1;
        overflow-y: auto;
        padding: 0.6rem 0.7rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        font-size: 0.85rem;
      }
      #reading-mate-mascot .rm-bubble {
        max-width: 85%;
        padding: 0.5rem 0.7rem;
        border-radius: 10px;
        line-height: 1.4;
        white-space: pre-wrap;
      }
      #reading-mate-mascot .rm-bubble.assistant {
        align-self: flex-start;
        background: var(--app-bg-sidebar, #181825);
        color: var(--app-text-primary, #eee);
      }
      #reading-mate-mascot .rm-bubble.user {
        align-self: flex-end;
        background: var(--app-accent, #7c5cff);
        color: #fff;
      }
      #reading-mate-mascot .rm-bubble.pending { opacity: 0.6; }
      #reading-mate-mascot .rm-chat-form {
        display: flex;
        gap: 0.4rem;
        padding: 0.6rem;
        border-top: 1px solid var(--app-border, #333);
      }
      #reading-mate-mascot .rm-chat-form input {
        flex: 1;
        min-width: 0;
        padding: 0.45rem 0.6rem;
        border-radius: 8px;
        border: 1px solid var(--app-border, #333);
        background: var(--app-bg-main, #11111b);
        color: var(--app-text-primary, #eee);
      }
      #reading-mate-mascot .rm-chat-form button {
        border: none;
        border-radius: 8px;
        background: var(--app-accent, #7c5cff);
        color: #fff;
        padding: 0 0.8rem;
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  // ------------------------------------------------------------------
  // 2) 마스코트 DOM을 document.body에 (컨테이너 밖에) 만든다 - 이미 있으면 재사용.
  // ------------------------------------------------------------------
  function ensureMascot() {
    ensureMascotStyle();

    let host = document.getElementById('reading-mate-mascot');
    if (host) return host;

    host = document.createElement('div');
    host.id = 'reading-mate-mascot';
    host.innerHTML = `
      <div class="rm-chat-panel" id="rm-chat-panel">
        <div class="rm-chat-header">
          <span id="rm-chat-title">독서메이트</span>
          <button type="button" class="rm-chat-close" id="rm-chat-close" title="닫기">&times;</button>
        </div>
        <div class="rm-chat-body" id="rm-chat-body"></div>
        <form class="rm-chat-form" id="rm-chat-form">
          <input id="rm-chat-input" type="text" placeholder="어떤 책이 읽고 싶은지 물어보세요..." autocomplete="off">
          <button type="submit"><i class="fa-solid fa-paper-plane"></i></button>
        </form>
      </div>
      <button type="button" class="rm-avatar-btn" id="rm-avatar-btn" title="독서메이트에게 물어보기">
        <span id="rm-avatar-fallback">📚</span>
      </button>
    `;
    document.body.appendChild(host);

    const avatarBtn = host.querySelector('#rm-avatar-btn');
    const panel = host.querySelector('#rm-chat-panel');
    const closeBtn = host.querySelector('#rm-chat-close');
    const form = host.querySelector('#rm-chat-form');
    const input = host.querySelector('#rm-chat-input');

    avatarBtn.addEventListener('click', () => {
      panel.classList.toggle('open');
      if (panel.classList.contains('open') && history.length === 0) {
        fetchReply(''); // 첫 오픈 시 인사말 요청
      }
    });
    closeBtn.addEventListener('click', () => panel.classList.remove('open'));

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const text = (input.value || '').trim();
      if (!text) return;
      input.value = '';
      sendMessage(text);
    });

    return host;
  }

  function appendBubble(role, text, pending) {
    const body = document.getElementById('rm-chat-body');
    if (!body) return null;
    const bubble = document.createElement('div');
    bubble.className = 'rm-bubble ' + role + (pending ? ' pending' : '');
    bubble.textContent = text;
    body.appendChild(bubble);
    body.scrollTop = body.scrollHeight;
    return bubble;
  }

  function setAvatarImage(url) {
    const fallback = document.getElementById('rm-avatar-fallback');
    if (!url || !fallback || fallback.dataset.applied) return;
    fallback.dataset.applied = '1';
    const img = document.createElement('img');
    img.src = url;
    img.alt = characterName || '독서메이트';
    fallback.replaceWith(img);
  }

  function fetchReply(userText) {
    const params = new URLSearchParams({
      message: userText || '',
      history: JSON.stringify(history),
    });

    let pendingBubble = null;
    if (userText) {
      pendingBubble = appendBubble('assistant', '생각 중...', true);
    }

    fetch(DATA_URL + '?' + params.toString())
      .then((res) => res.json())
      .then((data) => {
        if (pendingBubble) pendingBubble.remove();

        if (!data.success) {
          appendBubble('assistant', data.error || '오류가 발생했어요.');
          return;
        }

        if (data.character_name) {
          characterName = data.character_name;
          const title = document.getElementById('rm-chat-title');
          if (title) title.textContent = characterName;
        }
        if (data.character_image_url) {
          setAvatarImage(data.character_image_url);
        }

        appendBubble('assistant', data.reply || '...');
        if (userText) {
          history.push({ role: 'user', content: userText });
        }
        history.push({ role: 'assistant', content: data.reply || '' });
      })
      .catch((err) => {
        if (pendingBubble) pendingBubble.remove();
        console.error(LOG_PREFIX, '요청 실패:', err);
        appendBubble('assistant', '서버에 연결할 수 없어요.');
      });
  }

  function sendMessage(text) {
    appendBubble('user', text);
    fetchReply(text);
  }

  // ------------------------------------------------------------------
  // 3) 카테고리 탭(설정/안내 페이지) 쪽 상태 표시 - container 안쪽만 건드린다.
  // ------------------------------------------------------------------
  function renderTabStatus() {
    const status = container.querySelector('#rm-status');
    if (!status) return;
    const host = document.getElementById('reading-mate-mascot');
    status.textContent = host
      ? '마스코트가 우측 하단에 떠 있어요. 아무 곳이나 이동해도 사라지지 않아요.'
      : '마스코트를 준비하는 중...';
  }

  ensureMascot();
  renderTabStatus();
})();
