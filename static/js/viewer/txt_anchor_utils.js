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
    const cleanText = isEpub ? stripHtml(fullText) : fullText.replace(/\s+/g, ' ').trim();
    if (cleanText.length === 0) return null;

    const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;
    const ratio = maxScroll > 0 ? scrollWrapper.scrollTop / maxScroll : 0;
    const startIndex = Math.floor(cleanText.length * ratio);
    const anchorText = cleanText.substring(startIndex, startIndex + 30);

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
  const anchorText = cleanText.substring(startIndex, startIndex + 30);

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
