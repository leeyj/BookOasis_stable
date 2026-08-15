// external_domains.js - 사용자별 외부 도메인 허용 목록(화이트리스트) 설정 탭 제어 모듈
//
// 앱은 어떤 외부 도메인도 기본 제공/추천하지 않는다. 여기서 등록한 도메인만 플러그인의
// 웹뷰/다운로드 API(plugin_webview_api.js)가 사용할 수 있다 — 등록/책임은 전적으로 사용자 본인.

function escapeHtmlText(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function invalidateCache() {
  if (typeof window.invalidateWebviewWhitelistCache === 'function') {
    window.invalidateWebviewWhitelistCache();
  }
}

export async function loadExternalDomainsSettings() {
  const listEl = document.getElementById('external-domains-list');
  if (!listEl) return;

  listEl.innerHTML = '<div style="text-align:center; padding:1rem; color:#94a3b8;">불러오는 중...</div>';

  try {
    const res = await fetch('/api/webview/whitelist');
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'load_failed');
    renderDomainList(data.domains || []);
  } catch (e) {
    console.error('[ExternalDomains] 목록 로드 실패:', e);
    listEl.innerHTML = '<div style="text-align:center; padding:1rem; color:#f43f5e;">목록을 불러오지 못했습니다.</div>';
  }
}

function renderDomainList(domains) {
  const listEl = document.getElementById('external-domains-list');
  if (!listEl) return;

  if (!domains.length) {
    listEl.innerHTML = '<div style="text-align:center; padding:1.2rem; color:#94a3b8; font-size:0.85rem;">등록된 허용 도메인이 없습니다. 아래에서 추가해주세요.</div>';
    return;
  }

  listEl.innerHTML = domains.map(d => `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:0.6rem 0.9rem;
                background:rgba(30,41,59,0.4); border:1px solid rgba(255,255,255,0.06); border-radius:6px; margin-bottom:0.5rem;">
      <span style="color:#e2e8f0; font-size:0.88rem; font-family:monospace;">${escapeHtmlText(d.pattern)}</span>
      <button type="button" class="btn-remove-external-domain" data-domain="${escapeHtmlText(d.pattern)}"
              style="background:none; border:1px solid rgba(244,63,94,0.4); color:#f43f5e; border-radius:5px;
                     padding:0.25rem 0.6rem; font-size:0.78rem; cursor:pointer;">삭제</button>
    </div>
  `).join('');
}

export async function addWhitelistDomain(pattern) {
  if (!pattern || !pattern.trim()) return;
  try {
    const res = await fetch('/api/webview/whitelist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: pattern.trim() })
    });
    const data = await res.json();
    if (!data.success) {
      if (typeof window.showToast === 'function') window.showToast(data.error || '도메인 추가에 실패했습니다.', 'error');
      return;
    }
    invalidateCache();
    renderDomainList(data.domains || []);
    if (typeof window.showToast === 'function') window.showToast('도메인이 추가되었습니다.', 'success');
  } catch (e) {
    console.error('[ExternalDomains] 추가 실패:', e);
    if (typeof window.showToast === 'function') window.showToast('도메인 추가 중 오류가 발생했습니다.', 'error');
  }
}

export async function removeWhitelistDomain(pattern) {
  if (!pattern) return;
  if (!window.confirm(`"${pattern}" 도메인을 허용 목록에서 삭제할까요?`)) return;

  try {
    const res = await fetch('/api/webview/whitelist', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: pattern })
    });
    const data = await res.json();
    if (!data.success) {
      if (typeof window.showToast === 'function') window.showToast('도메인 삭제에 실패했습니다.', 'error');
      return;
    }
    invalidateCache();
    renderDomainList(data.domains || []);
  } catch (e) {
    console.error('[ExternalDomains] 삭제 실패:', e);
    if (typeof window.showToast === 'function') window.showToast('도메인 삭제 중 오류가 발생했습니다.', 'error');
  }
}

function initExternalDomainsDelegation() {
  if (window.__externalDomainsDelegationBound) return;

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!form || form.id !== 'external-domains-add-form') return;
    event.preventDefault();
    const input = document.getElementById('external-domains-input');
    if (!input) return;
    addWhitelistDomain(input.value);
    input.value = '';
  }, true);

  document.addEventListener('click', (event) => {
    const btn = event.target && event.target.closest ? event.target.closest('.btn-remove-external-domain') : null;
    if (!btn) return;
    removeWhitelistDomain(btn.getAttribute('data-domain'));
  }, true);

  window.__externalDomainsDelegationBound = true;
}

initExternalDomainsDelegation();
