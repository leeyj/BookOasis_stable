import { formatClockDuration } from '../utils/time.js';

export function renderVideoVolumes(orderedBooks, detailMeta = null) {
  const episodes = Array.isArray(orderedBooks) ? [...orderedBooks] : [];

  const toClock = (totalSec) => formatClockDuration(totalSec, { emptyLabel: i18n.t('detail.video_not_analyzed') });

  episodes.sort((left, right) => {
    const numLeft = Number(left.episode_number) || 0;
    const numRight = Number(right.episode_number) || 0;
    if (numLeft !== numRight) return numLeft - numRight;
    return (left.title || '').localeCompare(right.title || '', undefined, { numeric: true });
  });

  let rowsHtml = '';
  let totalDurationSec = 0;
  const videoId = episodes[0]?.video_id || detailMeta?.id || episodes[0]?.id;

  episodes.forEach((ep) => {
    const durationSec = Number(ep.duration) || 0;
    const durationText = ep.time_str && durationSec > 0 ? ep.time_str : toClock(durationSec);
    totalDurationSec += durationSec;

    const isEpCompleted = Number(ep.is_episode_completed) === 1;  // 완료 기준(%)은 서버가 사용자 설정으로 판정
    const completedDotHtml = `<span class="ab-track-completed-dot${isEpCompleted ? ' is-visible' : ''}"
      title="${i18n.t('detail.video_watched')}" aria-label="${i18n.t('detail.video_watched')}"></span>`;

    rowsHtml += `
      <tr data-role="detail-video-open" data-video-id="${videoId}" data-episode-id="${ep.id}">
        <td class="ab-col-play"><button class="ab-play-mini" data-role="detail-video-play" data-video-id="${videoId}" data-episode-id="${ep.id}"><i class="lc lc-play"></i></button></td>
        <td class="ab-col-id">${ep.episode_number}</td>
        <td class="ab-col-title"><span class="ab-track-title-text">${ep.title || ''}</span>${completedDotHtml}</td>
        <td class="ab-col-time">${ep.premiered || ''}</td>
        <td class="ab-col-time">${durationText}</td>
      </tr>
    `;
  });

  const totalDurationText = toClock(totalDurationSec);

  return `
    <div class="volumes-section ab-volumes-shell">
      <div class="ab-tab-header">
        <button class="ab-tab-btn active" data-role="detail-audio-tab" data-target="episodes">${i18n.t('detail.video_tab_episodes')} <span>${episodes.length}</span></button>
        <button class="ab-tab-btn" data-role="detail-audio-tab" data-target="detail">${i18n.t('detail.ab_tab_details')}</button>
      </div>

      <div class="ab-tab-pane active" data-pane="episodes">
        <div class="ab-table-wrap">
          <table class="ab-detail-table">
            <thead>
              <tr>
                <th class="ab-col-play"></th>
                <th class="ab-col-id">#</th>
                <th>${i18n.t('detail.ab_col_title')}</th>
                <th class="ab-col-time">${i18n.t('detail.video_col_aired')}</th>
                <th class="ab-col-time">${i18n.t('detail.video_col_runtime')}</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="ab-tab-pane" data-pane="detail">
        <div class="ab-stats-grid">
          <div class="ab-stat-card"><span class="k">${i18n.t('detail.video_stat_episodes')}</span><strong>${episodes.length}</strong></div>
          <div class="ab-stat-card"><span class="k">${i18n.t('detail.ab_stat_total_time')}</span><strong>${totalDurationText}</strong></div>
          <div class="ab-stat-card"><span class="k">${i18n.t('detail.ab_stat_avg')}</span><strong>${episodes.length > 0 ? toClock(Math.round(totalDurationSec / episodes.length)) : '-'}</strong></div>
        </div>
      </div>
    </div>
  `;
}
