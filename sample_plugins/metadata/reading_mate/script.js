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
      /* 3D(VRM) 모드: 캐릭터가 오른쪽에 서 있고 채팅 패널은 그 왼쪽에 열린다 */
      #reading-mate-mascot .rm-stage { display: none; width: 180px; height: 260px; cursor: pointer; }
      #reading-mate-mascot .rm-stage canvas { width: 100%; height: 100%; display: block; }
      #reading-mate-mascot.rm-3d { flex-direction: row; align-items: flex-end; right: 0.5rem; bottom: 0; }
      #reading-mate-mascot.rm-3d .rm-stage { display: block; }
      #reading-mate-mascot.rm-3d .rm-avatar-btn { display: none; }
      #reading-mate-mascot.rm-3d .rm-chat-panel { margin: 0 0 1.25rem 0; }
      #reading-mate-mascot.rm-reading { display: none !important; }
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
      <div class="rm-stage" id="rm-stage" title="독서메이트에게 물어보기"></div>
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

    const togglePanel = () => {
      panel.classList.toggle('open');
      if (panel.classList.contains('open') && history.length === 0) {
        fetchReply(''); // 첫 오픈 시 인사말 요청
      }
    };
    avatarBtn.addEventListener('click', togglePanel);
    host.querySelector('#rm-stage').addEventListener('click', togglePanel);
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
      mate3d.think();
    }

    fetch(DATA_URL + '?' + params.toString())
      .then((res) => res.json())
      .then((data) => {
        if (pendingBubble) pendingBubble.remove();

        if (!data.success) {
          appendBubble('assistant', data.error || '오류가 발생했어요.');
          mate3d.speak('', 'sad');
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
        mate3d.speak(data.reply || '');
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

  // ------------------------------------------------------------------
  // 4) 3D 캐릭터(VRM) - 설정에서 켰을 때만 로드한다.
  //    이 파일은 new Function으로 실행되는 일반 스크립트라 `import` 문을 못 쓴다.
  //    대신 동적 import()로 three.js / three-vrm 을 CDN(esm.sh)에서 불러온다.
  //    ?deps=three@... 로 three 버전을 고정해야 three 인스턴스가 하나로 유지된다.
  //    실패하거나 좁은 화면이면 기존 2D 아바타가 그대로 남는다.
  // ------------------------------------------------------------------
  const THREE_VER = '0.180.0';
  const VRM_VER = '3.5.5';
  const NARROW_QUERY = window.matchMedia('(max-width: 640px)');

  const mate3d = {
    vrm: null, talk: null, thinking: false, exprUntil: 0,
    think() {
      if (!this.vrm) return;
      this.thinking = true;
      this.setExpr('relaxed', 0.5);
    },
    speak(text, expr) {
      if (!this.vrm) return;
      this.thinking = false;
      this.setExpr(expr || 'happy', 1, 2500);
      this.talk = text ? { text: text.slice(0, 200), i: 0, acc: 0, cur: null } : null;
    },
    exprName(name) {
      const em = this.vrm.expressionManager;
      // VRM 0.x 의 '놀람'은 표준 프리셋이 없어 커스텀 'Surprised'로 들어오는 모델이 많다
      const aliases = { surprised: ['surprised', 'Surprised'] }[name] || [name];
      return aliases.find((k) => em.getExpression(k)) || null;
    },
    setExpr(name, weight, holdMs) {
      const em = this.vrm && this.vrm.expressionManager;
      if (!em) return;
      ['happy', 'relaxed', 'surprised', 'sad', 'angry'].forEach((k) => {
        const n = this.exprName(k);
        if (n) em.setValue(n, 0);
      });
      const n = name && name !== 'neutral' ? this.exprName(name) : null;
      if (n) em.setValue(n, weight == null ? 1 : weight);
      this.exprUntil = holdMs ? performance.now() + holdMs : 0;
    },
  };

  // 한글 음절의 중성으로 입 모양(aa/ih/ou/ee/oh)을 고른다. TTS를 붙이면 오디오 볼륨으로 바꾸면 된다.
  function vowelOf(ch) {
    const c = ch.charCodeAt(0);
    if (c >= 0xAC00 && c <= 0xD7A3) {
      const jung = Math.floor((c - 0xAC00) / 28) % 21;
      if ([0, 1, 2, 3, 9, 10, 11].includes(jung)) return 'aa';
      if ([4, 5, 6, 7, 14, 15].includes(jung)) return 'ee';
      if ([8, 12].includes(jung)) return 'oh';
      if ([13, 16, 17, 18].includes(jung)) return 'ou';
      return 'ih';
    }
    if (/[\s.,!?…~]/.test(ch)) return null;
    return ['aa', 'ih', 'ou', 'ee', 'oh'][c % 5];
  }

  function isReading() {
    const viewer = document.getElementById('media-viewer-modal');
    return !!viewer && viewer.style.display === 'flex';
  }

  // 책을 읽는 동안에는 마스코트(2D/3D 모두)를 숨긴다 - 읽기 화면을 가리지 않는다.
  function watchReading(host) {
    const sync = () => host.classList.toggle('rm-reading', isReading());
    const viewer = document.getElementById('media-viewer-modal');
    if (viewer) new MutationObserver(sync).observe(viewer, { attributes: true, attributeFilter: ['style', 'class'] });
    sync();
  }

  async function loadCharacter(host) {
    let info;
    try {
      const res = await fetch(DATA_URL + '?action=character');
      info = await res.json();
    } catch (e) {
      return;
    }
    if (!info || !info.success) return;
    if (info.character_name) {
      characterName = info.character_name;
      const title = document.getElementById('rm-chat-title');
      if (title) title.textContent = characterName;
    }
    if (info.character_image_url) setAvatarImage(info.character_image_url);
    if (!info.character_3d || !info.vrm_url || host.dataset.vrmLoaded) return;
    if (NARROW_QUERY.matches) {
      console.info(LOG_PREFIX, '좁은 화면이라 3D 캐릭터 대신 2D 아바타를 씁니다.');
      return;
    }
    host.dataset.vrmLoaded = 'loading';
    try {
      await mountVrm(host, info.vrm_url, info.vrma_url);
      host.dataset.vrmLoaded = 'ok';
    } catch (e) {
      host.dataset.vrmLoaded = 'failed';
      host.classList.remove('rm-3d');
      console.warn(LOG_PREFIX, '3D 캐릭터 로드 실패 - 2D 아바타로 대체:', e);
    }
  }

  async function mountVrm(host, vrmUrl, vrmaUrl) {
    const dep = '?deps=three@' + THREE_VER;
    const [THREE, { GLTFLoader }, VRMLib, VRMALib] = await Promise.all([
      import('https://esm.sh/three@' + THREE_VER),
      import('https://esm.sh/three@' + THREE_VER + '/examples/jsm/loaders/GLTFLoader.js'),
      import('https://esm.sh/@pixiv/three-vrm@' + VRM_VER + dep),
      import('https://esm.sh/@pixiv/three-vrm-animation@' + VRM_VER + dep),
    ]);
    const { VRMLoaderPlugin, VRMUtils } = VRMLib;
    const { VRMAnimationLoaderPlugin, VRMLookAtQuaternionProxy, createVRMAnimationClip } = VRMALib;

    const loader = new GLTFLoader();
    loader.register((p) => new VRMLoaderPlugin(p));
    loader.register((p) => new VRMAnimationLoaderPlugin(p));
    const gltf = await loader.loadAsync(vrmUrl);
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error('VRM 파일이 아닙니다: ' + vrmUrl);
    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.rotateVRM0(vrm); // VRM 0.x 는 반대쪽을 보고 있어 돌려준다 (1.0이면 아무것도 안 함)
    vrm.scene.traverse((o) => { o.frustumCulled = false; });

    const stage = host.querySelector('#rm-stage');
    const canvas = document.createElement('canvas');
    stage.appendChild(canvas);
    host.classList.add('rm-3d');

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const scene = new THREE.Scene();
    scene.add(vrm.scene);
    const light = new THREE.DirectionalLight(0xffffff, Math.PI * 0.9);
    light.position.set(1, 1, 1);
    scene.add(light, new THREE.AmbientLight(0xffffff, 0.6));
    const camera = new THREE.PerspectiveCamera(24, 180 / 260, 0.1, 20);
    const w = stage.clientWidth || 180;
    const h = stage.clientHeight || 260;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();

    // 머리 높이 기준으로 카메라를 둔다 (모델마다 키가 달라도 비슷한 구도가 되도록)
    vrm.scene.updateMatrixWorld(true);
    const headPos = new THREE.Vector3();
    vrm.humanoid.getNormalizedBoneNode('head').getWorldPosition(headPos);
    const hy = headPos.y;
    camera.position.set(0, hy, hy * 1.9);
    camera.lookAt(0, hy - 0.36, 0);

    // 시선: 마우스를 따라간다
    const lookTarget = new THREE.Object3D();
    camera.add(lookTarget);
    scene.add(camera);
    if (vrm.lookAt) {
      vrm.lookAt.target = lookTarget;
      const proxy = new VRMLookAtQuaternionProxy(vrm.lookAt);
      proxy.name = 'VRMLookAtQuaternionProxy';
      vrm.scene.add(proxy);
    }
    window.addEventListener('pointermove', (e) => {
      const r = canvas.getBoundingClientRect();
      const nx = (e.clientX - (r.left + r.width / 2)) / window.innerWidth * 2;
      const ny = -(e.clientY - (r.top + r.height * 0.2)) / window.innerHeight * 2;
      lookTarget.position.set(nx * 0.8, ny * 0.5, -1);
    }, { passive: true });

    // 대기 동작: VRMA가 있으면 그걸, 없으면 코드로 만든 숨쉬기/흔들림
    let mixer = null;
    if (vrmaUrl) {
      try {
        const g = await loader.loadAsync(vrmaUrl);
        const anim = g.userData.vrmAnimations && g.userData.vrmAnimations[0];
        if (anim) {
          mixer = new THREE.AnimationMixer(vrm.scene);
          mixer.clipAction(createVRMAnimationClip(anim, vrm)).play();
        }
      } catch (e) {
        console.warn(LOG_PREFIX, 'VRMA 로드 실패 - 기본 대기 동작 사용:', e);
      }
    }
    const bone = (n) => vrm.humanoid.getNormalizedBoneNode(n);
    const setRot = (n, x, y, z) => { const o = bone(n); if (o) o.rotation.set(x, y, z); };
    const proceduralIdle = (t) => {
      // T포즈 팔을 내리고, 숨쉬기 + 좌우 흔들림 + 고개 기울임(생각 중이면 더 기울임)
      const b = Math.sin(t * 1.6);
      const sway = Math.sin(t * 0.7);
      setRot('leftUpperArm', 0, 0, -1.2 + b * 0.02);
      setRot('rightUpperArm', 0, 0, 1.2 - b * 0.02);
      setRot('leftLowerArm', 0, -0.25, 0);
      setRot('rightLowerArm', 0, 0.25, 0);
      setRot('spine', b * 0.015, 0, sway * 0.02);
      setRot('chest', b * 0.02, 0, 0);
      setRot('neck', 0, sway * 0.04, 0);
      setRot('head', 0.02, 0, -sway * 0.03 + (mate3d.thinking ? 0.12 : 0));
    };

    mate3d.vrm = vrm;
    const em = vrm.expressionManager;
    let nextBlink = 2;
    let blinkT = -1;
    let running = false;
    const clock = new THREE.Clock();
    const shouldRun = () => !document.hidden && !isReading() && !NARROW_QUERY.matches;

    const frame = () => {
      if (!shouldRun()) { running = false; return; }
      requestAnimationFrame(frame);
      const dt = Math.min(clock.getDelta(), 0.1);
      if (mixer) mixer.update(dt); else proceduralIdle(clock.elapsedTime);

      if (em) {
        // 깜빡임
        nextBlink -= dt;
        if (nextBlink <= 0 && blinkT < 0) { blinkT = 0; nextBlink = 2 + Math.random() * 3; }
        let blink = 0;
        if (blinkT >= 0) {
          blinkT += dt;
          blink = blinkT < 0.07 ? blinkT / 0.07 : Math.max(0, 1 - (blinkT - 0.07) / 0.1);
          if (blinkT > 0.17) blinkT = -1;
        }
        em.setValue('blink', blink);

        // 립싱크: 답변 글자를 0.07초에 한 자씩 따라가며 입 모양을 바꾼다
        ['aa', 'ih', 'ou', 'ee', 'oh'].forEach((v) => em.setValue(v, 0));
        const talk = mate3d.talk;
        if (talk) {
          talk.acc += dt;
          while (talk.acc > 0.07 && talk.i < talk.text.length) {
            talk.acc -= 0.07;
            talk.cur = vowelOf(talk.text[talk.i++]);
          }
          if (talk.cur) em.setValue(talk.cur, Math.sin(Math.min(1, talk.acc / 0.07) * Math.PI) * 0.8);
          if (talk.i >= talk.text.length && talk.acc > 0.2) mate3d.talk = null;
        }
        if (mate3d.exprUntil && performance.now() > mate3d.exprUntil && !mate3d.talk) mate3d.setExpr('neutral');
      }
      vrm.update(dt);
      renderer.render(scene, camera);
    };
    const start = () => {
      if (running || !shouldRun()) return;
      running = true;
      clock.getDelta();
      requestAnimationFrame(frame);
    };
    // 책을 열거나 탭이 숨겨지면 루프가 스스로 멈추고, 돌아오면 다시 시작한다
    document.addEventListener('visibilitychange', start);
    NARROW_QUERY.addEventListener('change', () => {
      host.classList.toggle('rm-3d', !NARROW_QUERY.matches);
      start();
    });
    const viewer = document.getElementById('media-viewer-modal');
    if (viewer) new MutationObserver(start).observe(viewer, { attributes: true, attributeFilter: ['style'] });
    start();
    console.info(LOG_PREFIX, '3D 캐릭터 로드 완료:', vrmUrl);
  }

  const mascotHost = ensureMascot();
  watchReading(mascotHost);
  renderTabStatus();
  loadCharacter(mascotHost);
})();
