// settings_tab.js - 환경설정 제어 통합 엔트리포인트 및 프록시 모듈
import { applySettingsToUI, loadInitialSystemSettings, loadGeneralSettings, submitGeneralSettings } from './settings/general.js';
import { loadPluginsSettings } from './settings/plugins.js';
import { initReportsTab, loadReportList, loadReportDetail } from './settings/reports.js';
import { loadUsersList } from './settings/users.js';

export {
  applySettingsToUI,
  loadInitialSystemSettings,
  loadGeneralSettings,
  submitGeneralSettings,
  loadPluginsSettings,
  initReportsTab,
  loadReportList,
  loadReportDetail,
  loadUsersList
};

// 환경설정 내부 탭 전환 함수
export function switchSettingsTab(tabId) {
  console.log(`[Settings-Tab] Switching to settings tab: ${tabId}`);
  
  // 1. 모든 탭 버튼 active 클래스 해제
  document.querySelectorAll('.settings-tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  // 2. 모든 탭 콘텐츠 숨기기
  document.querySelectorAll('.settings-tab-content').forEach(content => {
    content.style.display = 'none';
    content.classList.remove('active');
  });
  
  // 3. 대상 탭 활성화 및 표시
  const targetContent = document.getElementById(`settings-tab-${tabId}`);
  if (targetContent) {
    targetContent.style.display = 'flex';
    targetContent.classList.add('active');
  }
  
  // 4. 활성화된 버튼 표시
  const activeBtn = Array.from(document.querySelectorAll('.settings-tab-btn')).find(btn => {
    return btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(`'${tabId}'`);
  });
  if (activeBtn) {
    activeBtn.classList.add('active');
  }

  // 5. 각 탭 데이터 조회 로드
  if (tabId === 'general') {
    loadGeneralSettings();
  } else if (tabId === 'plugins') {
    loadPluginsSettings();
  } else if (tabId === 'reports') {
    initReportsTab();
  } else if (tabId === 'users') {
    loadUsersList();
  } else if (tabId === 'about') {
    loadAboutInfo();
  }
}

// 이 S/W는... 버전 정보 로딩 및 렌더링
async function loadAboutInfo() {
  const dashEl = document.getElementById('about-ver-dashboard');
  const stateEl = document.getElementById('about-ver-state');
  if (!dashEl || !stateEl) return;
  
  try {
    const res = await fetch('/api/media/about');
    const data = await res.json();
    if (data.success) {
      dashEl.textContent = `v${data.version.dashboard}`;
      stateEl.textContent = data.version.state;
    } else {
      dashEl.textContent = '불러오기 실패';
      stateEl.textContent = '오류';
    }
  } catch (e) {
    console.error('About 정보 로딩 실패:', e);
    dashEl.textContent = '연결 오류';
    stateEl.textContent = '오류';
  }
}
