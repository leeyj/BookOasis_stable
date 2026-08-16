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

  function formatListenTime(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    if (sec === 0) return '0초';
    if (sec < 60) return `${sec}초`;
    const mins = Math.floor(sec / 60);
    if (mins < 60) return `${mins}분`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return remMins > 0 ? `${hours}시간 ${remMins}분` : `${hours}시간`;
  }

  function fetchStatsData(type) {
    fetch(`/api/media/dashboard/widgets/stats_dashboard/data?type=${type}`)
      .then(res => res.json())
      .then(data => {
        if (!data.success) return;
        const stats = data.stats || {};
        
        document.getElementById('stats-val-books').textContent = (stats.total_books || 0).toLocaleString();
        document.getElementById('stats-val-series').textContent = (stats.total_series || 0).toLocaleString();
        
        const isAudio = (type === 'audiobook');
        
        // 카드 3, 4 레이블 및 값 동적 업데이트
        const card3Label = document.querySelector('.stats-card:nth-child(3) .stats-card-label');
        const card4Label = document.querySelector('.stats-card:nth-child(4) .stats-card-label');
        const goalLabel = document.querySelector('.stats-progress-label-row span:first-child');
        const activityHeader = document.querySelector('.stats-panel:first-child .stats-panel-header h3');

        if (card3Label) card3Label.textContent = isAudio ? '주간 청취 시간' : '주간 독서 (페이지)';
        if (card4Label) card4Label.textContent = isAudio ? '월간 완청 도서' : '월간 완독 도서';
        if (activityHeader) activityHeader.innerHTML = isAudio ? '<i class="fa-solid fa-clock-rotate-left"></i> 주간 청취 활동 요약' : '<i class="fa-solid fa-clock-rotate-left"></i> 주간 독서 활동 요약';

        if (isAudio) {
          const listenSec = stats.week_listen_sec || 0;
          document.getElementById('stats-val-week-pages').textContent = formatListenTime(listenSec);
          document.getElementById('stats-val-month-completed').textContent = (stats.month_completed_books || 0).toLocaleString();

          // 오디오북 주간 목표 (5시간 = 18,000초 기준)
          const targetSec = 18000;
          const goalPercent = Math.min(100, Math.round((listenSec / targetSec) * 100));
          document.getElementById('stats-goal-percent').textContent = `${goalPercent}%`;
          document.getElementById('stats-goal-fill').style.width = `${goalPercent}%`;

          if (goalLabel) goalLabel.textContent = '주간 청취 목표 달성도 (5시간 기준)';
          document.getElementById('stats-activity-note').textContent = 
            `이번 주 총 ${formatListenTime(listenSec)} 청취하셨습니다. 꾸준한 청취 습관을 이어가세요!`;

          // 포맷 분석 동적 변경
          const fmtList = document.getElementById('stats-format-list');
          if (fmtList) {
            const m4Count = stats.format_counts?.m4b_m4a || 0;
            const mp3Count = stats.format_counts?.mp3 || 0;
            const otherCount = stats.format_counts?.other || 0;
            fmtList.innerHTML = `
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-file-audio"></i> M4B / M4A</span>
                <span class="fmt-count">${m4Count.toLocaleString()}권</span>
              </div>
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-music"></i> MP3</span>
                <span class="fmt-count">${mp3Count.toLocaleString()}권</span>
              </div>
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-compact-disc"></i> 기타 오디오</span>
                <span class="fmt-count">${otherCount.toLocaleString()}권</span>
              </div>
            `;
          }
        } else {
          const weekPages = stats.week_pages_read || 0;
          document.getElementById('stats-val-week-pages').textContent = weekPages.toLocaleString();
          document.getElementById('stats-val-month-completed').textContent = (stats.month_completed_books || 0).toLocaleString();

          const goalPercent = Math.min(100, Math.round((weekPages / 100) * 100));
          document.getElementById('stats-goal-percent').textContent = `${goalPercent}%`;
          document.getElementById('stats-goal-fill').style.width = `${goalPercent}%`;

          if (goalLabel) goalLabel.textContent = '주간 독서 목표 달성도 (100페이지 기준)';
          document.getElementById('stats-activity-note').textContent = 
            `이번 주 총 ${weekPages.toLocaleString()}페이지를 읽으셨습니다. 꾸준한 독서 습관을 이어가세요!`;

          const fmtList = document.getElementById('stats-format-list');
          if (fmtList) {
            const zipCount = stats.format_counts?.zip || 0;
            const epubCount = stats.format_counts?.epub || 0;
            const pdfCount = stats.format_counts?.pdf || 0;
            fmtList.innerHTML = `
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-file-zipper"></i> ZIP / CBZ 만화</span>
                <span class="fmt-count">${zipCount.toLocaleString()}권</span>
              </div>
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-book-bookmark"></i> EPUB / TXT 소설</span>
                <span class="fmt-count">${epubCount.toLocaleString()}권</span>
              </div>
              <div class="stats-format-item">
                <span class="fmt-name"><i class="fa-solid fa-file-pdf"></i> PDF 문서</span>
                <span class="fmt-count">${pdfCount.toLocaleString()}권</span>
              </div>
            `;
          }
        }
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
