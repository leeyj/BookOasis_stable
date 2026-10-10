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

  // 1순위: 지금 보이는 페이지의 첫 글자부터 30자 (iOS Safari scrollLeft 읽기 오류 방어).
  // 예전엔 화면 가운데를 elementFromPoint로 찍었는데, 본문 위를 페이지 넘김 터치 영역(.hotspot-zone)이 덮고 있어
  // 늘 실패하고 아래의 비율 추정으로 넘어갔다(2026-10-02 확인).
  try {
    const pos = captureTxtPageAnchor({ scrollWrapper, contentArea, chunkIdx: currentChunkIdx });
    const anchorText = pos ? _anchorTextAt(contentArea, pos) : null;
    if (anchorText) {
      return {
        chunkIdx: currentChunkIdx,
        anchorText,
      };
    }
  } catch (e) {}

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

    // 예전엔 floor(offsetTop / 높이)로 열 번호를 구해 페이지 폭을 곱했는데, 2장 모드에서는 한 번에 넘기는 폭이
    // 두 열이라 위치가 두 배 가까이 앞으로 갔고 offsetTop이 다단 레이아웃에서 브라우저마다 다르게 나왔다.
    // 실제 화면 좌표로 그 요소가 들어 있는 페이지를 찾는다.
    // 긴 문단은 여러 페이지에 걸치므로 문단 시작이 아니라 앵커 글자가 있는 페이지로 간다.
    const target = pageScrollLeftForRect({
      scrollWrapper,
      rect: _queryRectInElement(matchedElem, query)
        || matchedElem.getClientRects()[0] || matchedElem.getBoundingClientRect(),
      advanceWidth: getPageAdvanceWidth(scrollWrapper),
    });
    if (target === null) return false;
    scrollWrapper.scrollLeft = target;
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

// ---- 페이지 모드: 화면 크기가 바뀌어도 "보던 글자"를 따라가는 위치 앵커 ----
// 열(페이지) 번호는 화면 폭/높이가 바뀌면 다른 본문을 가리킨다. iPad는 앱을 내렸다 올리는 사이
// 창 크기를 잠깐 바꿨다 되돌리는데(앱 전환기 스냅샷 등), 그 사이 재조판되면 번호 기준 복원이
// 2~3페이지 밀렸다(2026-10-02 신고). 그래서 보이던 글자(본문 블록 번호 + 블록 안 글자 위치)를 기억했다가,
// 재조판 뒤 그 글자가 들어 있는 페이지를 실제 화면 좌표로 다시 찾는다.
// 좌표로 글자를 찍는 방식(caretRangeFromPoint/elementFromPoint)은 쓰지 않는다 - 본문 위를 페이지 넘김
// 터치 영역(.hotspot-zone)이 덮고 있어 늘 그 영역이 잡힌다. 대신 블록들의 화면 위치를 이진 탐색한다
// (다단 레이아웃에서 블록은 문서 순서대로 왼쪽→오른쪽에 놓이므로 위치가 단조 증가).
const PAGE_ANCHOR_BLOCKS = 'p, li, blockquote, h1, h2, h3, h4, h5, h6, pre, div';

// 다른 블록을 품지 않은 블록만 (챕터 컨테이너 div 등은 제외) - 캡처/복원이 같은 목록을 써야 한다.
function _anchorBlocks(contentArea) {
  return Array.prototype.filter.call(
    contentArea.querySelectorAll(PAGE_ANCHOR_BLOCKS),
    (el) => !el.querySelector(PAGE_ANCHOR_BLOCKS),
  );
}

function _lastRect(el) {
  const rects = el.getClientRects();
  return rects.length ? rects[rects.length - 1] : null;
}

function _textNodes(block) {
  const out = [];
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) out.push(t);
  return out;
}

function _charRect(textNodes, offset) {
  let remaining = offset;
  for (const t of textNodes) {
    const len = t.nodeValue.length;
    if (remaining < len) {
      const range = document.createRange();
      range.setStart(t, remaining);
      range.setEnd(t, remaining + 1);
      return range.getClientRects()[0] || null;
    }
    remaining -= len;
  }
  return null;
}

/**
 * 지금 보이는 페이지(스프레드)의 첫 글자 위치를 잡는다.
 * @returns {{chunkIdx:number, blockIndex:number, charOffset:number, probe:string}|null}
 */
export function captureTxtPageAnchor({ scrollWrapper, contentArea, chunkIdx }) {
  if (!scrollWrapper || !contentArea) return null;
  const view = scrollWrapper.getBoundingClientRect();
  if (!view.width || !view.height) return null;
  const blocks = _anchorBlocks(contentArea);
  if (!blocks.length) return null;
  const visibleLeft = view.left + 1;

  // 끝이 보이는 영역 왼쪽보다 오른쪽에 있는 첫 블록 = 지금 페이지에 걸친 첫 블록
  let lo = 0;
  let hi = blocks.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const r = _lastRect(blocks[mid]);
    if (r && r.right > visibleLeft) {
      found = mid;
      hi = mid - 1;
    } else {
      lo = mid + 1;
    }
  }
  if (found < 0) return null;

  // 빈 줄(&nbsp;)이면 다음 블록에서 실제 글자를 찾는다 (같은 페이지 안이면 어느 글자든 페이지를 가리킨다)
  for (let i = found; i < Math.min(blocks.length, found + 20); i++) {
    const block = blocks[i];
    const text = block.textContent || '';
    if (!text.replace(/[\s\u00a0]/g, '').length) continue;
    const nodes = _textNodes(block);
    // 블록 안에서 처음으로 보이는 글자 (긴 문단은 앞 페이지에서 시작해 이 페이지로 이어진다)
    let a = 0;
    let b = text.length - 1;
    let first = -1;
    while (a <= b) {
      const m = (a + b) >> 1;
      const r = _charRect(nodes, m);
      if (r && r.right > visibleLeft) {
        first = m;
        b = m - 1;
      } else {
        a = m + 1;
      }
    }
    if (first < 0) continue;
    const r = _charRect(nodes, first);
    if (!r || r.left > view.right) return null; // 이 페이지엔 글자가 없다
    return { chunkIdx, blockIndex: i, charOffset: first, probe: text.slice(0, 24) };
  }
  return null;
}

/** 화면 좌표의 사각형이 들어 있는 페이지의 scrollLeft (페이지 경계에 맞춤). */
export function pageScrollLeftForRect({ scrollWrapper, rect, advanceWidth }) {
  if (!scrollWrapper || !rect || !(advanceWidth > 0)) return null;
  const wrapRect = scrollWrapper.getBoundingClientRect();
  const x = rect.left + Math.min(rect.width, 2) / 2 - wrapRect.left + scrollWrapper.scrollLeft;
  const page = Math.max(0, Math.floor((x + 0.5) / advanceWidth));
  const maxScroll = Math.max(0, scrollWrapper.scrollWidth - scrollWrapper.clientWidth);
  return Math.min(maxScroll, page * advanceWidth);
}

/**
 * captureTxtPageAnchor로 잡은 글자가 재조판 뒤 들어 있는 페이지의 scrollLeft. 찾지 못하면 null.
 * 같은 챕터·같은 블록(앞부분 글자 확인)일 때만 믿는다.
 */
export function locateTxtPageAnchor({ scrollWrapper, contentArea, anchor, chunkIdx, advanceWidth }) {
  if (!anchor || !scrollWrapper || !contentArea || anchor.chunkIdx !== chunkIdx) return null;
  const block = _anchorBlocks(contentArea)[anchor.blockIndex];
  if (!block || (block.textContent || '').slice(0, 24) !== anchor.probe) return null;
  const rect = _charRect(_textNodes(block), anchor.charOffset) || block.getClientRects()[0] || null;
  return pageScrollLeftForRect({ scrollWrapper, rect, advanceWidth });
}

/** 캡처한 글자 위치에서 시작하는 30자 앵커 문구 (공백 정리). 같은 블록에 의미 있는 글자가 모자라면 다음 블록에서. */
function _anchorTextAt(contentArea, pos) {
  const blocks = _anchorBlocks(contentArea);
  for (let i = pos.blockIndex; i < Math.min(blocks.length, pos.blockIndex + 10); i++) {
    const raw = blocks[i].textContent || '';
    const text = (i === pos.blockIndex ? raw.slice(pos.charOffset) : raw).replace(/\s+/g, ' ').trim();
    if (text.replace(/\s/g, '').length >= 5) return text.slice(0, 30).trim();
  }
  return null;
}

/** 요소 안에서 앵커 문구(공백 정리된 형태)가 시작하는 글자의 화면 사각형. */
function _queryRectInElement(el, query) {
  if (!el || !query) return null;
  const pattern = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+');
  let match = null;
  try {
    match = new RegExp(pattern).exec(el.textContent || '');
  } catch (e) {
    return null;
  }
  return match ? _charRect(_textNodes(el), match.index) : null;
}

// 위치를 글자(앵커)로 되찾은 뒤, 이미지·글꼴이 늦게 로드돼 쪽 나눔이 다시 바뀌는 경우(원격 EPUB은 수 초)를 위해
// 잠시 동안 몇 번 더 같은 글자로 맞춘다. 사용자가 조작(터치·클릭·키·휠)하면 그 즉시 멈춘다.
// scrollLeft 변화로 '사용자가 넘겼는지' 판단하면 뷰어 자체의 쪽 맞춤(snap)도 이동으로 오인해 너무 일찍 멈췄다(2.8.9).
export function scheduleAnchorRechecks(reapply, delays = [700, 1800, 3500]) {
  const events = ['pointerdown', 'touchstart', 'keydown', 'wheel'];
  let stopped = false;
  const stop = () => {
    stopped = true;
    events.forEach((type) => document.removeEventListener(type, stop, true));
  };
  events.forEach((type) => document.addEventListener(type, stop, { capture: true, passive: true }));
  delays.forEach((delay, i) => {
    setTimeout(() => {
      if (stopped) return;
      try { reapply(); } catch (e) {}
      if (i === delays.length - 1) stop();
    }, delay);
  });
  return stop;
}
