(function () {
  console.log('[Reading-Review-Plugin] Category-Level Fullpage UI loaded.');

  const PLUGIN_ID = 'reading_review';
  let currentType = 'general';
  let selectedBook = null; // {book_id, title, series_name, author, cover_image, file_format}
  let searchDebounceTimer = null;

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  // marked.js는 코어가 이미 전역으로 로드해두므로(변경 이력 탭에서 사용) 새로
  // 라이브러리를 추가하지 않고 그대로 재사용한다. 없는 환경(로딩 실패 등)이면
  // 원문을 <pre>로 안전하게 보여주는 것으로 대체한다.
  function renderMarkdown(text) {
    const src = text == null ? '' : String(text);
    if (!src.trim()) return '';
    if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
      try {
        return marked.parse(src);
      } catch (e) {
        console.warn('[Reading-Review-Plugin] marked.parse failed, falling back to plain text.', e);
      }
    }
    return `<pre style="white-space:pre-wrap;font-family:inherit;margin:0;">${escapeHtml(src)}</pre>`;
  }

  function downloadBlob(filename, blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadTextFile(filename, content) {
    downloadBlob(filename, new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  }

  function downloadBase64File(filename, base64, mime) {
    const byteChars = atob(base64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
    downloadBlob(filename, new Blob([new Uint8Array(byteNumbers)], { type: mime || 'application/zip' }));
  }

  function callAction(actionId, context) {
    return fetch('/api/media/context-menu/book/plugins/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plugin_id: PLUGIN_ID,
        action_id: actionId,
        type: currentType,
        context: context || {},
      }),
    }).then((res) => res.json());
  }

  // ── 테마 실시간 연동 ──
  function getCurrentTheme() {
    return document.documentElement.getAttribute('data-app-theme') || 'purple';
  }
  new MutationObserver((mutations) => {
    mutations.forEach((m) => {
      if (m.type === 'attributes' && m.attributeName === 'data-app-theme') {
        console.log('[Reading-Review-Plugin] Theme changed:', getCurrentTheme());
      }
    });
  }).observe(document.documentElement, { attributes: true });

  // ── 라이브러리 타입 전환 ──
  document.querySelectorAll('.rr-type-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.rr-type-btn').forEach((b) => b.classList.remove('active'));
      const target = e.currentTarget;
      target.classList.add('active');
      currentType = target.dataset.type || 'general';
      refreshActiveTab();
    });
  });

  // ── 탭 전환 ──
  document.querySelectorAll('.rr-tab').forEach((tab) => {
    tab.addEventListener('click', (e) => {
      const name = e.currentTarget.dataset.tab;
      document.querySelectorAll('.rr-tab').forEach((t) => t.classList.remove('active'));
      e.currentTarget.classList.add('active');
      document.querySelectorAll('.rr-panel').forEach((p) => {
        p.hidden = p.dataset.panel !== name;
      });
      refreshActiveTab();
    });
  });

  function refreshActiveTab() {
    const active = document.querySelector('.rr-tab.active').dataset.tab;
    if (active === 'list') loadReviewList();
    if (active === 'stats') loadStats();
  }

  // ── 책 검색 ──
  const searchInput = document.getElementById('rr-book-search');
  const resultsBox = document.getElementById('rr-book-results');

  searchInput.addEventListener('input', () => {
    clearTimeout(searchDebounceTimer);
    const q = searchInput.value.trim();
    if (!q) {
      resultsBox.innerHTML = '';
      return;
    }
    searchDebounceTimer = setTimeout(() => {
      callAction('search_books', { query: q }).then((data) => {
        if (!data.success) return;
        renderBookResults(data.items || []);
      });
    }, 300);
  });

  function renderBookResults(items) {
    if (!items.length) {
      resultsBox.innerHTML = '<p class="rr-empty">검색 결과가 없습니다.</p>';
      return;
    }
    resultsBox.innerHTML = items
      .map((it, idx) => {
        const isSeries = Number(it.volume_count || 1) > 1;
        return `
        <div class="rr-book-result-item" data-idx="${idx}">
          <img class="rr-book-result-cover" src="${it.cover_image ? escapeHtml(it.cover_image) : ''}" onerror="this.style.visibility='hidden'" alt="">
          <div class="rr-book-result-info">
            <strong>${escapeHtml(it.title || '제목 없음')}${isSeries ? ` <span class="rr-series-badge">전체 ${it.volume_count}권</span>` : ''}</strong>
            <span>${escapeHtml(it.author || '작가 미상')}</span>
          </div>
        </div>`;
      })
      .join('');

    resultsBox.querySelectorAll('.rr-book-result-item').forEach((el, idx) => {
      el.addEventListener('click', () => selectBook(items[idx]));
    });
  }

  function selectBook(book) {
    selectedBook = {
      book_id: book.book_id,
      title: book.title,
      series_name: book.series_name,
      author: book.author,
      cover_image: book.cover_image,
      file_format: book.file_format,
    };
    document.getElementById('rr-book-title').value = book.title || '';
    document.getElementById('rr-selected-title').textContent = book.title || '';
    document.getElementById('rr-selected-author').textContent = book.author || '작가 미상';
    document.getElementById('rr-selected-cover').src = book.cover_image || '';
    document.getElementById('rr-selected-book').hidden = false;
    resultsBox.innerHTML = '';
    searchInput.value = '';
  }

  document.getElementById('rr-clear-selected').addEventListener('click', () => {
    selectedBook = null;
    document.getElementById('rr-selected-book').hidden = true;
  });

  // ── 별점 선택 ──
  const starPicker = document.getElementById('rr-star-picker');
  function paintStars(value) {
    starPicker.dataset.value = value;
    starPicker.querySelectorAll('i').forEach((star) => {
      star.classList.toggle('rr-star-filled', Number(star.dataset.star) <= value);
    });
  }
  starPicker.querySelectorAll('i').forEach((star) => {
    star.addEventListener('click', () => paintStars(Number(star.dataset.star)));
  });

  // ── Markdown 편집 / 미리보기 토글 ──
  const bodyModeToggle = document.getElementById('rr-body-mode-toggle');
  const bodyTextarea = document.getElementById('rr-body');
  const bodyPreview = document.getElementById('rr-body-preview');

  function switchBodyMode(mode) {
    bodyModeToggle.dataset.mode = mode;
    bodyModeToggle.querySelectorAll('.rr-mode-btn').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
    if (mode === 'preview') {
      bodyPreview.innerHTML = renderMarkdown(bodyTextarea.value) || '<p class="rr-empty">내용이 없습니다.</p>';
      bodyPreview.hidden = false;
      bodyTextarea.hidden = true;
    } else {
      bodyPreview.hidden = true;
      bodyTextarea.hidden = false;
    }
  }

  bodyModeToggle.querySelectorAll('.rr-mode-btn').forEach((btn) => {
    btn.addEventListener('click', () => switchBodyMode(btn.dataset.mode));
  });

  // ── 폼 초기화/제출 ──
  const form = document.getElementById('rr-review-form');
  const statusEl = document.getElementById('rr-save-status');

  function resetForm() {
    document.getElementById('rr-review-id').value = '';
    document.getElementById('rr-book-title').value = '';
    document.getElementById('rr-finished-date').value = '';
    document.getElementById('rr-tags').value = '';
    document.getElementById('rr-spoiler').checked = false;
    document.getElementById('rr-body').value = '';
    paintStars(0);
    switchBodyMode('edit');
    selectedBook = null;
    document.getElementById('rr-selected-book').hidden = true;
    statusEl.textContent = '';
    statusEl.className = 'rr-save-status';
  }

  document.getElementById('rr-reset-form').addEventListener('click', resetForm);

  document.getElementById('rr-export-current').addEventListener('click', () => {
    const reviewId = document.getElementById('rr-review-id').value;
    if (!reviewId) {
      statusEl.textContent = '먼저 저장한 뒤에 내보낼 수 있습니다.';
      statusEl.className = 'rr-save-status rr-status-err';
      return;
    }
    exportSingleReview(reviewId);
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const bookTitle = document.getElementById('rr-book-title').value.trim();
    if (!bookTitle) return;

    const context = {
      review_id: document.getElementById('rr-review-id').value || null,
      book_id: selectedBook ? selectedBook.book_id : null,
      book_title: bookTitle,
      series_name: selectedBook ? selectedBook.series_name : null,
      author: selectedBook ? selectedBook.author : null,
      cover_image: selectedBook ? selectedBook.cover_image : null,
      file_format: selectedBook ? selectedBook.file_format : null,
      rating: Number(starPicker.dataset.value || 0),
      tags: document.getElementById('rr-tags').value,
      spoiler: document.getElementById('rr-spoiler').checked,
      finished_date: document.getElementById('rr-finished-date').value || null,
      body: document.getElementById('rr-body').value,
    };

    statusEl.textContent = '저장 중...';
    statusEl.className = 'rr-save-status';

    callAction('save_review', context).then((data) => {
      if (data.success) {
        statusEl.textContent = data.message || '저장되었습니다.';
        statusEl.className = 'rr-save-status rr-status-ok';
        document.getElementById('rr-review-id').value = data.review_id || '';
      } else {
        statusEl.textContent = data.error || '저장에 실패했습니다.';
        statusEl.className = 'rr-save-status rr-status-err';
      }
    });
  });

  // ── 목록 탭 ──
  const listBox = document.getElementById('rr-review-list');
  const listSearch = document.getElementById('rr-list-search');
  const listSort = document.getElementById('rr-list-sort');
  const listMinRating = document.getElementById('rr-list-min-rating');

  let listDebounceTimer = null;
  [listSearch, listSort, listMinRating].forEach((el) => {
    el.addEventListener(el === listSearch ? 'input' : 'change', () => {
      clearTimeout(listDebounceTimer);
      listDebounceTimer = setTimeout(loadReviewList, 250);
    });
  });

  function exportSingleReview(reviewId) {
    callAction('export_review', { review_id: reviewId }).then((data) => {
      if (!data.success) {
        alert(data.error || '내보내기에 실패했습니다.');
        return;
      }
      downloadTextFile(data.filename, data.content);
    });
  }

  document.getElementById('rr-export-all').addEventListener('click', () => {
    callAction('export_all_reviews', {
      query: listSearch.value.trim(),
      sort: listSort.value,
      min_rating: Number(listMinRating.value || 0),
    }).then((data) => {
      if (!data.success) {
        alert(data.error || '내보낼 독후감이 없습니다.');
        return;
      }
      downloadBase64File(data.filename, data.content_base64, 'application/zip');
    });
  });

  function loadReviewList() {
    listBox.innerHTML = '<p class="rr-empty">불러오는 중입니다...</p>';
    callAction('list_reviews', {
      query: listSearch.value.trim(),
      sort: listSort.value,
      min_rating: Number(listMinRating.value || 0),
    }).then((data) => {
      if (!data.success) {
        listBox.innerHTML = `<p class="rr-empty">${escapeHtml(data.error || '불러오기에 실패했습니다.')}</p>`;
        return;
      }
      renderReviewList(data.items || []);
    });
  }

  function renderReviewList(items) {
    if (!items.length) {
      listBox.innerHTML = '<p class="rr-empty">아직 작성한 독후감이 없습니다. "독후감 쓰기" 탭에서 첫 기록을 남겨보세요.</p>';
      return;
    }
    listBox.innerHTML = items
      .map((r) => {
        const stars = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
        const tagsHtml = (r.tags || []).map((t) => `<span class="rr-review-tag">#${escapeHtml(t)}</span>`).join('');
        const cover = r.cover_image ? escapeHtml(r.cover_image) : '';
        const meta = [r.series_name, r.author, r.finished_date ? `완독 ${r.finished_date}` : null]
          .filter(Boolean)
          .map(escapeHtml)
          .join(' · ');
        const bodyHtml = renderMarkdown(r.body) || '<p class="rr-empty" style="padding:0;">내용 없음</p>';
        return `
        <div class="rr-review-card" data-id="${r.id}">
          <img class="rr-review-cover" src="${cover}" onerror="this.style.visibility='hidden'" alt="">
          <div class="rr-review-body">
            <div class="rr-review-top">
              <h4 class="rr-review-title">${escapeHtml(r.book_title)}</h4>
              <span class="rr-review-stars">${stars}</span>
            </div>
            <p class="rr-review-meta">${meta}</p>
            <div class="rr-review-tags">
              ${r.spoiler ? '<span class="rr-spoiler-badge">스포일러 포함</span>' : ''}
              ${tagsHtml}
            </div>
            <div class="rr-review-excerpt rr-md-rendered">${bodyHtml}</div>
            <div class="rr-review-actions">
              <button type="button" class="rr-btn rr-btn-ghost rr-edit-review" data-id="${r.id}"><i class="fa-solid fa-pen"></i> 수정</button>
              <button type="button" class="rr-btn rr-btn-ghost rr-export-review" data-id="${r.id}"><i class="fa-solid fa-file-export"></i> 내보내기</button>
              <button type="button" class="rr-btn rr-btn-danger rr-delete-review" data-id="${r.id}"><i class="fa-solid fa-trash"></i> 삭제</button>
            </div>
          </div>
        </div>`;
      })
      .join('');

    listBox.querySelectorAll('.rr-edit-review').forEach((btn) => {
      btn.addEventListener('click', () => editReview(btn.dataset.id));
    });
    listBox.querySelectorAll('.rr-export-review').forEach((btn) => {
      btn.addEventListener('click', () => exportSingleReview(btn.dataset.id));
    });
    listBox.querySelectorAll('.rr-delete-review').forEach((btn) => {
      btn.addEventListener('click', () => deleteReview(btn.dataset.id));
    });
  }

  function editReview(reviewId) {
    callAction('get_review', { review_id: reviewId }).then((data) => {
      if (!data.success) return;
      const r = data.review;
      document.querySelector('.rr-tab[data-tab="write"]').click();
      document.getElementById('rr-review-id').value = r.id;
      document.getElementById('rr-book-title').value = r.book_title || '';
      document.getElementById('rr-finished-date').value = r.finished_date || '';
      document.getElementById('rr-tags').value = (r.tags || []).join(', ');
      document.getElementById('rr-spoiler').checked = !!r.spoiler;
      document.getElementById('rr-body').value = r.body || '';
      paintStars(r.rating || 0);
      switchBodyMode('edit');

      if (r.book_id) {
        selectedBook = {
          book_id: r.book_id,
          title: r.book_title,
          series_name: r.series_name,
          author: r.author,
          cover_image: r.cover_image,
          file_format: r.file_format,
        };
        document.getElementById('rr-selected-title').textContent = r.book_title || '';
        document.getElementById('rr-selected-author').textContent = r.author || '작가 미상';
        document.getElementById('rr-selected-cover').src = r.cover_image || '';
        document.getElementById('rr-selected-book').hidden = false;
      }
      statusEl.textContent = '기존 독후감을 불러왔습니다. 수정 후 저장하세요.';
      statusEl.className = 'rr-save-status';
    });
  }

  function deleteReview(reviewId) {
    if (!confirm('이 독후감을 삭제할까요? 되돌릴 수 없습니다.')) return;
    callAction('delete_review', { review_id: reviewId }).then((data) => {
      if (data.success) loadReviewList();
      else alert(data.error || '삭제에 실패했습니다.');
    });
  }

  // ── 통계 탭 ──
  function loadStats() {
    callAction('get_stats', {}).then((data) => {
      if (!data.success) return;
      const s = data.stats;
      document.getElementById('rr-stat-total').textContent = s.total_reviews;
      document.getElementById('rr-stat-avg').textContent = s.total_reviews ? `★ ${s.avg_rating}` : '-';

      const tagCloud = document.getElementById('rr-tag-cloud');
      if (!s.top_tags.length) {
        tagCloud.innerHTML = '<p class="rr-empty">아직 태그 데이터가 없습니다.</p>';
      } else {
        tagCloud.innerHTML = s.top_tags
          .map((t) => `<span class="rr-tag-pill">#${escapeHtml(t.tag)}<b>${t.count}</b></span>`)
          .join('');
      }

      const monthBars = document.getElementById('rr-month-bars');
      if (!s.monthly.length) {
        monthBars.innerHTML = '<p class="rr-empty">아직 월별 데이터가 없습니다.</p>';
      } else {
        const max = Math.max(...s.monthly.map((m) => m.count), 1);
        monthBars.innerHTML = s.monthly
          .map((m) => {
            const heightPct = Math.max(6, Math.round((m.count / max) * 100));
            return `
            <div class="rr-month-bar-col">
              <div class="rr-month-bar-fill" style="height:${heightPct}%"></div>
              <span class="rr-month-bar-label">${escapeHtml(m.month.slice(5))}월 (${m.count})</span>
            </div>`;
          })
          .join('');
      }
    });
  }

  // ── 컨텍스트 메뉴 핸드오프: 도서 카드에서 "독후감 쓰기"로 넘어온 포커스가 있는지 확인 ──
  function checkFocus() {
    callAction('get_focus', {}).then((data) => {
      if (!data.success || !data.focus) return;
      const f = data.focus;
      document.querySelector('.rr-tab[data-tab="write"]').click();
      selectBook({
        book_id: f.book_id,
        title: f.book_title,
        series_name: f.series_name,
        author: f.author,
        cover_image: f.cover_image,
        file_format: f.file_format,
      });
      callAction('clear_focus', {});
    });
  }

  resetForm();
  checkFocus();
})();
