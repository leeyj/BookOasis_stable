(function() {
  console.log('[Stats-Dashboard-Plugin] Category-Level Fullpage UI loaded.');

  let currentType = 'general';

  // 🎨 테마 변경 실시간 감지 (MutationObserver - 가이드 문서 표준)
  function getCurrentTheme() {
    return document.documentElement.getAttribute('data-app-theme') || 'purple';
  }

  const themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'data-app-theme') {
        const newTheme = getCurrentTheme();
        console.log(`[Stats-Dashboard-Plugin] Theme changed to: ${newTheme}`);
      }
    });
  });

  themeObserver.observe(document.documentElement, { attributes: true });

  function fetchStatsData(type) {
    fetch(`/api/media/dashboard/widgets/stats_dashboard/data?type=${type}`)
      .then(res => res.json())
      .then(data => {
        if (!data.success) return;
        const stats = data.stats || {};
        
        document.getElementById('stats-val-books').textContent = (stats.total_books || 0).toLocaleString();
        document.getElementById('stats-val-series').textContent = (stats.total_series || 0).toLocaleString();
        document.getElementById('stats-val-week-pages').textContent = (stats.week_pages_read || 0).toLocaleString();
        document.getElementById('stats-val-month-completed').textContent = (stats.month_completed_books || 0).toLocaleString();

        const weekPages = stats.week_pages_read || 0;
        const goalPercent = Math.min(100, Math.round((weekPages / 100) * 100));
        document.getElementById('stats-goal-percent').textContent = `${goalPercent}%`;
        document.getElementById('stats-goal-fill').style.width = `${goalPercent}%`;

        document.getElementById('stats-activity-note').textContent = 
          `이번 주 총 ${weekPages.toLocaleString()}페이지를 읽으셨습니다. 꾸준한 독서 습관을 이어가세요!`;

        document.getElementById('fmt-val-zip').textContent = (stats.format_counts?.zip || 0) + '권';
        document.getElementById('fmt-val-epub').textContent = (stats.format_counts?.epub || 0) + '권';
        document.getElementById('fmt-val-pdf').textContent = (stats.format_counts?.pdf || 0) + '권';
      })
      .catch(err => {
        console.error('[Stats-Plugin] Fetch stats failed:', err);
      });
  }

  document.querySelectorAll('.stats-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.stats-btn').forEach(b => b.classList.remove('active'));
      const target = e.currentTarget;
      target.classList.add('active');
      currentType = target.dataset.type || 'general';
      fetchStatsData(currentType);
    });
  });

  fetchStatsData(currentType);
})();
