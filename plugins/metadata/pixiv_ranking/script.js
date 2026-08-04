(function () {
  const LOG_PREFIX = '[Pixiv-Ranking-Plugin]';
  console.log(LOG_PREFIX, '0/3 Category-Level Fullpage UI loaded.');

  function fetchRankingData() {
    const grid = document.getElementById('pr-grid');
    const status = document.getElementById('pr-status');
    const contentSelect = document.getElementById('pr-content-select');
    const modeSelect = document.getElementById('pr-mode-select');
    if (!grid || !status) {
      console.warn(LOG_PREFIX, '컨테이너 엘리먼트(#pr-grid/#pr-status)를 찾지 못함');
      return;
    }

    const content = contentSelect ? contentSelect.value : 'all';
    const mode = modeSelect ? modeSelect.value : 'daily';

    status.textContent = '불러오는 중...';
    status.style.display = 'block';
    grid.innerHTML = '';

    // 참고: random_gallery 플러그인과 동일한 엔드포인트 규격을 사용합니다.
    // /api/media/dashboard/widgets/{plugin_id}/data?type={db_type}&limit={limit}
    // 여기에 상단 드롭다운에서 고른 mode/content를 추가 쿼리 파라미터로 실어보냅니다.
    // (백엔드가 flask.request.args로 이 값을 읽어 설정값보다 우선 적용함)
    // db_type은 우선 'general'로 고정했습니다. 성인 서재(adult) 등 다른 타입에서도
    // 이 탭을 노출하려면 코어가 현재 db_type을 어떻게 프론트엔드에 넘겨주는지
    // 확인 후 하드코딩된 'general' 부분을 교체해야 합니다.
    const params = new URLSearchParams({
      type: 'general',
      limit: '50',
      mode: mode,
      content: content,
    });
    const url = '/api/media/dashboard/widgets/pixiv_ranking/data?' + params.toString();

    console.log(LOG_PREFIX, '1/3 데이터 요청 시작:', url);
    const t0 = performance.now();

    fetch(url)
      .then((res) => {
        console.log(LOG_PREFIX, '1/3 응답 수신: status=' + res.status);
        return res.json();
      })
      .then((data) => {
        const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
        if (!data.success) {
          console.warn(LOG_PREFIX, '2/3 서버 오류 응답 (' + elapsed + 's):', data.error);
          status.textContent = '랭킹을 가져오지 못했습니다: ' + (data.error || '알 수 없는 오류');
          status.style.display = 'block';
          return;
        }
        const items = Array.isArray(data.items) ? data.items : [];
        console.log(
          LOG_PREFIX,
          '2/3 데이터 파싱 완료 (' + elapsed + 's): 항목 ' + items.length + '개'
        );
        renderGrid(items);
      })
      .catch((err) => {
        console.error(LOG_PREFIX, '1/3 요청 실패:', err);
        status.textContent = '서버 연결 오류';
        status.style.display = 'block';
      });
  }

  function renderGrid(items) {
    const grid = document.getElementById('pr-grid');
    const status = document.getElementById('pr-status');
    if (!grid || !status) return;
    grid.innerHTML = '';

    if (items.length === 0) {
      console.log(LOG_PREFIX, '3/3 표시할 항목 없음');
      status.textContent = '표시할 랭킹이 없습니다.';
      status.style.display = 'block';
      return;
    }
    status.style.display = 'none';

    let renderedCount = 0;
    let missingCoverCount = 0;

    items.forEach((item) => {
      const cover = item.cover || item.image || item.image_url || '';
      if (!cover) missingCoverCount += 1;

      const cell = document.createElement('a');
      cell.className = 'pr-cell';
      cell.href = item.link || item.url || '#';
      cell.target = '_blank';
      cell.rel = 'noopener noreferrer';

      const img = document.createElement('img');
      img.src = cover;
      img.alt = item.title || '';
      img.loading = 'lazy';
      img.addEventListener('error', () => {
        console.warn(LOG_PREFIX, '이미지 로드 실패:', item.title, cover.slice(0, 80));
      });
      cell.appendChild(img);

      if (item.rank) {
        const rankBadge = document.createElement('span');
        rankBadge.className = 'pr-rank-badge';
        rankBadge.textContent = '#' + item.rank;
        cell.appendChild(rankBadge);
      }

      if (item.title) {
        const caption = document.createElement('span');
        caption.className = 'pr-caption';
        caption.textContent = item.title;
        cell.appendChild(caption);
      }

      grid.appendChild(cell);
      renderedCount += 1;
    });

    console.log(
      LOG_PREFIX,
      '3/3 렌더링 완료: ' + renderedCount + '개 (cover 누락 ' + missingCoverCount + '개)'
    );
  }

  const refreshBtn = document.getElementById('pr-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      console.log(LOG_PREFIX, '새로고침 버튼 클릭');
      fetchRankingData();
    });
  }

  const contentSelectEl = document.getElementById('pr-content-select');
  if (contentSelectEl) {
    contentSelectEl.addEventListener('change', () => {
      console.log(LOG_PREFIX, '콘텐츠 타입 변경:', contentSelectEl.value);
      fetchRankingData();
    });
  }

  const modeSelectEl = document.getElementById('pr-mode-select');
  if (modeSelectEl) {
    modeSelectEl.addEventListener('change', () => {
      console.log(LOG_PREFIX, '랭킹 모드 변경:', modeSelectEl.value);
      fetchRankingData();
    });
  }

  fetchRankingData();
})();
