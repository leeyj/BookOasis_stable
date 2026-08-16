// tv.js – BookOasis TV(킷오스크 브라우징) 화면 전용 스크립트
// 설정/관리 기능 없이 카테고리 드로어 + 커버 그리드만 제공, 탭하면 /?kiosk=1 리더/플러그인 화면으로 이동한다.
(function () {
  'use strict';

  var TV_TYPE = 'general';
  var RETURN_URL = '/tv';
  var DRAWER_AUTOHIDE_MS = 6000;

  var SORT_CYCLE = { asc: 'desc', desc: 'date_desc', date_desc: 'date_asc', date_asc: 'asc' };
  var SORT_LABELS = {
    asc: { icon: 'fa-sort-alpha-down', label: '가나다 오름차순' },
    desc: { icon: 'fa-sort-alpha-up', label: '가나다 내림차순' },
    date_desc: { icon: 'fa-sort-numeric-down-alt', label: '최신 추가순' },
    date_asc: { icon: 'fa-sort-numeric-up', label: '과거 추가순' }
  };

  var state = {
    category: null, // {id, name}
    page: 1,
    hasMore: false,
    sort: localStorage.getItem('tv_sort_direction') || 'asc'
  };

  var drawerHideTimer = null;
  var loginPopupOpenedForUnauthorized = false;

  function $(id) { return document.getElementById(id); }

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fetchJson(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (res) {
      if (res.status === 401) {
        handleUnauthorized();
        return { success: false, unauthorized: true };
      }
      return res.json();
    });
  }

  function resolveCoverSrc(coverImage) {
    if (!coverImage || typeof coverImage !== 'string') return '';
    var clean = coverImage.trim();
    if (!clean) return '';
    if (clean.indexOf('http://') === 0 || clean.indexOf('https://') === 0 || clean.indexOf('/covers/') === 0 || clean.indexOf('/api/') === 0) {
      return clean;
    }
    clean = clean.replace(/^[\/\\]+/, '');
    if (clean.toLowerCase().indexOf('covers/') === 0) {
      clean = clean.substring(7).replace(/^[\/\\]+/, '');
    }
    return clean ? '/covers/' + clean : '';
  }

  function goToReader(bookId) {
    if (!bookId) return;
    var url = '/?kiosk=1&book=' + encodeURIComponent(bookId) +
      '&type=' + encodeURIComponent(TV_TYPE) +
      '&return=' + encodeURIComponent(RETURN_URL);
    window.location.href = url;
  }

  function goToPlugin(pluginId) {
    if (!pluginId) return;
    var url = '/?kiosk=1&plugin=' + encodeURIComponent(pluginId) +
      '&type=' + encodeURIComponent(TV_TYPE) +
      '&return=' + encodeURIComponent(RETURN_URL);
    window.location.href = url;
  }

  function createCard(item) {
    var card = document.createElement('div');
    card.className = 'tv-card';
    card.tabIndex = 0;

    var title = item.series_alias || item.series_name || item.title_alias || item.title || '제목 없음';
    var cover = resolveCoverSrc(item.cover_image);
    var pagesRead = Number(item.pages_read || 0);
    var totalPages = Number(item.total_pages || 0);
    var progressHtml = '';
    if (totalPages > 0 && pagesRead > 0) {
      var pct = Math.min(100, Math.round((pagesRead / totalPages) * 100));
      progressHtml = '<div class="tv-card-progress"><div class="tv-card-progress-fill" style="width:' + pct + '%;"></div></div>';
    }

    card.innerHTML =
      '<img class="tv-card-cover" src="' + escapeHtml(cover) + '" alt="" loading="lazy" onerror="this.style.visibility=\'hidden\';">' +
      '<div class="tv-card-body">' +
        '<div class="tv-card-title">' + escapeHtml(title) + '</div>' +
        progressHtml +
      '</div>';

    var bookId = item.representative_book_id || item.id;
    var open = function () { goToReader(bookId); };
    card.addEventListener('click', open);
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
    return card;
  }

  function renderRow(containerId, items) {
    var track = $(containerId);
    if (!track) return;
    track.innerHTML = '';
    if (!items || items.length === 0) {
      track.innerHTML = '<div class="tv-empty">표시할 항목이 없습니다.</div>';
      return;
    }
    var fragment = document.createDocumentFragment();
    items.forEach(function (item) { fragment.appendChild(createCard(item)); });
    track.appendChild(fragment);
  }

  function focusFirstCard(container) {
    var card = container && container.querySelector('.tv-card');
    if (card) card.focus();
  }

  function loadHomeRows() {
    Promise.all([
      fetchJson('/api/media/history?type=' + TV_TYPE),
      fetchJson('/api/media/recently-added?type=' + TV_TYPE)
    ]).then(function (results) {
      renderRow('tv-row-history', results[0].success ? results[0].books : []);
      renderRow('tv-row-recent', results[1].success ? results[1].books : []);
      if ($('tv-home-view').style.display !== 'none') {
        focusFirstCard($('tv-home-view'));
      }
    }).catch(function () {
      renderRow('tv-row-history', []);
      renderRow('tv-row-recent', []);
    });
  }

  function setActiveDrawerItem(el) {
    document.querySelectorAll('.tv-drawer-item.active').forEach(function (item) { item.classList.remove('active'); });
    if (el) el.classList.add('active');
  }

  function showHomeView() {
    state.category = null;
    $('tv-home-view').style.display = '';
    $('tv-category-view').style.display = 'none';
    setActiveDrawerItem($('tv-drawer-home'));
    focusFirstCard($('tv-home-view'));
  }

  function showCategoryView(libraryId, name, triggerEl) {
    state.category = { id: libraryId, name: name };
    state.page = 1;
    $('tv-home-view').style.display = 'none';
    $('tv-category-view').style.display = '';
    $('tv-category-title').textContent = name;
    $('tv-category-grid').innerHTML = '<div class="tv-row-loading">불러오는 중...</div>';
    $('tv-category-more').style.display = 'none';
    setActiveDrawerItem(triggerEl || null);
    loadCategoryPage(false);
  }

  function updateSortToggleUI() {
    var info = SORT_LABELS[state.sort] || SORT_LABELS.asc;
    var toggle = $('tv-sort-toggle');
    if (!toggle) return;
    toggle.querySelector('i').className = 'fa-solid ' + info.icon;
    $('tv-sort-label').textContent = info.label;
  }

  function cycleSort() {
    state.sort = SORT_CYCLE[state.sort] || 'asc';
    localStorage.setItem('tv_sort_direction', state.sort);
    updateSortToggleUI();
    state.page = 1;
    loadCategoryPage(false);
  }

  function loadCategoryPage(append) {
    if (!state.category) return;
    if (!append) $('tv-category-grid').innerHTML = '<div class="tv-row-loading">불러오는 중...</div>';
    var url = '/api/media/list?type=' + TV_TYPE +
      '&library_id=' + encodeURIComponent(state.category.id) +
      '&sort=' + encodeURIComponent(state.sort) +
      '&page=' + state.page + '&limit=30';
    fetchJson(url).then(function (data) {
      var grid = $('tv-category-grid');
      var items = (data.success && data.series) ? data.series : [];
      if (!append) grid.innerHTML = '';
      if (!items || items.length === 0) {
        if (!append) grid.innerHTML = '<div class="tv-empty">이 카테고리에 콘텐츠가 없습니다.</div>';
        $('tv-category-more').style.display = 'none';
        return;
      }
      var fragment = document.createDocumentFragment();
      items.forEach(function (item) { fragment.appendChild(createCard(item)); });
      grid.appendChild(fragment);

      $('tv-category-more').style.display = data.has_more ? '' : 'none';
      if (!append) focusFirstCard(grid);
    }).catch(function () {
      if (!append) $('tv-category-grid').innerHTML = '<div class="tv-empty">불러오지 못했습니다.</div>';
    });
  }

  function renderDrawer(libraryPayload, pluginPayload) {
    var list = $('tv-drawer-list');
    if (!list) return;
    var libraries = libraryPayload.libraries || [];
    var groups = libraryPayload.groups || [];
    var plugins = pluginPayload.category_plugins || [];

    var byGroup = {};
    var ungrouped = [];
    libraries.forEach(function (lib) {
      var key = lib.group_id == null ? '' : String(lib.group_id);
      if (key) {
        if (!byGroup[key]) byGroup[key] = [];
        byGroup[key].push(lib);
      } else {
        ungrouped.push(lib);
      }
    });

    var html = '';
    groups.forEach(function (group) {
      var groupLibs = byGroup[String(group.id)] || [];
      if (groupLibs.length === 0) return;
      html += '<div class="tv-drawer-group-header"><i class="fa-solid ' + escapeHtml(group.icon || 'fa-folder') + '"></i>' + escapeHtml(group.name || '') + '</div>';
      groupLibs.forEach(function (lib) {
        html += '<button type="button" class="tv-drawer-item" data-library-id="' + lib.id + '" data-name="' + escapeHtml(lib.name || '') + '"><i class="fa-solid ' + escapeHtml(lib.icon || 'fa-book') + '"></i><span>' + escapeHtml(lib.name || '') + '</span></button>';
      });
    });
    ungrouped.forEach(function (lib) {
      html += '<button type="button" class="tv-drawer-item" data-library-id="' + lib.id + '" data-name="' + escapeHtml(lib.name || '') + '"><i class="fa-solid ' + escapeHtml(lib.icon || 'fa-book') + '"></i><span>' + escapeHtml(lib.name || '') + '</span></button>';
    });

    if (plugins.length > 0) {
      html += '<div class="tv-drawer-group-header"><i class="fa-solid fa-puzzle-piece"></i>플러그인</div>';
      plugins.forEach(function (plugin) {
        html += '<button type="button" class="tv-drawer-item" data-plugin-id="' + escapeHtml(plugin.id) + '" data-name="' + escapeHtml(plugin.title || plugin.name || '') + '"><i class="' + escapeHtml(plugin.icon || 'fa-solid fa-puzzle-piece') + '"></i><span>' + escapeHtml(plugin.title || plugin.name || '') + '</span></button>';
      });
    }

    list.innerHTML = html || '<div class="tv-empty" style="padding:1rem 1.4rem;">카테고리가 없습니다.</div>';

    list.querySelectorAll('.tv-drawer-item[data-library-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        showCategoryView(btn.getAttribute('data-library-id'), btn.getAttribute('data-name'), btn);
        collapseDrawer();
      });
    });
    list.querySelectorAll('.tv-drawer-item[data-plugin-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        goToPlugin(btn.getAttribute('data-plugin-id'));
      });
    });
  }

  function loadDrawer() {
    Promise.all([
      fetchJson('/api/media/libraries?type=' + TV_TYPE),
      fetchJson('/api/media/category-plugins?type=' + TV_TYPE)
    ]).then(function (results) {
      var libData = results[0];
      var pluginData = results[1];
      if (libData.success || pluginData.success) {
        renderDrawer(libData.success ? libData : {}, pluginData.success ? pluginData : {});
      }
    }).catch(function () {});
  }

  function expandDrawer() {
    $('tv-drawer').classList.add('expanded');
    $('tv-drawer-scrim').classList.add('visible');
    $('tv-drawer-toggle').classList.add('is-hidden');
    clearTimeout(drawerHideTimer);
    drawerHideTimer = setTimeout(collapseDrawer, DRAWER_AUTOHIDE_MS);
    var active = document.querySelector('#tv-drawer .tv-drawer-item.active') || $('tv-drawer-home');
    if (active) active.focus();
  }

  function collapseDrawer() {
    $('tv-drawer').classList.remove('expanded');
    $('tv-drawer-scrim').classList.remove('visible');
    $('tv-drawer-toggle').classList.remove('is-hidden');
    clearTimeout(drawerHideTimer);
  }

  function toggleDrawer() {
    if ($('tv-drawer').classList.contains('expanded')) {
      collapseDrawer();
    } else {
      expandDrawer();
      closeAccountPopup();
    }
  }

  // ---------- 계정 배지 / 로그인·로그아웃 팝업 ----------

  function updateAccountBadge() {
    var nameEl = $('tv-account-name');
    var user = window.__tvUser;
    nameEl.textContent = user ? user.username : '로그인';
  }

  function renderAccountPopupState() {
    var user = window.__tvUser;
    var userBox = $('tv-account-popup-user');
    var loginForm = $('tv-login-form');
    if (user) {
      userBox.style.display = '';
      loginForm.style.display = 'none';
      $('tv-account-popup-username').textContent = user.username + (user.role === 'admin' ? ' (관리자)' : '');
    } else {
      userBox.style.display = 'none';
      loginForm.style.display = '';
      $('tv-login-error').style.display = 'none';
    }
  }

  function openAccountPopup() {
    renderAccountPopupState();
    $('tv-account-popup').style.display = '';
    collapseDrawer();
  }

  function closeAccountPopup() {
    $('tv-account-popup').style.display = 'none';
  }

  function toggleAccountPopup() {
    if ($('tv-account-popup').style.display === 'none') {
      openAccountPopup();
    } else {
      closeAccountPopup();
    }
  }

  function handleUnauthorized() {
    window.__tvUser = null;
    updateAccountBadge();
    if (loginPopupOpenedForUnauthorized) return;
    loginPopupOpenedForUnauthorized = true;
    openAccountPopup();
  }

  function handleLoginSubmit(e) {
    e.preventDefault();
    var username = $('tv-login-username').value.trim();
    var password = $('tv-login-password').value;
    var errorEl = $('tv-login-error');
    errorEl.style.display = 'none';
    if (!username || !password) return;

    fetch('/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password })
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (result) {
      if (result.ok && result.data.success) {
        window.__tvUser = { username: username, role: result.data.role };
        loginPopupOpenedForUnauthorized = false;
        updateAccountBadge();
        closeAccountPopup();
        $('tv-login-password').value = '';
        loadDrawer();
        loadHomeRows();
      } else {
        errorEl.textContent = (result.data && result.data.error) || '로그인에 실패했습니다.';
        errorEl.style.display = '';
      }
    }).catch(function () {
      errorEl.textContent = '서버에 연결할 수 없습니다.';
      errorEl.style.display = '';
    });
  }

  function handleLogout() {
    window.location.href = '/logout';
  }

  // ---------- 리모컨(방향키) 내비게이션 ----------

  function getRowCards(rowEl) {
    return Array.prototype.slice.call(rowEl.querySelectorAll('.tv-card'));
  }

  function focusHomeRowNeighbor(currentCard, direction) {
    var row = currentCard.closest('.tv-row-track');
    if (!row) return false;
    var cards = getRowCards(row);
    var idx = cards.indexOf(currentCard);

    if (direction === 'left' || direction === 'right') {
      var next = cards[direction === 'left' ? idx - 1 : idx + 1];
      if (next) next.focus();
      return true;
    }

    var rows = Array.prototype.slice.call(document.querySelectorAll('#tv-home-view .tv-row-track'));
    var rowIdx = rows.indexOf(row);
    if (direction === 'down') {
      var nextRow = rows[rowIdx + 1];
      if (nextRow) {
        var nextCards = getRowCards(nextRow);
        var target = nextCards[Math.min(idx, nextCards.length - 1)];
        if (target) target.focus();
      }
      return true;
    }
    if (direction === 'up') {
      if (rowIdx === 0) {
        $('tv-drawer-toggle').focus();
        return true;
      }
      var prevRow = rows[rowIdx - 1];
      var prevCards = getRowCards(prevRow);
      var prevTarget = prevCards[Math.min(idx, prevCards.length - 1)];
      if (prevTarget) prevTarget.focus();
      return true;
    }
    return false;
  }

  function getGridRows(gridEl) {
    var cards = Array.prototype.slice.call(gridEl.querySelectorAll('.tv-card'));
    var rows = [];
    cards.forEach(function (card) {
      var top = card.offsetTop;
      var row = null;
      for (var i = 0; i < rows.length; i++) {
        if (Math.abs(rows[i].top - top) < 4) { row = rows[i]; break; }
      }
      if (!row) {
        row = { top: top, cards: [] };
        rows.push(row);
      }
      row.cards.push(card);
    });
    rows.sort(function (a, b) { return a.top - b.top; });
    return rows.map(function (r) { return r.cards; });
  }

  function focusCategoryGridNeighbor(currentCard, direction) {
    var grid = $('tv-category-grid');
    if (!grid || !grid.contains(currentCard)) return false;
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.tv-card'));
    var idx = cards.indexOf(currentCard);
    var moreBtn = $('tv-category-more');
    var moreVisible = moreBtn && moreBtn.style.display !== 'none';

    if (direction === 'left') {
      if (cards[idx - 1]) cards[idx - 1].focus();
      return true;
    }
    if (direction === 'right') {
      if (cards[idx + 1]) cards[idx + 1].focus();
      else if (moreVisible) moreBtn.focus();
      return true;
    }

    var rows = getGridRows(grid);
    var rowIdx = -1, colIdx = -1;
    rows.forEach(function (row, ri) {
      var ci = row.indexOf(currentCard);
      if (ci !== -1) { rowIdx = ri; colIdx = ci; }
    });
    if (rowIdx === -1) return false;

    if (direction === 'down') {
      var nextRow = rows[rowIdx + 1];
      if (nextRow) {
        (nextRow[colIdx] || nextRow[nextRow.length - 1]).focus();
      } else if (moreVisible) {
        moreBtn.focus();
      }
      return true;
    }
    if (direction === 'up') {
      if (rowIdx === 0) {
        $('tv-sort-toggle').focus();
      } else {
        var prevRow = rows[rowIdx - 1];
        (prevRow[colIdx] || prevRow[prevRow.length - 1]).focus();
      }
      return true;
    }
    return false;
  }

  function focusDrawerNeighbor(current, direction) {
    var items = Array.prototype.slice.call(
      document.querySelectorAll('#tv-drawer-home, #tv-drawer-list .tv-drawer-item')
    );
    var idx = items.indexOf(current);
    if (idx === -1) return false;
    if (direction === 'down') {
      if (items[idx + 1]) items[idx + 1].focus();
      return true;
    }
    if (direction === 'up') {
      if (items[idx - 1]) items[idx - 1].focus();
      else $('tv-drawer-close').focus();
      return true;
    }
    return direction === 'left' || direction === 'right';
  }

  function handleEscapeKey() {
    if ($('tv-account-popup').style.display !== 'none') {
      closeAccountPopup();
      $('tv-account-badge').focus();
      return;
    }
    if ($('tv-drawer').classList.contains('expanded')) {
      collapseDrawer();
      $('tv-drawer-toggle').focus();
      return;
    }
    if ($('tv-category-view').style.display !== 'none') {
      showHomeView();
    }
  }

  // 콘텐츠 영역(홈 첫 카드 또는 카테고리 정렬 버튼)으로 내려가는 공통 목적지
  function focusContentTop() {
    if ($('tv-category-view').style.display !== 'none') {
      var sortBtn = $('tv-sort-toggle');
      if (sortBtn) { sortBtn.focus(); return; }
    }
    focusFirstCard($('tv-home-view'));
  }

  function handleGlobalKeydown(e) {
    if (e.key === 'Escape') {
      handleEscapeKey();
      e.preventDefault();
      return;
    }

    var directionMap = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
    var direction = directionMap[e.key];
    if (!direction) return;

    var active = document.activeElement;
    if (!active || !active.classList) return;

    var handled = false;
    if (active.classList.contains('tv-card')) {
      var grid = $('tv-category-grid');
      handled = (grid && grid.contains(active))
        ? focusCategoryGridNeighbor(active, direction)
        : focusHomeRowNeighbor(active, direction);
    } else if (active.id === 'tv-drawer-home' || active.classList.contains('tv-drawer-item')) {
      handled = focusDrawerNeighbor(active, direction);
    } else if (active.id === 'tv-sort-toggle') {
      if (direction === 'down') {
        focusFirstCard($('tv-category-grid'));
        handled = true;
      } else if (direction === 'left' || direction === 'up') {
        $('tv-drawer-toggle').focus();
        handled = true;
      } else if (direction === 'right') {
        $('tv-account-badge').focus();
        handled = true;
      }
    } else if (active.id === 'tv-category-more') {
      if (direction === 'up') {
        var gridCards = $('tv-category-grid').querySelectorAll('.tv-card');
        if (gridCards.length) gridCards[gridCards.length - 1].focus();
        handled = true;
      }
    } else if (active.id === 'tv-drawer-toggle') {
      if (direction === 'down') {
        focusContentTop();
        handled = true;
      } else if (direction === 'right') {
        $('tv-account-badge').focus();
        handled = true;
      }
    } else if (active.id === 'tv-account-badge') {
      if (direction === 'down') {
        focusContentTop();
        handled = true;
      } else if (direction === 'left') {
        $('tv-drawer-toggle').focus();
        handled = true;
      }
    }

    if (handled) e.preventDefault();
  }

  function init() {
    $('tv-drawer-toggle').addEventListener('click', toggleDrawer);
    $('tv-drawer-close').addEventListener('click', collapseDrawer);
    $('tv-drawer-scrim').addEventListener('click', collapseDrawer);
    $('tv-drawer').addEventListener('mouseenter', function () { clearTimeout(drawerHideTimer); });
    $('tv-drawer').addEventListener('mouseleave', function () {
      if ($('tv-drawer').classList.contains('expanded')) {
        drawerHideTimer = setTimeout(collapseDrawer, DRAWER_AUTOHIDE_MS);
      }
    });
    $('tv-category-more').addEventListener('click', function () {
      state.page += 1;
      loadCategoryPage(true);
    });
    $('tv-drawer-home').addEventListener('click', function () {
      showHomeView();
      collapseDrawer();
    });
    $('tv-sort-toggle').addEventListener('click', cycleSort);

    $('tv-account-badge').addEventListener('click', toggleAccountPopup);
    $('tv-account-logout-btn').addEventListener('click', handleLogout);
    $('tv-login-form').addEventListener('submit', handleLoginSubmit);
    document.addEventListener('click', function (e) {
      var popup = $('tv-account-popup');
      if (popup.style.display === 'none') return;
      if (popup.contains(e.target) || $('tv-account-badge').contains(e.target)) return;
      closeAccountPopup();
    });

    document.addEventListener('keydown', handleGlobalKeydown);

    updateAccountBadge();
    updateSortToggleUI();
    showHomeView();
    loadHomeRows();
    loadDrawer();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
