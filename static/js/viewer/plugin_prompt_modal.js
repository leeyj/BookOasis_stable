// plugin_prompt_modal.js — 플러그인 컨텍스트 메뉴 액션이 사용자 입력을 요구할 때
// (run_*_context_menu_action이 {success: True, 'prompt': {...}}를 반환하는 경우) 보여줄
// 범용 입력 모달. 예: "메모 추가" 액션은 실제 저장 전에 텍스트를 입력받아야 하는데,
// run_annotation_context_menu_action() 자체는 서버에서 실행되는 헤드리스 응답이라 직접
// 입력 UI를 띄울 수 없다 — 그래서 "이런 입력을 보여줘 달라"는 요청만 반환하게 하고,
// 프런트가 이 모달로 입력을 받아 같은 액션을 프롬프트 응답과 함께 다시 호출한다.
//
// prompt 스펙(docs/guide_plugins.md 계약 문서 기준 snake_case):
//   { title, message?, placeholder?, default_value?, multiline?(기본 true), submit_label? }
//   (camelCase도 방어적으로 허용하지만, 플러그인은 파이썬 dict를 반환하므로 snake_case가 정본)
// 반환값: 사용자가 입력한 문자열, 또는 취소 시 null (Promise)
let modalEl = null;

function ensureModal() {
  if (modalEl) return modalEl;
  modalEl = document.createElement('div');
  modalEl.id = 'plugin-prompt-modal';
  modalEl.style.cssText = [
    'position:fixed', 'inset:0', 'z-index:20100', 'display:none',
    'align-items:center', 'justify-content:center',
    'background:rgba(0,0,0,0.55)',
  ].join(';');

  const box = document.createElement('div');
  box.style.cssText = [
    'width:min(420px, 90vw)', 'padding:1.1rem', 'display:flex', 'flex-direction:column',
    'gap:0.7rem', 'background:#1e293b', 'border:1px solid rgba(255,255,255,0.12)',
    'border-radius:10px', 'box-shadow:0 12px 32px rgba(0,0,0,0.5)',
  ].join(';');
  box.innerHTML = `
    <div data-role="plugin-prompt-title" style="font-weight:600; font-size:1rem; color:#f8fafc;"></div>
    <div data-role="plugin-prompt-message" style="font-size:0.82rem; color:#94a3b8; display:none;"></div>
    <textarea data-role="plugin-prompt-input" style="width:100%; box-sizing:border-box; background:#0f172a; color:#e2e8f0; border:1px solid rgba(255,255,255,0.15); border-radius:6px; padding:0.55rem; font:inherit; resize:vertical;"></textarea>
    <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:0.2rem;">
      <button type="button" data-role="plugin-prompt-cancel" style="cursor:pointer; padding:0.45rem 1rem; border-radius:6px; border:1px solid rgba(255,255,255,0.15); background:transparent; color:#cbd5e1; font:inherit;">취소</button>
      <button type="button" data-role="plugin-prompt-submit" style="cursor:pointer; padding:0.45rem 1rem; border-radius:6px; border:none; background:#fbbf24; color:#1e293b; font-weight:600; font:inherit;"></button>
    </div>
  `;
  modalEl.appendChild(box);
  document.body.appendChild(modalEl);
  return modalEl;
}

export function showPluginPromptModal(spec = {}) {
  return new Promise((resolve) => {
    const modal = ensureModal();
    const titleEl = modal.querySelector('[data-role="plugin-prompt-title"]');
    const msgEl = modal.querySelector('[data-role="plugin-prompt-message"]');
    const input = modal.querySelector('[data-role="plugin-prompt-input"]');
    const submitBtn = modal.querySelector('[data-role="plugin-prompt-submit"]');
    const cancelBtn = modal.querySelector('[data-role="plugin-prompt-cancel"]');

    titleEl.textContent = spec.title || '입력';
    if (spec.message) {
      msgEl.textContent = spec.message;
      msgEl.style.display = 'block';
    } else {
      msgEl.style.display = 'none';
    }
    // 플러그인은 파이썬 dict로 응답을 작성하므로(docs/guide_plugins.md 계약 문서 기준
    // snake_case: default_value/submit_label), 그 표기를 우선으로 읽는다. camelCase도
    // 방어적으로 함께 지원해 표기 실수로 조용히 빈 값이 되는 걸 막는다.
    input.value = spec.default_value ?? spec.defaultValue ?? '';
    input.placeholder = spec.placeholder || '';
    input.rows = spec.multiline === false ? 1 : 4;
    submitBtn.textContent = spec.submit_label ?? spec.submitLabel ?? '확인';

    modal.style.display = 'flex';
    input.focus();
    input.select();

    function cleanup(result) {
      modal.style.display = 'none';
      submitBtn.removeEventListener('click', onSubmit);
      cancelBtn.removeEventListener('click', onCancel);
      modal.removeEventListener('click', onBackdrop);
      input.removeEventListener('keydown', onKeydown);
      resolve(result);
    }
    function onSubmit() { cleanup(input.value); }
    function onCancel() { cleanup(null); }
    function onBackdrop(event) { if (event.target === modal) cleanup(null); }
    function onKeydown(event) {
      if (event.key === 'Escape') cleanup(null);
      else if (event.key === 'Enter' && !event.shiftKey && spec.multiline === false) {
        event.preventDefault();
        onSubmit();
      }
    }

    submitBtn.addEventListener('click', onSubmit);
    cancelBtn.addEventListener('click', onCancel);
    modal.addEventListener('click', onBackdrop);
    input.addEventListener('keydown', onKeydown);
  });
}
