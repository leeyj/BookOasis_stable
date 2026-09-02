// plugins.js - 메타데이터 플러그인 설정 제어 모듈
import { state } from '../state.js';
import * as api from '../api.js';

// 플러그인 목록 조회 및 동적 UI 생성
export async function loadPluginsSettings() {
  console.log('[Plugins-Settings] loadPluginsSettings() 함수 진입');
  const container = document.getElementById('settings-plugins-container');
  console.log('[Plugins-Settings] container 엘리먼트 검색 결과:', container);
  if (!container) {
    console.warn('[Plugins-Settings] 경고: #settings-plugins-container 엘리먼트를 찾을 수 없습니다.');
    return;
  }

  container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #a855f7;"><i class="fa-solid fa-circle-notch fa-spin fa-2x"></i><br><br>플러그인 목록 로드 중...</div>';

  try {
    console.log('[Plugins-Settings] api.fetchMetadataPluginsForManagement() API 호출 시작');
    const data = await api.fetchMetadataPluginsForManagement();
    console.log('[Plugins-Settings] API 응답 데이터 수신 완료:', data);
    if (data.success && data.plugins && data.plugins.length > 0) {
      container.innerHTML = '';
      data.plugins.forEach(p => {
        const schema = p.config_schema || [];
        const config = p.config || {};
        const hasCustomSettingsUi = !!(p.settings_ui && p.settings_ui.html);
        const updateManifest = p.update_manifest || null;
        const showSampleUpdateButton = !!(
          updateManifest &&
          updateManifest.enabled &&
          updateManifest.show_sample_update_button
        );

        const hasConfigurableBody = hasCustomSettingsUi || schema.length > 0 || showSampleUpdateButton;

        const card = document.createElement('div');
        card.className = 'plugin-settings-card';
        card.style.cssText = 'background: rgba(var(--app-panel-rgb), 0.4); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 8px; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.2rem;';

        // 플러그인별 카드 및 폼 템플릿 구성
        // 접힌 상태(기본값)에서는 이름/ID/토글만 보이는 한 줄 헤더만 남고, 설명·설정 폼·저장 버튼은
        // 헤더 클릭 시에만 펼쳐지는 본문(.plugin-settings-card-body)으로 숨긴다 — 플러그인 수가 많아지면
        // (커뮤니티 피드백: 20개만 돼도 스크롤이 너무 길어짐) 카드 하나당 세로 공간이 설명 유무와
        // 무관하게 항상 커서 생기던 문제를 렌더링 쪽에서만 해결(플러그인 작성자 쪽 변경 불필요).
        card.innerHTML = `
              <div class="plugin-settings-card-header" data-role="plugin-card-toggle" data-plugin-id="${p.id}" style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 0; flex-wrap: wrap; gap: 0.8rem; cursor: pointer;">
                  <div style="display: flex; align-items: center; gap: 0.6rem; min-width: 0;">
                      <i class="fa-solid fa-chevron-right plugin-settings-card-chevron" data-plugin-chevron="${p.id}" style="color: var(--app-text-muted); font-size: 0.8rem; transition: transform 0.2s; flex-shrink: 0;"></i>
                      <div style="min-width: 0;">
                          <h4 style="margin: 0; color: var(--app-text-primary); font-size: 1.05rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                              ${escapeHtmlText(p.name)}
                              ${hasConfigurableBody ? '<span style="font-size: 0.68rem; font-weight: 600; color: #c4b5fd; background: rgba(168,85,247,0.15); border: 1px solid rgba(168,85,247,0.4); border-radius: 4px; padding: 0.1rem 0.4rem;">설정 있음</span>' : ''}
                          </h4>
                          <span style="font-size: 0.75rem; color: var(--app-text-muted);">플러그인 고유 ID: ${escapeHtmlText(p.id)}</span>
                      </div>
                  </div>
                  <!-- ON/OFF 활성화 토글 -->
                  <div style="display: flex; align-items: center; gap: 0.6rem;" data-role="plugin-toggle-zone">
                      <span id="plugin-status-text-${p.id}" style="font-size: 0.82rem; color: ${p.enabled ? '#4ade80' : '#94a3b8'}; font-weight: 600;">
                          ${p.enabled ? '활성화됨' : '비활성화됨'}
                      </span>
                      <label style="position: relative; display: inline-block; width: 46px; height: 24px; margin: 0;">
                          <input type="checkbox" class="plugin-toggle-checkbox" data-plugin-id="${p.id}" ${p.enabled ? 'checked' : ''} style="opacity: 0; width: 0; height: 0;">
                          <span style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #334155; transition: .3s; border-radius: 24px;" class="toggle-slider"></span>
                      </label>
                  </div>
              </div>

              <div class="plugin-settings-card-body" data-plugin-body="${p.id}" style="display: none; flex-direction: column; gap: 1.2rem; border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 1.2rem;">
                  <!-- 설정값 동적 폼 -->
                  <form class="plugin-config-form" data-plugin-id="${p.id}" style="display: flex; flex-direction: column; gap: 1.2rem;">
                      ${hasCustomSettingsUi ? `
                      <div class="plugin-settings-ui-root" data-plugin-settings-root="${p.id}" data-plugin-config='${escapeHtmlAttr(JSON.stringify(config))}'>
                        ${p.settings_ui.html}
                      </div>
                      ` : (schema.length > 0 ? schema.map(f => {
                        const curVal = config[f.key];
                        return renderSchemaField(f, curVal);
                      }).join('') : '<p style="font-size: 0.82rem; color: var(--app-text-muted); margin: 0;">이 플러그인은 별도의 추가 설정값이 필요하지 않습니다.</p>')}

                      ${(hasCustomSettingsUi || schema.length > 0) ? `
                      <div style="margin-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 1rem;">
                          <button type="submit" class="btn-submit" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1.2rem; font-size: 0.82rem;">
                              <i class="fa-regular fa-floppy-disk"></i> 설정 저장
                          </button>
                      </div>
                      ` : ''}

                      ${showSampleUpdateButton ? `
                      <div style="margin-top: 0.4rem; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 0.9rem; display: flex; flex-direction: column; gap: 0.5rem;">
                        <button type="button" class="plugin-sample-update-btn" data-plugin-id="${p.id}" style="display: inline-flex; align-items: center; gap: 0.45rem; width: fit-content; padding: 0.5rem 1.0rem; font-size: 0.8rem; border-radius: 6px; border: 1px solid rgba(56,189,248,0.5); background: rgba(2,132,199,0.22); color: #dbeafe; cursor: pointer;">
                          <i class="fa-solid fa-cloud-arrow-down"></i> 샘플 업데이트 (${p.id})
                        </button>
                        <span id="plugin-sample-update-status-${p.id}" style="font-size: 0.78rem; color: var(--app-text-muted);">업데이트 가능 조건: 현재 버전 &lt; GitHub 버전</span>
                      </div>
                      ` : ''}
                  </form>
              </div>
        `;
        container.appendChild(card);
      });

      injectPluginSettingsStyles(data.plugins);
      applyConfigValues(container, data.plugins);
      initPluginSettingsScripts(container, data.plugins);

      // 토글 스위치 스타일링을 위한 CSS 헤드 인젝트 (최초 1회)
      injectToggleSwitchCSS();

      // 이벤트 바인딩
      bindPluginEvents();
    } else {
      container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--app-text-muted);">로드된 메타데이터 플러그인이 없습니다.</div>';
    }
  } catch (err) {
    console.error('플러그인 목록 조회 에러:', err);
    container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #f43f5e;">서버와 통신 중 오류가 발생했습니다.</div>';
  }

  initSamplePluginsModal();
}

function escapeHtmlAttr(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeHtmlText(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderSchemaField(f, curVal) {
  const label = f.label || f.key;
  const required = !!f.required;
  const descHtml = f.description ? `<p style="font-size: 0.76rem; color: var(--app-text-muted); margin: 0.4rem 0 0 0;">${f.description}</p>` : '';
  const key = f.key || '';
  const type = (f.type || 'text').toLowerCase();

  if (type === 'checkbox') {
    const checked = curVal === true || curVal === '1' || curVal === 1 || curVal === 'true';
    return `
      <div class="library-form-group" style="margin: 0;">
        <label style="font-weight: 700; color: var(--app-text-primary); font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
          ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
        </label>
        <label style="display:flex; align-items:center; gap:0.5rem; color: var(--app-text-muted);">
          <input type="checkbox" name="${key}" ${checked ? 'checked' : ''}>
          <span>사용</span>
        </label>
        ${descHtml}
      </div>
    `;
  }

  if (type === 'select') {
    const options = Array.isArray(f.options) ? f.options : [];
    const cur = curVal ?? f.default ?? '';
    return `
      <div class="library-form-group" style="margin: 0;">
        <label style="font-weight: 700; color: var(--app-text-primary); font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
          ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
        </label>
        <select name="${key}" ${required ? 'required' : ''} style="width: 100%; max-width: 480px; background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.1); color: var(--app-text-primary); padding: 0.6rem 0.8rem; border-radius: 6px; outline: none; transition: border-color 0.2s;">
          ${options.map(opt => {
            const val = typeof opt === 'object' ? opt.value : opt;
            const text = typeof opt === 'object' ? (opt.label || opt.value) : opt;
            const selected = String(cur) === String(val) ? 'selected' : '';
            return `<option value="${escapeHtmlAttr(val)}" ${selected}>${escapeHtmlText(text)}</option>`;
          }).join('')}
        </select>
        ${descHtml}
      </div>
    `;
  }

  const inputType = (type === 'number' || type === 'password' || type === 'text') ? type : 'text';
  const value = curVal ?? f.default ?? '';
  return `
    <div class="library-form-group" style="margin: 0;">
      <label style="font-weight: 700; color: var(--app-text-primary); font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
        ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
      </label>
      <input type="${inputType}" name="${key}" value="${escapeHtmlAttr(value)}" ${required ? 'required' : ''} style="width: 100%; max-width: 480px; background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.1); color: var(--app-text-primary); padding: 0.6rem 0.8rem; border-radius: 6px; outline: none; transition: border-color 0.2s;">
      ${descHtml}
    </div>
  `;
}

function injectPluginSettingsStyles(plugins) {
  plugins.forEach((p) => {
    if (!p.settings_ui || !p.settings_ui.css) return;
    const styleId = `plugin-settings-style-${p.id}`;
    const existing = document.getElementById(styleId);
    if (existing) {
      existing.textContent = p.settings_ui.css;
      return;
    }
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = p.settings_ui.css;
    document.head.appendChild(style);
  });
}

function applyConfigValues(container, plugins) {
  plugins.forEach((p) => {
    const form = container.querySelector(`form.plugin-config-form[data-plugin-id="${p.id}"]`);
    if (!form) return;
    const config = p.config || {};
    Object.keys(config).forEach((key) => {
      const el = form.querySelector(`[name="${CSS.escape(key)}"]`);
      if (!el) return;
      if (el.type === 'checkbox') {
        el.checked = config[key] === true || config[key] === '1' || config[key] === 1 || config[key] === 'true';
      } else {
        el.value = config[key] ?? '';
      }
    });
  });
}

function initPluginSettingsScripts(container, plugins) {
  plugins.forEach((p) => {
    if (!p.settings_ui || !p.settings_ui.js) return;
    const root = container.querySelector(`[data-plugin-settings-root="${p.id}"]`);
    if (!root || root.dataset.pluginScriptInited === '1') return;
    try {
      const fn = new Function('window', 'pluginId', 'root', 'config', p.settings_ui.js);
      fn(window, p.id, root, p.config || {});
      root.dataset.pluginScriptInited = '1';
    } catch (e) {
      console.error(`[Plugins-Settings] custom script init failed (${p.id}):`, e);
    }
  });
}

// 토글 버튼 디자인용 CSS 동적 생성
function injectToggleSwitchCSS() {
  if (document.getElementById('plugin-toggle-css')) return;
  const style = document.createElement('style');
  style.id = 'plugin-toggle-css';
  style.innerHTML = `
    .plugin-toggle-checkbox:checked + .toggle-slider {
      background-color: #a855f7 !important;
    }
    .plugin-toggle-checkbox:checked + .toggle-slider:before {
      transform: translateX(22px);
    }
    .toggle-slider:before {
      position: absolute;
      content: "";
      height: 18px;
      width: 18px;
      left: 3px;
      bottom: 3px;
      background-color: white;
      transition: .3s;
      border-radius: 50%;
    }
    .plugin-settings-card-header:hover {
      opacity: 0.85;
    }
    .plugin-settings-card-chevron-open {
      transform: rotate(90deg);
    }
  `;
  document.head.appendChild(style);
}

function buildPluginReloadStatusText(res) {
  const base = `업데이트 완료 (${res.local_version} -> ${res.github_version})`;
  const reload = res.reload || null;
  if (!reload) return base;

  if (reload.reload_ok) {
    return `${base} | 핫리로드 완료 (모듈 ${reload.removed_count || 0}개 반영)`;
  }

  return `${base} | 업데이트는 완료됐지만 핫리로드 실패`;
}

// 플러그인 이벤트 핸들러 바인딩
function bindPluginEvents() {
  const container = document.getElementById('settings-plugins-container');
  if (!container) return;

  if (!window.__pluginsStaticDelegationBound) {
    document.addEventListener('click', (event) => {
      const guide = event && event.target && typeof event.target.closest === 'function'
        ? event.target.closest('[data-role="plugins-contrib-guide"]')
        : null;
      if (!guide) return;
      event.preventDefault();
      alert('준비 중인 기여 항목입니다. GitHub 기여 가이드를 확인해 주세요!');
    }, true);
    window.__pluginsStaticDelegationBound = true;
  }

  // 0. 카드 헤더 클릭 시 설정 본문 펼치기/접기 (토글 스위치 영역 클릭은 제외)
  container.querySelectorAll('.plugin-settings-card-header').forEach(header => {
    header.addEventListener('click', (e) => {
      if (e.target.closest('[data-role="plugin-toggle-zone"]')) return;
      const pluginId = header.dataset.pluginId;
      const body = container.querySelector(`[data-plugin-body="${CSS.escape(pluginId)}"]`);
      const chevron = container.querySelector(`[data-plugin-chevron="${CSS.escape(pluginId)}"]`);
      if (!body) return;
      const isOpen = body.style.display !== 'none';
      body.style.display = isOpen ? 'none' : 'flex';
      if (chevron) chevron.classList.toggle('plugin-settings-card-chevron-open', !isOpen);
    });
  });

  // 1. 활성/비활성 스위치 토글 이벤트
  container.querySelectorAll('.plugin-toggle-checkbox').forEach(chk => {
    chk.addEventListener('change', async (e) => {
      const pluginId = e.target.dataset.pluginId;
      const isEnabled = e.target.checked;
      const statusText = document.getElementById(`plugin-status-text-${pluginId}`);
      
      try {
        const res = await api.toggleMetadataPlugin(state.currentLibraryType, pluginId, isEnabled);
        if (res.success) {
          if (statusText) {
            statusText.innerText = isEnabled ? '활성화됨' : '비활성화됨';
            statusText.style.color = isEnabled ? '#4ade80' : '#94a3b8';
          }
          
          // 플러그인 활성 토글에 따른 전역 검색 플러그인 캐시 무효화 처리
          if (typeof window.invalidateMetadataPluginsCache === 'function') {
            window.invalidateMetadataPluginsCache();
          }

          if (typeof window.showToast === 'function') {
            window.showToast(res.message, 'success');
          }
        } else {
          alert(i18n.t('settings.plugins_toggle_fail', {error: res.error}));
        }
      } catch (err) {
        console.error('플러그인 활성 토글 에러:', err);
      }
    });
  });

  // 2. 각 플러그인의 설정 저장 폼 이벤트
  container.querySelectorAll('.plugin-config-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const pluginId = form.dataset.pluginId;
      
      // 폼 데이터를 딕셔너리로 취합
      const configData = {};
      const inputs = form.querySelectorAll('input, select');
      inputs.forEach(inp => {
        if (inp.name) {
          if (inp.type === 'checkbox') {
            configData[inp.name] = !!inp.checked;
          } else {
            configData[inp.name] = String(inp.value ?? '').trim();
          }
        }
      });

      try {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerText = '저장 중...';
        }
        
        const res = await api.saveMetadataPluginConfig(state.currentLibraryType, pluginId, configData);
        if (res.success) {
          if (typeof window.showToast === 'function') {
            window.showToast(res.message, 'success');
          } else {
            alert(res.message);
          }
        } else {
          alert(i18n.t('settings.plugins_save_fail', {error: res.error}));
        }
      } catch (err) {
        console.error('플러그인 설정 저장 에러:', err);
        alert(i18n.t('settings.plugins_server_error'));
      } finally {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fa-regular fa-floppy-disk"></i> 설정 저장';
        }
      }
    });
  });

  // 3. 샘플 업데이트 버튼 (plugin update_manifest.show_sample_update_button 기반)
  container.querySelectorAll('.plugin-sample-update-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const pluginId = e.currentTarget.dataset.pluginId;
      const statusEl = document.getElementById(`plugin-sample-update-status-${pluginId}`);
      const prevText = btn.innerHTML;
      try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 업데이트 중...';
        if (statusEl) {
          statusEl.textContent = '업데이트 확인/적용 진행 중...';
          statusEl.style.color = '#38bdf8';
        }

        const res = await api.sampleUpdateMetadataPlugin(pluginId);
        if (res.success) {
          const msg = buildPluginReloadStatusText(res);
          if (statusEl) {
            statusEl.textContent = msg;
            statusEl.style.color = (res.reload && res.reload.reload_ok === false) ? '#f59e0b' : '#4ade80';
          }
          if (typeof window.showToast === 'function') {
            window.showToast(msg, 'success');
          }

          if (res.reload && res.reload.reload_ok === false) {
            const warn = `핫리로드 실패: ${res.reload.reload_error || '원인 미상'} (필요 시 컨테이너 재시작)`;
            if (statusEl) {
              statusEl.textContent = `${msg} | ${warn}`;
              statusEl.style.color = '#f59e0b';
            }
            if (typeof window.showToast === 'function') {
              window.showToast(warn, 'error');
            }
          }
        } else {
          const err = res.error || '업데이트 실패';
          if (statusEl) {
            statusEl.textContent = err;
            statusEl.style.color = '#f43f5e';
          }
          if (typeof window.showToast === 'function') {
            window.showToast(err, 'error');
          } else {
            alert(err);
          }
        }
      } catch (err) {
        console.error('샘플 플러그인 업데이트 에러:', err);
        if (statusEl) {
          statusEl.textContent = '서버 통신 오류';
          statusEl.style.color = '#f43f5e';
        }
      } finally {
        btn.disabled = false;
        btn.innerHTML = prevText;
      }
    });
  });
}

// ── 샘플 플러그인 설치 모달 ──────────────────────────────

function openSamplePluginsModal() {
  const modal = document.getElementById('sample-plugins-modal');
  if (!modal) return;
  modal.style.display = 'flex';
  loadSamplePluginsList();
}

function closeSamplePluginsModal() {
  const modal = document.getElementById('sample-plugins-modal');
  if (modal) modal.style.display = 'none';
}

async function loadSamplePluginsList() {
  const list = document.getElementById('sample-plugins-list');
  if (!list) return;
  list.innerHTML = '<div style="text-align: center; padding: 1.5rem; color: #a855f7;"><i class="fa-solid fa-circle-notch fa-spin"></i></div>';

  try {
    const data = await api.fetchSamplePlugins();
    if (!data.success || !data.samples || data.samples.length === 0) {
      list.innerHTML = '<div style="text-align: center; padding: 1.5rem; color: var(--app-text-muted);">설치 가능한 샘플 플러그인이 없습니다.</div>';
      return;
    }

    list.innerHTML = data.samples.map((s) => `
      <div class="sample-plugin-item" style="display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.9rem 1rem; background: rgba(var(--app-panel-rgb), 0.4); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 8px;">
        <div style="min-width: 0;">
          <div style="color: var(--app-text-primary); font-weight: 600; font-size: 0.92rem;">${escapeHtmlText(s.name)}</div>
          <div style="color: var(--app-text-muted); font-size: 0.75rem;">${escapeHtmlText(s.id)}</div>
        </div>
        ${s.installed
          ? `<span style="flex-shrink: 0; font-size: 0.8rem; color: #4ade80; font-weight: 600; display: inline-flex; align-items: center; gap: 0.35rem;"><i class="fa-solid fa-check"></i> 설치됨</span>`
          : `<button type="button" class="sample-plugin-install-btn" data-plugin-id="${escapeHtmlAttr(s.id)}" style="flex-shrink: 0; padding: 0.45rem 0.9rem; font-size: 0.8rem; border-radius: 6px; border: 1px solid rgba(168,85,247,0.5); background: rgba(168,85,247,0.18); color: #e9d5ff; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem;">
              <i class="fa-solid fa-download"></i> 설치
            </button>`
        }
      </div>
    `).join('');

    list.querySelectorAll('.sample-plugin-install-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const pluginId = btn.dataset.pluginId;
        const prevText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 설치 중...';
        try {
          const res = await api.installSamplePlugin(pluginId);
          if (res.success) {
            if (typeof window.showToast === 'function') {
              window.showToast(res.message, 'success');
            }
            await loadSamplePluginsList();
            await loadPluginsSettings();
          } else {
            if (typeof window.showToast === 'function') {
              window.showToast(res.error || '설치 실패', 'error');
            } else {
              alert(res.error || '설치 실패');
            }
            btn.disabled = false;
            btn.innerHTML = prevText;
          }
        } catch (err) {
          console.error('샘플 플러그인 설치 에러:', err);
          btn.disabled = false;
          btn.innerHTML = prevText;
        }
      });
    });
  } catch (err) {
    console.error('샘플 플러그인 목록 조회 에러:', err);
    list.innerHTML = '<div style="text-align: center; padding: 1.5rem; color: #f43f5e;">서버와 통신 중 오류가 발생했습니다.</div>';
  }
}

function initSamplePluginsModal() {
  if (window.__samplePluginsModalBound) return;
  window.__samplePluginsModalBound = true;

  document.addEventListener('click', (event) => {
    const openBtn = event.target.closest('[data-role="open-sample-plugins-modal"]');
    if (openBtn) {
      event.preventDefault();
      openSamplePluginsModal();
      return;
    }
    const closeBtn = event.target.closest('[data-role="close-sample-plugins-modal"]');
    if (closeBtn) {
      event.preventDefault();
      closeSamplePluginsModal();
    }
  });
}
