// general.js - "일반 설정"/"내 설정" 탭의 폼 로드·저장 오케스트레이션 + 이벤트 위임 진입점
//
// 테마/커버저장소이관/단축키녹화/VAAPI점검·스캐너트리거처럼 서로 무관한 관심사는
// 각자의 파일(theme_settings.js, cover_storage_settings.js, shortcut_recorder.js,
// system_actions.js)로 분리돼 있다. 이 파일은 "일반 설정"/"내 설정" 두 폼 자체의
// 로드/저장 흐름과, 그 폼에서 발생하는 이벤트를 각 모듈로 위임하는 역할만 담당한다.
import { state } from '../state.js';
import * as api from '../api.js';
import { changeDashboardTheme, populateCustomThemeOptions, rescanCustomThemesUi, toggleDashboardInsightsSetting } from './theme_settings.js';
import { startCoverStorageMigration } from './cover_storage_settings.js';
import { getTempShortcut, setTempShortcut, initShortcutRecorderEvents } from './shortcut_recorder.js';
import { runVaapiCheck, triggerLazyScanNow } from './system_actions.js';

function initGeneralDelegation() {
  if (window.__generalDelegationBound) return;

  document.addEventListener('submit', (event) => {
    const form = event && event.target;
    if (!form || form.id !== 'settings-general-form') return;
    submitGeneralSettings(event);
  }, true);

  document.addEventListener('submit', (event) => {
    const form = event && event.target;
    if (!form || form.id !== 'settings-my-form') return;
    submitMySettings(event);
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

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="custom-theme-rescan"]')
      : null;
    if (!target) return;
    event.preventDefault();
    rescanCustomThemesUi();
  }, true);

  document.addEventListener('click', (event) => {
    const target = event && event.target && typeof event.target.closest === 'function'
      ? event.target.closest('[data-role="cover-storage-migrate"]')
      : null;
    if (!target) return;
    event.preventDefault();
    startCoverStorageMigration();
  }, true);

  document.addEventListener('change', (event) => {
    const target = event && event.target;
    if (!target) return;
    if (target.matches && target.matches('[data-role="my-dashboard-theme"]')) {
      changeDashboardTheme(target.value);
      // 서버에도 개인화 설정으로 저장 (다른 기기/재로그인 시에도 유지되도록) - 실패해도 UI는 이미 반영됨
      api.updateUserSetting('DASHBOARD_THEME', target.value).catch((e) => {
        console.error('[Settings] 대시보드 테마 서버 저장 실패:', e);
      });
      return;
    }
    if (target.matches && target.matches('[data-role="my-dashboard-insights"]')) {
      toggleDashboardInsightsSetting(target.checked);
      api.updateUserSetting('SHOW_DASHBOARD_INSIGHTS', target.checked ? '1' : '0').catch((e) => {
        console.error('[Settings] 대시보드 통계 위젯 표시 서버 저장 실패:', e);
      });
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
  // 테마/대시보드 표시/뷰어 글꼴 등 개인화 가능한 항목은 모두 "내 설정" 탭으로 이전됐으므로,
  // 이 탭(일반 설정)은 이제 전부 관리자 전용이다 - 예외 없이 전체 비활성화한다.
  const form = document.getElementById('settings-general-form');
  if (!form) return;

  const controls = form.querySelectorAll('input, select, textarea, button');
  controls.forEach((el) => {
    if (!el) return;
    el.disabled = true;
    if (el.type === 'submit') {
      el.title = '관리자 권한에서만 저장 가능합니다.';
    } else if (!el.title) {
      el.title = '관리자 권한에서만 변경 가능합니다.';
    }
  });
}

// 설정값을 CSS 변수 및 메모리 상태에 적용하는 헬퍼 함수
export function applySettingsToUI(settings) {
  const savedTheme = localStorage.getItem('app_dashboard_theme') || 'purple';
  changeDashboardTheme(savedTheme);
  const themeSelect = document.getElementById('my-setting-dashboard-theme');
  if (themeSelect) {
    themeSelect.value = savedTheme;
  }
  populateCustomThemeOptions();

  const isShowInsights = (localStorage.getItem('show_dashboard_insights') !== '0');
  const insightsChk = document.getElementById('my-setting-show-dashboard-insights');
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
    const res = await api.fetchPublicUiSettings();
    if (res.success && res.settings) {
      applySettingsToUI(res.settings);
    }
  } catch (e) {
    console.error('[Settings] 최초 시스템 설정 로딩 실패:', e);
  }

  migrateLocalOnlyUserSettingsOnce();
}

// DASHBOARD_THEME / SHOW_DASHBOARD_INSIGHTS는 예전엔 localStorage에만 저장됐다.
// 서버 개인화 설정(user_settings)이 도입된 뒤, 아직 서버에 오버라이드가 없는 사용자에 한해
// 기존 localStorage 값을 1회성으로 서버에 시딩한다. 페이지 로드당 한 번만 실행한다.
let __localSettingsMigrationDone = false;
async function migrateLocalOnlyUserSettingsOnce() {
  if (__localSettingsMigrationDone) return;
  __localSettingsMigrationDone = true;

  try {
    const res = await api.fetchUserSettings();
    if (!res || !res.success) return;
    const overrides = res.overrides || {};

    const localTheme = localStorage.getItem('app_dashboard_theme');
    if (!('DASHBOARD_THEME' in overrides) && localTheme) {
      api.updateUserSetting('DASHBOARD_THEME', localTheme).catch((e) => {
        console.error('[Settings] DASHBOARD_THEME 마이그레이션 실패:', e);
      });
    }

    const localInsights = localStorage.getItem('show_dashboard_insights');
    if (!('SHOW_DASHBOARD_INSIGHTS' in overrides) && localInsights !== null) {
      api.updateUserSetting('SHOW_DASHBOARD_INSIGHTS', localInsights).catch((e) => {
        console.error('[Settings] SHOW_DASHBOARD_INSIGHTS 마이그레이션 실패:', e);
      });
    }
  } catch (e) {
    console.error('[Settings] 로컬 설정 서버 마이그레이션 실패:', e);
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
    const data = await api.fetchSystemSettings();
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

      const coverStorageRootEl = document.getElementById('setting-cover-storage-root');
      if (coverStorageRootEl) coverStorageRootEl.value = s.COVER_STORAGE_ROOT || '';

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

      const hddAggressiveWarmupEl = document.getElementById('setting-hdd-aggressive-warmup');
      if (hddAggressiveWarmupEl) {
        hddAggressiveWarmupEl.checked = (s.HDD_AGGRESSIVE_WARMUP === '1');
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
        setTempShortcut(saved);
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
  const hddAggressiveWarmup = document.getElementById('setting-hdd-aggressive-warmup')?.checked ? '1' : '0';
  const proxyAuth = document.getElementById('setting-proxy-header-auth')?.value || '0';
  const rcloneRcUrl = document.getElementById('setting-rclone-rc-url')?.value || 'http://localhost:5572';
  const coverStorageRoot = document.getElementById('setting-cover-storage-root')?.value?.trim() || '';
  const timezone = document.getElementById('setting-timezone')?.value || 'UTC';
  const ffmpegTranscodeArgs = document.getElementById('setting-ffmpeg-transcode-args')?.value || '';
  const ffmpegVaapiArgs = document.getElementById('setting-ffmpeg-vaapi-args')?.value || '';
  const ffmpegVaapiDevice = document.getElementById('setting-vaapi-device-path')?.value?.trim() || '/dev/dri/renderD128';

  try {
    // 🌟 단축키 설정 영구 저장 및 활성화
    const tempShortcut = getTempShortcut();
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
      api.updateSystemSetting('DB_POOL_SIZE', dbPoolSize),
      api.updateSystemSetting('SCANNER_WRITE_LOG', scannerLog),
      api.updateSystemSetting('LAZY_SCAN_CRON', lazyCron),
      api.updateSystemSetting('LAZY_SCAN_MAX_FILE_SIZE_MB', lazyMaxFileSize),
      api.updateSystemSetting('LAZY_SCAN_MAX_BATCH_SIZE_MB', lazyMaxBatchSize),
      api.updateSystemSetting('LAZY_SCAN_VIDEO_MAX_EPISODES_PER_RUN', lazyVideoMaxEpisodes),
      api.updateSystemSetting('LAZY_SCAN_VIDEO_PROBE_WORKERS', lazyVideoProbeWorkers),
      api.updateSystemSetting('SCAN_IGNORE_PATTERNS', scanIgnorePatterns),
      api.updateSystemSetting('COVER_STORAGE_ROOT', coverStorageRoot),
      api.updateSystemSetting('TIMEZONE', timezone),
      api.updateSystemSetting('RECENT_BOOKS_LIMIT', recentBooks),
      api.updateSystemSetting('SYSTEM_MEM_LIMIT', sysMem),
      api.updateSystemSetting('PROCESS_RSS_LIMIT', procRss),
      api.updateSystemSetting('HDD_AGGRESSIVE_WARMUP', hddAggressiveWarmup),
      api.updateSystemSetting('PROXY_HEADER_AUTH', proxyAuth),
      api.updateSystemSetting('RCLONE_RC_URL', rcloneRcUrl),
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
        HDD_AGGRESSIVE_WARMUP: hddAggressiveWarmup
      });
      loadGeneralSettings();
      if (typeof window.loadLibraries === 'function') {
        window.loadLibraries();
      }
    } else {
      alert(i18n.t('settings.general_save_fail', {error: failed.error}));
    }
  } catch (err) {
    console.error('설정 저장 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}

// 내 설정(사용자별 개인화) 탭 로드
export async function loadMySettings() {
  try {
    const res = await api.fetchUserSettings();
    if (!res.success || !res.settings) return;
    const s = res.settings;

    const themeEl = document.getElementById('my-setting-dashboard-theme');
    if (themeEl) themeEl.value = s.DASHBOARD_THEME || localStorage.getItem('app_dashboard_theme') || 'purple';

    const insightsEl = document.getElementById('my-setting-show-dashboard-insights');
    if (insightsEl) insightsEl.checked = (s.SHOW_DASHBOARD_INSIGHTS !== undefined)
      ? (s.SHOW_DASHBOARD_INSIGHTS !== '0')
      : (localStorage.getItem('show_dashboard_insights') !== '0');

    const fontSizeEl = document.getElementById('my-setting-viewer-font-size');
    if (fontSizeEl) fontSizeEl.value = s.VIEWER_FONT_SIZE || '18';

    const fontFamilyEl = document.getElementById('my-setting-viewer-font-family');
    if (fontFamilyEl) fontFamilyEl.value = s.VIEWER_FONT_FAMILY || 'sans-serif';

    const audioMiniPlayerModeEl = document.getElementById('my-setting-audio-mini-player-mode');
    if (audioMiniPlayerModeEl) {
      audioMiniPlayerModeEl.value = (s.AUDIO_MINI_PLAYER_MODE === 'right_dock') ? 'right_dock' : 'mini';
    }

    const audioRightDockDimEl = document.getElementById('my-setting-audio-right-dock-dim');
    if (audioRightDockDimEl) audioRightDockDimEl.checked = (s.AUDIO_RIGHT_DOCK_DIM_ENABLED === '1');

    const detailVolumeGridViewEl = document.getElementById('my-setting-detail-volume-grid-view');
    if (detailVolumeGridViewEl) detailVolumeGridViewEl.checked = (s.DETAIL_VOLUME_GRID_VIEW === '1');

    const collapseDetailGenreTagsEl = document.getElementById('my-setting-collapse-detail-genre-tags');
    if (collapseDetailGenreTagsEl) collapseDetailGenreTagsEl.checked = (s.COLLAPSE_DETAIL_GENRE_TAGS === '1');

    const showCategoryAllEl = document.getElementById('my-setting-show-sidebar-category-all');
    if (showCategoryAllEl) showCategoryAllEl.checked = (s.SHOW_SIDEBAR_CATEGORY_ALL !== '0');

    const hideCompletedEl = document.getElementById('my-setting-hide-completed-in-history');
    if (hideCompletedEl) hideCompletedEl.checked = (s.HIDE_COMPLETED_IN_HISTORY === '1');

    const tagScopeAllEl = document.getElementById('my-setting-tag-filter-scope-all');
    if (tagScopeAllEl) tagScopeAllEl.checked = (s.TAG_FILTER_SEARCH_SCOPE_ALL === '1');

    const txtNoCoverBannerEl = document.getElementById('my-setting-show-txt-no-cover-info-banner');
    if (txtNoCoverBannerEl) txtNoCoverBannerEl.checked = (s.SHOW_TXT_NO_COVER_INFO_BANNER !== '0');

    const smartRecommendEnabledEl = document.getElementById('my-setting-smart-recommend-enabled');
    if (smartRecommendEnabledEl) smartRecommendEnabledEl.checked = (s.SMART_RECOMMEND_ENABLED !== '0');

    const bookRecommendEnabledEl = document.getElementById('my-setting-book-recommend-enabled');
    if (bookRecommendEnabledEl) bookRecommendEnabledEl.checked = (s.BOOK_RECOMMEND_ENABLED !== '0');
  } catch (err) {
    console.error('[Settings] 내 설정 로드 에러:', err);
  }
}

// 내 설정(사용자별 개인화) 탭 저장
export async function submitMySettings(event) {
  if (event) event.preventDefault();

  const themeValue = document.getElementById('my-setting-dashboard-theme')?.value || 'purple';
  const showInsights = document.getElementById('my-setting-show-dashboard-insights')?.checked ? '1' : '0';
  const fontSize = document.getElementById('my-setting-viewer-font-size')?.value || '18';
  const fontFamily = document.getElementById('my-setting-viewer-font-family')?.value || 'sans-serif';
  const audioMiniPlayerModeRaw = document.getElementById('my-setting-audio-mini-player-mode')?.value || 'mini';
  const audioMiniPlayerMode = (audioMiniPlayerModeRaw === 'right_dock') ? 'right_dock' : 'mini';
  const audioRightDockDimEnabled = document.getElementById('my-setting-audio-right-dock-dim')?.checked ? '1' : '0';
  const detailVolumeGridView = document.getElementById('my-setting-detail-volume-grid-view')?.checked ? '1' : '0';
  const collapseDetailGenreTags = document.getElementById('my-setting-collapse-detail-genre-tags')?.checked ? '1' : '0';
  const showSidebarCategoryAll = document.getElementById('my-setting-show-sidebar-category-all')?.checked ? '1' : '0';
  const hideCompleted = document.getElementById('my-setting-hide-completed-in-history')?.checked ? '1' : '0';
  const tagFilterScopeAll = document.getElementById('my-setting-tag-filter-scope-all')?.checked ? '1' : '0';
  const showTxtNoCoverInfoBanner = document.getElementById('my-setting-show-txt-no-cover-info-banner')?.checked ? '1' : '0';
  const smartRecommendEnabled = document.getElementById('my-setting-smart-recommend-enabled')?.checked ? '1' : '0';
  const bookRecommendEnabled = document.getElementById('my-setting-book-recommend-enabled')?.checked ? '1' : '0';

  try {
    // 테마/대시보드 표시는 로컬스토리지에도 즉시 반영 (change 핸들러와 별개로 폼 제출 시에도 보장)
    localStorage.setItem('app_dashboard_theme', themeValue);
    localStorage.setItem('show_dashboard_insights', showInsights);
    changeDashboardTheme(themeValue);
    toggleDashboardInsightsSetting(showInsights === '1');

    const results = await Promise.all([
      api.updateUserSetting('DASHBOARD_THEME', themeValue),
      api.updateUserSetting('SHOW_DASHBOARD_INSIGHTS', showInsights),
      api.updateUserSetting('VIEWER_FONT_SIZE', fontSize),
      api.updateUserSetting('VIEWER_FONT_FAMILY', fontFamily),
      api.updateUserSetting('AUDIO_MINI_PLAYER_MODE', audioMiniPlayerMode),
      api.updateUserSetting('AUDIO_RIGHT_DOCK_DIM_ENABLED', audioRightDockDimEnabled),
      api.updateUserSetting('DETAIL_VOLUME_GRID_VIEW', detailVolumeGridView),
      api.updateUserSetting('COLLAPSE_DETAIL_GENRE_TAGS', collapseDetailGenreTags),
      api.updateUserSetting('SHOW_SIDEBAR_CATEGORY_ALL', showSidebarCategoryAll),
      api.updateUserSetting('HIDE_COMPLETED_IN_HISTORY', hideCompleted),
      api.updateUserSetting('TAG_FILTER_SEARCH_SCOPE_ALL', tagFilterScopeAll),
      api.updateUserSetting('SHOW_TXT_NO_COVER_INFO_BANNER', showTxtNoCoverInfoBanner),
      api.updateUserSetting('SMART_RECOMMEND_ENABLED', smartRecommendEnabled),
      api.updateUserSetting('BOOK_RECOMMEND_ENABLED', bookRecommendEnabled)
    ]);
    const failed = results.find(r => !r.success);

    if (!failed) {
      if (typeof window.showToast === 'function') {
        window.showToast(i18n.t('settings.general_save_success'), 'success');
      } else {
        alert(i18n.t('settings.general_save_done'));
      }
      loadMySettings();
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
    console.error('[Settings] 내 설정 저장 에러:', err);
    alert(i18n.t('settings.general_server_error'));
  }
}
