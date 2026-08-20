// annotation_render.js — 챕터/청크가 렌더링될 때마다 저장된 하이라이트(주석)를
// annotation_anchor.js의 decodeAnchor()로 다시 찾아 <mark>로 재적용한다.
// EPUB은 챕터(=청크) 기준 DOM 렌더 오프셋을 그대로 쓰고, TXT는 원본 파일(raw)
// 기준 오프셋을 그 청크의 raw 시작 위치로 역산해서 로컬 오프셋 근사치를 구한 뒤
// decodeAnchor의 quote 자가복구에 맡긴다 (설계는 static/js/viewer/annotation_anchor.js 상단 주석 참고).
import { decodeAnchor, wrapRangeWithMark } from './annotation_anchor.js';
import { getAnnotationsForChapter, getTxtAnnotations } from './annotation_state.js';

export function rawChunkStartOffset(txtChunks, chunkIdx) {
  let cum = 0;
  for (let i = 0; i < chunkIdx; i += 1) {
    cum += (txtChunks[i] && typeof txtChunks[i] === 'string') ? txtChunks[i].length : 0;
  }
  return cum;
}

export function applyAnnotationsToChunkElement(chunkEl, chunkIdx, { format, txtChunks } = {}) {
  if (!chunkEl) return;
  // 같은 청크가 재렌더(innerHTML 재대입)될 때 이전 <mark>는 새 DOM과 함께 이미 사라지므로
  // 중복 wrap 걱정 없이 매번 새로 적용하면 된다.

  let targets = [];
  if (format === 'epub') {
    targets = getAnnotationsForChapter(chunkIdx).map((a) => ({ annotation: a, localAnchor: a }));
  } else {
    const chunkStartRaw = rawChunkStartOffset(txtChunks || [], chunkIdx);
    const chunkRawLen = (txtChunks && txtChunks[chunkIdx] && typeof txtChunks[chunkIdx] === 'string') ? txtChunks[chunkIdx].length : 0;
    targets = getTxtAnnotations()
      .filter((a) => a.start_offset >= chunkStartRaw - 64 && a.start_offset < chunkStartRaw + chunkRawLen + 64)
      .map((a) => ({
        annotation: a,
        localAnchor: {
          start: Math.max(0, a.start_offset - chunkStartRaw),
          end: Math.max(0, a.end_offset - chunkStartRaw),
          quote: a.quote,
          prefix: a.prefix,
          suffix: a.suffix,
        },
      }));
  }

  for (const { annotation, localAnchor } of targets) {
    try {
      const result = decodeAnchor(chunkEl, localAnchor);
      if (result.range) {
        wrapRangeWithMark(result.range, { id: annotation.id, color: annotation.color, marker: annotation.plugin_marker });
      }
    } catch (e) {
      // 하나의 하이라이트 복원 실패가 나머지 렌더링을 막지 않도록 개별적으로 무시
      console.warn('[Annotation] failed to apply highlight', annotation.id, e);
    }
  }
}

export function applyAnnotationsToAllRenderedChunks({ contentArea, format, txtChunks } = {}) {
  if (!contentArea) return;
  const chunkEls = contentArea.querySelectorAll('.txt-chunk[data-idx], .txt-scroll-chunk[data-idx]');
  chunkEls.forEach((chunkEl) => {
    const idx = parseInt(chunkEl.getAttribute('data-idx') || '-1', 10);
    if (!Number.isFinite(idx) || idx < 0) return;
    // EPUB 로딩 플레이스홀더 상태인 청크는 아직 실 콘텐츠가 없으므로 건너뛴다
    // (챕터가 늦게 로드되면 epub_loader.js의 개별 하이드레이션 훅이 그때 다시 적용함)
    if (chunkEl.querySelector('.epub-ch-loading')) return;
    applyAnnotationsToChunkElement(chunkEl, idx, { format, txtChunks });
  });
}
