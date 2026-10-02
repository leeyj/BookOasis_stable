// kosync_settings.js – 계정 메뉴의 "KOReader 동기화" (동기화 비밀번호 설정)
//
// KOReader 진행 동기화(kosync)는 비밀번호의 MD5만 보내서 BookOasis 로그인 비밀번호로는 확인할 수 없다.
// 그래서 계정마다 '동기화 비밀번호'를 따로 정한다(/api/kosync/settings). 서버 주소와 사용자명을 보여 주고,
// 사용자가 KOReader에 그대로 옮겨 적게 한다.

function el(id) {
  return document.getElementById(id);
}

function showMessage(text, isError = false) {
  const message = el('kosync-message');
  if (!message) return;
  message.textContent = text || '';
  message.classList.toggle('is-error', !!isError);
}

function applyState(data) {
  const enabled = !!(data && data.enabled);
  const badge = el('kosync-status-badge');
  if (badge) badge.hidden = !enabled;
  const clearBtn = el('btn-kosync-clear');
  if (clearBtn) clearBtn.hidden = !enabled;
  const saveBtn = el('btn-kosync-save');
  if (saveBtn) saveBtn.textContent = enabled ? '변경' : '저장';
  if (data && data.server_url && el('kosync-server-url')) el('kosync-server-url').textContent = data.server_url;
  if (data && data.username && el('kosync-username')) el('kosync-username').textContent = data.username;
}

async function request(method, body) {
  const res = await fetch('/api/kosync/settings', {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.success === false) throw new Error(data.error || '요청에 실패했습니다.');
  return data;
}

async function loadState() {
  try {
    applyState(await request('GET'));
  } catch (e) {
    showMessage(e.message, true);
  }
}

export function initKosyncSettings() {
  const toggle = el('btn-kosync-settings');
  const panel = el('kosync-settings-panel');
  if (!toggle || !panel || toggle.dataset.bound === '1') return;
  toggle.dataset.bound = '1';

  toggle.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');
    if (!panel.hidden) {
      showMessage('');
      loadState();
    }
  });

  el('btn-kosync-save')?.addEventListener('click', async () => {
    const input = el('kosync-password');
    try {
      applyState(await request('POST', { password: input ? input.value : '' }));
      if (input) input.value = '';
      showMessage('저장했습니다. KOReader에서 이 비밀번호로 로그인하세요.');
      loadState();
    } catch (e) {
      showMessage(e.message, true);
    }
  });

  el('btn-kosync-clear')?.addEventListener('click', async () => {
    if (!window.confirm('KOReader 동기화를 해제할까요? KOReader에서 다시 로그인해야 합니다.')) return;
    try {
      applyState(await request('DELETE'));
      showMessage('해제했습니다.');
    } catch (e) {
      showMessage(e.message, true);
    }
  });

  // 처음 화면에서도 "켜짐" 배지를 보이도록 상태만 한 번 읽는다
  loadState();
}
