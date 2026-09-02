// system_actions.js - "일반 설정" 탭의 단발성 관리자 액션 버튼 (VAAPI 하드웨어 점검, Lazy 스캔 즉시 실행)
import * as api from '../api.js';

export async function runVaapiCheck() {
  const btn = document.getElementById('btn-check-vaapi');
  const resultEl = document.getElementById('vaapi-check-result');
  const devicePathEl = document.getElementById('setting-vaapi-device-path');
  if (!resultEl) return;

  const devicePath = devicePathEl?.value?.trim() || '/dev/dri/renderD128';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 점검 중...';
  }
  resultEl.style.display = 'block';
  resultEl.style.background = 'rgba(15, 23, 42, 0.6)';
  resultEl.style.border = '1px solid rgba(255,255,255,0.1)';
  resultEl.style.color = '#cbd5e1';
  resultEl.textContent = '점검 중입니다...';

  try {
    const data = await api.checkVaapiSupport(devicePath);
    if (!data.success) {
      resultEl.style.border = '1px solid rgba(239, 68, 68, 0.4)';
      resultEl.style.color = '#fca5a5';
      resultEl.textContent = `점검 실패: ${data.error || '알 수 없는 오류'}`;
      return;
    }

    const overallLabel = {
      ok: '✅ 사용 가능 (VAAPI 하드웨어 가속을 바로 쓸 수 있습니다)',
      partial: '⚠️ 부분적으로 확인됨 (ffmpeg/디바이스는 준비됐지만 vainfo로 실동작 확인은 실패했습니다)',
      unavailable: '❌ 사용 불가 (아래 상세 내역에서 어느 단계가 막혔는지 확인하세요)',
      error: '❌ ffmpeg를 찾을 수 없습니다',
    }[data.overall] || data.overall;

    const colorMap = { ok: '#34d399', partial: '#fbbf24', unavailable: '#f87171', error: '#f87171' };
    resultEl.style.border = `1px solid ${colorMap[data.overall] || 'rgba(255,255,255,0.1)'}`;
    resultEl.style.color = '#e2e8f0';

    const lines = [overallLabel, '', ...(data.detail || [])];
    if (data.vainfo_output) {
      lines.push('', '[vainfo 출력 일부]', data.vainfo_output.split('\n').slice(0, 12).join('\n'));
    }
    resultEl.textContent = lines.join('\n');

    // 점검한 디바이스 경로를 그대로 저장 - 실제 스트리밍 시(_detect_vaapi_available)도
    // 이 값을 참조하므로, 점검 결과와 실사용 판단 기준이 항상 같은 경로를 보게 만든다.
    try {
      await api.updateSystemSetting('FFMPEG_VAAPI_DEVICE', devicePath);
    } catch (saveErr) {
      console.error('[Settings] VAAPI 디바이스 경로 저장 실패:', saveErr);
    }
  } catch (e) {
    console.error('[Settings] VAAPI 점검 요청 실패:', e);
    resultEl.style.border = '1px solid rgba(239, 68, 68, 0.4)';
    resultEl.style.color = '#fca5a5';
    resultEl.textContent = '서버 요청 중 오류가 발생했습니다.';
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> 지금 점검';
    }
  }
}

window.runVaapiCheck = runVaapiCheck;

export async function triggerLazyScanNow() {
  try {
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('settings.general_scanner_start'), 'info');
    }
    const res = await api.triggerLazyScan();
    if (res.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(res.message, 'success');
      } else {
        alert(res.message);
      }
    } else {
      alert(i18n.t('settings.general_scanner_fail', {error: res.error}));
    }
  } catch (err) {
    console.error('Lazy 스캔 즉시 실행 중 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}

window.triggerLazyScanNow = triggerLazyScanNow;
