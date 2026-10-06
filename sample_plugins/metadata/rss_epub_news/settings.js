// 이 파일 전체는 core가 new Function('window', 'pluginId', 'root', 'config', <이 파일 내용>)로
// 감싸서 호출하는 함수 본문이다 - 최상위 IIFE로 다시 감싸지 않는다.
const btn = root.querySelector('[data-role="ren-run-now"]');
const statusEl = root.querySelector('[data-role="ren-status"]');

if (btn && statusEl) {
  const callAction = async (actionId) => {
    const res = await fetch('/api/media/context-menu/book/plugins/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'general', plugin_id: pluginId, action_id: actionId, context: {} }),
    });
    return res.json();
  };

  const formatStatus = (d) => {
    if (!d || d.status === 'never_run') return '아직 수집한 적이 없습니다.';
    if (d.status === 'running') return '수집 중...';
    if (d.status === 'error') return `마지막 수집 실패: ${d.error || '알 수 없는 오류'}`;
    const at = d.finished_at ? new Date(d.finished_at * 1000).toLocaleString() : '';
    const lines = (d.results || []).map((r) => {
      if (!r.ok) return `${r.feed}: 실패 (${r.error})`;
      if (r.skipped) return `${r.feed}: ${r.skipped}`;
      return `${r.feed}: ${r.articles}건 → ${r.file}`;
    });
    return `마지막 수집 ${d.status === 'partial' ? '일부 실패' : '완료'} (${at}) ${lines.join(' / ')}`;
  };

  const refresh = async () => {
    try {
      const d = await callAction('status');
      statusEl.textContent = formatStatus(d);
      return d;
    } catch (err) {
      console.error('[rss_epub_news] 상태 조회 실패:', err);
    }
    return null;
  };

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      const d = await callAction('run_now');
      if (!d.success) {
        statusEl.textContent = `시작 실패: ${d.error || '알 수 없는 오류'}`;
        return;
      }
      statusEl.textContent = '수집 중...';
      const poll = setInterval(async () => {
        const s = await refresh();
        if (!s || s.status === 'running') return;
        clearInterval(poll);
      }, 3000);
    } catch (err) {
      console.error('[rss_epub_news] 실행 실패:', err);
      statusEl.textContent = '서버 요청 중 오류가 발생했습니다.';
    } finally {
      btn.disabled = false;
    }
  });

  refresh();
}
