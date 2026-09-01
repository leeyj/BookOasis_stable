// general.js - 일반 환경설정 클라이언트 제어 모듈
import { state } from '../state.js';
import * as api from '../api.js';

let tempShortcut = null;
let isRecordingShortcut = false;

function initGeneralDelegation() {
  if (window.__generalDelegationBound) return;

  document.addEventListener('submit', (event) => {
    const form = event && event.target;
    if (!form || form.id !== 'settings-general-form') return;
    submitGeneralSettings(event);
  }, true);

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="general-lazy-scan-now"]')
      : null;
    if (!target) return;
    event.preventDefault();
    triggerLazyScanNow();
  }, true);

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('#btn-check-vaapi')
      : null;
    if (!target) return;
    event.preventDefault();
    runVaapiCheck();
  }, true);

  document.addEventListener('change', (event) => {
    const target = event && event.target;
    if (!target) return;
    if (target.matches && target.matches('[data-role="general-dashboard-theme"]')) {
      changeDashboardTheme(target.value);
      return;
    }
    if (target.matches && target.matches('[data-role="general-dashboard-insights"]')) {
      toggleDashboardInsightsSetting(target.checked);
    }
  }, true);

  document.addEventListener('input', (event) => {
    const target = event && event.target;
    if (!target) return;
    if (target.matches && target.matches('[data-role="general-thumbnail-width"]')) {
      const valueEl = document.getElementById('setting-thumbnail-width-val');
      if (valueEl) valueEl.innerText = target.value;
    }
  }, true);

  window.__generalDelegationBound = true;
}

function isAdminUser() {
  return !!(window.currentUser && window.currentUser.role === 'admin');
}

function applyNonAdminGeneralSettingsMode() {
  const form = document.getElementById('settings-general-form');
  if (!form) return;

  const allowedIds = new Set([
    'setting-dashboard-theme',
    'setting-show-dashboard-insights'
  ]);

  const controls = form.querySelectorAll('input, select, textarea, button');
  controls.forEach((el) => {
    if (!el || !el.id) {
      if (el && el.type === 'submit') {
        el.disabled = true;
        el.title = '관리자 권한에서만 저장 가능합니다.';
      }
      return;
    }

    if (!allowedIds.has(el.id)) {
      el.disabled = true;
      if (!el.title) {
        el.title = '관리자 권한에서만 변경 가능합니다.';
      }
    }
  });
}

export function changeDashboardTheme(themeName) {
  if (!themeName) themeName = 'purple';
  localStorage.setItem('app_dashboard_theme', themeName);
  document.documentElement.setAttribute('data-app-theme', themeName);
}

export function toggleDashboardInsightsSetting(enabled) {
  const isShow = !!enabled;
  localStorage.setItem('show_dashboard_insights', isShow ? '1' : '0');
  
  const container = document.querySelector('.dashboard-insights-container');
  const divider = document.getElementById('dashboard-insights-divider');
  if (container) container.style.display = isShow ? 'block' : 'none';
  if (divider) divider.style.display = isShow ? 'block' : 'none';
}

if (typeof window !== 'undefined') {
  window.changeDashboardTheme = changeDashboardTheme;
  window.toggleDashboardInsightsSetting = toggleDashboardInsightsSetting;
}

// 설정값을 CSS 변수 및 메모리 상태에 적용하는 헬퍼 함수
export function applySettingsToUI(settings) {
  const savedTheme = localStorage.getItem('app_dashboard_theme') || 'purple';
  changeDashboardTheme(savedTheme);
  const themeSelect = document.getElementById('setting-dashboard-theme');
  if (themeSelect) {
    themeSelect.value = savedTheme;
  }

  const isShowInsights = (localStorage.getItem('show_dashboard_insights') !== '0');
  const insightsChk = document.getElementById('setting-show-dashboard-insights');
  if (insightsChk) {
    insightsChk.checked = isShowInsights;
  }
  toggleDashboardInsightsSetting(isShowInsights);
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
  if (settings.SHOW_TXT_NO_COVER_INFO_BANNER !== undefined) {
    state.showTxtNoCoverInfoBanner = (settings.SHOW_TXT_NO_COVER_INFO_BANNER === '1');
  }
  if (settings.SHOW_SIDEBAR_CATEGORY_ALL !== undefined) {
    state.showSidebarCategoryAll = (settings.SHOW_SIDEBAR_CATEGORY_ALL !== '0');
  }
  if (settings.HDD_AGGRESSIVE_WARMUP !== undefined) {
    state.hddAggressiveWarmup = (settings.HDD_AGGRESSIVE_WARMUP === '1');
  }
  if (settings.AUDIO_MINI_PLAYER_MODE !== undefined) {
    state.audioMiniPlayerMode = (settings.AUDIO_MINI_PLAYER_MODE === 'right_dock') ? 'right_dock' : 'mini';
  }
  if (settings.AUDIO_RIGHT_DOCK_DIM_ENABLED !== undefined) {
    state.audioRightDockDimEnabled = (settings.AUDIO_RIGHT_DOCK_DIM_ENABLED === '1');
  }
  if (settings.DETAIL_VOLUME_GRID_VIEW !== undefined) {
    state.detailVolumeGridView = (settings.DETAIL_VOLUME_GRID_VIEW === '1');
  }
  if (settings.COLLAPSE_DETAIL_GENRE_TAGS !== undefined) {
    state.collapseDetailGenreTags = (settings.COLLAPSE_DETAIL_GENRE_TAGS === '1');
  }
  if (settings.SMART_RECOMMEND_ENABLED !== undefined) {
    state.smartRecommendEnabled = (settings.SMART_RECOMMEND_ENABLED !== '0');
  }
  if (settings.BOOK_RECOMMEND_ENABLED !== undefined) {
    state.bookRecommendEnabled = (settings.BOOK_RECOMMEND_ENABLED !== '0');
  }

  if (typeof window !== 'undefined') {
    window.__audioMiniPlayerMode = state.audioMiniPlayerMode || 'mini';
    window.__audioRightDockDimEnabled = (state.audioRightDockDimEnabled === true);
    if (typeof window.applyAudioMiniPlayerMode === 'function') {
      window.applyAudioMiniPlayerMode(window.__audioMiniPlayerMode);
    }
  }
}

// 최초 로드 시 설정 일괄 호출 적용
// 관리자 전용 API(/api/media/settings)가 아니라, 모든 로그인 사용자가 접근 가능한
// 공개 UI 설정 API를 사용한다. 예전에는 관리자 전용 API를 썼는데, 일반 사용자는
// 403으로 실패해서 applySettingsToUI가 아예 호출되지 않아 관리자가 저장한 값과
// 무관하게 항상 JS 기본값으로만 동작하는 버그가 있었다.
export async function loadInitialSystemSettings() {
  try {
    const res = await api.fetchPublicUiSettings(state.currentLibraryType || 'general');
    if (res.success && res.settings) {
      applySettingsToUI(res.settings);
    }
  } catch (e) {
    console.error('[Settings] 최초 시스템 설정 로딩 실패:', e);
  }
}



// 일반 환경설정 로드
export async function loadGeneralSettings() {
  initGeneralDelegation();
  if (!isAdminUser()) {
    // 일반 사용자는 로컬 UI 설정(테마/대시보드 위젯 표시)만 사용한다.
    applySettingsToUI({});
    applyNonAdminGeneralSettingsMode();
    return;
  }

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

      const lazyMaxFileSizeEl = document.getElementById('setting-lazy-scan-max-file-size');
      if (lazyMaxFileSizeEl) lazyMaxFileSizeEl.value = s.LAZY_SCAN_MAX_FILE_SIZE_MB !== undefined ? s.LAZY_SCAN_MAX_FILE_SIZE_MB : '300';

      const lazyMaxBatchSizeEl = document.getElementById('setting-lazy-scan-max-batch-size');
      if (lazyMaxBatchSizeEl) lazyMaxBatchSizeEl.value = s.LAZY_SCAN_MAX_BATCH_SIZE_MB !== undefined ? s.LAZY_SCAN_MAX_BATCH_SIZE_MB : '1024';

      const lazyVideoMaxEpisodesEl = document.getElementById('setting-lazy-scan-video-max-episodes');
      if (lazyVideoMaxEpisodesEl) lazyVideoMaxEpisodesEl.value = s.LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN !== undefined ? s.LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN : '300';

      const lazyVideoProbeWorkersEl = document.getElementById('setting-lazy-scan-video-probe-workers');
      if (lazyVideoProbeWorkersEl) lazyVideoProbeWorkersEl.value = s.LAZY_SCAN_VIDEO_PROBE_WORKERS !== undefined ? s.LAZY_SCAN_VIDEO_PROBE_WORKERS : '4';

      const scanIgnorePatternsEl = document.getElementById('setting-scan-ignore-patterns');
      if (scanIgnorePatternsEl) scanIgnorePatternsEl.value = s.SCAN_IGNORE_PATTERNS !== undefined ? s.SCAN_IGNORE_PATTERNS : "@eaDir/\n#recycle/\n*.tmp\n*.sample.cbz\n.DS_Store\nThumbs.db\ndesktop.ini";

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

      const txtNoCoverBannerEl = document.getElementById('setting-show-txt-no-cover-info-banner');
      if (txtNoCoverBannerEl) {
        txtNoCoverBannerEl.checked = (s.SHOW_TXT_NO_COVER_INFO_BANNER !== '0');
      }

      const showCategoryAllEl = document.getElementById('setting-show-sidebar-category-all');
      if (showCategoryAllEl) {
        showCategoryAllEl.checked = (s.SHOW_SIDEBAR_CATEGORY_ALL !== '0');
      }

      const hddAggressiveWarmupEl = document.getElementById('setting-hdd-aggressive-warmup');
      if (hddAggressiveWarmupEl) {
        hddAggressiveWarmupEl.checked = (s.HDD_AGGRESSIVE_WARMUP === '1');
      }

      const audioMiniPlayerModeEl = document.getElementById('setting-audio-mini-player-mode');
      if (audioMiniPlayerModeEl) {
        audioMiniPlayerModeEl.value = (s.AUDIO_MINI_PLAYER_MODE === 'right_dock') ? 'right_dock' : 'mini';
      }

      const audioRightDockDimEnabledEl = document.getElementById('setting-audio-right-dock-dim-enabled');
      if (audioRightDockDimEnabledEl) {
        audioRightDockDimEnabledEl.checked = (s.AUDIO_RIGHT_DOCK_DIM_ENABLED === '1');
      }

      const detailVolumeGridViewEl = document.getElementById('setting-detail-volume-grid-view');
      if (detailVolumeGridViewEl) {
        detailVolumeGridViewEl.checked = (s.DETAIL_VOLUME_GRID_VIEW === '1');
      }

      const collapseDetailGenreTagsEl = document.getElementById('setting-collapse-detail-genre-tags');
      if (collapseDetailGenreTagsEl) {
        collapseDetailGenreTagsEl.checked = (s.COLLAPSE_DETAIL_GENRE_TAGS === '1');
      }

      const smartRecommendEnabledEl = document.getElementById('setting-smart-recommend-enabled');
      if (smartRecommendEnabledEl) {
        smartRecommendEnabledEl.checked = (s.SMART_RECOMMEND_ENABLED !== '0');
      }

      const bookRecommendEnabledEl = document.getElementById('setting-book-recommend-enabled');
      if (bookRecommendEnabledEl) {
        bookRecommendEnabledEl.checked = (s.BOOK_RECOMMEND_ENABLED !== '0');
      }

      const ffmpegTranscodeArgsEl = document.getElementById('setting-ffmpeg-transcode-args');
      if (ffmpegTranscodeArgsEl) {
        ffmpegTranscodeArgsEl.value = s.FFMPEG_TRANSCODE_ARGS !== undefined ? s.FFMPEG_TRANSCODE_ARGS : '';
      }

      const ffmpegVaapiArgsEl = document.getElementById('setting-ffmpeg-vaapi-args');
      if (ffmpegVaapiArgsEl) {
        ffmpegVaapiArgsEl.value = s.FFMPEG_VAAPI_ARGS !== undefined ? s.FFMPEG_VAAPI_ARGS : '';
      }

      const vaapiDevicePathEl = document.getElementById('setting-vaapi-device-path');
      if (vaapiDevicePathEl) {
        vaapiDevicePathEl.value = s.FFMPEG_VAAPI_DEVICE || '/dev/dri/renderD128';
      }

      // 프록시 헤더 인증 (SSO) 설정
      const proxyAuthEl = document.getElementById('setting-proxy-header-auth');
      if (proxyAuthEl) proxyAuthEl.value = s.PROXY_HEADER_AUTH || '0';
      
      // 만화 뷰어 로딩 지연 시간 (LocalStorage)
      const comicDelayEl = document.getElementById('setting-comic-loading-delay');
      if (comicDelayEl) {
        const delayStr = localStorage.getItem('comic_loading_delay');
        comicDelayEl.value = (delayStr !== null) ? parseInt(delayStr, 10) : '700';
      }
      
      // 🌟 도서관 검색 단축키 설정 로드
      const shortcutDisplay = document.getElementById('setting-search-shortcut-display');
      if (shortcutDisplay) {
        const savedRaw = localStorage.getItem('settings_search_shortcut');
        let saved = null;
        try {
          saved = savedRaw ? JSON.parse(savedRaw) : null;
        } catch (e) {
          saved = null;
        }
        if (!saved) {
          saved = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };
        }
        tempShortcut = saved;
        shortcutDisplay.value = saved.display;
      }

      initShortcutRecorderEvents();
      
      // UI 즉시 갱신
      applySettingsToUI(s);
    }
  } catch (err) {
    console.error('설정 로드 에러:', err);
  }
}

// 🌟 단축키 레코더 이벤트 리스너 바인딩 헬퍼
function initShortcutRecorderEvents() {
  const btnRecord = document.getElementById('btn-record-shortcut');
  const btnReset = document.getElementById('btn-reset-shortcut');
  const displayEl = document.getElementById('setting-search-shortcut-display');
  if (!btnRecord || !btnReset || !displayEl) return;

  if (btnRecord.__bound) return;
  btnRecord.__bound = true;

  btnRecord.addEventListener('click', () => {
    if (isRecordingShortcut) return;
    isRecordingShortcut = true;
    btnRecord.innerText = '입력 대기...';
    displayEl.value = '원하는 단축키 조합을 누르세요...';

    const onKeyDown = (e) => {
      e.preventDefault();
      e.stopPropagation();

      const isModifierOnly = ['control', 'alt', 'shift', 'meta'].includes(e.key.toLowerCase());

      const parts = [];
      if (e.ctrlKey) parts.push('Ctrl');
      if (e.altKey) parts.push('Alt');
      if (e.shiftKey) parts.push('Shift');
      if (e.metaKey) parts.push('Win');

      if (isModifierOnly) {
        displayEl.value = parts.join(' + ') + ' + ...';
      } else {
        let keyDisplay = e.key;
        if (e.code === 'Space') keyDisplay = 'Space';
        else if (e.code === 'Backquote') keyDisplay = '`';
        else if (keyDisplay.length === 1) keyDisplay = keyDisplay.toUpperCase();

        parts.push(keyDisplay);
        const finalDisplay = parts.join(' + ');

        tempShortcut = {
          ctrlKey: e.ctrlKey,
          altKey: e.altKey,
          shiftKey: e.shiftKey,
          metaKey: e.metaKey,
          key: e.key,
          code: e.code,
          display: finalDisplay
        };

        displayEl.value = finalDisplay;

        // 대기 종료
        isRecordingShortcut = false;
        btnRecord.innerText = '기록 시작';
        window.removeEventListener('keydown', onKeyDown, true);
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
  });

  btnReset.addEventListener('click', () => {
    if (isRecordingShortcut) return;
    tempShortcut = { ctrlKey: false, altKey: true, shiftKey: false, metaKey: false, key: '`', code: 'Backquote', display: 'Alt + `' };
    displayEl.value = tempShortcut.display;
  });
}

// 일반 환경설정 저장
export async function submitGeneralSettings(event) {
  if (event) {
    event.preventDefault();
  }

  if (!isAdminUser()) {
    applySettingsToUI({});
    if (typeof window.showToast === 'function') {
      window.showToast('테마와 대시보드 표시 설정은 즉시 적용되었습니다.', 'info');
    }
    return;
  }
  
  const thumbWidth = document.getElementById('setting-thumbnail-width')?.value || '160';
  const pageLimit = document.getElementById('setting-page-limit')?.value || '60';
  const fontSize = document.getElementById('setting-viewer-font-size')?.value || '18';
  const fontFamily = document.getElementById('setting-viewer-font-family')?.value || 'sans-serif';
  const dbPoolSize = document.getElementById('setting-db-pool-size')?.value || '5';
  const scannerLog = document.getElementById('setting-scanner-write-log')?.value || '1';
  const lazyCron = document.getElementById('setting-lazy-scan-cron')?.value || '0 3 * * *';
  const lazyMaxFileSize = document.getElementById('setting-lazy-scan-max-file-size')?.value || '300';
  const lazyMaxBatchSize = document.getElementById('setting-lazy-scan-max-batch-size')?.value || '1024';
  const lazyVideoMaxEpisodes = document.getElementById('setting-lazy-scan-video-max-episodes')?.value || '300';
  const lazyVideoProbeWorkers = document.getElementById('setting-lazy-scan-video-probe-workers')?.value || '4';
  const scanIgnorePatterns = document.getElementById('setting-scan-ignore-patterns')?.value || "@eaDir/\n#recycle/\n*.tmp\n*.sample.cbz\n.DS_Store\nThumbs.db\ndesktop.ini";
  const recentBooks = document.getElementById('setting-recent-books-limit')?.value || '30';
  const sysMem = document.getElementById('setting-system-mem-limit')?.value || '1536';
  const procRss = document.getElementById('setting-process-rss-limit')?.value || '2048';
  const comicDelay = document.getElementById('setting-comic-loading-delay')?.value || '700';
  const hideCompleted = document.getElementById('setting-hide-completed-in-history')?.checked ? '1' : '0';
  const tagFilterScopeAll = document.getElementById('setting-tag-filter-scope-all')?.checked ? '1' : '0';
  const showTxtNoCoverInfoBanner = document.getElementById('setting-show-txt-no-cover-info-banner')?.checked ? '1' : '0';
  const showSidebarCategoryAll = document.getElementById('setting-show-sidebar-category-all')?.checked ? '1' : '0';
  const hddAggressiveWarmup = document.getElementById('setting-hdd-aggressive-warmup')?.checked ? '1' : '0';
  const audioMiniPlayerModeRaw = document.getElementById('setting-audio-mini-player-mode')?.value || 'mini';
  const audioMiniPlayerMode = (audioMiniPlayerModeRaw === 'right_dock') ? 'right_dock' : 'mini';
  const audioRightDockDimEnabled = document.getElementById('setting-audio-right-dock-dim-enabled')?.checked ? '1' : '0';
  const proxyAuth = document.getElementById('setting-proxy-header-auth')?.value || '0';
  const rcloneRcUrl = document.getElementById('setting-rclone-rc-url')?.value || 'http://localhost:5572';
  const timezone = document.getElementById('setting-timezone')?.value || 'UTC';
  const detailVolumeGridView = document.getElementById('setting-detail-volume-grid-view')?.checked ? '1' : '0';
  const collapseDetailGenreTags = document.getElementById('setting-collapse-detail-genre-tags')?.checked ? '1' : '0';
  const smartRecommendEnabled = document.getElementById('setting-smart-recommend-enabled')?.checked ? '1' : '0';
  const bookRecommendEnabled = document.getElementById('setting-book-recommend-enabled')?.checked ? '1' : '0';
  const ffmpegTranscodeArgs = document.getElementById('setting-ffmpeg-transcode-args')?.value || '';
  const ffmpegVaapiArgs = document.getElementById('setting-ffmpeg-vaapi-args')?.value || '';
  const ffmpegVaapiDevice = document.getElementById('setting-vaapi-device-path')?.value?.trim() || '/dev/dri/renderD128';

  try {
    // 🌟 단축키 설정 영구 저장 및 활성화
    if (tempShortcut) {
      localStorage.setItem('settings_search_shortcut', JSON.stringify(tempShortcut));
      if (typeof window.applySearchShortcutSetting === 'function') {
        window.applySearchShortcutSetting();
      }
    }
    
    // LocalStorage 만화 지연 시간
    localStorage.setItem('comic_loading_delay', comicDelay);

    // 모든 설정을 병렬 업데이트
    const promises = [
      api.updateSystemSetting('BOOK_THUMBNAIL_WIDTH', thumbWidth),
      api.updateSystemSetting('PAGE_LIMIT', pageLimit),
      api.updateSystemSetting('VIEWER_FONT_SIZE', fontSize),
      api.updateSystemSetting('VIEWER_FONT_FAMILY', fontFamily),
      api.updateSystemSetting('DB_POOL_SIZE', dbPoolSize),
      api.updateSystemSetting('SCANNER_WRITE_LOG', scannerLog),
      api.updateSystemSetting('LAZY_SCAN_CRON', lazyCron),
      api.updateSystemSetting('LAZY_SCAN_MAX_FILE_SIZE_MB', lazyMaxFileSize),
      api.updateSystemSetting('LAZY_SCAN_MAX_BATCH_SIZE_MB', lazyMaxBatchSize),
      api.updateSystemSetting('LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN', lazyVideoMaxEpisodes),
      api.updateSystemSetting('LAZY_SCAN_VIDEO_PROBE_WORKERS', lazyVideoProbeWorkers),
      api.updateSystemSetting('SCAN_IGNORE_PATTERNS', scanIgnorePatterns),
      api.updateSystemSetting('TIMEZONE', timezone),
      api.updateSystemSetting('RECENT_BOOKS_LIMIT', recentBooks),
      api.updateSystemSetting('SYSTEM_MEM_LIMIT', sysMem),
      api.updateSystemSetting('PROCESS_RSS_LIMIT', procRss),
      api.updateSystemSetting('HIDE_COMPLETED_IN_HISTORY', hideCompleted),
      api.updateSystemSetting('TAG_FILTER_SEARCH_SCOPE_ALL', tagFilterScopeAll),
      api.updateSystemSetting('SHOW_TXT_NO_COVER_INFO_BANNER', showTxtNoCoverInfoBanner),
      api.updateSystemSetting('SHOW_SIDEBAR_CATEGORY_ALL', showSidebarCategoryAll),
      api.updateSystemSetting('HDD_AGGRESSIVE_WARMUP', hddAggressiveWarmup),
      api.updateSystemSetting('AUDIO_MINI_PLAYER_MODE', audioMiniPlayerMode),
      api.updateSystemSetting('AUDIO_RIGHT_DOCK_DIM_ENABLED', audioRightDockDimEnabled),
      api.updateSystemSetting('PROXY_HEADER_AUTH', proxyAuth),
      api.updateSystemSetting('RCLONE_RC_URL', rcloneRcUrl),
      api.updateSystemSetting('DETAIL_VOLUME_GRID_VIEW', detailVolumeGridView),
      api.updateSystemSetting('COLLAPSE_DETAIL_GENRE_TAGS', collapseDetailGenreTags),
      api.updateSystemSetting('SMART_RECOMMEND_ENABLED', smartRecommendEnabled),
      api.updateSystemSetting('BOOK_RECOMMEND_ENABLED', bookRecommendEnabled),
      api.updateSystemSetting('FFMPEG_TRANSCODE_ARGS', ffmpegTranscodeArgs),
      api.updateSystemSetting('FFMPEG_VAAPI_ARGS', ffmpegVaapiArgs),
      api.updateSystemSetting('FFMPEG_VAAPI_DEVICE', ffmpegVaapiDevice)
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
        TAG_FILTER_SEARCH_SCOPE_ALL: tagFilterScopeAll,
        SHOW_TXT_NO_COVER_INFO_BANNER: showTxtNoCoverInfoBanner,
        SHOW_SIDEBAR_CATEGORY_ALL: showSidebarCategoryAll,
        HDD_AGGRESSIVE_WARMUP: hddAggressiveWarmup,
        AUDIO_MINI_PLAYER_MODE: audioMiniPlayerMode,
        AUDIO_RIGHT_DOCK_DIM_ENABLED: audioRightDockDimEnabled,
        DETAIL_VOLUME_GRID_VIEW: detailVolumeGridView,
        COLLAPSE_DETAIL_GENRE_TAGS: collapseDetailGenreTags,
        SMART_RECOMMEND_ENABLED: smartRecommendEnabled,
        BOOK_RECOMMEND_ENABLED: bookRecommendEnabled
      });
      loadGeneralSettings();
      if (typeof window.loadLibraries === 'function') {
        window.loadLibraries();
      }
      if (smartRecommendEnabled === '0' && state.currentLibraryId === 'smart_rec' && typeof window.selectCategory === 'function') {
        window.selectCategory('home');
      }
    } else {
      alert(i18n.t('settings.general_save_fail', {error: failed.error}));
    }
  } catch (err) {
    console.error('설정 저장 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}

export async function runVaapiCheck() {
  const btn = document.getElementById('btn-check-vaapi');
  const resultEl = document.getElementById('vaapi-check-result');
  const devicePathEl = document.getElementById('setting-vaapi-device-path');
  if (!resultEl) return;

  const devicePath = devicePathEl?.value?.trim() || '/dev/dri/renderD128';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 점검 중...';
  }
  resultEl.style.display = 'block';
  resultEl.style.background = 'rgba(15, 23, 42, 0.6)';
  resultEl.style.border = '1px solid rgba(255,255,255,0.1)';
  resultEl.style.color = '#cbd5e1';
  resultEl.textContent = '점검 중입니다...';

  try {
    const data = await api.checkVaapiSupport(devicePath);
    if (!data.success) {
      resultEl.style.border = '1px solid rgba(239, 68, 68, 0.4)';
      resultEl.style.color = '#fca5a5';
      resultEl.textContent = `점검 실패: ${data.error || '알 수 없는 오류'}`;
      return;
    }

    const overallLabel = {
      ok: '✅ 사용 가능 (VAAPI 하드웨어 가속을 바로 쓸 수 있습니다)',
      partial: '⚠️ 부분적으로 확인됨 (ffmpeg/디바이스는 준비됐지만 vainfo로 실동작 확인은 실패했습니다)',
      unavailable: '❌ 사용 불가 (아래 상세 내역에서 어느 단계가 막혔는지 확인하세요)',
      error: '❌ ffmpeg를 찾을 수 없습니다',
    }[data.overall] || data.overall;

    const colorMap = { ok: '#34d399', partial: '#fbbf24', unavailable: '#f87171', error: '#f87171' };
    resultEl.style.border = `1px solid ${colorMap[data.overall] || 'rgba(255,255,255,0.1)'}`;
    resultEl.style.color = '#e2e8f0';

    const lines = [overallLabel, '', ...(data.detail || [])];
    if (data.vainfo_output) {
      lines.push('', '[vainfo 출력 일부]', data.vainfo_output.split('\n').slice(0, 12).join('\n'));
    }
    resultEl.textContent = lines.join('\n');

    // 점검한 디바이스 경로를 그대로 저장 - 실제 스트리밍 시(_detect_vaapi_available)도
    // 이 값을 참조하므로, 점검 결과와 실사용 판단 기준이 항상 같은 경로를 보게 만든다.
    try {
      await api.updateSystemSetting('FFMPEG_VAAPI_DEVICE', devicePath);
    } catch (saveErr) {
      console.error('[Settings] VAAPI 디바이스 경로 저장 실패:', saveErr);
    }
  } catch (e) {
    console.error('[Settings] VAAPI 점검 요청 실패:', e);
    resultEl.style.border = '1px solid rgba(239, 68, 68, 0.4)';
    resultEl.style.color = '#fca5a5';
    resultEl.textContent = '서버 요청 중 오류가 발생했습니다.';
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> 지금 점검';
    }
  }
}

window.runVaapiCheck = runVaapiCheck;

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

