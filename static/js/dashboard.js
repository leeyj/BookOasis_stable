// dashboard.js – 대시보드 데이터 로드 및 수평 휠/버튼 스크롤 제어
import { state } from './state.js';
import * as api from './api.js';
import { renderDashboardHistory, renderDashboardRecentlyAdded } from './ui.js';

let dashboardLoadToken = 0;

export async function loadDashboardData() {
  const requestToken = ++dashboardLoadToken;
  state.isLoading = true;
  const historyRow = document.getElementById('dashboard-history-row');
  const newRow = document.getElementById('dashboard-new-row');
  if (historyRow) historyRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 최근 읽은 도서를 불러오는 중...</div>';
  if (newRow) newRow.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> 신규 도서를 불러오는 중...</div>';
  
  try {
    // 1. 최근 읽은 도서 조회
    const historyData = await api.fetchReadingHistory(state.currentLibraryType);
    if (historyData.success) {
      let books = historyData.books || [];
      if (state.hideCompletedInHistory) {
        books = books.filter(b => !(b.is_completed === 1 || (b.total_pages > 0 && b.pages_read >= b.total_pages)));
      }
      renderDashboardHistory(books);

    } else {
      if (historyRow) historyRow.innerHTML = `<div class="loading-spinner">히스토리 로드 실패: ${historyData.error || '오류'}</div>`;
    }

    // 2. 신규 추가 도서 조회
    const newRes = await fetch(`/api/media/recently-added?type=${state.currentLibraryType}`);
    const newData = await newRes.json();
    if (newData.success) {
      renderDashboardRecentlyAdded(newData.books);
    } else {
      if (newRow) newRow.innerHTML = `<div class="loading-spinner">신규 도서 로드 실패: ${newData.error || '오류'}</div>`;
    }
    
    // 3. 플러그인 렌더링 (동적 위젯)
    await loadDashboardPlugins(requestToken);
  } catch (e) {
    console.error('대시보드 데이터 로드 오류:', e);
    if (historyRow) historyRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
    if (newRow) newRow.innerHTML = '<div class="loading-spinner">서버 연결 오류</div>';
  } finally {
    state.isLoading = false;
  }
}

export function scrollDashboardRow(type, dir) {
  const rowId = type === 'history' ? 'dashboard-history-row' : 'dashboard-new-row';
  const container = document.getElementById(rowId);
  if (container) {
    const scrollAmount = container.clientWidth * 0.7;
    container.scrollBy({
      left: dir === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  }
}

async function loadDashboardPlugins(requestToken) {
  const section = document.getElementById('dashboard-plugins-section');
  const container = document.getElementById('dashboard-plugins-container');
  if (!section || !container) return;

  try {
    const res = await fetch('/api/media/dashboard/widgets');
    const data = await res.json();

    // Stale 요청은 렌더링하지 않습니다.
    if (requestToken !== dashboardLoadToken) return;

    if (data.success && data.widgets && data.widgets.length > 0) {
      section.style.display = 'block';
      container.innerHTML = '';

      const widgetById = new Map();
      for (const widget of data.widgets) {
        const widgetId = String((widget && widget.id) || '').trim();
        if (!widgetId) continue;
        if (widgetById.has(widgetId)) {
          console.warn(`[Dashboard] Duplicate widget id ignored: ${widgetId}`);
          continue;
        }
        widgetById.set(widgetId, widget);
      }

      for (const widget of widgetById.values()) {
        if (requestToken !== dashboardLoadToken) return;

        const widgetId = String(widget.id || '').trim();
        if (!widgetId) continue;

        const contentId = `dashboard-widget-content-${widgetId}`;
        const iconClass = widget.icon || 'fa-solid fa-puzzle-piece';
        const title = escapeHtml(widget.title || widget.name || widgetId);
        const provider = escapeHtml(widget.provider || widget.name || 'Plugin');
        const subtitle = widget.subtitle ? `<div style="margin-top: 0.35rem; color: #94a3b8; font-size: 0.78rem;">${escapeHtml(widget.subtitle)}</div>` : '';

        const cardHtml = `
          <div class="plugin-card" id="plugin-${widgetId}" style="width: 100%; max-width: 500px; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 1rem;">
              <h4 style="margin: 0 0 0.7rem 0; color: #cbd5e1; font-size: 1rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center; gap: 0.6rem;">
                  <span style="display:flex; align-items:center; min-width:0;"><i class="${iconClass}" style="color: #38bdf8; margin-right: 0.35rem;"></i><span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${title}</span></span>
                  <span style="font-size: 0.75rem; color: #64748b; font-weight: normal; flex-shrink:0;">제공: ${provider}</span>
              </h4>
              ${subtitle}
              <div id="${contentId}" style="display: flex; flex-direction: column; gap: 1rem; max-height: 400px; overflow-y: auto; padding-right: 0.5rem; margin-top: 0.6rem;">
                  <div class="loading-spinner" style="padding: 1rem 0;"><i class="fa-solid fa-circle-notch fa-spin"></i> 위젯 데이터를 불러오는 중...</div>
              </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);

        await loadDashboardWidgetData(widgetId, Number(widget.limit) || 10, contentId, requestToken);
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

async function loadDashboardWidgetData(pluginId, limit, contentId, requestToken) {
  if (requestToken !== dashboardLoadToken) return;

  const container = document.getElementById(contentId);
  if (!container) return;

  try {
    const res = await fetch(`/api/media/dashboard/widgets/${encodeURIComponent(pluginId)}/data?type=${state.currentLibraryType}&limit=${limit}`);
    const data = await res.json();

    if (requestToken !== dashboardLoadToken) return;

    if (data.success && Array.isArray(data.items) && data.items.length > 0) {
      container.innerHTML = '';
      data.items.forEach(item => {
        if (item && (item.item_type === 'metric' || item.metric)) {
          const metric = escapeHtml(item.metric || item.title || '통계');
          const value = escapeHtml(item.value || '-');
          const desc = escapeHtml(item.description || '');
          const metricHtml = `
            <div style="padding: 0.85rem 0.9rem; border-radius: 8px; background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.15); display: flex; flex-direction: column; gap: 0.2rem;">
              <span style="color: #94a3b8; font-size: 0.8rem;">${metric}</span>
              <strong style="color: #f8fafc; font-size: 1.15rem; line-height: 1.35;">${value}</strong>
              ${desc ? `<span style="color: #64748b; font-size: 0.74rem;">${desc}</span>` : ''}
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

        const itemHtml = `
          <div style="display: flex; gap: 1rem; align-items: flex-start; padding-bottom: 0.8rem; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <div style="width: 60px; height: 85px; flex-shrink: 0; border-radius: 4px; overflow: hidden; background: #1e293b;">
              <img src="${cover}" alt="cover" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.3rem; flex: 1; min-width: 0;">
              <a href="${isExternal ? link : '#'}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} style="color: #f8fafc; font-size: 0.95rem; font-weight: 600; text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${title}">${title}</a>
              <span style="color: #94a3b8; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${author}</span>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.2rem;">
                <span style="color: #64748b; font-size: 0.75rem;">${publisher}</span>
                <span style="color: #a855f7; font-size: 0.75rem;">${pubDate}</span>
              </div>
            </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
      });
    } else {
      const emptyMsg = escapeHtml(data.error || '표시할 항목이 없습니다.');
      container.innerHTML = `<div style="text-align: center; color: #ef4444; font-size: 0.9rem; padding: 1rem 0;">${emptyMsg}</div>`;
    }
  } catch (e) {
    console.error(`대시보드 위젯 로드 오류(${pluginId}):`, e);
    container.innerHTML = '<div style="text-align: center; color: #ef4444; font-size: 0.9rem; padding: 1rem 0;">서버 연결 오류</div>';
  }
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

