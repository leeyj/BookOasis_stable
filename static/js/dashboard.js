// dashboard.js – 대시보드 데이터 로드 및 수평 휠/버튼 스크롤 제어
import { state } from './state.js';
import * as api from './api.js';
import { renderDashboardHistory, renderDashboardRecentlyAdded } from './ui.js?v=20260809-unread-series-v3';
import { updateLibraryTotalCount } from './book_list.js';
import { loadPluginHealthPanel } from './plugin_health_panel.js';

let dashboardLoadToken = 0;
let pluginsLoadToken = 0;
let dashboardRowLastType = null;

// 대시보드 섹션 제목("최근 읽은 도서"/"신규 추가 도서")은 오디오북/영상 강좌 세션에서도
// "도서" 문구를 그대로 쓰고 있었다 - 상단 총계 배지(book_list.js::updateLibraryTotalCount)와
// 동일한 이유로 세션 타입별 라벨을 따로 둔다.
function updateDashboardSectionLabels(targetType) {
  const recentTitleEl = document.getElementById('dashboard-recent-title');
  const recentSuffixEl = document.getElementById('dashboard-recent-title-suffix');
  const newTitleEl = document.getElementById('dashboard-new-title');

  const recentKey = targetType === 'audiobook'
    ? 'dashboard.recent_title_audiobook'
    : targetType === 'video'
      ? 'dashboard.recent_title_video'
      : 'dashboard.recent_title';
  const newKey = targetType === 'audiobook'
    ? 'dashboard.new_books_title_audiobook'
    : targetType === 'video'
      ? 'dashboard.new_books_title_video'
      : 'dashboard.new_books_title';
  const suffixKey = targetType === 'video'
    ? 'dashboard.recent_title_suffix_video'
    : 'dashboard.recent_title_suffix';

  if (recentTitleEl) recentTitleEl.textContent = i18n.t(recentKey);
  if (newTitleEl) newTitleEl.textContent = i18n.t(newKey);
  if (recentSuffixEl) recentSuffixEl.textContent = i18n.t(suffixKey);
}

export async function loadDashboardData() {
  const requestToken = ++dashboardLoadToken;
  const targetType = state.currentLibraryType || 'general';
  state.isLoading = true;

  updateDashboardSectionLabels(targetType);

  const historyRow = document.getElementById('dashboard-history-row');
  const newRow = document.getElementById('dashboard-new-row');
  const countSpan = document.getElementById('library-total-count');
  if (countSpan) countSpan.innerText = '';

  const isTypeSwitched = dashboardRowLastType !== targetType;
  dashboardRowLastType = targetType;

  // 탭 타입 전환 시 이전 탭의 카드를 즉시 지우고 로딩 스피너로 초기화 (1~2초 잔상 현상 방지)
  if (isTypeSwitched || (historyRow && !historyRow.children.length)) {
    if (historyRow) historyRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 최근 항목을 불러오는 중...</div>';
  }
  if (isTypeSwitched || (newRow && !newRow.children.length)) {
    if (newRow) newRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 신규 항목을 불러오는 중...</div>';
  }
  
  try {
    // 0. 독서 동기부여 위젯 로드
    if (typeof window.loadDashboardInsights === 'function') {
      window.loadDashboardInsights(targetType);
    }

    // 0-1. 플러그인 로드 상태 패널 (관리자 전용, 나머지 대시보드 로딩을 막지 않도록 별도 실행)
    loadPluginHealthPanel();

    // 1. 전체 보관함 합계, 최근 읽은 도서, 신규 추가 도서를 동시에 요청
    const totalsPromise = api.fetchBooksTotals({type: targetType, libraryId: 'all'})
      .catch(err => ({ success: false, error: String(err) }));
    const historyPromise = api.fetchReadingHistory(targetType);
    const recentlyAddedPromise = fetch(`/api/media/recently-added?type=${targetType}&_=${Date.now()}`, {cache: 'no-store'})
      .then(res => res.json())
      .catch(err => ({ success: false, error: String(err) }));

    const [totalsData, historyData, newData] = await Promise.all([totalsPromise, historyPromise, recentlyAddedPromise]);
    if (requestToken !== dashboardLoadToken) return;
    if (state.currentLibraryId !== 'home' || state.currentLibraryType !== targetType) return;

    if (totalsData && totalsData.success) {
      updateLibraryTotalCount([], totalsData);
    }

    // 최근 읽은 도서 렌더링
    if (historyData && historyData.success) {
      let books = historyData.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => {
          const fmt = String(b.file_format || '').toLowerCase();
          const isAudiobook = fmt === 'audiobook' || fmt === 'audio';
          return isAudiobook
            ? (b.is_completed !== 1)
            : !(b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages));
        });
      }
      renderDashboardHistory(books);
    } else {
      if (historyRow) historyRow.innerHTML = `<div class="loading-spinner">히스토리 로드 실패: ${(historyData && historyData.error) || '오류'}</div>`;
    }

    // 신규 추가 도서 렌더링
    if (newData && newData.success) {
      renderDashboardRecentlyAdded(newData.books);
    } else {
      if (newRow) newRow.innerHTML = `<div class="loading-spinner">신규 도서 로드 실패: ${(newData && newData.error) || '오류'}</div>`;
    }
    
  } catch (e) {
    if (requestToken !== dashboardLoadToken) return;
    console.error('대시보드 데이터 로드 오류:', e);
    if (historyRow) historyRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
    if (newRow) newRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
  } finally {
    if (requestToken === dashboardLoadToken) {
      state.isLoading = false;
    }
  }
}


export async function loadDashboardPlugins(requestToken = null) {
  const section = document.getElementById('dashboard-plugins-section');
  const container = document.getElementById('dashboard-plugins-container');
  const tabsContainer = document.getElementById('plugins-view-tabs');
  const dynamicWrapper = document.getElementById('plugins-dynamic-contents-wrapper');

  if (!section || !container) return;

  const currentToken = requestToken !== null ? requestToken : ++pluginsLoadToken;

  // 1. 이전 동적 생성 탭 및 콘텐츠 초기화
  if (tabsContainer) {
    tabsContainer.querySelectorAll('.plugin-dynamic-tab-btn').forEach(btn => btn.remove());
  }
  if (dynamicWrapper) {
    dynamicWrapper.innerHTML = '';
  }
  container.innerHTML = '';

  try {
    const res = await fetch(`/api/media/dashboard/widgets?type=${state.currentLibraryType}`);
    const data = await res.json();

    if (currentToken !== pluginsLoadToken) return;

    if (data.success && data.widgets && data.widgets.length > 0) {
      section.style.display = 'block';

      // 순서 복원을 위한 정렬 리스트 획득
      let savedOrder = [];
      try {
        savedOrder = JSON.parse(localStorage.getItem('plugins_order') || '[]');
      } catch (err) {}

      // widgets 정렬 처리 (all_desk_tab가 없고 순서 저장이 있는 경우 우선 적용)
      const commonWidgets = data.widgets.filter(w => !w.all_desk_tab);
      const tabWidgets = data.widgets.filter(w => w.all_desk_tab);

      commonWidgets.sort((a, b) => {
        const idxA = savedOrder.indexOf(a.id);
        const idxB = savedOrder.indexOf(b.id);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return 0;
      });

      // 2. 공통 데스크 위젯 카드 렌더링
      for (const widget of commonWidgets) {
        if (currentToken !== pluginsLoadToken) return;

        const widgetId = String(widget.id || '').trim();
        if (!widgetId) continue;

        const contentId = `dashboard-widget-content-${widgetId}`;
        const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
        const title = escapeHtml(widget.title || widget.name || widgetId);
        const provider = escapeHtml(widget.provider || widget.name || 'Plugin');
        const subtitle = widget.subtitle ? `<div class="plugin-widget-subtitle">${escapeHtml(widget.subtitle)}</div>` : '';

        const cardHtml = `
          <div class="plugin-card" id="plugin-${widgetId}">
              <h4 class="plugin-card-header">
                  <span class="plugin-card-header-title"><i class="${iconClass}"></i><span class="plugin-card-header-title-text">${title}</span></span>
                  <span class="plugin-card-provider">제공: ${provider}</span>
              </h4>
              ${subtitle}
              <div id="${contentId}" class="plugin-widget-body">
                  <div class="loading-spinner loading-spinner--widget"><i class="fa-solid fa-circle-notch fa-spin"></i> 위젯 데이터를 불러오는 중...</div>
              </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);
        await loadDashboardWidgetData(widgetId, Number(widget.limit) || 10, contentId, currentToken);
      }

      // 3. 독점 탭 플러그인 구성
      for (const widget of tabWidgets) {
        if (currentToken !== pluginsLoadToken) return;

        const widgetId = String(widget.id || '').trim();
        if (!widgetId) continue;

        const contentId = `dashboard-widget-content-${widgetId}`;
        const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
        const title = escapeHtml(widget.title || widget.name || widgetId);
        const provider = escapeHtml(widget.provider || widget.name || 'Plugin');
        const subtitle = widget.subtitle ? `<div class="plugin-widget-subtitle plugin-widget-subtitle--tab">${escapeHtml(widget.subtitle)}</div>` : '';

        // 탭 버튼 생성
        if (tabsContainer) {
          const tabBtnHtml = `
            <button class="settings-tab-btn plugin-dynamic-tab-btn" id="tab-btn-${widgetId}" data-role="plugins-view-tab" data-plugin-tab="${widgetId}">
              <i class="${iconClass}"></i> <span>${title}</span>
            </button>
          `;
          tabsContainer.insertAdjacentHTML('beforeend', tabBtnHtml);
        }

        // 탭 본문 생성
        if (dynamicWrapper) {
          const tabContentHtml = `
            <div class="plugins-tab-content plugin-dynamic-tab-content" id="plugins-content-${widgetId}">
              <div class="dashboard-section">
                <div class="section-header">
                  <h3 class="section-title">
                    <i class="${iconClass}"></i> <span>${title}</span>
                  </h3>
                  <span class="plugin-tab-provider">제공: ${provider}</span>
                </div>
                ${subtitle}
                <div id="${contentId}" class="plugin-tab-widget-body">
                  <div class="loading-spinner loading-spinner--widget-grid"><i class="fa-solid fa-circle-notch fa-spin"></i> 데이터를 불러오는 중...</div>
                </div>
              </div>
            </div>
          `;
          dynamicWrapper.insertAdjacentHTML('beforeend', tabContentHtml);
        }

        await loadDashboardWidgetData(widgetId, Number(widget.limit) || 12, contentId, currentToken);
      }

      // 4. Sortable 활성화 (공통 데스크 카드들)
      if (typeof Sortable !== 'undefined' && container && commonWidgets.length > 0) {
        Sortable.create(container, {
          animation: 180,
          ghostClass: 'dragging',
          onEnd: function () {
            const newOrder = Array.from(container.children).map(child => child.id.replace('plugin-', ''));
            localStorage.setItem('plugins_order', JSON.stringify(newOrder));
          }
        });
      }

    } else {
      section.style.display = 'none';
      container.innerHTML = '';
    }
  } catch (e) {
    console.error('대시보드 위젯 로드 오류:', e);
    section.style.display = 'none';
  }
}

// 플러그인 뷰 내부 탭 전환 함수
export function switchPluginsViewTab(tabId) {
  // 1. 버튼 활성화 클래스 조율
  const tabsContainer = document.getElementById('plugins-view-tabs');
  if (tabsContainer) {
    tabsContainer.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(tabId === 'common-desk' ? 'tab-btn-common-desk' : `tab-btn-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');
  }

  // 2. 본문 활성화 전환
  document.querySelectorAll('.plugins-tab-content').forEach(el => {
    el.style.display = 'none';
  });

  const activeContent = document.getElementById(tabId === 'common-desk' ? 'plugins-content-common-desk' : `plugins-content-${tabId}`);
  if (activeContent) {
    activeContent.style.display = 'flex';
  }
}
window.switchPluginsViewTab = switchPluginsViewTab;

if (!window.__pluginsViewTabDelegationBound) {
  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="plugins-view-tab"], [data-role="dashboard-widget-item"]')
      : null;
    if (!target) return;

    console.log('[Dashboard-Delegation] Delegation target clicked:', target);
    event.preventDefault();
    if (target.getAttribute('data-role') === 'plugins-view-tab') {
      switchPluginsViewTab(target.getAttribute('data-plugin-tab') || 'common-desk');
      return;
    }

    const action = target.getAttribute('data-item-action');
    if (action === 'open-reader' && typeof window.openReader === 'function') {
      const bookId = Number.parseInt(target.getAttribute('data-book-id') || '', 10);
      const pagesRead = Number.parseInt(target.getAttribute('data-pages-read') || '0', 10) || 0;
      const totalPages = Number.parseInt(target.getAttribute('data-total-pages') || '0', 10) || 0;
      console.log('[Dashboard-Delegation] Delegated open-reader:', { bookId, pagesRead, totalPages });
      if (Number.isFinite(bookId) && bookId > 0) {
        window.openReader(bookId, target.getAttribute('data-file-format') || '', target.getAttribute('data-book-title') || '', pagesRead, totalPages);
      }
      return;
    }

    if (action === 'open-detail' && typeof window.openBookDetail === 'function') {
      console.log('[Dashboard-Delegation] Delegated open-detail:', target.getAttribute('data-series-name'));
      window.openBookDetail(event, target.getAttribute('data-series-name') || '', target.getAttribute('data-library-id') || null);
    }
  }, true);
  window.__pluginsViewTabDelegationBound = true;
}

async function loadDashboardWidgetData(pluginId, limit, contentId, requestToken) {
  if (requestToken !== pluginsLoadToken) return;

  const container = document.getElementById(contentId);
  if (!container) return;

  try {
    const res = await fetch(`/api/media/dashboard/widgets/${encodeURIComponent(pluginId)}/data?type=${state.currentLibraryType}&limit=${limit}`);
    const data = await res.json();

    if (requestToken !== pluginsLoadToken) return;

    if (data.success && Array.isArray(data.items) && data.items.length > 0) {
      container.innerHTML = '';
      data.items.forEach(item => {
        if (item && (item.item_type === 'metric' || item.metric)) {
          const metric = formatDashboardMetricText(item.metric || item.title || '통계');
          const value = formatDashboardMetricText(item.value || '-');
          const desc = formatDashboardMetricText(item.description || '');
          const metricHtml = `
            <div class="dashboard-metric-card">
              <span class="dashboard-metric-label">${metric}</span>
              <strong class="dashboard-metric-value">${value}</strong>
              ${desc ? `<span class="dashboard-metric-desc">${desc}</span>` : ''}
            </div>
          `;
          container.insertAdjacentHTML('beforeend', metricHtml);
          return;
        }

        const cover = item.cover || 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=100&auto=format&fit=crop&q=60';
        const title = escapeHtml(item.title || '제목 없음');
        const author = escapeHtml(item.author || '저자 미상');
        const publisher = escapeHtml(item.publisher || '출판사 미상');
        const pubDate = escapeHtml(item.pubDate || '');
        const link = item.link || '#';
        const isExternal = link && link !== '#';
        const rawSeriesName = String(item.series_name || item.series || '');
        const rawLibraryId = String(item.library_id || item.libraryId || '');
        const rawBookId = item.book_id || item.bookId || null;
        const rawFileFormat = item.file_format || item.format || '';
        const rawTitle = item.title || '';
        const rawPagesRead = item.pages_read || item.pagesRead || 0;
        const rawTotalPages = item.total_pages || item.totalPages || 0;

        let clickAttr = '';
        let isClickable = false;
        if (!isExternal) {
            if (rawBookId && rawFileFormat) {
            clickAttr = `data-role="dashboard-widget-item" data-item-action="open-reader" data-book-id="${rawBookId}" data-file-format="${escapeHtml(rawFileFormat)}" data-book-title="${escapeHtml(rawTitle)}" data-pages-read="${rawPagesRead}" data-total-pages="${rawTotalPages}"`;
                isClickable = true;
            } else if (rawSeriesName) {
            clickAttr = `data-role="dashboard-widget-item" data-item-action="open-detail" data-series-name="${escapeHtml(rawSeriesName)}" data-library-id="${escapeHtml(rawLibraryId)}"`;
                isClickable = true;
            }
        }

        const itemHtml = `
          <div class="plugin-item-card${isClickable ? ' plugin-item-card--clickable' : ''}" data-series-name="${escapeHtml(rawSeriesName)}" data-library-id="${escapeHtml(rawLibraryId)}" data-book-id="${rawBookId || ''}" data-file-format="${escapeHtml(rawFileFormat)}" ${clickAttr}>
            <div class="plugin-item-cover">
              <img src="${cover}" alt="cover">
            </div>
            <div class="plugin-item-info">
              <a class="plugin-item-title" href="${isExternal ? link : '#'}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} title="${title}">${title}</a>
              <span class="plugin-item-meta">${author}</span>
              <div class="plugin-item-footer">
                <span class="plugin-item-publisher">${publisher}</span>
                <span class="plugin-item-pubdate">${pubDate}</span>
              </div>
            </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
      });
    }
  } catch (e) {
    console.error(`대시보드 위젯 로드 오류(${pluginId}):`, e);
    container.innerHTML = '<div class="plugin-widget-error">서버 연결 오류</div>';
  }
}

function formatDashboardMetricText(value) {
  // metric/value/description 필드: 안전한 HTML 태그 허용
  return sanitizePluginHtml(value)
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\r\n/g, '\n');
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * sanitizePluginHtml – 플러그인 콘텐츠용 제한적 HTML 허용 함수
 *
 * 허용 태그: b, i, em, strong, br, span, a(href만), ul, ol, li, p, small, mark, code
 * 차단 대상: <script>, <iframe>, <object>, <embed>, on* 이벤트 속성, javascript: href
 *
 * title/author/publisher 같은 고유명사 필드에는 사용하지 말 것 (escapeHtml 유지).
 * metric/value/description/subtitle 같은 플러그인 콘텐츠 필드에만 사용할 것.
 */
function sanitizePluginHtml(value) {
  const raw = String(value || '');

  // 1단계: 위험 태그 완전 제거 (script, iframe, object, embed, form, input, style)
  const DANGEROUS_TAGS = /(<\s*\/?(script|iframe|object|embed|form|input|button|select|textarea|style|link|meta|base|svg|math)[^>]*>)/gi;
  let sanitized = raw.replace(DANGEROUS_TAGS, '');

  // 2단계: on* 이벤트 속성 제거 (onclick, onerror, onload 등)
  sanitized = sanitized.replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, '');

  // 3단계: href/src의 javascript: 프로토콜 제거
  sanitized = sanitized.replace(/(href|src)\s*=\s*["']?\s*javascript:[^"'>]*/gi, '$1="#"');

  // 4단계: 허용 태그 화이트리스트 외 모든 태그 이스케이프
  const ALLOWED_TAGS = new Set(['b', 'i', 'em', 'strong', 'br', 'span', 'a', 'ul', 'ol', 'li', 'p', 'small', 'mark', 'code']);
  sanitized = sanitized.replace(/<(\/?)(\w+)([^>]*)>/g, (match, slash, tag, attrs) => {
    const lowerTag = tag.toLowerCase();
    if (!ALLOWED_TAGS.has(lowerTag)) {
      // 허용 목록에 없는 태그는 텍스트로 이스케이프
      return match.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    if (lowerTag === 'a') {
      // <a> 태그: href, title, target만 허용 (rel="noopener" 강제)
      const hrefMatch = attrs.match(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]*))/i);
      const titleMatch = attrs.match(/title\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      const href = hrefMatch ? (hrefMatch[1] || hrefMatch[2] || hrefMatch[3] || '#') : '#';
      const title = titleMatch ? ` title="${escapeHtml(titleMatch[1] || titleMatch[2] || '')}"` : '';
      const safeHref = /^(https?:\/\/|\/)/.test(href) ? href : '#';
      return `<a href="${escapeHtml(safeHref)}"${title} target="_blank" rel="noopener noreferrer">`;
    }
    if (lowerTag === 'span') {
      // <span>: class, style만 허용 (style은 color/font-weight/font-style만)
      const styleMatch = attrs.match(/style\s*=\s*(?:"([^"]*)"|'([^']*)')/i);
      if (styleMatch) {
        const styleVal = styleMatch[1] || styleMatch[2] || '';
        // color, font-weight, font-style, font-size, text-decoration만 허용
        const safeStyle = styleVal.split(';')
          .filter(rule => /^\s*(color|font-weight|font-style|font-size|text-decoration)\s*:/i.test(rule))
          .join(';');
        return safeStyle ? `<span style="${escapeHtml(safeStyle)}">` : '<span>';
      }
      return '<span>';
    }
    // 그 외 허용 태그: 속성 전체 제거 (태그 이름만 유지)
    return `<${slash}${lowerTag}>`;
  });

  return sanitized;
}
