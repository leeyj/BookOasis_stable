// plugin_health_panel.js – 관리자 대시보드 상단 플러그인 로드 상태(성공/실패) 알림 패널
const DISMISS_KEY = 'plugin_health_panel_dismissed_signature';

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function t(key, vars, fallback) {
  if (window.i18n && typeof window.i18n.t === 'function') return window.i18n.t(key, vars, fallback);
  return fallback || key;
}

function buildSignature(statuses) {
  return statuses
    .filter(s => s.status === 'error')
    .map(s => `${s.plugin_id}:${s.occurred_at}`)
    .sort()
    .join('|');
}

function renderDetails(statuses) {
  const failed = statuses.filter(s => s.status === 'error');
  if (!failed.length) return '';
  return failed.map(s => `
    <div class="plugin-health-detail-row">
      <span class="plugin-health-detail-badge plugin-health-detail-badge--error">${escapeHtml(t('dashboard.plugin_health_status_error', {}, '실패'))}</span>
      <span class="plugin-health-detail-id">${escapeHtml(s.plugin_id)}</span>
      <span class="plugin-health-detail-message">${escapeHtml(s.message || '')}</span>
    </div>
  `).join('');
}

export async function loadPluginHealthPanel() {
  const panel = document.getElementById('plugin-health-panel');
  if (!panel) return;

  if (!window.currentUser || window.currentUser.role !== 'admin') {
    panel.style.display = 'none';
    return;
  }

  try {
    const res = await fetch('/api/media/plugins/load-status', { cache: 'no-store' });
    const data = await res.json();
    if (!data || !data.success) {
      panel.style.display = 'none';
      return;
    }

    const statuses = data.statuses || [];
    const errorCount = data.error_count || 0;

    // 정상(실패 0건)일 때는 패널 자체를 띄우지 않는다 — 문제 있을 때만 알림
    if (errorCount === 0) {
      panel.style.display = 'none';
      return;
    }

    const signature = buildSignature(statuses);
    if (sessionStorage.getItem(DISMISS_KEY) === signature) {
      panel.style.display = 'none';
      return;
    }

    const summaryEl = document.getElementById('plugin-health-panel-summary-text');
    const toggleBtn = document.getElementById('plugin-health-panel-toggle');
    const detailsEl = document.getElementById('plugin-health-panel-details');
    const dismissBtn = document.getElementById('plugin-health-panel-dismiss');

    panel.classList.add('plugin-health-panel--error');
    if (summaryEl) summaryEl.textContent = t('dashboard.plugin_health_error_summary', { count: errorCount }, `플러그인 ${errorCount}개 로드 실패`);
    if (toggleBtn) toggleBtn.style.display = '';
    if (detailsEl) detailsEl.innerHTML = renderDetails(statuses);

    if (toggleBtn && !toggleBtn.dataset.bound) {
      toggleBtn.dataset.bound = '1';
      toggleBtn.addEventListener('click', () => {
        if (!detailsEl) return;
        const isOpen = detailsEl.style.display !== 'none';
        detailsEl.style.display = isOpen ? 'none' : '';
      });
    }
    if (dismissBtn && !dismissBtn.dataset.bound) {
      dismissBtn.dataset.bound = '1';
      dismissBtn.addEventListener('click', () => {
        sessionStorage.setItem(DISMISS_KEY, signature);
        panel.style.display = 'none';
      });
    }

    panel.style.display = '';
  } catch (e) {
    panel.style.display = 'none';
  }
}
