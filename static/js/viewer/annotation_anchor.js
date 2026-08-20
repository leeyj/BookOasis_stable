// annotation_anchor.js — EPUB/TXT 하이라이트(주석) 텍스트 위치 앵커링.
//
// 설계 요지 (test/annotation_anchor_poc/ 에서 실제 샘플 EPUB/TXT/한영기호 혼합
// 문서/CP949 인코딩 문서 총 366개 케이스로 검증됨):
//  1. 별도의 stripHtml 문자열을 따로 만들지 않고, 항상 렌더링된 DOM을 TreeWalker로
//     직접 순회해서 오프셋을 계산한다 (encode/decode 모두 동일 경로).
//  2. 오프셋만 신뢰하지 않고 quote/prefix/suffix(W3C Web Annotation 방식)를 함께
//     저장해서, 오프셋이 어긋났을 때(콘텐츠 드리프트, 청킹 알고리즘 변경 등) 검색으로
//     자가복구한다.
//  3. 세그먼트(텍스트 노드) 배열은 문서 순서대로 정렬돼 있으므로 이진 탐색으로
//     O(log n)에 조회 가능 — DOM에 물리적 앵커 마커를 심을 필요 없음.
//
// EPUB(챕터=청크 1:1)은 start/end를 "그 챕터 컨테이너 기준 DOM 렌더 오프셋"으로 쓰고,
// TXT(청킹 알고리즘이 나중에 바뀔 수 있음)는 "원본 파일(raw) 기준 오프셋"을 근사치로
// 써서 현재 청킹으로 재계산 + quote 검색 자가복구에 맡긴다. 이 둘을 섞지 말 것.

const CONTEXT_LEN = 32;

export function buildTextSegments(rootEl) {
  const doc = rootEl.ownerDocument;
  const walker = doc.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, null);
  const segments = [];
  let cursor = 0;
  let node = walker.nextNode();
  while (node) {
    const text = node.nodeValue || '';
    if (text.length > 0) {
      segments.push({ node, start: cursor, end: cursor + text.length });
      cursor += text.length;
    }
    node = walker.nextNode();
  }
  return { segments, totalLength: cursor };
}

function segmentIndexForOffset(segments, offset) {
  // offset이 어떤 세그먼트의 [start, end) 범위에 속하는지 이진 탐색.
  let lo = 0;
  let hi = segments.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const seg = segments[mid];
    if (offset < seg.start) {
      hi = mid - 1;
    } else if (offset >= seg.end) {
      lo = mid + 1;
    } else {
      return mid;
    }
  }
  return Math.max(0, Math.min(segments.length - 1, lo));
}

export function offsetToNodeOffset(segments, offset) {
  if (segments.length === 0) return null;
  const idx = segmentIndexForOffset(segments, offset);
  const seg = segments[idx];
  const localOffset = Math.max(0, Math.min(seg.node.nodeValue.length, offset - seg.start));
  return { node: seg.node, localOffset, segIndex: idx };
}

export function domPositionToOffset(segments, node, localOffset) {
  const idx = segments.findIndex((seg) => seg.node === node);
  if (idx === -1) return null;
  return segments[idx].start + localOffset;
}

export function getFullText(segments) {
  return segments.map((seg) => seg.node.nodeValue).join('');
}

function buildRange(doc, segments, start, end) {
  const startPos = offsetToNodeOffset(segments, start);
  const endPos = offsetToNodeOffset(segments, end);
  if (!startPos || !endPos) return null;
  const range = doc.createRange();
  range.setStart(startPos.node, startPos.localOffset);
  range.setEnd(endPos.node, endPos.localOffset);
  return range;
}

/**
 * 현재 선택된 Range를 저장 가능한 앵커로 인코딩한다.
 * @returns {{start:number, end:number, quote:string, prefix:string, suffix:string}}
 */
export function encodeRange(rootEl, range) {
  const { segments, totalLength } = buildTextSegments(rootEl);
  const start = domPositionToOffset(segments, range.startContainer, range.startOffset);
  const end = domPositionToOffset(segments, range.endContainer, range.endOffset);
  if (start == null || end == null || end <= start) {
    return null;
  }
  const fullText = getFullText(segments);
  return {
    start,
    end,
    quote: fullText.slice(start, end),
    prefix: fullText.slice(Math.max(0, start - CONTEXT_LEN), start),
    suffix: fullText.slice(end, Math.min(totalLength, end + CONTEXT_LEN)),
  };
}

/**
 * 저장된 앵커를 현재 렌더링된 DOM에서 다시 찾아 Range로 복원한다.
 * @param {Element} rootEl
 * @param {{start:number, end:number, quote:string, prefix?:string, suffix?:string}} anchor
 * @returns {{range: Range|null, method: 'offset'|'search'|'not_found', recoveredStart?: number}}
 */
export function decodeAnchor(rootEl, anchor) {
  const doc = rootEl.ownerDocument;
  const { segments, totalLength } = buildTextSegments(rootEl);
  if (segments.length === 0 || !anchor) return { range: null, method: 'not_found' };

  // 1) 오프셋 직행 경로 (빠름, 콘텐츠가 변하지 않았으면 항상 성공)
  if (anchor.start <= totalLength && anchor.end <= totalLength && anchor.start <= anchor.end) {
    const range = buildRange(doc, segments, anchor.start, anchor.end);
    if (range && range.toString() === anchor.quote) {
      return { range, method: 'offset' };
    }
  }

  // 2) quote 검색 자가복구 경로 (오프셋이 어긋났을 때)
  if (!anchor.quote) return { range: null, method: 'not_found' };
  const fullText = getFullText(segments);
  const candidates = [];
  let searchFrom = 0;
  for (;;) {
    const idx = fullText.indexOf(anchor.quote, searchFrom);
    if (idx === -1) break;
    candidates.push(idx);
    searchFrom = idx + 1;
  }
  if (candidates.length === 0) {
    return { range: null, method: 'not_found' };
  }

  let best = candidates[0];
  if (candidates.length > 1) {
    // prefix/suffix 문맥이 가장 잘 맞는 후보를 고르고, 동점이면 원 오프셋과 가까운 쪽 선택
    let bestScore = -1;
    let bestDist = Infinity;
    for (const idx of candidates) {
      const gotPrefix = fullText.slice(Math.max(0, idx - CONTEXT_LEN), idx);
      const gotSuffix = fullText.slice(idx + anchor.quote.length, idx + anchor.quote.length + CONTEXT_LEN);
      let score = 0;
      if (gotPrefix === anchor.prefix) score += 2;
      else if (anchor.prefix && gotPrefix.endsWith(anchor.prefix.slice(-8))) score += 1;
      if (gotSuffix === anchor.suffix) score += 2;
      else if (anchor.suffix && gotSuffix.startsWith(anchor.suffix.slice(0, 8))) score += 1;
      const dist = Math.abs(idx - anchor.start);
      if (score > bestScore || (score === bestScore && dist < bestDist)) {
        bestScore = score;
        bestDist = dist;
        best = idx;
      }
    }
  }

  const range = buildRange(doc, segments, best, best + anchor.quote.length);
  return { range, method: 'search', recoveredStart: best };
}

/**
 * TXT 전용: 원본 파일(raw) 기준 오프셋이 현재 청킹(chunks 배열, chunkText() 결과)의
 * 어느 청크에 속하는지 찾는다. 청킹 알고리즘이 나중에 바뀌어도(간격 등) 이 함수만
 * 다시 실행하면 되고, 저장된 앵커 자체는 그대로 유효하다.
 * @param {string[]} rawChunks - chunkText()의 결과
 * @param {number} rawOffset - book_annotations.start_offset (raw 파일 기준)
 * @returns {{ chunkIndex: number, localRaw: number, chunkStartRaw: number } | null}
 */
export function resolveRawOffsetToChunk(rawChunks, rawOffset) {
  let cum = 0;
  for (let i = 0; i < rawChunks.length; i += 1) {
    if (rawOffset < cum + rawChunks[i].length) {
      return { chunkIndex: i, localRaw: rawOffset - cum, chunkStartRaw: cum };
    }
    cum += rawChunks[i].length;
  }
  return null;
}

const PLUGIN_MARKER_CLASS = 'annotation-plugin-marker';

/**
 * 하이라이트 뒤에 플러그인이 남긴 표시(예: '*')를 붙이거나 뗀다. 플러그인
 * 컨텍스트 메뉴 액션 응답의 'marker' 필드를 그대로 반영할 때, 혹은 저장된
 * annotation.plugin_marker 값으로 최초 렌더링할 때 둘 다 이 함수 하나로 처리한다.
 * 항상 먼저 기존 표시를 지우고 다시 그리므로 중복 삽입 걱정 없이 여러 번 호출해도 안전하다.
 * @param {Document} doc
 * @param {number|string} annotationId
 * @param {string|null|undefined} marker - falsy면 표시를 제거만 하고 끝낸다
 */
export function setAnnotationMarker(doc, annotationId, marker) {
  doc.querySelectorAll(`sup.${PLUGIN_MARKER_CLASS}[data-annotation-id="${annotationId}"]`)
    .forEach((el) => el.remove());
  if (!marker) return;

  const marks = doc.querySelectorAll(`mark.annotation-highlight[data-annotation-id="${annotationId}"]`);
  if (marks.length === 0) return;

  // 하이라이트가 여러 텍스트 노드(문장 중간에 <strong> 등)로 쪼개져 있어도, 화면상
  // 가장 마지막(오른쪽/아래) mark 바로 뒤에 하나만 붙여야 "하이라이트 맨 끝"처럼 보인다.
  const lastMark = marks[marks.length - 1];
  const sup = doc.createElement('sup');
  sup.className = PLUGIN_MARKER_CLASS;
  sup.dataset.annotationId = String(annotationId);
  sup.textContent = marker;
  sup.title = '플러그인이 추가 정보를 남겼습니다';
  sup.style.cssText = 'margin-left:1px; color:#fbbf24; user-select:none;';
  lastMark.insertAdjacentElement('afterend', sup);
}

/**
 * 복원된 Range를 <mark>로 시각화한다. Range가 여러 텍스트 노드에 걸쳐 있으면
 * 노드별로 쪼개서 각각 wrap한다 (인라인 요소(strong/em/ruby 등)를 건드리지 않고
 * 텍스트 노드만 감싸므로 문서 구조를 해치지 않음).
 * @param {Range} range
 * @param {{id:number|string, color:string, marker?:string|null}} meta
 */
export function wrapRangeWithMark(range, meta) {
  if (!range || range.collapsed) return [];
  const doc = range.startContainer.ownerDocument;
  const marks = [];

  if (range.startContainer === range.endContainer) {
    const mark = doc.createElement('mark');
    mark.className = 'annotation-highlight';
    mark.dataset.annotationId = String(meta.id);
    mark.style.backgroundColor = meta.color || '#fbbf24';
    range.surroundContents(mark);
    marks.push(mark);
    if (meta.marker) setAnnotationMarker(doc, meta.id, meta.marker);
    return marks;
  }

  // 여러 텍스트 노드에 걸친 선택: TreeWalker로 range 내부의 텍스트 노드를 모아
  // 각각을 개별 Range로 잘라 wrap (surroundContents는 단일 컨테이너에서만 동작)
  const walker = doc.createTreeWalker(range.commonAncestorContainer, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => (range.intersectsNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
  });
  const nodes = [];
  let node = walker.nextNode();
  while (node) {
    nodes.push(node);
    node = walker.nextNode();
  }

  for (const textNode of nodes) {
    const nodeRange = doc.createRange();
    nodeRange.selectNodeContents(textNode);
    if (textNode === range.startContainer) nodeRange.setStart(textNode, range.startOffset);
    if (textNode === range.endContainer) nodeRange.setEnd(textNode, range.endOffset);
    if (nodeRange.collapsed) continue;

    const mark = doc.createElement('mark');
    mark.className = 'annotation-highlight';
    mark.dataset.annotationId = String(meta.id);
    mark.style.backgroundColor = meta.color || '#fbbf24';
    nodeRange.surroundContents(mark);
    marks.push(mark);
  }
  if (meta.marker) setAnnotationMarker(doc, meta.id, meta.marker);
  return marks;
}
