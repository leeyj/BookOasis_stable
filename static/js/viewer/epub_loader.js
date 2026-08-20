/* epub_loader.js – EPUB 챕터 비동기 로더, 이미지 사전디코딩 및 플레이스홀더 복구 엔진 */
import { state } from '../state.js';
import { highlightEpubTocChapter } from './txt_toc.js';
import { applyAnnotationsToChunkElement } from './annotation_render.js';

const epubChapterFetchInFlight = new Set();
const epubChapterRetryState = new Map();

export function clearEpubChapterRetryState() {
  epubChapterRetryState.clear();
}

export function clampNumber(value, min, max) {
  const num = Number(value);
  if (!Number.isFinite(num)) return min;
  return Math.max(min, Math.min(max, num));
}

export function pickEpubStartIndex(totalChapters, initialPageIdx, serverEpubSession) {
  const maxIdx = Math.max(0, Number(totalChapters || 0) - 1);
  let resolved = 0;

  const initialPercent = clampNumber(initialPageIdx, 0, 100);
  resolved = Math.round((initialPercent / 100) * maxIdx);

  if (!serverEpubSession || maxIdx <= 0) return Math.max(0, Math.min(maxIdx, resolved));

  const idxRaw = serverEpubSession.index;
  const percentRaw = serverEpubSession.percent;
  const hasValidIndex = Number.isFinite(Number(idxRaw));
  const hasValidPercent = Number.isFinite(Number(percentRaw));
  const percent = hasValidPercent ? clampNumber(percentRaw, 0, 100) : null;
  const idx = hasValidIndex ? clampNumber(idxRaw, 0, maxIdx) : null;

  if (percent !== null && (idx === null || (idx === 0 && percent > 0))) {
    resolved = Math.round((percent / 100) * maxIdx);
  } else if (idx !== null) {
    resolved = idx;
  }

  return Math.max(0, Math.min(maxIdx, resolved));
}

export function syncActiveEpubToc(currentChunkIdx, scrollIntoView = false) {
  if ((state.currentViewerFormat || '').toLowerCase() !== 'epub') return;
  highlightEpubTocChapter(currentChunkIdx, { scrollIntoView });
}

export function preloadEpubChapterImages(htmlContent, timeoutMs = 800) {
  if (!htmlContent || typeof htmlContent !== 'string' || !htmlContent.includes('<img')) {
    return Promise.resolve();
  }

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    const imgEls = Array.from(doc.querySelectorAll('img'));
    if (!imgEls.length) return Promise.resolve();

    const fetchPromises = imgEls.map(img => {
      const src = img.getAttribute('src');
      if (!src) return Promise.resolve();

      return new Promise((resolve) => {
        const preloader = new Image();
        let settled = false;

        const onDone = () => {
          if (!settled) {
            settled = true;
            resolve();
          }
        };

        preloader.onload = onDone;
        preloader.onerror = onDone;

        if ('decode' in preloader) {
          preloader.src = src;
          preloader.decode().then(onDone).catch(onDone);
        } else {
          preloader.src = src;
        }
      });
    });

    const timeoutPromise = new Promise(resolve => setTimeout(resolve, timeoutMs));
    return Promise.race([Promise.all(fetchPromises), timeoutPromise]);
  } catch (e) {
    return Promise.resolve();
  }
}

export function requestEpubChapterContent(txtChunks, chapterIdx, options = {}) {
  const idx = parseInt(chapterIdx, 10);
  if (!Number.isFinite(idx) || idx < 0 || idx >= txtChunks.length) {
    return Promise.resolve(null);
  }
  if ((state.currentViewerFormat || '').toLowerCase() !== 'epub') {
    return Promise.resolve(null);
  }

  const force = !!options.force;
  const updateDom = options.updateDom !== false;
  const existing = txtChunks[idx];
  if (!force && existing !== null && existing !== 'LOADING_PENDING') {
    return Promise.resolve(existing);
  }
  if (epubChapterFetchInFlight.has(idx)) {
    return Promise.resolve(null);
  }

  const retryState = epubChapterRetryState.get(idx) || { attempts: 0, lastAttemptAt: 0 };
  retryState.attempts += 1;
  retryState.lastAttemptAt = Date.now();
  epubChapterRetryState.set(idx, retryState);

  epubChapterFetchInFlight.add(idx);
  if (txtChunks[idx] === null) {
    txtChunks[idx] = 'LOADING_PENDING';
  }

  return fetch(`/api/media/epub/chapter?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&chapter_idx=${idx}`)
    .then(r => r.json())
    .then(async d => {
      const content = (d && d.content) ? d.content : '<p>내용이 없습니다.</p>';
      txtChunks[idx] = content;
      epubChapterRetryState.delete(idx);

      await preloadEpubChapterImages(content);

      if (updateDom) {
        const contentArea = document.getElementById('txt-content-area');
        if (contentArea) {
          const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${idx}"]`);
          if (chunkEl) {
            chunkEl.innerHTML = content;
            applyAnnotationsToChunkElement(chunkEl, idx, { format: 'epub' });
          }
        }
      }
      return content;
    })
    .catch(() => {
      txtChunks[idx] = null;
      return null;
    })
    .finally(() => {
      epubChapterFetchInFlight.delete(idx);
    });
}

// 여러 챕터를 한 번의 HTTP 요청(＝서버에서 zip을 1번만 오픈)으로 묶어서 프리페치.
// requestEpubChapterContent와 동일한 in-flight/캐시 규약(epubChapterFetchInFlight, txtChunks
// 슬롯 상태)을 공유해 단일 요청과 배치 요청이 같은 챕터를 동시에 중복 요청하지 않게 한다.
export function requestEpubChaptersBatch(txtChunks, chapterIndices) {
  if ((state.currentViewerFormat || '').toLowerCase() !== 'epub') {
    return Promise.resolve();
  }

  const targets = Array.from(new Set((chapterIndices || []).map(i => parseInt(i, 10))))
    .filter(idx => Number.isFinite(idx) && idx >= 0 && idx < txtChunks.length)
    .filter(idx => !epubChapterFetchInFlight.has(idx))
    .filter(idx => txtChunks[idx] === null || txtChunks[idx] === 'LOADING_PENDING');

  if (targets.length === 0) {
    return Promise.resolve();
  }

  targets.forEach(idx => {
    epubChapterFetchInFlight.add(idx);
    txtChunks[idx] = 'LOADING_PENDING';
    const retryState = epubChapterRetryState.get(idx) || { attempts: 0, lastAttemptAt: 0 };
    retryState.attempts += 1;
    retryState.lastAttemptAt = Date.now();
    epubChapterRetryState.set(idx, retryState);
  });

  const url = `/api/media/epub/chapters?db_type=${state.currentLibraryType}&book_id=${state.activeBookId}&chapter_idx=${targets.join(',')}`;

  return fetch(url)
    .then(r => r.json())
    .then(async d => {
      const chapters = (d && Array.isArray(d.chapters)) ? d.chapters : [];
      const receivedIdxSet = new Set();

      for (const ch of chapters) {
        const idx = parseInt(ch.chapter_idx, 10);
        if (!Number.isFinite(idx)) continue;
        receivedIdxSet.add(idx);

        const content = ch.content || '<p>내용이 없습니다.</p>';
        txtChunks[idx] = content;
        epubChapterRetryState.delete(idx);

        await preloadEpubChapterImages(content);

        const contentArea = document.getElementById('txt-content-area');
        if (contentArea) {
          const chunkEl = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${idx}"]`);
          if (chunkEl) {
            chunkEl.innerHTML = content;
            applyAnnotationsToChunkElement(chunkEl, idx, { format: 'epub' });
          }
        }
      }

      // 배치 응답에 빠진(개별 파싱 실패한) 챕터는 null로 되돌려 기존 재시도 경로가 나중에 채우도록 둔다
      targets.forEach(idx => {
        if (!receivedIdxSet.has(idx) && txtChunks[idx] === 'LOADING_PENDING') {
          txtChunks[idx] = null;
        }
      });
    })
    .catch(() => {
      targets.forEach(idx => {
        if (txtChunks[idx] === 'LOADING_PENDING') {
          txtChunks[idx] = null;
        }
      });
    })
    .finally(() => {
      targets.forEach(idx => epubChapterFetchInFlight.delete(idx));
    });
}

export function getVisibleEpubPlaceholderIndexes(txtChunks, maxCount = 10) {
  const contentArea = document.getElementById('txt-content-area');
  const scrollWrapper = document.getElementById('txt-scroll-wrapper');
  if (!contentArea || !scrollWrapper) return [];

  const wrapperTop = scrollWrapper.scrollTop;
  const wrapperBottom = wrapperTop + scrollWrapper.clientHeight;
  const indexes = [];

  for (const node of contentArea.querySelectorAll('.txt-scroll-chunk[data-idx]')) {
    const idx = parseInt(node.getAttribute('data-idx') || '-1', 10);
    if (!Number.isFinite(idx) || idx < 0) continue;

    const isPlaceholder = !!node.querySelector('.epub-ch-loading') || txtChunks[idx] === null || txtChunks[idx] === 'LOADING_PENDING';
    if (!isPlaceholder) continue;

    const top = node.offsetTop;
    const bottom = top + node.offsetHeight;
    const isNearViewport = bottom >= wrapperTop - 200 && top <= wrapperBottom + 200;
    if (isNearViewport) {
      indexes.push(idx);
      if (indexes.length >= maxCount) break;
    }
  }

  return indexes;
}

export function scheduleVisibleEpubPlaceholderRecovery(txtChunks, delays = [50, 180, 450]) {
  if ((state.currentViewerFormat || '').toLowerCase() !== 'epub') return;
  if (!Array.isArray(delays) || delays.length === 0) return;

  delays.forEach(delay => {
    setTimeout(() => {
      retryVisibleEpubPlaceholders(txtChunks, 10);
    }, delay);
  });
}

export function hydrateEpubChapterWindow(txtChunks, centerIdx, radius = 10) {
  const center = parseInt(centerIdx, 10);
  if (!Number.isFinite(center) || txtChunks.length === 0) return;
  const start = Math.max(0, center - Math.max(0, radius));
  const end = Math.min(txtChunks.length - 1, center + Math.max(0, radius));
  const missing = [];
  for (let i = start; i <= end; i++) {
    if (txtChunks[i] === null || txtChunks[i] === 'LOADING_PENDING') {
      missing.push(i);
    }
  }
  // 반경 내 미로드 챕터를 개별 요청 N개가 아니라 배치 요청 1개로 묶어서 프리페치한다
  // (서버가 요청당 zip을 새로 여는 구조라, 이게 반경을 키워도 안전한 이유).
  requestEpubChaptersBatch(txtChunks, missing);
}

export function retryVisibleEpubPlaceholders(txtChunks, maxCount = 8) {
  const candidateIndexes = getVisibleEpubPlaceholderIndexes(txtChunks, maxCount);
  for (const idx of candidateIndexes) {
    const retryState = epubChapterRetryState.get(idx) || { attempts: 0, lastAttemptAt: 0 };
    const now = Date.now();
    const minRetryDelay = retryState.attempts <= 1 ? 0 : retryState.attempts === 2 ? 250 : 800;
    if (retryState.lastAttemptAt && now - retryState.lastAttemptAt < minRetryDelay) continue;
    if (retryState.attempts >= 5) continue;
    requestEpubChapterContent(txtChunks, idx, { force: true, updateDom: true });
  }
}
