// theme_settings.js - 대시보드 테마(내장 8개 + 커스텀 YAML) 및 독서 통계 위젯 표시 설정
import * as api from '../api.js';

export function changeDashboardTheme(themeName) {
  if (!themeName) themeName = 'purple';
  localStorage.setItem('app_dashboard_theme', themeName);
  document.documentElement.setAttribute('data-app-theme', themeName);
}

let customThemesLoaded = false;

// themes/*.yaml 검증 통과분을 테마 선택 드롭다운에 동적으로 추가한다.
// (플러그인 신뢰 경계와 동일하게, label은 반드시 textContent로만 넣는다 - innerHTML 금지)
export async function populateCustomThemeOptions() {
  if (customThemesLoaded) return;
  const themeSelect = document.getElementById('my-setting-dashboard-theme');
  if (!themeSelect) return;
  try {
    const data = await api.fetchCustomThemes();
    if (!data || !data.success || !Array.isArray(data.themes)) return;
    data.themes.forEach((theme) => {
      if (!theme || !theme.id || themeSelect.querySelector(`option[value="${CSS.escape(theme.id)}"]`)) return;
      const opt = document.createElement('option');
      opt.value = theme.id;
      opt.textContent = theme.label || theme.id;
      themeSelect.appendChild(opt);
    });
    customThemesLoaded = true;
    // 옵션이 이제서야 추가됐으므로, 이미 선택돼 있어야 할 커스텀 테마가 있다면 반영
    const savedTheme = localStorage.getItem('app_dashboard_theme') || 'purple';
    if (themeSelect.querySelector(`option[value="${CSS.escape(savedTheme)}"]`)) {
      themeSelect.value = savedTheme;
    }
  } catch (e) {
    console.error('[Settings] 커스텀 테마 목록 로드 실패:', e);
  }
}

export async function rescanCustomThemesUi() {
  const resultEl = document.getElementById('custom-theme-rescan-result');
  try {
    const data = await api.rescanCustomThemes();
    if (!data || !data.success) throw new Error((data && data.error) || '알 수 없는 오류');
    customThemesLoaded = false;
    await populateCustomThemeOptions();
    if (resultEl) {
      const rejected = Array.isArray(data.rejected) ? data.rejected : [];
      let msg = `로드됨: ${data.loaded_count}개`;
      if (rejected.length > 0) {
        msg += ` / 거부됨: ${rejected.length}개 (${rejected.map((r) => `${r.file}: ${r.reason}`).join(', ')})`;
      }
      resultEl.textContent = msg;
      resultEl.style.color = rejected.length > 0 ? '#f87171' : 'var(--app-text-muted)';
    }
  } catch (e) {
    console.error('[Settings] 커스텀 테마 재스캔 실패:', e);
    if (resultEl) {
      resultEl.textContent = `재스캔 실패: ${e.message || e}`;
      resultEl.style.color = '#f87171';
    }
  }
}

export function toggleDashboardInsightsSetting(enabled) {
  const isShow = !!enabled;
  localStorage.setItem('show_dashboard_insights', isShow ? '1' : '0');

  const container = document.querySelector('.dashboard-insights-container');
  const divider = document.getElementById('dashboard-insights-divider');
  if (container) container.style.display = isShow ? 'block' : 'none';
  if (divider) divider.style.display = isShow ? 'block' : 'none';
}

if (typeof window !== 'undefined') {
  window.changeDashboardTheme = changeDashboardTheme;
  window.toggleDashboardInsightsSetting = toggleDashboardInsightsSetting;
}
