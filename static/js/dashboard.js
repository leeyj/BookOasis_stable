// dashboard.js – 대시보드 데이터 로드 및 수평 휠/버튼 스크롤 제어
import { state } from './state.js';
import * as api from './api.js';
import { renderDashboardHistory, renderDashboardRecentlyAdded } from './ui.js';

export async function loadDashboardData() {
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
    await loadDashboardPlugins();
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

async function loadDashboardPlugins() {
  const section = document.getElementById('dashboard-plugins-section');
  const container = document.getElementById('dashboard-plugins-container');
  if (!section || !container) return;

  try {
    const res = await fetch('/api/media/dashboard/widgets');
    const data = await res.json();
    
    if (data.success && data.widgets && data.widgets.length > 0) {
      section.style.display = 'block'; // 활성 위젯이 있으므로 섹션 노출
      container.innerHTML = ''; // 기존 위젯 초기화
      
      // 알라딘 신간 플러그인 처리
      if (data.widgets.includes('aladin_new')) {
        const aladinHtml = `
          <div class="plugin-card" id="plugin-aladin-new" style="width: 100%; max-width: 500px; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 1rem;">
              <h4 style="margin: 0 0 1rem 0; color: #cbd5e1; font-size: 1rem; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                  <span><i class="fa-solid fa-book-open" style="color: #38bdf8; margin-right: 0.3rem;"></i> <span data-i18n="dashboard.aladin_new_title">알라딘 오늘의 신간</span></span>
                  <span style="font-size: 0.75rem; color: #64748b; font-weight: normal;"><span data-i18n="dashboard.aladin_provided">제공</span>: Aladin</span>
              </h4>
              <div id="aladin-new-content" style="display: flex; flex-direction: column; gap: 1rem; max-height: 400px; overflow-y: auto; padding-right: 0.5rem;">
                  <div class="loading-spinner" style="padding: 1rem 0;"><i class="fa-solid fa-circle-notch fa-spin"></i> <span data-i18n="dashboard.aladin_loading">신간 정보를 불러오는 중...</span></div>
              </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', aladinHtml);
        loadAladinNewReleases();
      }
    } else {
      section.style.display = 'none'; // 활성화된 위젯이 전혀 없으면 섹션 자체를 숨김
      container.innerHTML = '';
    }
  } catch (e) {
    console.error('대시보드 위젯 로드 오류:', e);
    section.style.display = 'none';
  }
}

// 알라딘 신간 플러그인 로드
export async function loadAladinNewReleases() {
  const container = document.getElementById('aladin-new-content');
  if (!container) return;
  
  try {
    const res = await fetch(`/api/media/metadata/plugins/aladin/new-releases?type=${state.currentLibraryType}&limit=10`);
    const data = await res.json();
    
    if (data.success && data.books && data.books.length > 0) {
      container.innerHTML = '';
      data.books.forEach(book => {
        const itemHtml = `
          <div style="display: flex; gap: 1rem; align-items: flex-start; padding-bottom: 0.8rem; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <div style="width: 60px; height: 85px; flex-shrink: 0; border-radius: 4px; overflow: hidden; background: #1e293b;">
              <img src="${book.cover || 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?w=100&auto=format&fit=crop&q=60'}" alt="cover" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.3rem; flex: 1; min-width: 0;">
              <a href="${book.link}" target="_blank" style="color: #f8fafc; font-size: 0.95rem; font-weight: 600; text-decoration: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${book.title}">${book.title}</a>
              <span style="color: #94a3b8; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${book.author || '저자 미상'}</span>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.2rem;">
                <span style="color: #64748b; font-size: 0.75rem;">${book.publisher || '출판사 미상'}</span>
                <span style="color: #a855f7; font-size: 0.75rem;">${book.pubDate || ''}</span>
              </div>
            </div>
          </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
      });
    } else {
      container.innerHTML = `<div style="text-align: center; color: #ef4444; font-size: 0.9rem; padding: 1rem 0;">${data.error || '신간 정보를 가져올 수 없습니다.'}</div>`;
    }
  } catch (e) {
    console.error('알라딘 신간 플러그인 로드 오류:', e);
    container.innerHTML = '<div style="text-align: center; color: #ef4444; font-size: 0.9rem; padding: 1rem 0;">서버 연결 오류</div>';
  }
}

