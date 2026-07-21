/**
 * startIndex 주변에서 실제 내용(비공백 5자 이상)이 포함된 30자 앵커 텍스트를 탐색.
 * 앞에서 실패하면 뒤(startIndex+1 방향)로 최대 100자까지 탐색 후 반환.
 * @param {string} text - 정제된 전체 텍스트
 * @param {number} startIndex - 탐색 시작 인덱스
 * @param {number} length - 앵커 길이 (기본 30)
 * @returns {string|null}
 */
function _findMeaningfulAnchor(text, startIndex, length = 30) {
  if (!text || text.length === 0) return null;

  // 앞뒤로 탐색 (최대 ±200자 범위)
  const searchRange = 200;
  const lo = Math.max(0, startIndex - searchRange);
  const hi = Math.min(text.length - length, startIndex + searchRange);

  // 먼저 startIndex 부근 → 앞 방향으로 탐색
  for (let i = startIndex; i <= hi; i++) {
    const slice = text.substring(i, i + length);
    if (slice.replace(/\s/g, '').length >= 5) return slice.trim();
  }
  // 그다음 startIndex 이전 방향으로 탐색
  for (let i = startIndex - 1; i >= lo; i--) {
    const slice = text.substring(i, i + length);
    if (slice.replace(/\s/g, '').length >= 5) return slice.trim();
  }
  return null;
}

export function getTxtAnchorInfoByMode({
  scrollWrapper,
  contentArea,
  forcedMode,
  storage,
  isEpub,
  fullText,
  txtChunks,
  currentChunkIdx,
  stripHtml,
}) {
  if (!scrollWrapper || !contentArea) return null;

  const scrollMode = forcedMode || storage.getItem('viewer_scroll_mode') || 'page';

  if (scrollMode === 'scroll') {
    const rawChunk = (Array.isArray(txtChunks) && txtChunks[currentChunkIdx]) ? txtChunks[currentChunkIdx] : '';
    const cleanText = isEpub ? stripHtml(rawChunk) : (rawChunk || fullText || '').replace(/\s+/g, ' ').trim();
    if (cleanText.length === 0) return null;

    const targetChunk = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${currentChunkIdx}"]`);
    let ratio = 0;
    if (targetChunk && targetChunk.offsetHeight > 0) {
      const chunkRelativeScroll = Math.max(0, scrollWrapper.scrollTop - targetChunk.offsetTop);
      ratio = Math.min(1, chunkRelativeScroll / targetChunk.offsetHeight);
    } else {
      const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
      ratio = maxScroll > 0 ? scrollWrapper.scrollTop / maxScroll : 0;
    }

    const startIndex = Math.floor(cleanText.length * ratio);
    // 공백/특수문자만 있는 구간을 피해 실제 의미있는 텍스트가 나오는 위치를 앞뒤로 탐색
    const anchorText = _findMeaningfulAnchor(cleanText, startIndex, 30);
    if (!anchorText) return null;

    return {
      chunkIdx: currentChunkIdx,
      anchorText,
    };
  }

  const rawChunk = txtChunks[currentChunkIdx] || '';
  const cleanText = isEpub ? stripHtml(rawChunk) : rawChunk.replace(/\s+/g, ' ').trim();
  if (cleanText.length === 0) return null;

  const maxScroll = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
  const ratio = maxScroll > 0 ? scrollWrapper.scrollLeft / maxScroll : 0;
  const startIndex = Math.floor(cleanText.length * ratio);
  // 공백/특수문자만 있는 구간을 피해 실제 의미있는 텍스트가 나오는 위치를 앞뒤로 탐색
  const anchorText = _findMeaningfulAnchor(cleanText, startIndex, 30);
  if (!anchorText) return null;

  return {
    chunkIdx: currentChunkIdx,
    anchorText,
  };
}

export function restoreTxtAnchorInfoByMode({
  anchorInfo,
  scrollWrapper,
  contentArea,
  storage,
  currentChunkIdx,
  getPageAdvanceWidth,
  isEpub,
  fullText,
  txtChunks,
  stripHtml,
}) {
  if (!anchorInfo || !anchorInfo.anchorText || !scrollWrapper || !contentArea) return false;

  const scrollMode = storage.getItem('viewer_scroll_mode') || 'page';
  const query = anchorInfo.anchorText;
  const targetChunkIdx = anchorInfo.chunkIdx !== undefined ? anchorInfo.chunkIdx : currentChunkIdx;

  let targetArea = contentArea;
  if (scrollMode === 'scroll') {
    const chunkContainer = contentArea.querySelector(`.txt-scroll-chunk[data-idx="${targetChunkIdx}"]`);
    if (chunkContainer) targetArea = chunkContainer;
  } else {
    const chunkContainer = contentArea.querySelector(`.txt-chunk[data-idx="${targetChunkIdx}"]`);
    if (chunkContainer) targetArea = chunkContainer;
  }

  const elements = targetArea.querySelectorAll('p, div, li, blockquote, h1, h2, h3, h4, h5, h6');
  let matchedElem = null;

  for (let el of elements) {
    if (el.children.length === 0 || el.tagName === 'P') {
      const txt = el.textContent.replace(/\s+/g, ' ').trim();
      if (txt.includes(query)) {
        matchedElem = el;
        break;
      }
    }
  }

  if (!matchedElem) {
    for (let el of elements) {
      if (el.textContent.includes(query)) {
        matchedElem = el;
        break;
      }
    }
  }

  if (matchedElem) {
    if (scrollMode === 'scroll') {
      scrollWrapper.scrollTop = Math.max(0, matchedElem.offsetTop - 30);
      return true;
    }

    const colWidth = getPageAdvanceWidth(scrollWrapper);
    const pageIndex = Math.floor(matchedElem.offsetTop / scrollWrapper.clientHeight);
    scrollWrapper.scrollLeft = pageIndex * colWidth;
    return true;
  }

  if (scrollMode === 'scroll') {
    const cleanText = isEpub ? stripHtml(fullText) : fullText.replace(/\s+/g, ' ').trim();

    let charOffset = 0;
    for (let i = 0; i < targetChunkIdx; i++) {
      const chunkText = isEpub ? stripHtml(txtChunks[i]) : txtChunks[i].replace(/\s+/g, ' ').trim();
      charOffset += chunkText.length;
    }

    const matchIndex = cleanText.indexOf(query, charOffset);
    if (matchIndex !== -1) {
      const ratio = matchIndex / cleanText.length;
      const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
      scrollWrapper.scrollTop = maxScroll * ratio;
      return true;
    }
  } else {
    const rawChunk = txtChunks[targetChunkIdx] || '';
    const cleanText = isEpub ? stripHtml(rawChunk) : rawChunk.replace(/\s+/g, ' ').trim();
    const matchIndex = cleanText.indexOf(query);
    if (matchIndex !== -1) {
      const ratio = matchIndex / cleanText.length;
      const colWidth = getPageAdvanceWidth(scrollWrapper);
      const maxScroll = scrollWrapper.scrollWidth - scrollWrapper.clientWidth;
      scrollWrapper.scrollLeft = Math.round((maxScroll * ratio) / colWidth) * colWidth;
      return true;
    }
  }

  return false;
}
