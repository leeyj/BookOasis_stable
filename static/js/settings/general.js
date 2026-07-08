// general.js - 일반 환경설정 클라이언트 제어 모듈
import { state } from '../state.js';
import * as api from '../api.js';

// 설정값을 CSS 변수 및 메모리 상태에 적용하는 헬퍼 함수
export function applySettingsToUI(settings) {
  if (settings.BOOK_THUMBNAIL_WIDTH) {
    const width = parseInt(settings.BOOK_THUMBNAIL_WIDTH, 10) || 160;
    const height = Math.round(width * 1.375); // 160:220 비율 유지
    document.documentElement.style.setProperty('--book-card-width', `${width}px`);
    document.documentElement.style.setProperty('--book-card-height', `${height}px`);
  }
  if (settings.PAGE_LIMIT) {
    state.LIMIT = parseInt(settings.PAGE_LIMIT, 10) || 60;
  }
  if (settings.HIDE_COMPLETED_IN_HISTORY !== undefined) {
    state.hideCompletedInHistory = (settings.HIDE_COMPLETED_IN_HISTORY === '1');
  }
  if (settings.TAG_FILTER_SEARCH_SCOPE_ALL !== undefined) {
    state.tagFilterSearchInAll = (settings.TAG_FILTER_SEARCH_SCOPE_ALL === '1');
  }
}

// 최초 로드 시 설정 일괄 호출 적용
export async function loadInitialSystemSettings() {
  try {
    const res = await api.fetchSystemSettings(state.currentLibraryType || 'general');
    if (res.success && res.settings) {
      applySettingsToUI(res.settings);
    }
  } catch (e) {
    console.error('[Settings] 최초 시스템 설정 로딩 실패:', e);
  }
}



// 일반 환경설정 로드
export async function loadGeneralSettings() {
  try {
    const data = await api.fetchSystemSettings(state.currentLibraryType);
    if (data.success && data.settings) {
      const s = data.settings;
      
      // 썸네일 크기
      const thumbEl = document.getElementById('setting-thumbnail-width');
      const thumbValEl = document.getElementById('setting-thumbnail-width-val');
      if (thumbEl) {
        thumbEl.value = s.BOOK_THUMBNAIL_WIDTH || '160';
        if (thumbValEl) thumbValEl.innerText = thumbEl.value;
      }
      
      // 페이지 로드 제한
      const limitEl = document.getElementById('setting-page-limit');
      if (limitEl) limitEl.value = s.PAGE_LIMIT || '60';
      
      // 뷰어 폰트 크기 및 서체
      const fontSizeEl = document.getElementById('setting-viewer-font-size');
      if (fontSizeEl) fontSizeEl.value = s.VIEWER_FONT_SIZE || '18';
      
      const fontFamilyEl = document.getElementById('setting-viewer-font-family');
      if (fontFamilyEl) fontFamilyEl.value = s.VIEWER_FONT_FAMILY || 'sans-serif';
      
      const dbPoolSizeEl = document.getElementById('setting-db-pool-size');
      if (dbPoolSizeEl) dbPoolSizeEl.value = s.DB_POOL_SIZE || '10';
      
      const scannerLogEl = document.getElementById('setting-scanner-write-log');
      if (scannerLogEl) scannerLogEl.value = s.SCANNER_WRITE_LOG || '1';
      
      const lazyCronEl = document.getElementById('setting-lazy-scan-cron');
      if (lazyCronEl) lazyCronEl.value = s.LAZY_SCAN_CRON || '0 3 * * *';
      
      const timezoneEl = document.getElementById('setting-timezone');
      if (timezoneEl) timezoneEl.value = s.TIMEZONE || 'UTC';
      
      const recentBooksEl = document.getElementById('setting-recent-books-limit');
      if (recentBooksEl) recentBooksEl.value = s.RECENT_BOOKS_LIMIT || '30';

      const rcloneRcUrlEl = document.getElementById('setting-rclone-rc-url');
      if (rcloneRcUrlEl) rcloneRcUrlEl.value = s.RCLONE_RC_URL || 'http://localhost:5572';

      const sysMemEl = document.getElementById('setting-system-mem-limit');
      if (sysMemEl) sysMemEl.value = s.SYSTEM_MEM_LIMIT || '1536';

      const procRssEl = document.getElementById('setting-process-rss-limit');
      if (procRssEl) procRssEl.value = s.PROCESS_RSS_LIMIT || '2048';

      // 다 읽은 도서 최근 읽은 도서에서 삭제
      const hideCompletedEl = document.getElementById('setting-hide-completed-in-history');
      if (hideCompletedEl) {
        hideCompletedEl.checked = (s.HIDE_COMPLETED_IN_HISTORY === '1');
      }

      const tagScopeAllEl = document.getElementById('setting-tag-filter-scope-all');
      if (tagScopeAllEl) {
        tagScopeAllEl.checked = (s.TAG_FILTER_SEARCH_SCOPE_ALL === '1');
      }

      // 프록시 헤더 인증 (SSO) 설정
      const proxyAuthEl = document.getElementById('setting-proxy-header-auth');
      if (proxyAuthEl) proxyAuthEl.value = s.PROXY_HEADER_AUTH || '0';
      
      // 만화 뷰어 로딩 지연 시간 (LocalStorage)
      const comicDelayEl = document.getElementById('setting-comic-loading-delay');
      if (comicDelayEl) {
        const delayStr = localStorage.getItem('comic_loading_delay');
        comicDelayEl.value = (delayStr !== null) ? parseInt(delayStr, 10) : '300';
      }
      
      // UI 즉시 갱신
      applySettingsToUI(s);
    }
  } catch (err) {
    console.error('설정 로드 에러:', err);
  }
}

// 일반 환경설정 저장
export async function submitGeneralSettings(event) {
  if (event) {
    event.preventDefault();
  }
  
  const thumbWidth = document.getElementById('setting-thumbnail-width')?.value || '160';
  const pageLimit = document.getElementById('setting-page-limit')?.value || '60';
  const fontSize = document.getElementById('setting-viewer-font-size')?.value || '18';
  const fontFamily = document.getElementById('setting-viewer-font-family')?.value || 'sans-serif';
  const dbPoolSize = document.getElementById('setting-db-pool-size')?.value || '5';
  const scannerLog = document.getElementById('setting-scanner-write-log')?.value || '1';
  const lazyCron = document.getElementById('setting-lazy-scan-cron')?.value || '0 3 * * *';
  const recentBooks = document.getElementById('setting-recent-books-limit')?.value || '30';
  const sysMem = document.getElementById('setting-system-mem-limit')?.value || '1536';
  const procRss = document.getElementById('setting-process-rss-limit')?.value || '2048';
  const comicDelay = document.getElementById('setting-comic-loading-delay')?.value || '300';
  const hideCompleted = document.getElementById('setting-hide-completed-in-history')?.checked ? '1' : '0';
  const tagFilterScopeAll = document.getElementById('setting-tag-filter-scope-all')?.checked ? '1' : '0';
  const proxyAuth = document.getElementById('setting-proxy-header-auth')?.value || '0';
  const rcloneRcUrl = document.getElementById('setting-rclone-rc-url')?.value || 'http://localhost:5572';
  const timezone = document.getElementById('setting-timezone')?.value || 'UTC';
  
  try {
    // 모든 설정을 병렬 업데이트
    const promises = [
      api.updateSystemSetting('BOOK_THUMBNAIL_WIDTH', thumbWidth),
      api.updateSystemSetting('PAGE_LIMIT', pageLimit),
      api.updateSystemSetting('VIEWER_FONT_SIZE', fontSize),
      api.updateSystemSetting('VIEWER_FONT_FAMILY', fontFamily),
      api.updateSystemSetting('DB_POOL_SIZE', dbPoolSize),
      api.updateSystemSetting('SCANNER_WRITE_LOG', scannerLog),
      api.updateSystemSetting('LAZY_SCAN_CRON', lazyCron),
      api.updateSystemSetting('TIMEZONE', timezone),
      api.updateSystemSetting('RECENT_BOOKS_LIMIT', recentBooks),
      api.updateSystemSetting('SYSTEM_MEM_LIMIT', sysMem),
      api.updateSystemSetting('PROCESS_RSS_LIMIT', procRss),
      api.updateSystemSetting('HIDE_COMPLETED_IN_HISTORY', hideCompleted),
      api.updateSystemSetting('TAG_FILTER_SEARCH_SCOPE_ALL', tagFilterScopeAll),
      api.updateSystemSetting('PROXY_HEADER_AUTH', proxyAuth),
      api.updateSystemSetting('RCLONE_RC_URL', rcloneRcUrl)
    ];
    
    const results = await Promise.all(promises);
    const failed = results.find(r => !r.success);
    
    if (!failed) {
      // 로컬 스토리지에 만화 뷰어 로딩 지연 시간 저장
      localStorage.setItem('comic_loading_delay', comicDelay);

      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('settings.general_save_success'), 'success');
      } else {
        alert(i18n.t('settings.general_save_done'));
      }
      
      // UI 실시간 갱신 적용
      applySettingsToUI({
        BOOK_THUMBNAIL_WIDTH: thumbWidth,
        PAGE_LIMIT: pageLimit,
        HIDE_COMPLETED_IN_HISTORY: hideCompleted,
        TAG_FILTER_SEARCH_SCOPE_ALL: tagFilterScopeAll
      });
      loadGeneralSettings();
    } else {
      alert(i18n.t('settings.general_save_fail', {error: failed.error}));
    }
  } catch (err) {
    console.error('설정 저장 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}

export async function triggerLazyScanNow() {
  try {
    if (typeof window.showToast === 'function') {
      window.showToast(i18n.t('settings.general_scanner_start'), 'info');
    }
    const res = await api.triggerLazyScan();
    if (res.success) {
      if (typeof window.showToast === 'function') {
        window.showToast(res.message, 'success');
      } else {
        alert(res.message);
      }
    } else {
      alert(i18n.t('settings.general_scanner_fail', {error: res.error}));
    }
  } catch (err) {
    console.error('Lazy 스캔 즉시 실행 중 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}

window.triggerLazyScanNow = triggerLazyScanNow;

