// settings_tab.js - 환경설정 제어 통합 엔트리포인트 및 프록시 모듈
import { applySettingsToUI, loadInitialSystemSettings, loadGeneralSettings, submitGeneralSettings } from './settings/general.js';
import { loadPluginsSettings } from './settings/plugins.js';
import { initReportsTab, loadReportList, loadReportDetail } from './settings/reports.js';
import { loadUsersList } from './settings/users.js';
import { loadPermissionsMatrix } from './settings/permissions.js';

export {
  applySettingsToUI,
  loadInitialSystemSettings,
  loadGeneralSettings,
  submitGeneralSettings,
  loadPluginsSettings,
  initReportsTab,
  loadReportList,
  loadReportDetail,
  loadUsersList,
  loadPermissionsMatrix,
  loadViewerSettings,
  submitViewerSettings
};

// 환경설정 내부 탭 전환 함수
export function switchSettingsTab(tabId) {
  // 일반 사용자는 어드민 전용 탭에 접근하지 못하도록 차단 및 'about'으로 우회
  const isAdmin = window.currentUser && window.currentUser.role === 'admin';
  const adminOnlyTabs = ['schedule', 'queue', 'general', 'plugins', 'reports', 'users', 'permissions', 'trash'];
  
  if (!isAdmin && adminOnlyTabs.includes(tabId)) {
    console.warn(`[Settings-Tab] Access denied for tab '${tabId}'. Redirecting to 'about'...`);
    switchSettingsTab('about');
    return;
  }

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
  } else if (tabId === 'viewer') {
    loadViewerSettings();
  } else if (tabId === 'plugins') {
    loadPluginsSettings();
  } else if (tabId === 'reports') {
    initReportsTab();
  } else if (tabId === 'users') {
    loadUsersList();
  } else if (tabId === 'permissions') {
    loadPermissionsMatrix();
  } else if (tabId === 'trash') {
    if (window.loadTrashList) {
      window.loadTrashList();
    }
  } else if (tabId === 'about') {
    loadAboutInfo();
  } else if (tabId === 'changelog') {
    loadChangelog();
  } else if (tabId === 'queue') {
    if (window.loadQueueStatus) {
      window.loadQueueStatus();
    }
    if (!window.queueRefreshInterval && window.loadQueueStatus) {
      window.queueRefreshInterval = setInterval(window.loadQueueStatus, 5000);
    }
  }

  // Handle queue refresh interval clearing if leaving queue tab
  if (tabId !== 'queue') {
    if (window.queueRefreshInterval) {
      clearInterval(window.queueRefreshInterval);
      window.queueRefreshInterval = null;
    }
  }
}

// 이 S/W는... 버전 정보 로딩 및 렌더링
async function loadAboutInfo() {
  const dashEl = document.getElementById('about-ver-dashboard');
  const latestEl = document.getElementById('about-ver-latest');
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

  if (latestEl) {
    try {
      const gitRes = await fetch('https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/VERSION');
      if (gitRes.ok) {
        const text = await gitRes.text();
        const match = text.match(/"dashboard":\s*([0-9\.]+)/);
        if (match && match[1]) {
          latestEl.textContent = `v${match[1]}`;
        } else {
          latestEl.textContent = '버전 파싱 실패';
        }
      } else {
        latestEl.textContent = '불러오기 실패';
      }
    } catch (e) {
      console.error('GitHub 최신 버전 로딩 실패:', e);
      latestEl.textContent = '연결 오류';
    }
  }
}

// 업데이트 내역 (Changelog) 탭 로딩
async function loadChangelog() {
  const contentEl = document.getElementById('changelog-content');
  const loadingEl = document.getElementById('changelog-loading');
  if (!contentEl || !loadingEl) return;
  
  if (contentEl.innerHTML.trim() !== '') return; // 이미 로딩됨

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  try {
    const res = await fetch('https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/CHANGELOG.md');
    if (res.ok) {
      const text = await res.text();
      // marked.js를 통해 렌더링
      if (typeof marked !== 'undefined') {
        contentEl.innerHTML = marked.parse(text);
      } else {
        // Fallback for raw text
        contentEl.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${text}</pre>`;
      }
    } else {
      contentEl.innerHTML = `<p style="color: #ef4444;">${i18n.t('settings.changelog_error') || '패치 노트를 불러오지 못했습니다. (서버 응답 오류)'}</p>`;
    }
  } catch (e) {
    console.error('Changelog 로딩 실패:', e);
    contentEl.innerHTML = `<p style="color: #ef4444;">${i18n.t('settings.changelog_error') || '패치 노트를 불러오지 못했습니다. (네트워크 오류)'}</p>`;
  } finally {
    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
  }
}

// 뷰어 여백 설정 로드
function loadViewerSettings() {
  const padTop = localStorage.getItem('viewer_padding_top') || '40';
  const padBottom = localStorage.getItem('viewer_padding_bottom') || '60';
  const padLeft = localStorage.getItem('viewer_padding_left') || '20';
  const padRight = localStorage.getItem('viewer_padding_right') || '20';

  const cPadTop = localStorage.getItem('comic_padding_top') || '0';
  const cPadBottom = localStorage.getItem('comic_padding_bottom') || '40';
  const cPadLeft = localStorage.getItem('comic_padding_left') || '0';
  const cPadRight = localStorage.getItem('comic_padding_right') || '0';

  const topInput = document.getElementById('setting-viewer-padding-top');
  const bottomInput = document.getElementById('setting-viewer-padding-bottom');
  const leftInput = document.getElementById('setting-viewer-padding-left');
  const rightInput = document.getElementById('setting-viewer-padding-right');

  const cTopInput = document.getElementById('setting-comic-padding-top');
  const cBottomInput = document.getElementById('setting-comic-padding-bottom');
  const cLeftInput = document.getElementById('setting-comic-padding-left');
  const cRightInput = document.getElementById('setting-comic-padding-right');

  if (topInput) {
    topInput.value = padTop;
    document.getElementById('setting-viewer-padding-top-val').innerText = padTop;
  }
  if (bottomInput) {
    bottomInput.value = padBottom;
    document.getElementById('setting-viewer-padding-bottom-val').innerText = padBottom;
  }
  if (leftInput) {
    leftInput.value = padLeft;
    document.getElementById('setting-viewer-padding-left-val').innerText = padLeft;
  }
  if (rightInput) {
    rightInput.value = padRight;
    document.getElementById('setting-viewer-padding-right-val').innerText = padRight;
  }

  if (cTopInput) {
    cTopInput.value = cPadTop;
    document.getElementById('setting-comic-padding-top-val').innerText = cPadTop;
  }
  if (cBottomInput) {
    cBottomInput.value = cPadBottom;
    document.getElementById('setting-comic-padding-bottom-val').innerText = cPadBottom;
  }
  if (cLeftInput) {
    cLeftInput.value = cPadLeft;
    document.getElementById('setting-comic-padding-left-val').innerText = cPadLeft;
  }
  if (cRightInput) {
    cRightInput.value = cPadRight;
    document.getElementById('setting-comic-padding-right-val').innerText = cPadRight;
  }
}

// 뷰어 여백 설정 저장
function submitViewerSettings(event) {
  console.log('[Settings-Viewer] submitViewerSettings triggered');
  if (event) event.preventDefault();
  try {
    const padTop = document.getElementById('setting-viewer-padding-top').value;
    const padBottom = document.getElementById('setting-viewer-padding-bottom').value;
    const padLeft = document.getElementById('setting-viewer-padding-left').value;
    const padRight = document.getElementById('setting-viewer-padding-right').value;
    console.log(`[Settings-Viewer] Read Novel Padding from Form: Top=${padTop}, Bottom=${padBottom}, Left=${padLeft}, Right=${padRight}`);

    localStorage.setItem('viewer_padding_top', padTop);
    localStorage.setItem('viewer_padding_bottom', padBottom);
    localStorage.setItem('viewer_padding_left', padLeft);
    localStorage.setItem('viewer_padding_right', padRight);
    console.log('[Settings-Viewer] Saved Novel padding values to localStorage');

    const cTopInput = document.getElementById('setting-comic-padding-top');
    const cBottomInput = document.getElementById('setting-comic-padding-bottom');
    const cLeftInput = document.getElementById('setting-comic-padding-left');
    const cRightInput = document.getElementById('setting-comic-padding-right');

    if (cTopInput) localStorage.setItem('comic_padding_top', cTopInput.value);
    if (cBottomInput) localStorage.setItem('comic_padding_bottom', cBottomInput.value);
    if (cLeftInput) localStorage.setItem('comic_padding_left', cLeftInput.value);
    if (cRightInput) localStorage.setItem('comic_padding_right', cRightInput.value);
    console.log('[Settings-Viewer] Saved Comic padding values to localStorage if present');

    // 실시간 뷰어 여백 즉시 반영을 위해 통합 함수 대리 호출
    if (typeof window.applyViewerPaddingRealtime === 'function') {
      window.applyViewerPaddingRealtime('novel', 'top', padTop);
      window.applyViewerPaddingRealtime('novel', 'bottom', padBottom);
      window.applyViewerPaddingRealtime('novel', 'left', padLeft);
      window.applyViewerPaddingRealtime('novel', 'right', padRight);
      console.log('[Settings-Viewer] Realtime styles applied via applyViewerPaddingRealtime');
    }

    alert(window.i18n && window.i18n.t ? window.i18n.t('settings.viewer_settings_saved') || '뷰어 여백 설정이 저장되었습니다!' : '뷰어 여백 설정이 저장되었습니다!');
  } catch (e) {
    console.error('[Settings-Viewer] Error occurred inside submitViewerSettings:', e);
  }
}
