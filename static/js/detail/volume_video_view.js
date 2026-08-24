import { formatClockDuration } from '../utils/time.js';

export function renderVideoVolumes(orderedBooks, detailMeta = null) {
  const episodes = Array.isArray(orderedBooks) ? [...orderedBooks] : [];

  const toClock = (totalSec) => formatClockDuration(totalSec, { emptyLabel: '분석전' });

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

    const isEpCompleted = Number(ep.is_episode_completed) === 1 || Number(ep.episode_progress_pct || 0) >= 95;
    const completedDotHtml = `<span class="ab-track-completed-dot${isEpCompleted ? ' is-visible' : ''}"
      title="시청 완료" aria-label="시청 완료"></span>`;

    rowsHtml += `
      <tr data-role="detail-video-open" data-video-id="${videoId}" data-episode-id="${ep.id}">
        <td class="ab-col-play"><button class="ab-play-mini" data-role="detail-video-play" data-video-id="${videoId}" data-episode-id="${ep.id}"><i class="fa-solid fa-play"></i></button></td>
        <td class="ab-col-id">${ep.episode_number}</td>
        <td class="ab-col-title"><span class="ab-track-title-text">${ep.title || ''}</span>${completedDotHtml}</td>
        <td class="ab-col-time">${ep.premiered || ''}</td>
        <td class="ab-col-time">${durationText}</td>
      </tr>
    `;
  });

  const totalDurationText = toClock(totalDurationSec);

  return `
    <div class="volumes-section ab-volumes-shell" style="margin-top: 1.2rem;">
      <div class="ab-tab-header">
        <button class="ab-tab-btn active" data-role="detail-audio-tab" data-target="episodes">에피소드 <span>${episodes.length}</span></button>
        <button class="ab-tab-btn" data-role="detail-audio-tab" data-target="detail">세부사항</button>
      </div>

      <div class="ab-tab-pane active" data-pane="episodes">
        <div class="ab-table-wrap">
          <table class="ab-detail-table">
            <thead>
              <tr>
                <th class="ab-col-play"></th>
                <th class="ab-col-id">#</th>
                <th>제목</th>
                <th class="ab-col-time">방영일</th>
                <th class="ab-col-time">재생시간</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="ab-tab-pane" data-pane="detail">
        <div class="ab-stats-grid">
          <div class="ab-stat-card"><span class="k">총 에피소드</span><strong>${episodes.length}</strong></div>
          <div class="ab-stat-card"><span class="k">총 재생시간</span><strong>${totalDurationText}</strong></div>
          <div class="ab-stat-card"><span class="k">평균 길이</span><strong>${episodes.length > 0 ? toClock(Math.round(totalDurationSec / episodes.length)) : '-'}</strong></div>
        </div>
      </div>
    </div>
  `;
}
