export function renderAudiobookVolumes(orderedBooks, detailMeta = null) {
  const books = Array.isArray(orderedBooks) ? [...orderedBooks] : [];

  const toClock = (totalSec) => {
    const sec = Math.max(0, Math.floor(Number(totalSec) || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  const toSizeMB = (bytes) => {
    const n = Number(bytes) || 0;
    if (n <= 0) return '-';
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  };

  books.sort((left, right) => {
    const trackLeft = Number(left.track_number) || 0;
    const trackRight = Number(right.track_number) || 0;
    if (trackLeft !== trackRight) return trackLeft - trackRight;
    return (left.title || '').localeCompare(right.title || '', undefined, { numeric: true });
  });

  let chapterRowsHtml = '';
  let trackRowsHtml = '';
  let runningStartSec = 0;
  let totalBytes = 0;
  const audiobookId = books[0]?.audiobook_id || detailMeta?.id || books[0]?.id;

  books.forEach((book, idx) => {
    const rawTitle = String(book.title || '');
    const cleanTitle = rawTitle.replace(/^\s*\[\s*\d+\s*\]\s*/, '').trim() || rawTitle;
    const durationSec = Number(book.duration) || 0;
    const durationText = book.time_str || toClock(durationSec);
    const startText = toClock(runningStartSec);
    runningStartSec += durationSec;

    const fileSize = Number(book.file_size) || 0;
    totalBytes += fileSize;
    const codec = String(book.file_format || '-').toLowerCase();
    const kbps = durationSec > 0 ? Math.round((fileSize * 8 / 1000) / durationSec) : 0;

    chapterRowsHtml += `
      <tr data-role="detail-audio-open" data-audiobook-id="${audiobookId}" data-track-id="${book.id}">
        <td class="ab-col-play"><button class="ab-play-mini" data-role="detail-audio-play" data-audiobook-id="${audiobookId}" data-track-id="${book.id}"><i class="fa-solid fa-play"></i></button></td>
        <td class="ab-col-id">${idx}</td>
        <td class="ab-col-title">${cleanTitle}</td>
        <td class="ab-col-time">${startText}</td>
        <td class="ab-col-time">${durationText}</td>
      </tr>
    `;

    trackRowsHtml += `
      <tr data-role="detail-audio-open" data-audiobook-id="${audiobookId}" data-track-id="${book.id}">
        <td class="ab-col-play"><button class="ab-play-mini" data-role="detail-audio-play" data-audiobook-id="${audiobookId}" data-track-id="${book.id}"><i class="fa-solid fa-play"></i></button></td>
        <td class="ab-col-id">${idx + 1}</td>
        <td class="ab-col-title">${rawTitle}</td>
        <td class="ab-col-codec">${codec}</td>
        <td class="ab-col-time">${kbps > 0 ? `${kbps} KB` : '-'}</td>
        <td class="ab-col-size">${toSizeMB(fileSize)}</td>
        <td class="ab-col-time">${durationText}</td>
      </tr>
    `;
  });

  const totalDurationText = toClock(runningStartSec);

  return `
    <div class="volumes-section ab-volumes-shell" style="margin-top: 1.2rem;">
      <div class="ab-tab-header">
        <button class="ab-tab-btn active" data-role="detail-audio-tab" data-target="chapters">챕터 <span>${books.length}</span></button>
        <button class="ab-tab-btn" data-role="detail-audio-tab" data-target="tracks">오디오 트랙 <span>${books.length}</span></button>
        <button class="ab-tab-btn" data-role="detail-audio-tab" data-target="detail">세부사항</button>
      </div>

      <div class="ab-tab-pane active" data-pane="chapters">
        <div class="ab-table-wrap">
          <table class="ab-detail-table">
            <thead>
              <tr>
                <th class="ab-col-play"></th>
                <th class="ab-col-id">Id</th>
                <th>제목</th>
                <th class="ab-col-time">시작</th>
                <th class="ab-col-time">기간</th>
              </tr>
            </thead>
            <tbody>${chapterRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="ab-tab-pane" data-pane="tracks">
        <div class="ab-table-wrap">
          <table class="ab-detail-table">
            <thead>
              <tr>
                <th class="ab-col-play"></th>
                <th class="ab-col-id">#</th>
                <th>파일 이름</th>
                <th class="ab-col-codec">코덱</th>
                <th class="ab-col-time">비트레이트</th>
                <th class="ab-col-size">크기</th>
                <th class="ab-col-time">기간</th>
              </tr>
            </thead>
            <tbody>${trackRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div class="ab-tab-pane" data-pane="detail">
        <div class="ab-stats-grid">
          <div class="ab-stat-card"><span class="k">총 트랙</span><strong>${books.length}</strong></div>
          <div class="ab-stat-card"><span class="k">총 재생시간</span><strong>${totalDurationText}</strong></div>
          <div class="ab-stat-card"><span class="k">총 크기</span><strong>${toSizeMB(totalBytes)}</strong></div>
          <div class="ab-stat-card"><span class="k">평균 길이</span><strong>${books.length > 0 ? toClock(Math.round(runningStartSec / books.length)) : '-'}</strong></div>
        </div>
      </div>
    </div>
  `;
}