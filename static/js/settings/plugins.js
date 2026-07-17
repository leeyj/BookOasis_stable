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
      let html = '';
      data.plugins.forEach(p => {
        const schema = p.config_schema || [];
        const config = p.config || {};
        const hasCustomUi = !!(p.ui && p.ui.html);
        const updateManifest = p.update_manifest || null;
        const showSampleUpdateButton = !!(
          updateManifest &&
          updateManifest.enabled &&
          updateManifest.show_sample_update_button
        );
        
        // 플러그인별 카드 및 폼 템플릿 구성
        html += `
          <div class="plugin-card" style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 1.5rem; display: flex; flex-direction: column; gap: 1.2rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.05); padding-bottom: 0.8rem; flex-wrap: wrap; gap: 0.8rem;">
                  <div>
                      <h4 style="margin: 0; color: #fff; font-size: 1.05rem; font-weight: 700;">${p.name}</h4>
                      <span style="font-size: 0.75rem; color: #94a3b8;">플러그인 고유 ID: ${p.id}</span>
                  </div>
                  <!-- ON/OFF 활성화 토글 -->
                  <div style="display: flex; align-items: center; gap: 0.6rem;">
                      <span id="plugin-status-text-${p.id}" style="font-size: 0.82rem; color: ${p.enabled ? '#4ade80' : '#94a3b8'}; font-weight: 600;">
                          ${p.enabled ? '활성화됨' : '비활성화됨'}
                      </span>
                      <label style="position: relative; display: inline-block; width: 46px; height: 24px; margin: 0;">
                          <input type="checkbox" class="plugin-toggle-checkbox" data-plugin-id="${p.id}" ${p.enabled ? 'checked' : ''} style="opacity: 0; width: 0; height: 0;">
                          <span style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #334155; transition: .3s; border-radius: 24px;" class="toggle-slider"></span>
                      </label>
                  </div>
              </div>
              
              <!-- 설정값 동적 폼 -->
              <form class="plugin-config-form" data-plugin-id="${p.id}" style="display: flex; flex-direction: column; gap: 1.2rem;">
                  ${hasCustomUi ? `
                  <div class="plugin-ui-root" data-plugin-ui-root="${p.id}" data-plugin-config='${escapeHtmlAttr(JSON.stringify(config))}'>
                    ${p.ui.html}
                  </div>
                  ` : schema.map(f => {
                    const curVal = config[f.key];
                    return renderSchemaField(f, curVal);
                  }).join('')}

                  ${(hasCustomUi || schema.length > 0) ? `
                  <div style="margin-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 1rem;">
                      <button type="submit" class="btn-submit" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1.2rem; font-size: 0.82rem;">
                          <i class="fa-regular fa-floppy-disk"></i> 설정 저장
                      </button>
                  </div>
                  ` : '<p style="font-size: 0.82rem; color: #94a3b8; margin: 0;">이 플러그인은 별도의 추가 설정값이 필요하지 않습니다.</p>'}

                  ${showSampleUpdateButton ? `
                  <div style="margin-top: 0.4rem; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 0.9rem; display: flex; flex-direction: column; gap: 0.5rem;">
                    <button type="button" class="plugin-sample-update-btn" data-plugin-id="${p.id}" style="display: inline-flex; align-items: center; gap: 0.45rem; width: fit-content; padding: 0.5rem 1.0rem; font-size: 0.8rem; border-radius: 6px; border: 1px solid rgba(56,189,248,0.5); background: rgba(2,132,199,0.22); color: #dbeafe; cursor: pointer;">
                      <i class="fa-solid fa-cloud-arrow-down"></i> 샘플 업데이트 (${p.id})
                    </button>
                    <span id="plugin-sample-update-status-${p.id}" style="font-size: 0.78rem; color: #94a3b8;">업데이트 가능 조건: 현재 버전 &lt; GitHub 버전</span>
                  </div>
                  ` : ''}
              </form>
          </div>
        `;
      });
      container.innerHTML = html;

            // 폴더 기반 커스텀 UI/style/script 지원
            injectPluginCustomStyles(data.plugins);
            applyConfigValues(container, data.plugins);
            initPluginCustomScripts(container, data.plugins);
      
      // 토글 스위치 스타일링을 위한 CSS 헤드 인젝트 (최초 1회)
      injectToggleSwitchCSS();
      
      // 이벤트 바인딩
      bindPluginEvents();
    } else {
      container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #94a3b8;">로드된 메타데이터 플러그인이 없습니다.</div>';
    }
  } catch (err) {
    console.error('플러그인 목록 조회 에러:', err);
    container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #f43f5e;">서버와 통신 중 오류가 발생했습니다.</div>';
  }
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
  const descHtml = f.description ? `<p style="font-size: 0.76rem; color: #94a3b8; margin: 0.4rem 0 0 0;">${f.description}</p>` : '';
  const key = f.key || '';
  const type = (f.type || 'text').toLowerCase();

  if (type === 'checkbox') {
    const checked = curVal === true || curVal === '1' || curVal === 1 || curVal === 'true';
    return `
      <div class="library-form-group" style="margin: 0;">
        <label style="font-weight: 700; color: #fff; font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
          ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
        </label>
        <label style="display:flex; align-items:center; gap:0.5rem; color:#cbd5e1;">
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
        <label style="font-weight: 700; color: #fff; font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
          ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
        </label>
        <select name="${key}" ${required ? 'required' : ''} style="width: 100%; max-width: 480px; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); color: #fff; padding: 0.6rem 0.8rem; border-radius: 6px; outline: none; transition: border-color 0.2s;">
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
      <label style="font-weight: 700; color: #fff; font-size: 0.88rem; margin-bottom: 0.4rem; display: block;">
        ${label} ${required ? '<span style="color:#f43f5e;">*</span>' : ''}
      </label>
      <input type="${inputType}" name="${key}" value="${escapeHtmlAttr(value)}" ${required ? 'required' : ''} style="width: 100%; max-width: 480px; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); color: #fff; padding: 0.6rem 0.8rem; border-radius: 6px; outline: none; transition: border-color 0.2s;">
      ${descHtml}
    </div>
  `;
}

function injectPluginCustomStyles(plugins) {
  plugins.forEach((p) => {
    if (!p.ui || !p.ui.css) return;
    const styleId = `plugin-custom-style-${p.id}`;
    const existing = document.getElementById(styleId);
    if (existing) {
      existing.textContent = p.ui.css;
      return;
    }
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = p.ui.css;
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

function initPluginCustomScripts(container, plugins) {
  plugins.forEach((p) => {
    if (!p.ui || !p.ui.js) return;
    const root = container.querySelector(`[data-plugin-ui-root="${p.id}"]`);
    if (!root || root.dataset.pluginScriptInited === '1') return;
    try {
      const fn = new Function('window', 'pluginId', 'root', 'config', p.ui.js);
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
