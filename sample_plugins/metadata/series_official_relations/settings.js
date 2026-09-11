// 이 파일 전체는 core가 new Function('window', 'pluginId', 'root', 'config', <이 파일 내용>)로
// 감싸서 호출하는 함수 본문이다 - 최상위 IIFE로 다시 감싸지 않는다 (window/pluginId/root/config는
// 이미 인자로 바인딩되어 있다).
const btn = root.querySelector('[data-role="sor-sync-now"]');
const statusEl = root.querySelector('[data-role="sor-status"]');
const pathInput = root.querySelector('#sor-source-path');

if (btn && statusEl) {
  const callAction = async (actionId, extraContext) => {
    const res = await fetch('/api/media/context-menu/book/plugins/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'general', plugin_id: pluginId, action_id: actionId, context: extraContext || {} }),
    });
    return res.json();
  };

  const formatStatus = (data) => {
    if (!data || data.status === 'never_run') {
      return '아직 동기화한 적이 없습니다.';
    }
    if (data.status === 'running') {
      return '동기화 진행 중...';
    }
    if (data.status === 'error') {
      return `마지막 동기화 실패: ${data.error || '알 수 없는 오류'}`;
    }
    if (data.status === 'success') {
      const finishedAt = data.finished_at ? new Date(data.finished_at * 1000).toLocaleString() : '';
      const summary = Object.entries(data.results || {})
        .map(([dbType, r]) => `${dbType} ${r.matched_series}개 시리즈/${r.relations}건`)
        .join(', ');
      return `마지막 동기화 완료 (${finishedAt}) - ${summary}`;
    }
    return '';
  };

  const refreshStatus = async () => {
    try {
      const data = await callAction('sync_status');
      statusEl.textContent = formatStatus(data);
      return data;
    } catch (err) {
      console.error('[series_official_relations] 상태 조회 실패:', err);
    }
    return null;
  };

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      // 입력창의 현재 값을 그대로 보낸다 - "설정 저장" 버튼을 먼저 눌러야만 동기화되는 게
      // 아니라, 화면에 입력한 값으로 바로 실행되게 하기 위함 (플러그인 쪽에서 이 값을 받으면
      // 알아서 설정에도 저장해준다).
      const sourcePath = (pathInput && pathInput.value || '').trim();
      const data = await callAction('sync_now', { source_db_path: sourcePath });
      if (!data.success) {
        statusEl.textContent = `시작 실패: ${data.error || '알 수 없는 오류'}`;
        return;
      }
      statusEl.textContent = '동기화 진행 중...';
      const poll = setInterval(async () => {
        const status = await refreshStatus();
        if (!status || status.status === 'running') return;
        clearInterval(poll);
      }, 5000);
    } catch (err) {
      console.error('[series_official_relations] 동기화 시작 실패:', err);
      statusEl.textContent = '서버 요청 중 오류가 발생했습니다.';
    } finally {
      btn.disabled = false;
    }
  });

  refreshStatus();
}
