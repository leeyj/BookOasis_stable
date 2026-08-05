// detail_render.js – 도서 상세 화면의 HTML 템플릿 생성기
import { state } from './state.js';
import { stripLeadingBracketTags } from './series_display.js';
import { renderAudiobookVolumes } from './detail/volume_audiobook_view.js';
import { renderVolumeGrid } from './detail/volume_grid_view.js';
import { renderVolumeList } from './detail/volume_list_view.js';
export { renderDetailHeader } from './detail/header_view.js';

export function renderVolumesList(books, safeSeriesName, actualLibraryId, dbType = 'general', viewOptions = {}) {
  const unreadOnly = viewOptions.unreadOnly === true;
  const sortOrder = viewOptions.sortOrder === 'newest' ? 'newest' : 'oldest';
  const gridMode = viewOptions.gridMode === true || state.detailVolumeGridView === true;

  const orderedBooks = [...books].sort((left, right) => {
    const titleL = (left.title || '').toLowerCase();
    const titleR = (right.title || '').toLowerCase();
    const cmp = titleL.localeCompare(titleR, undefined, { numeric: true, sensitivity: 'base' });
    return sortOrder === 'newest' ? -cmp : cmp;
  });

  const isAudiobook = (state.currentLibraryType === 'audiobook') || (books && books.length > 0 && (books[0].audiobook_id || (books[0].file_format || '').toLowerCase() === 'm4a'));

  if (isAudiobook) {
    return renderAudiobookVolumes(orderedBooks, state.detailMeta);
  }

  if (gridMode) {
    return renderVolumeGrid(orderedBooks, safeSeriesName, dbType, { unreadOnly, sortOrder });
  }

  return renderVolumeList(orderedBooks, safeSeriesName, actualLibraryId, dbType, { unreadOnly, sortOrder });
}

export function renderRecommendList(recommends, seriesName) {
  let recHtml = '';
  recommends.forEach(rec => {
    const recDisplaySeries = stripLeadingBracketTags(rec.series_name);
    recHtml += `
      <div class="recommend-card" style="display: flex; flex-direction: column; gap: 0.3rem; padding: 0.6rem; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
          <strong style="font-size: 0.85rem; color: #fff;">${recDisplaySeries}</strong>
          <button class="btn-apply-meta" data-source-id="${rec.id}" style="padding: 0.2rem 0.6rem; font-size: 0.72rem; font-weight: 700; color: #fff; background: #7c3aed; border: none; border-radius: 4px; cursor: pointer; transition: background 0.2s;">${i18n.t('detail.btn_apply_meta')}</button>
        </div>
        <div style="font-size: 0.72rem; color: #94a3b8;">
          <span>${i18n.t('detail.text_author', { author: rec.author })}</span> | <span>${i18n.t('detail.text_publisher', { publisher: rec.publisher })}</span>
        </div>
        <p style="margin: 0.2rem 0 0 0; font-size: 0.72rem; color: #cbd5e1; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; line-height: 1.4;">${rec.summary}</p>
      </div>
    `;
  });
  return recHtml;
}
