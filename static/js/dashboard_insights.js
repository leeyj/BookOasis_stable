// static/js/dashboard_insights.js - 대시보드 독서 동기부여 위젯 컨트롤러 (Compact & Slim)
import { escapeHtml } from './utils/html.js';
import { getBookCoverSrc, buildFallbackCoverUrl } from './cover_fallback.js';

if (!window.__dashboardInsightsDelegationBound) {
  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="reading-goal-edit"]')
      : null;
    if (!target) return;

    event.preventDefault();
    window.openEditReadingGoalModal?.();
  }, true);
  window.__dashboardInsightsDelegationBound = true;
}

export async function loadDashboardInsights(libraryType = 'general') {
  try {
    const isShow = (localStorage.getItem('show_dashboard_insights') !== '0');
    const container = document.querySelector('.dashboard-insights-container');
    const slot = document.querySelector('[data-widget-id="core.reading_insights"]');
    if (container) container.style.display = isShow ? 'block' : 'none';
    if (slot) slot.style.display = isShow ? '' : 'none';
    window.refreshHomeWidgetDividers?.();
    if (!isShow) return;

    const res = await fetch(`/api/dashboard/insights?library_type=${encodeURIComponent(libraryType)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.success) return;

    // 1. Reading Streak
    const streakDaysEl = document.getElementById('streak-days-count');
    if (streakDaysEl) streakDaysEl.textContent = data.streak.days || 0;

    const dotsContainer = document.getElementById('streak-dots-container');
    if (dotsContainer && Array.isArray(data.streak.last_7_days)) {
      dotsContainer.innerHTML = '';
      data.streak.last_7_days.forEach((isRead, idx) => {
        const dot = document.createElement('span');
        dot.className = 'streak-dot';
        dot.style.cssText = `width: 7px; height: 7px; border-radius: 50%; transition: all 0.3s;`;
        if (isRead) {
          if (idx === 6) {
            dot.style.background = '#f97316';
            dot.style.boxShadow = '0 0 6px #f97316';
          } else {
            dot.style.background = '#38bdf8';
          }
        } else {
          dot.style.background = 'rgba(255, 255, 255, 0.15)';
        }
        dotsContainer.appendChild(dot);
      });
    }

    // 2. Currently Reading
    const currentlyContainer = document.getElementById('currently-reading-list');
    if (currentlyContainer) {
      if (Array.isArray(data.currently_reading) && data.currently_reading.length > 0) {
        currentlyContainer.innerHTML = data.currently_reading.map(book => {
          const detectedFmt = (book.file_format || book.format || '').toLowerCase();
          const resolvedFmt = detectedFmt || (
            (book.file_path || book.title || '').match(/\.(epub|pdf|mp3|m4a|m4b|flac|cbz|zip)$/i)?.[1]?.toLowerCase() || 'zip'
          );

          const coverSrc = getBookCoverSrc({
            coverImage: book.cover_url || book.cover_image,
            title: book.title,
            format: resolvedFmt,
            seed: book.id
          });
          const fallbackSrc = buildFallbackCoverUrl({
            title: book.title,
            format: resolvedFmt,
            seed: book.id
          });

          return `
            <div class="currently-book-item ui-hover-currently-book" data-role="currently-reading-book" data-book-id="${book.id}" data-file-format="${escapeHtml(resolvedFmt)}" data-book-title="${escapeHtml(book.title)}" data-pages-read="${book.current_page || book.pages_read || 0}" data-total-pages="${book.total_pages || 0}" style="display: flex; align-items: center; gap: 0.5rem; background: rgba(var(--app-panel-rgb), 0.4); padding: 0.35rem 0.5rem; border-radius: 8px; cursor: pointer; transition: background 0.2s;">
              <img src="${coverSrc}" onerror="this.onerror=null; this.src='${fallbackSrc}';" alt="Cover" style="width: 26px; height: 36px; object-fit: cover; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
              <div style="flex: 1; min-width: 0;">
                <div style="font-size: 0.78rem; font-weight: 700; color: var(--app-text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(book.title)}</div>
                <div style="font-size: 0.68rem; color: var(--app-text-muted); margin-bottom: 0.2rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(book.author)}</div>
                <div style="width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; overflow: hidden;">
                  <div style="width: ${book.progress_pct}%; height: 100%; background: #38bdf8; border-radius: 2px;"></div>
                </div>
              </div>
              <div style="font-size: 0.75rem; font-weight: 700; color: #38bdf8; margin-left: 0.2rem;">${book.progress_pct}%</div>
            </div>
          `;
        }).join('');
      } else {
        currentlyContainer.innerHTML = `<div style="text-align: center; color: var(--app-text-muted); font-size: 0.78rem; padding: 0.4rem 0;" data-i18n="dashboard.insights_no_currently">${(window.i18n?.t && window.i18n.t('dashboard.insights_no_currently')) || '현재 진행 중인 도서가 없습니다.'}</div>`;
      }
    }

    // 3. Reading Goal 2026
    const yearLabel = document.getElementById('insights-year-label');
    if (yearLabel) yearLabel.textContent = data.annual_goal.year || 2026;

    const completedEl = document.getElementById('goal-completed-count');
    if (completedEl) completedEl.textContent = data.annual_goal.completed || 0;

    const targetEl = document.getElementById('goal-target-count');
    if (targetEl) targetEl.textContent = data.annual_goal.target || 30;

    const pctLabel = document.getElementById('goal-pct-label');
    if (pctLabel) pctLabel.textContent = data.annual_goal.pct || 0;

    const svgProgress = document.getElementById('goal-svg-progress');
    if (svgProgress) {
      const circumference = 2 * Math.PI * 27; // r=27 ➔ 169.64
      const pct = (data.annual_goal.pct || 0) / 100;
      const offset = circumference * (1 - pct);
      svgProgress.style.strokeDasharray = `${circumference}`;
      svgProgress.style.strokeDashoffset = `${offset}`;
    }

    // 4. Genre Breakdown 2026
    const genreContainer = document.getElementById('genre-breakdown-list');
    if (genreContainer) {
      if (Array.isArray(data.genre_breakdown) && data.genre_breakdown.length > 0) {
        genreContainer.innerHTML = data.genre_breakdown.map(g => `
          <div class="genre-item" style="display: flex; flex-direction: column; gap: 0.15rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--app-text-muted); font-weight: 600;">
              <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;">${escapeHtml(g.name)}</span>
              <span style="color: ${g.color}; font-weight: 700;">${g.pct}%</span>
            </div>
            <div style="width: 100%; height: 5px; background: rgba(255, 255, 255, 0.1); border-radius: 2.5px; overflow: hidden;">
              <div style="width: ${g.pct}%; height: 100%; background: ${g.color}; border-radius: 2.5px; transition: width 0.6s ease-in-out;"></div>
            </div>
          </div>
        `).join('');
      } else {
        genreContainer.innerHTML = `<div style="text-align: center; color: var(--app-text-muted); font-size: 0.78rem;" data-i18n="dashboard.insights_no_genre">${(window.i18n?.t && window.i18n.t('dashboard.insights_no_genre')) || '올해 독서 장르 기록이 없습니다.'}</div>`;
      }
    }

    if (typeof window.updateI18nDOM === 'function') {
      window.updateI18nDOM();
    }

  } catch (err) {
    console.error('[DashboardInsights] Load error:', err);
  }
}

// 책 ID만 알 때 여는 경로: reader-info로 형식/제목/진도를 받아 openReader로 연다.
window.openBookViewer = async function(bookId) {
  const id = Number.parseInt(bookId, 10);
  if (!Number.isFinite(id) || id <= 0) return;
  const type = window.currentLibraryType || 'general';
  try {
    const res = await fetch(`/api/media/books/${encodeURIComponent(id)}/reader-info?type=${encodeURIComponent(type)}`);
    const data = await res.json();
    const book = data && data.success ? data.book : null;
    if (!book) {
      console.error('[DashboardInsights] reader-info 실패:', data && data.error);
      return;
    }
    const fmt = String(book.file_format || '').toLowerCase();
    if ((fmt === 'audiobook' || fmt === 'audio') && typeof window.openAudioPlayer === 'function') {
      window.openAudioPlayer(id);
    } else if (typeof window.openReader === 'function') {
      window.openReader(book.id || id, book.file_format, book.title || '', book.pages_read || 0, book.total_pages || 0);
    }
  } catch (e) {
    console.error('[DashboardInsights] openBookViewer error:', e);
  }
};

window.openEditReadingGoalModal = async function() {
  const currentTarget = document.getElementById('goal-target-count')?.textContent || '30';
  const year = document.getElementById('insights-year-label')?.textContent || new Date().getFullYear();
  const promptText = i18n.t('dashboard.insights_edit_prompt', { year });
  const input = prompt(promptText, currentTarget);
  if (input === null) return;

  const val = parseInt(input.trim(), 10);
  if (isNaN(val) || val <= 0) {
    alert(i18n.t('dashboard.insights_goal_invalid'));
    return;
  }

  try {
    const activeType = window.currentLibraryType || 'general';
    const res = await fetch('/api/dashboard/goal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_books: val, library_type: activeType })
    });
    const data = await res.json();
    if (data.success) {
      window.loadDashboardInsights(activeType);
    } else {
      alert(data.error || i18n.t('dashboard.insights_goal_save_failed'));
    }
  } catch (e) {
    console.error('[EditGoal] Error:', e);
    alert(i18n.t('dashboard.insights_goal_save_error'));
  }
};

window.loadDashboardInsights = function(libType) {
  const activeType = libType || window.currentLibraryType || 'general';
  loadDashboardInsights(activeType);
};

// ── 현재 읽는 중 카드 클릭 핸들러 등록 ──
if (!window.__currentlyReadingClickBound) {
  document.addEventListener('click', (e) => {
    const item = e.target.closest('[data-role="currently-reading-book"]');
    if (!item) return;

    e.preventDefault();
    const bookId = Number.parseInt(item.getAttribute('data-book-id') || '', 10);
    const fileFormat = (item.getAttribute('data-file-format') || 'zip').toLowerCase();
    const title = item.getAttribute('data-book-title') || '';
    const pagesRead = Number.parseInt(item.getAttribute('data-pages-read') || '0', 10) || 0;
    const totalPages = Number.parseInt(item.getAttribute('data-total-pages') || '0', 10) || 0;

    const isAudio = fileFormat === 'audiobook' || fileFormat === 'audio';
    if (isAudio && typeof window.openAudioPlayer === 'function') {
      window.openAudioPlayer(bookId);
    } else if (bookId && typeof window.openReader === 'function') {
      window.openReader(bookId, fileFormat, title, pagesRead, totalPages);
    } else if (typeof window.openBookViewer === 'function') {
      window.openBookViewer(bookId);
    }
  });
  window.__currentlyReadingClickBound = true;
}

document.addEventListener('DOMContentLoaded', () => {
  const activeType = window.currentLibraryType || 'general';
  loadDashboardInsights(activeType);
});
