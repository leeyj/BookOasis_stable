// api.js – 서버와 통신하는 함수들
export async function fetchLibraries(type) {
  const res = await fetch(`/api/media/libraries?type=${type}`);
  return res.json();
}

export async function fetchBooksList({type, libraryId, page, limit, append, search, sort}) {
  const searchQuery = search ? `&search=${encodeURIComponent(search)}` : '';
  const sortQuery = sort ? `&sort=${sort}` : '';
  const url = `/api/media/list?type=${type}&library_id=${libraryId}&page=${page}&limit=${limit}${searchQuery}${sortQuery}`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchAllBooksList(type, libraryId) {
  const url = `/api/media/all-list?type=${type}&library_id=${libraryId}`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchReadingHistory(type) {
  const res = await fetch(`/api/media/history?type=${type}`);
  return res.json();
}

export async function fetchMediaDetail(type, libraryId, series) {
  const res = await fetch(`/api/media/detail?type=${type}&library_id=${libraryId}&series=${encodeURIComponent(series)}`);
  return res.json();
}

export async function fetchMetaRecommend(type, series) {
  const res = await fetch(`/api/media/meta/recommend?type=${type}&series=${encodeURIComponent(series)}`);
  return res.json();
}

export async function copyMetadata(formData) {
  const res = await fetch('/api/media/meta/copy', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function fetchStream(params) {
  const url = `/api/media/stream?${new URLSearchParams(params).toString()}`;
  return fetch(url);
}

export async function addLibrary(formData) {
  const res = await fetch('/api/media/libraries/add', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function editLibrary(formData) {
  const res = await fetch('/api/media/libraries/edit', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function deleteLibrary(formData) {
  const res = await fetch('/api/media/libraries/delete', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function toggleFavorite(type, bookId, isFavorite) {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('is_favorite', isFavorite ? 1 : 0);
  const res = await fetch(`/api/media/books/${bookId}/favorite`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function toggleSeriesFavorite(type, seriesName, isFavorite) {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('series_name', seriesName);
  formData.append('is_favorite', isFavorite ? 1 : 0);
  const res = await fetch(`/api/media/series/favorite`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function scanSingleBook(type, bookId) {
  const formData = new FormData();
  formData.append('type', type);
  const res = await fetch(`/api/media/books/${bookId}/scan`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function markBookAsUnread(type, bookId) {
  const res = await fetch('/api/media/unread', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ db_type: type, book_id: bookId })
  });
  return res.json();
}

export async function fetchLibrarySchedules(type) {
  const res = await fetch(`/api/media/libraries/schedules?type=${type}`);
  return res.json();
}

export async function triggerLibraryScan(type, libraryId, force = false) {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('force', force ? 'true' : 'false');
  const res = await fetch(`/api/media/libraries/${libraryId}/scan`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function triggerAllLibrariesScan(type, force = false) {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('force', force ? 'true' : 'false');
  const res = await fetch(`/api/media/libraries/scan-all`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function triggerLibraryCoversScan(type, libraryId) {
  const formData = new FormData();
  formData.append('type', type);
  const res = await fetch(`/api/media/libraries/${libraryId}/scan-covers`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function cancelLibraryScan(type, libraryId) {
  const formData = new FormData();
  formData.append('type', type);
  const res = await fetch(`/api/media/libraries/${libraryId}/cancel-scan`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function updateLibrarySchedule(type, libraryId, cronSchedule, vfsRefresh = 'false', rcloneRcUrl = '') {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('cron_schedule', cronSchedule);
  formData.append('vfs_refresh_before_scan', vfsRefresh);
  formData.append('rclone_rc_url', rcloneRcUrl);
  const res = await fetch(`/api/media/libraries/${libraryId}/schedule`, {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function fetchSystemSettings(type) {
  const res = await fetch(`/api/media/settings?type=${type}`);
  return res.json();
}

export async function fetchMetadataPlugins() {
  const res = await fetch('/api/media/metadata/plugins');
  return res.json();
}

export async function searchMetadata(type, query, source) {
  const sourceParam = source ? `&source=${encodeURIComponent(source)}` : '';
  const res = await fetch(`/api/media/books/search-metadata?type=${type}&query=${encodeURIComponent(query)}${sourceParam}`);
  return res.json();
}

export async function applyMetadata(type, bookId, itemData, source) {
  const res = await fetch(`/api/media/books/${bookId}/apply-metadata`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      type: type,
      source: source,
      item_data: itemData
    })
  });
  return res.json();
}

export async function searchAladinMetadata(type, query) {
  return searchMetadata(type, query, 'aladin');
}

export async function applyAladinMetadata(type, bookId, aladinItem) {
  return applyMetadata(type, bookId, aladinItem, 'aladin');
}

export async function updateSystemSetting(key, value) {
  const formData = new FormData();
  formData.append('key', key);
  formData.append('value', value);
  const res = await fetch('/api/media/settings', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function toggleMetadataPlugin(type, pluginId, enabled) {
  const formData = new FormData();
  formData.append('type', type);
  formData.append('plugin_id', pluginId);
  formData.append('enabled', enabled ? '1' : '0');
  const res = await fetch('/api/media/metadata/plugins/toggle', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function saveMetadataPluginConfig(type, pluginId, configData) {
  const res = await fetch('/api/media/metadata/plugins/save-config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      type: type,
      plugin_id: pluginId,
      config: configData
    })
  });
  return res.json();
}

export async function editMediaDetail(formData) {
  const res = await fetch('/api/media/detail/edit', {
    method: 'POST',
    body: formData
  });
  return res.json();
}

export async function fetchScanReports(libraryId) {
  const res = await fetch(`/api/media/libraries/${libraryId}/reports`);
  return res.json();
}

export async function fetchReportDetail(filename) {
  const res = await fetch(`/api/media/libraries/reports/view?file=${encodeURIComponent(filename)}`);
  return res.json();
}

export async function triggerLazyScan() {
  const res = await fetch('/api/media/settings/trigger-lazy-scan', {
    method: 'POST'
  });
  return res.json();
}

export async function fetchTags(type, libraryId) {
  const libQuery = libraryId ? `&library_id=${libraryId}` : '';
  const res = await fetch(`/api/media/tags?type=${type}${libQuery}`);
  return res.json();
}

export async function fetchGenres(type, libraryId) {
  const libQuery = libraryId ? `&library_id=${libraryId}` : '';
  const res = await fetch(`/api/media/genres?type=${type}${libQuery}`);
  return res.json();
}



