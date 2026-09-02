// static/js/plugin_custom_view.js – 카테고리 레벨 플러그인 전용 풀페이지 뷰포트 마운트 오케스트레이터
import { state } from './state.js';
import { switchActiveView } from './view_manager.js';
import { updateCurrentCategoryIndicator } from './category_indicator.js';

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export async function mountCategoryPluginUI(pluginId) {
  const container = document.getElementById('library-plugin-custom-view');
  if (!container) return;

  // 1. 뷰 전환: plugin_custom 뷰 활성화 (플러그인 데스크 탭바 및 공통 헤더 컨트롤 전면 숨김)
  switchActiveView('plugin_custom');
  updateCurrentCategoryIndicator(`plugin_${pluginId}`);

  container.innerHTML = `
    <div class="loading-spinner" style="padding: 4rem 1rem; text-align: center; color: var(--app-text-muted); width: 100%;">
      <i class="fa-solid fa-circle-notch fa-spin fa-2x" style="color: var(--app-accent-hover);"></i>
      <div style="margin-top: 1rem; font-size: 0.95rem;">플러그인 전용 화면을 불러오는 중...</div>
    </div>
  `;

  try {
    // 2. 먼저 플러그인 풀페이지 UI 번들 확인 (/api/media/plugins/<pluginId>/ui)
    const resUi = await fetch(`/api/media/plugins/${encodeURIComponent(pluginId)}/ui`);
    if (resUi.ok) {
      const dataUi = await resUi.json();
      if (dataUi.success && dataUi.bundle) {
        const bundle = dataUi.bundle;
        let html = '';
        if (bundle.css) {
          html += `<style id="plugin-custom-style-${pluginId}">${bundle.css}</style>`;
        }
        if (bundle.html) {
          html += bundle.html;
        }
        container.innerHTML = html;
        if (bundle.js) {
          try {
            const scriptFn = new Function('pluginId', 'container', bundle.js);
            scriptFn(pluginId, container);
          } catch (err) {
            console.error(`[PluginCustomView] Script execution error (${pluginId}):`, err);
          }
        }
        return;
      }
    }

    // 3. 번들이 없는 경우: get_dashboard_data API를 호출하여 독립 카테고리 풀페이지 뷰로 렌더링
    const resData = await fetch(`/api/media/dashboard/widgets/${encodeURIComponent(pluginId)}/data?type=${state.currentLibraryType}&limit=50`);
    const data = await resData.json();

    if (!data.success) {
      container.innerHTML = `<div style="padding: 3rem; color: #ef4444; text-align: center; width: 100%;">플러그인 데이터를 불러오지 못했습니다: ${escapeHtml(data.error || '오류')}</div>`;
      return;
    }

    // 카테고리 정보 조회
    const resCat = await fetch(`/api/media/category-plugins?type=${state.currentLibraryType}`);
    const catData = await resCat.json();
    const pluginInfo = (catData.category_plugins || []).find(p => p.id === pluginId) || {};
    const title = escapeHtml(pluginInfo.title || pluginInfo.name || pluginId);
    const icon = escapeHtml(pluginInfo.icon || 'fa-solid fa-puzzle-piece');

    // 카테고리 헤더 지시자 동기화
    updateCurrentCategoryIndicator(`plugin_${pluginId}`);

    // 독점 풀페이지 전용 레이아웃 템플릿 생성
    container.innerHTML = `
      <div class="custom-plugin-page-container" style="padding: 1.5rem 2rem; width: 100%; box-sizing: border-box; display: flex; flex-direction: column; min-height: 80vh;">
        <div class="custom-plugin-page-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 1rem;">
          <h2 style="margin: 0; color: var(--app-text-primary); font-size: 1.5rem; font-weight: 700; display: flex; align-items: center; gap: 0.6rem;">
            <i class="${icon}" style="color: var(--app-accent-hover);"></i> <span>${title}</span>
          </h2>
          <span style="color: var(--app-text-muted); font-size: 0.85rem;">제공: ${escapeHtml(pluginInfo.name || 'BookOasis Plugin')}</span>
        </div>
        <div id="custom-plugin-body-${pluginId}" class="custom-plugin-page-body" style="width: 100%; flex: 1;">
        </div>
      </div>
    `;

    const bodyContainer = document.getElementById(`custom-plugin-body-${pluginId}`);
    if (pluginId === 'stats_dashboard') {
      renderStatsDashboardCustomView(bodyContainer, data.stats || {});
    } else {
      renderCustomPluginGridItems(bodyContainer, data.items || []);
    }

  } catch (e) {
    console.error(`[PluginCustomView] Loading error (${pluginId}):`, e);
    container.innerHTML = `<div style="padding: 3rem; color: #ef4444; text-align: center; width: 100%;">플러그인 뷰 로딩 중 오류가 발생했습니다. (${escapeHtml(e.message)})</div>`;
  }
}
window.mountCategoryPluginUI = mountCategoryPluginUI;

function renderStatsDashboardCustomView(container, stats) {
  const books = (stats.total_books || 0).toLocaleString();
  const series = (stats.total_series || 0).toLocaleString();
  const weekPages = (stats.week_pages_read || 0).toLocaleString();
  const monthCompleted = (stats.month_completed_books || stats.monthly_completed || 0).toLocaleString();
  const weekCompleted = (stats.weekly_completed || 0).toLocaleString();

  const fmtMap = stats.format_counts || {};
  const zipCnt = fmtMap.zip || 0;
  const epubCnt = fmtMap.epub || 0;
  const pdfCnt = fmtMap.pdf || 0;
  const m4bCnt = fmtMap.m4b_m4a || 0;
  const mp3Cnt = fmtMap.mp3 || 0;

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.2rem; margin-bottom: 2rem;">
      <div style="background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem; display: flex; align-items: center; gap: 1rem;">
        <div style="width: 50px; height: 50px; border-radius: 10px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
          <i class="fa-solid fa-book-open"></i>
        </div>
        <div>
          <div style="color: var(--app-text-muted); font-size: 0.85rem; font-weight: 500;">총 보유 시리즈 / 도서</div>
          <div style="color: var(--app-text-primary); font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem;">${series} 시리즈 / ${books} 권</div>
        </div>
      </div>

      <div style="background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem; display: flex; align-items: center; gap: 1rem;">
        <div style="width: 50px; height: 50px; border-radius: 10px; background: color-mix(in srgb, var(--app-accent) 15%, transparent); color: var(--app-accent); display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
          <i class="fa-solid fa-chart-line"></i>
        </div>
        <div>
          <div style="color: var(--app-text-muted); font-size: 0.85rem; font-weight: 500;">주간 완독 현황</div>
          <div style="color: var(--app-text-primary); font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem;">이번주 ${weekCompleted} 권</div>
        </div>
      </div>

      <div style="background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem; display: flex; align-items: center; gap: 1rem;">
        <div style="width: 50px; height: 50px; border-radius: 10px; background: rgba(34, 197, 94, 0.15); color: #4ade80; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
          <i class="fa-solid fa-circle-check"></i>
        </div>
        <div>
          <div style="color: var(--app-text-muted); font-size: 0.85rem; font-weight: 500;">월간 완독 도서</div>
          <div style="color: var(--app-text-primary); font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem;">이번달 ${monthCompleted} 권</div>
        </div>
      </div>

      <div style="background: rgba(var(--app-panel-rgb), 0.6); border: 1px solid rgba(var(--app-panel-border-rgb), 0.08); border-radius: 12px; padding: 1.2rem; display: flex; align-items: center; gap: 1rem;">
        <div style="width: 50px; height: 50px; border-radius: 10px; background: rgba(251, 146, 60, 0.15); color: #fb923c; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
          <i class="fa-solid fa-file-lines"></i>
        </div>
        <div>
          <div style="color: var(--app-text-muted); font-size: 0.85rem; font-weight: 500;">주간 읽은 페이지 수</div>
          <div style="color: var(--app-text-primary); font-size: 1.4rem; font-weight: 700; margin-top: 0.2rem;">${weekPages} Page</div>
        </div>
      </div>
    </div>

    <!-- 포맷 분석 영역 -->
    <div style="background: rgba(var(--app-panel-rgb), 0.4); border: 1px solid rgba(var(--app-panel-border-rgb), 0.05); border-radius: 12px; padding: 1.5rem;">
      <h3 style="margin: 0 0 1rem 0; color: var(--app-text-muted); font-size: 1.1rem;">보유 미디어 파일 포맷 분석</h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem;">
        <div style="background: rgba(var(--app-panel-rgb), 0.6); border-radius: 8px; padding: 1rem; text-align: center;">
          <div style="color: #38bdf8; font-size: 1.5rem; font-weight: 700;">${zipCnt.toLocaleString()}</div>
          <div style="color: var(--app-text-muted); font-size: 0.8rem; margin-top: 0.2rem;">압축 파일 (ZIP/CBZ/RAR)</div>
        </div>
        <div style="background: rgba(var(--app-panel-rgb), 0.6); border-radius: 8px; padding: 1rem; text-align: center;">
          <div style="color: var(--app-accent); font-size: 1.5rem; font-weight: 700;">${epubCnt.toLocaleString()}</div>
          <div style="color: var(--app-text-muted); font-size: 0.8rem; margin-top: 0.2rem;">전자책 (EPUB/TXT)</div>
        </div>
        <div style="background: rgba(var(--app-panel-rgb), 0.6); border-radius: 8px; padding: 1rem; text-align: center;">
          <div style="color: #4ade80; font-size: 1.5rem; font-weight: 700;">${pdfCnt.toLocaleString()}</div>
          <div style="color: var(--app-text-muted); font-size: 0.8rem; margin-top: 0.2rem;">문서 파일 (PDF)</div>
        </div>
        ${(m4bCnt || mp3Cnt) ? `
        <div style="background: rgba(var(--app-panel-rgb), 0.6); border-radius: 8px; padding: 1rem; text-align: center;">
          <div style="color: #fb923c; font-size: 1.5rem; font-weight: 700;">${(m4bCnt + mp3Cnt).toLocaleString()}</div>
          <div style="color: var(--app-text-muted); font-size: 0.8rem; margin-top: 0.2rem;">오디오북 (M4B/MP3)</div>
        </div>
        ` : ''}
      </div>
    </div>
  `;
}

function renderCustomPluginGridItems(container, items) {
  if (!items || items.length === 0) {
    container.innerHTML = '<div style="padding: 3rem; color: var(--app-text-muted); text-align: center;">표시할 항목이 없습니다.</div>';
    return;
  }

  let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1.5rem; width: 100%;">';
  items.forEach(item => {
    const cover = item.cover || item.image || item.image_url || 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=100&auto=format&fit=crop&q=60';
    const title = escapeHtml(item.title || '제목 없음');
    const author = escapeHtml(item.author || item.artist || '저자 미상');
    const link = item.link || item.url || '#';
    const isExternal = link && link !== '#';

    html += `
      <div style="background: rgba(var(--app-panel-rgb), 0.5); border: 1px solid rgba(var(--app-panel-border-rgb), 0.06); border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; transition: transform 0.2s, box-shadow 0.2s;" class="custom-plugin-card">
        <a href="${isExternal ? link : '#'}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} style="display: block; width: 100%; aspect-ratio: 3/4; overflow: hidden; background: #0f172a; position: relative;">
          <img src="${cover}" alt="${title}" style="width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s;" loading="lazy">
        </a>
        <div style="padding: 0.8rem; display: flex; flex-direction: column; gap: 0.3rem; flex: 1; justify-content: space-between;">
          <a href="${isExternal ? link : '#'}" ${isExternal ? 'target="_blank" rel="noopener noreferrer"' : ''} style="color: var(--app-text-primary); font-size: 0.9rem; font-weight: 600; text-decoration: none; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;" title="${title}">${title}</a>
          <span style="color: var(--app-text-muted); font-size: 0.78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${author}</span>
        </div>
      </div>
    `;
  });
  html += '</div>';
  container.innerHTML = html;
}
