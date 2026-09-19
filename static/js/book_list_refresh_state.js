// Tracks whether the currently rendered library list predates a data invalidation.
export class BookListRefreshState {
  constructor() {
    this.versionsByList = new Map();
  }

  getVersionState(listKey) {
    if (!this.versionsByList.has(listKey)) {
      this.versionsByList.set(listKey, { latestVersion: 0, loadedVersion: 0 });
    }
    return this.versionsByList.get(listKey);
  }

  invalidate(listKey) {
    const versionState = this.getVersionState(listKey);
    versionState.latestVersion += 1;
    return versionState.latestVersion;
  }

  beginRequest(listKey) {
    return this.getVersionState(listKey).latestVersion;
  }

  markLoaded(listKey, requestVersion) {
    // An older in-flight request must never clear an invalidation that happened later.
    const versionState = this.getVersionState(listKey);
    versionState.loadedVersion = Math.max(
      versionState.loadedVersion,
      Math.min(Number(requestVersion) || 0, versionState.latestVersion),
    );
  }

  isStale(listKey) {
    const versionState = this.getVersionState(listKey);
    return versionState.loadedVersion < versionState.latestVersion;
  }
}

export function getLoadedPageRange(firstLoadedPage, currentPage, hasMore) {
  const firstPage = Math.max(1, Math.floor(Number(firstLoadedPage) || 1));
  const pageCursor = Math.max(firstPage, Math.floor(Number(currentPage) || firstPage));
  return {
    firstPage,
    lastPage: Math.max(firstPage, hasMore ? pageCursor - 1 : pageCursor),
  };
}
